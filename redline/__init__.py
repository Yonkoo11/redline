"""Redline: Hermes plugin that holds a ClawPump agent under a signed trade policy."""
from __future__ import annotations
import os, time
from pathlib import Path
from .policy import Policy, State, evaluate, record_refusal
from .intent import intent_from_call

HOME = Path(os.environ.get("REDLINE_HOME", Path.home() / ".hermes" / "redline"))
POLICY_PATH = HOME / "policy.json"
STATE_PATH = HOME / "state.json"

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
    """Hermes hook. Returns None to allow, or {"action": "block", "message": ...} to refuse."""
    intent = intent_from_call(tool_name, args, _price_reader)
    if intent is None:
        return None
    HOME.mkdir(parents=True, exist_ok=True)
    policy = Policy.load(POLICY_PATH) if POLICY_PATH.exists() else Policy()
    state = State.load(STATE_PATH)
    now = time.time()
    equity = _equity()
    verdict = evaluate(policy, state, intent, equity, now)
    record = {"ts": int(now), "tool": tool_name, "intent": intent.__dict__,
              "allowed": verdict.allowed, "rule": verdict.rule, "reason": verdict.reason,
              "equity_usd": round(equity, 2) if equity is not None else None,
              "equity_source": _equity_source}
    if not verdict.allowed:
        record_refusal(state, now)
    state.save(STATE_PATH)
    if _tape:
        try:
            _tape(record)
        except Exception:
            pass   # the tape must never block the refusal itself
    if verdict.allowed:
        return None
    return {"action": "block", "message": f"REDLINE refused ({verdict.rule}): {verdict.reason}"}


def register(ctx):
    from .runtime import wire
    wire()
    ctx.register_hook("pre_tool_call", pre_tool_call)
