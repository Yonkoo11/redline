"""Redline policy engine. Pure functions plus a small state store. Fails closed."""
from __future__ import annotations
import json, math, os, time
from dataclasses import dataclass, field, fields, asdict
from pathlib import Path
from typing import Optional

from .signing import verify_policy

# Names checked against the live ClawPump MCP on 2026-09-19 (@clawpump/agents v0.1.27, 132 tools,
# 61 of them not read-only). An earlier version of this map listed 8 names and let 15 money-moving
# tools through, including one that pays an arbitrary URL an arbitrary amount from the wallet.
GOVERNED = {
    # trading
    "perps_order_execute": "perp",
    "limit_order_create": "perp",
    "swap_execute": "swap",
    "dca_create": "swap",
    # funds leaving the wallet
    "wallet_transfer": "transfer",
    "transfer_sol": "transfer",
    "transfer_token": "transfer",
    "perps_collateral_withdraw": "withdraw",
    "agent_card_withdraw": "withdraw",
    # funds leaving the *readable* wallet: the equity reader cannot see Phoenix collateral or a
    # UsePod pod, so a deposit reads as a loss and moves value out of reach at the same time
    "perps_collateral_deposit": "spend",
    "usepod_deposit": "spend",
    # arbitrary payments
    "x402_pay": "spend",
    "pay_sh_execute_approved": "spend",
    "pay_sh_prepare_call": "spend",
    # launches cost SOL
    "launch_token_gasless": "spend",
    "launch_metaplex_genesis_token": "spend",
    # Added 2026-09-19 after auditing all 132 tools against the venue's own readOnly/destructive
    # flags rather than against this file's imagination. Each line quotes what the platform says
    # the tool does. Every one of these was ungoverned, which means invisible.
    "predictions_open": "swap",            # "Places a bet on a specific outcome" — wallet money, at risk
    "agent_card_create": "spend",          # "create/buy a card" — buys a spendable instrument
    "agent_card_reveal": "withdraw",       # reveals the card number: the funds leave where we can see them
    "agent_mail_create": "spend",          # "One-time payment of..."
    "agent_mail_send": "spend",            # "over x402 — any per-send fee is paid in USDC"
    "usepod_provision": "spend",           # "if `amount` is given — fund" the new pod
    "perps_account_prepare": "spend",      # "optionally deposit wallet USDC into Phoenix collateral"
    "create_agent_run": "spend",           # "an autonomous objective ... with budget" — delegated spending
    "trigger_automation": "spend",         # "trigger an automation now, bypassing its trigger condition"
}

# Read-only by the platform's own flag, and money-shaped enough to be caught by MONEY_WORDS below.
# Blocking these does not protect the wallet, it just stops the agent looking before it leaps:
# swap_quote and perps_order_preview and x402_pay_check are the tools that price a thing BEFORE
# committing to it, and the venue's own description of swap_execute says "Always get a quote
# first". All eight were being refused. Checked against the live tool list on 2026-09-19.
READ_ONLY = ("swap_quote", "perps_order_preview", "x402_pay_check", "get_launch_status",
             "limit_order_history", "agent_card_withdrawals", "pay_sh_search",
             "pay_sh_provider_details", "agent_card_quote", "arbitrage_quote")

# The platform ships 132 tools today and can ship more tomorrow, so an allowlist alone is always a
# release behind. Anything whose name reads like it moves value and is not mapped above is treated
# as an unpriceable spend, which the policy refuses. False positives are visible in the log and
# cost one line in the policy's `ungoverned_allow`; a false negative costs the wallet.
MONEY_WORDS = ("swap", "transfer", "send", "withdraw", "deposit", "order", "buy", "sell",
               "trade", "stake", "launch", "bridge", "pay", "fund", "collateral", "liquidat")

