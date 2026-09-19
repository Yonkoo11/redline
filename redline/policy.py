"""Redline policy engine. Pure functions plus a small state store. Fails closed."""
from __future__ import annotations
import json, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from .signing import verify_policy

GOVERNED = {
    "perps_order_execute": "perp",
    "swap_execute": "swap",
    "perps_collateral_withdraw": "withdraw",
    "wallet_transfer": "transfer",
    "transfer_sol": "transfer",
    "transfer_token": "transfer",
    "dca_create": "swap",
    "limit_order_create": "perp",
}


def governed_kind(tool_name: str) -> Optional[str]:
    """Map a Hermes tool name (any MCP prefix) to a governed kind, or None."""
    bare = tool_name.split("_", 2)[-1] if tool_name.startswith("mcp_") else tool_name
    for suffix, kind in GOVERNED.items():
        if bare.endswith(suffix):
            return kind
    return None


@dataclass
class Policy:
    max_trade_pct_equity: float = 10.0
    max_daily_loss_pct: float = 5.0
    max_drawdown_pct: float = 15.0
    max_leverage: float = 2.0
    equity_floor_usd: float = 5.0
    allowed_markets: list = field(default_factory=lambda: ["SOL", "ETH"])
    allowed_tokens: list = field(default_factory=lambda: ["SOL", "USDC"])
    allowed_destinations: list = field(default_factory=list)
    refusal_cooldown_count: int = 5
    refusal_cooldown_minutes: int = 30

    # Not a limit: whether these limits were signed by the pinned operator key.
    # Set only by load(). An unverified policy refuses everything.
    verified: bool = False
    unverified_reason: str = "policy was never loaded from a signed file"

    @classmethod
    def load(cls, path: Path, operator_pubkey: Optional[str] = None) -> "Policy":
        """Read a policy and check the operator's signature over it.

        A bad, missing or unpinned signature does NOT raise and does NOT fall back to defaults.
        The limits load as written and the policy is marked unverified, so evaluate() refuses
        every governed call with a reason the operator can read."""
        data = json.loads(Path(path).read_text())
        ok, why = verify_policy(data, operator_pubkey)
        data.pop("signature", None)
        data.pop("verified", None)
        data.pop("unverified_reason", None)
        return cls(**data, verified=ok, unverified_reason=why)


@dataclass
class Intent:
    kind: str                      # perp | swap | withdraw | transfer
    notional_usd: Optional[float]  # None means "could not price" -> refuse
    market: Optional[str] = None
    leverage: float = 1.0
    token: Optional[str] = None
    destination: Optional[str] = None


@dataclass
class State:
    high_water_usd: float = 0.0
    day_start_usd: float = 0.0
    day_key: str = ""
    refusals: list = field(default_factory=list)   # unix timestamps
    halted: bool = False
    halt_reason: str = ""

    @classmethod
    def load(cls, path: Path) -> "State":
        p = Path(path)
        return cls(**json.loads(p.read_text())) if p.exists() else cls()

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=1))


@dataclass
class Verdict:
    allowed: bool
    reason: str
    rule: str = ""


def _day_key(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def roll_day(state: State, equity_usd: float, now: float) -> None:
    """Start a new daily loss window when the UTC day changes."""
    key = _day_key(now)
    if state.day_key != key:
        state.day_key, state.day_start_usd = key, equity_usd
    state.high_water_usd = max(state.high_water_usd, equity_usd)


def _cooldown_active(policy: Policy, state: State, now: float) -> bool:
    window = now - policy.refusal_cooldown_minutes * 60
    recent = [t for t in state.refusals if t >= window]
    return len(recent) >= policy.refusal_cooldown_count


def evaluate(policy: Policy, state: State, intent: Intent,
             equity_usd: Optional[float], now: float) -> Verdict:
    """The whole rulebook. Order matters: hard stops first, sizing last."""
    if not policy.verified:
        return Verdict(False, f"policy not verified: {policy.unverified_reason}", "unsigned_policy")
    if state.halted:
        return Verdict(False, f"halted: {state.halt_reason}", "halt")
    if equity_usd is None:
        return Verdict(False, "equity unreadable; refusing (fail closed)", "equity")
    roll_day(state, equity_usd, now)
    if _cooldown_active(policy, state, now):
        return Verdict(False, "too many refusals recently; cooling down", "cooldown")
    dd = 100.0 * (1 - equity_usd / state.high_water_usd) if state.high_water_usd else 0.0
    if dd >= policy.max_drawdown_pct:
        state.halted, state.halt_reason = True, f"drawdown {dd:.1f}% >= {policy.max_drawdown_pct}%"
        return Verdict(False, state.halt_reason, "drawdown")
    daily = 100.0 * (1 - equity_usd / state.day_start_usd) if state.day_start_usd else 0.0
    if daily >= policy.max_daily_loss_pct and intent.kind in ("perp", "swap"):
        return Verdict(False, f"daily loss {daily:.1f}% >= {policy.max_daily_loss_pct}%", "daily_loss")
    return _size_and_scope(policy, intent, equity_usd)


def _size_and_scope(policy: Policy, intent: Intent, equity_usd: float) -> Verdict:
    if intent.kind == "transfer":
        ok = intent.destination in policy.allowed_destinations
        return Verdict(ok, "destination allowed" if ok else f"destination {intent.destination} not on the allowlist", "destination")
    if intent.kind == "withdraw":
        return Verdict(False, "collateral withdrawals are operator-only", "withdraw")
    if intent.notional_usd is None:
        return Verdict(False, "could not price the order; refusing (fail closed)", "price")
    if equity_usd < policy.equity_floor_usd:
        return Verdict(False, f"equity ${equity_usd:.2f} below floor ${policy.equity_floor_usd}", "floor")
    if intent.kind == "perp" and intent.market not in policy.allowed_markets:
        return Verdict(False, f"market {intent.market} not allowed", "market")
    if intent.kind == "swap" and intent.token not in policy.allowed_tokens:
        return Verdict(False, f"token {intent.token} not allowed", "token")
    if intent.leverage > policy.max_leverage:
        return Verdict(False, f"leverage {intent.leverage}x > {policy.max_leverage}x", "leverage")
    cap = equity_usd * policy.max_trade_pct_equity / 100.0
    if intent.notional_usd > cap:
        return Verdict(False, f"notional ${intent.notional_usd:.2f} > cap ${cap:.2f} ({policy.max_trade_pct_equity}% of equity)", "trade_cap")
    return Verdict(True, "within policy")


def record_refusal(state: State, now: float) -> None:
    state.refusals = [t for t in state.refusals if t > now - 86400] + [now]
