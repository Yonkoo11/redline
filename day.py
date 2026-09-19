"""The day's loss window, and the one thing an operator sometimes has to tell it.

The daily loss limit compares equity now against equity at the start of the UTC day. It cannot see
*why* equity moved. Money you deliberately spend or withdraw looks exactly like money the agent
lost, so a launch fee, a transfer out, or a withdrawal can trip the limit and stop all trading.

Refusing in that situation is not a bug: the account really is smaller, and the agent really should
risk less. But it is attributed to trading when it was not, so an operator needs a way to say "that
was me". That is this command.

It is deliberately awkward to do by accident:

  - it never runs on its own, and nothing in the hook path calls it
  - it writes a record to the tape, so a rebaseline is as visible as a refusal
  - it refuses to raise the baseline above current equity, so it can only ever forgive an outflow
    that already happened, never create headroom for a future one
  - it does not touch the drawdown high-water mark, which is the limit that exists for the worst
    day and is meant to survive this

  redline day               show the window
  redline day reset         set the day's starting point to equity now
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .policy import State


def _paths():
    from . import HOME, STATE_PATH

    return HOME, STATE_PATH


def _equity_now():
    from . import runtime
    import redline

    runtime.wire()
    return redline._equity()


def show(state: State, equity: float | None) -> None:
    print(f"day           {state.day_key or '(not started)'}")
    print(f"started at    ${state.day_start_usd:.2f}")
    print(f"equity now    {'unreadable' if equity is None else f'${equity:.2f}'}")
    if equity is not None and state.day_start_usd:
        move = 100 * (1 - equity / state.day_start_usd)
        print(f"day is        {'down' if move > 0 else 'up'} {abs(move):.1f}%")
    print(f"high-water    ${state.high_water_usd:.2f}  (the drawdown halt measures from here)")
    print(f"halted        {state.halt_reason or 'no'}")


def reset(state: State, equity: float, state_path: Path, home: Path) -> None:
    if equity >= state.day_start_usd:
        print("nothing to do: the day is not down, so the starting point already reflects reality.")
        return
    before = state.day_start_usd
    state.day_start_usd = equity
    state.day_key = time.strftime("%Y-%m-%d", time.gmtime())
    state.save(state_path)

    record = {
        "ts": int(time.time()),
        "tool": "operator:day_reset",
        "allowed": True,
        "rule": "day_reset",
        "reason": (f"operator declared the fall from ${before:.2f} to ${equity:.2f} an outflow, "
                   f"not a trading loss"),
        "equity_usd": round(equity, 2),
        "equity_source": "live",
        "policy_verified": True,
    }
    tape = home / "tape.jsonl"
    with tape.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"day starting point moved from ${before:.2f} to ${equity:.2f}")
    print(f"written to {tape} so the rebaseline is as visible as a refusal")
    print("the drawdown high-water mark is untouched, on purpose")


def main(argv: list[str]) -> int:
    home, state_path = _paths()
    state = State.load(state_path)
    equity = _equity_now()

    if len(argv) > 1 and argv[1] == "reset":
        if equity is None:
            print("equity is unreadable, so there is nothing trustworthy to rebaseline to.")
            return 1
        reset(state, equity, state_path, home)
        return 0

    show(state, equity)
    if equity is not None and state.day_start_usd and equity < state.day_start_usd:
        print("\nIf that fall was money you spent or moved rather than lost trading:")
        print("  redline day reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