# Named exceptions: these appear money-shaped and return funds or move nothing.
# Cancels and closes: they return funds to the wallet or move nothing. agent_mail_send used to sit
# here, which was simply wrong — the platform says its per-send fee is paid in USDC from the
# wallet, so it is a spend and it moved to GOVERNED above.
NOT_MONEY = ("dca_cancel", "limit_order_cancel", "perps_order_cancel", "withdraw_marketplace_bid",
             "predictions_close", "perps_trader_register")


def bare_tool_name(tool_name: str) -> str:
    """Strip any MCP prefix: mcp_clawpump_swap_execute -> swap_execute."""
    return tool_name.split("_", 2)[-1] if tool_name.startswith("mcp_") else tool_name


def _name_candidates(tool_name: str) -> list:
    """Every reading of the name, because the prefix is not ours to predict.

    Hermes composes an MCP tool name as mcp_<server>_<tool>, and the stripper above assumes
    exactly that. A server whose own name has no underscore, say `swap`, produces
    `mcp_swap_execute`, which the stripper reduces to `execute` -- not a governed suffix, not a
    money word, and therefore invisible. A swap would have gone straight through.

    So every suffix is considered, not just the one the three-segment assumption produces. A
    false positive here costs one line in the operator's policy and is visible in the log. A
    false negative costs the wallet.
    """
    parts = tool_name.split("_")
    return [tool_name] + ["_".join(parts[i:]) for i in range(1, len(parts))]


