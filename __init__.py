"""Redline: Hermes plugin that holds a ClawPump agent under a signed trade policy."""
from __future__ import annotations
import os, time
from pathlib import Path
from .policy import Policy, State, evaluate, governed_kind, record_refusal
from .intent import intent_from_call

HOME = Path(os.environ.get("REDLINE_HOME", Path.home() / ".hermes" / "redline"))
POLICY_PATH = HOME / "policy.json"
STATE_PATH = HOME / "state.json"

# The operator's Ed25519 public key, base58. Pinned in the environment, not in a file the agent
# can rewrite. Absent means no policy can verify, which means every governed call is refused.
OPERATOR_PUBKEY_ENV = "REDLINE_OPERATOR_PUBKEY"

# Shadow mode: judge every call and write the verdict, but block nothing. It is how a new policy
# should be introduced — watch what WOULD have been refused for a session, then enforce the same
# limits. Set REDLINE_MODE=shadow, or put "mode": "shadow" in the policy so the choice is signed
# too. Enforcing is the default, because a guardrail that is off by accident is worse than none.
MODE_ENV = "REDLINE_MODE"


def _shadow(policy) -> bool:
    env = os.environ.get(MODE_ENV, "").strip().lower()
    if env in ("shadow", "enforce"):
        return env == "shadow"
    return getattr(policy, "mode", "enforce") == "shadow"

_equity_reader = None   # callable -> Optional[float]; installed by runtime.py
_equity_source = "unset"  # "live" once runtime.wire() runs; anything else is a test fixture
_price_reader = lambda sym: None
_tape = None            # callable(record: dict) -> None; installed by runtime.py


def configure(equity_reader=None, price_reader=None, tape=None, equity_source=None) -> None:
    global _equity_reader, _price_reader, _tape, _equity_source
    if equity_source is not None:
        _equity_source = equity_source
    elif equity_reader is not None:
        _equity_source = "fixture"
    _equity_reader = equity_reader or _equity_reader
    _price_reader = price_reader or _price_reader
    _tape = tape or _tape


def _equity():
    try:
        return _equity_reader() if _equity_reader else None
    except Exception:
        return None


def pre_tool_call(tool_name: str, args: dict, task_id: str = "", **kwargs):
    """Hermes hook. Returns None to allow, or {"action": "block", "message": ...} to refuse.

    This wrapper is the difference between a guardrail and a decoration. Measured against the
    installed runtime on 2026-09-19: when this callback raises, Hermes logs
    `Hook 'pre_tool_call' callback pre_tool_call raised: ...` and **lets the tool call through**.
    Writing one broken byte into the state file was enough to do it, and that file sits in a
    directory the agent's own process can write. So an agent able to run a shell command could
    disable every limit and then trade freely.

    Nothing below may escape. An error on a money-moving tool refuses; an error while looking at a
    tool that cannot move value allows, because blocking every read on a bad argument would be its
    own kind of damage.
    """
    try:
        if governed_kind(tool_name) is None:
            return None                      # pure string work, touches no disk and no network
    except Exception:
        pass                                 # even that failed: fall through and refuse

    try:
        return _decide(tool_name, args, task_id, **kwargs)
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        try:
            if _tape:
                _tape({"ts": int(time.time()), "tool": tool_name, "allowed": False,
                       "rule": "internal_error", "reason": reason,
                       "equity_usd": None, "equity_source": _equity_source,
                       "policy_verified": False, "mode": "enforce"})
        except Exception:
            pass                             # the record must never be why the refusal is lost
        return {"action": "block",
                "message": f"REDLINE refused (internal_error): {reason}. "
                           f"Redline could not make a decision, so it made the safe one."}


def _decide(tool_name: str, args: dict, task_id: str = "", **kwargs):
    intent = intent_from_call(tool_name, args, _price_reader)
    if intent is None:
        return None
    HOME.mkdir(parents=True, exist_ok=True)
    pubkey = os.environ.get(OPERATOR_PUBKEY_ENV)
    policy = (Policy.load(POLICY_PATH, pubkey) if POLICY_PATH.exists()
              else Policy(unverified_reason=f"no policy file at {POLICY_PATH}"))
    state = State.load(STATE_PATH)
    now = time.time()
    equity = _equity()
    verdict = evaluate(policy, state, intent, equity, now)
    record = {"ts": int(now), "tool": tool_name, "intent": intent.__dict__,
              "allowed": verdict.allowed, "rule": verdict.rule, "reason": verdict.reason,
              "equity_usd": round(equity, 2) if equity is not None else None,
              "equity_source": _equity_source,
              "policy_verified": policy.verified}
    shadow = _shadow(policy)
    record["mode"] = "shadow" if shadow else "enforce"
    if shadow and not verdict.allowed:
        # What the operator is watching for: the order that would have been stopped.
        record["would_refuse"] = True
        record["allowed"] = True
    if verdict.allowed and intent.notional_usd:
        state.day_notional_usd += intent.notional_usd     # only what actually went through
    if not verdict.allowed and not shadow:
        record_refusal(state, now)
    state.save(STATE_PATH)
    if _tape:
        try:
            _tape(record)
        except Exception:
            pass   # the tape must never block the refusal itself
    if verdict.allowed or shadow:
        return None
    return {"action": "block", "message": f"REDLINE refused ({verdict.rule}): {verdict.reason}"}


def register(ctx):
    from .runtime import wire
    wire()
    ctx.register_hook("pre_tool_call", pre_tool_call)