def governed_kind(tool_name: str) -> Optional[str]:
    """Map a tool name to a governed kind, or None for tools that cannot move value."""
    names = _name_candidates(tool_name)
    for suffix, kind in GOVERNED.items():
        if any(n.endswith(suffix) for n in names):
            return kind
    if any(n.endswith(x) for n in names for x in NOT_MONEY + READ_ONLY):
        return None
    if any(w in n.lower() for n in names for w in MONEY_WORDS):
        return "spend"          # unknown, money-shaped: priced as None, therefore refused
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
    # The ceiling on a payment that is not a trade: an x402 call, a pod top-up, a token launch,
    # collateral moved out of the readable wallet. Deliberately small, because these tools take an
    # arbitrary amount and send it somewhere this plugin cannot see.
    max_spend_usd: float = 1.0
    # Turnover, as a multiple of equity, allowed in one UTC day. Every individual order can sit
    # inside the per-order cap while an agent in a loop cycles the account many times over and
    # pays a fee on each pass. The daily loss limit only notices once the losses land; this
    # notices the churn. Generous by default, because it is a runaway brake, not a strategy limit.
    max_daily_notional_pct_equity: float = 300.0
    # The ceiling on a single transfer out. The allowlist says WHERE funds may go and says nothing
    # about HOW MUCH, so one allowlisted address plus one transfer used to be the whole wallet.
    # Zero by default, which matches the empty allowlist: an agent moves nothing until an operator
    # decides otherwise, and then decides how much.
    max_transfer_usd: float = 0.0
    # "enforce" blocks a failing order. "shadow" judges and records it but lets it through, so a
    # new policy can be watched before it is trusted. Signed along with the limits.
    mode: str = "enforce"

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
        for meta in ("signature", "schema", "generated", "verified", "unverified_reason"):
            data.pop(meta, None)
        # A misspelled limit would otherwise be silently ignored, and a limit that is silently
        # ignored is a limit that is not enforced. Unknown keys refuse.
        unknown = sorted(set(data) - {f.name for f in fields(cls)})
        if unknown:
            ok, why = False, f"policy has unknown field(s): {', '.join(unknown)}"
            for k in unknown:
                data.pop(k)
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
    day_notional_usd: float = 0.0                 # turnover allowed so far in this UTC day
    halted: bool = False
    halt_reason: str = ""

    @classmethod
    def load(cls, path: Path) -> "State":
        p = Path(path)
        return cls(**json.loads(p.read_text())) if p.exists() else cls()

    def save(self, path: Path) -> None:
        """Write via a temporary file and rename.

        A plain write truncates first, so a crash or a full disk in the middle leaves a half
        written file. That file then fails to parse, which refuses every call: safe, and also a
        dead agent until someone notices. os.replace is atomic on the same filesystem, so a reader
        sees either the old state or the new one and never a torn one."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        try:
            with tmp.open("w") as fh:
                json.dump(asdict(self), fh, indent=1)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


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
        state.day_notional_usd = 0.0
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
    return _size_and_scope(policy, state, intent, equity_usd)


def _size_and_scope(policy: Policy, state: State, intent: Intent, equity_usd: float) -> Verdict:
    if intent.kind == "transfer":
        if intent.destination not in policy.allowed_destinations:
            return Verdict(False, f"destination {intent.destination} not on the allowlist", "destination")
        if intent.notional_usd is None:
            return Verdict(False, "could not price the transfer; refusing (fail closed)", "transfer_unpriced")
        if not math.isfinite(intent.notional_usd) or intent.notional_usd < 0:
            return Verdict(False, f"transfer amount {intent.notional_usd} is not a usable number", "bad_notional")
        if intent.notional_usd > policy.max_transfer_usd:
            return Verdict(False,
                           f"transfer ${intent.notional_usd:.2f} > transfer limit ${policy.max_transfer_usd:.2f}",
                           "transfer_cap")
        return Verdict(True, "destination allowed and within the transfer limit")
    if intent.kind == "withdraw":
        return Verdict(False, "collateral withdrawals are operator-only", "withdraw")
    if intent.notional_usd is None:
        if intent.kind == "spend":
            return Verdict(False, "payment of an unreadable amount; refusing (fail closed)", "spend_unpriced")
        return Verdict(False, "could not price the order; refusing (fail closed)", "price")
    # NaN compares false against every bound, so it would sail through each cap below and be
    # reported as within policy. A negative size does the same and is meaningless besides. Both are
    # reachable from tool arguments: float("nan") and float("-1") both parse.
    if not math.isfinite(intent.notional_usd) or intent.notional_usd < 0:
        return Verdict(False,
                       f"notional {intent.notional_usd} is not a usable number; refusing (fail closed)",
                       "bad_notional")
    if equity_usd < policy.equity_floor_usd:
        return Verdict(False, f"equity ${equity_usd:.2f} below floor ${policy.equity_floor_usd}", "floor")
    if intent.kind == "perp" and intent.market not in policy.allowed_markets:
        return Verdict(False, f"market {intent.market} not allowed", "market")
    if intent.kind == "swap" and intent.token not in policy.allowed_tokens:
        return Verdict(False, f"token {intent.token} not allowed", "token")
    if intent.leverage > policy.max_leverage:
        return Verdict(False, f"leverage {intent.leverage}x > {policy.max_leverage}x", "leverage")
    if intent.kind == "spend" and intent.notional_usd > policy.max_spend_usd:
        return Verdict(False,
                       f"payment ${intent.notional_usd:.2f} > spend limit ${policy.max_spend_usd:.2f}",
                       "spend_cap")
    cap = equity_usd * policy.max_trade_pct_equity / 100.0
    if intent.notional_usd > cap:
        return Verdict(False, f"notional ${intent.notional_usd:.2f} > cap ${cap:.2f} ({policy.max_trade_pct_equity}% of equity)", "trade_cap")
    budget = equity_usd * policy.max_daily_notional_pct_equity / 100.0
    if state.day_notional_usd + intent.notional_usd > budget:
        return Verdict(False,
                       f"today's turnover ${state.day_notional_usd:.2f} plus ${intent.notional_usd:.2f} "
                       f"exceeds ${budget:.2f} ({policy.max_daily_notional_pct_equity}% of equity)",
                       "daily_turnover")
    return Verdict(True, "within policy")


def record_refusal(state: State, now: float) -> None:
    state.refusals = [t for t in state.refusals if t > now - 86400] + [now]
