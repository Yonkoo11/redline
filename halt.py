"""The drawdown halt, and the only supported way out of it.

The drawdown halt latches. Once equity falls far enough below its high-water mark, everything is
refused and stays refused across restarts, because the limit exists for the day you are not there
to watch. That is the intended behaviour and it should stay uncomfortable.

But until now the documented way out was "edit the state file by hand", which is not a recovery
path, it is an invitation to delete the wrong thing at the worst moment. So:

  redline halt               why it halted, and what it would take to clear
  redline halt clear         clear it, and write that decision to the log

Clearing is a deliberate operator act. It writes a record exactly like a refusal does, and it
resets the high-water mark to current equity, because leaving the old mark in place would re-halt
on the next call and teach an operator to clear it twice.
"""
from __future__ import annotations

import json
import sys
import time

from .policy import State


def _paths():
    from . import HOME, STATE_PATH

    return HOME, STATE_PATH


def _equity_now():
    from . import runtime
    import redline

    runtime.wire()
    return redline._equity()


def main(argv: list[str]) -> int:
    home, state_path = _paths()
    state = State.load(state_path)
    equity = _equity_now()

    if not state.halted:
        print("not halted.")
        print(f"high-water   ${state.high_water_usd:.2f}")
        print(f"equity now   {'unreadable' if equity is None else f'${equity:.2f}'}")
        if equity is not None and state.high_water_usd:
            down = 100 * (1 - equity / state.high_water_usd)
            print(f"currently    {'down' if down > 0 else 'up'} {abs(down):.1f}% from the high-water mark")
        return 0

    print(f"HALTED: {state.halt_reason}")
    print(f"high-water   ${state.high_water_usd:.2f}")
    print(f"equity now   {'unreadable' if equity is None else f'${equity:.2f}'}")

    if len(argv) < 2 or argv[1] != "clear":
        print("\nEvery order is being refused. Read the log before clearing this:")
        print("  redline log --refused")
        print("\nWhen you have decided it is safe:")
        print("  redline halt clear")
        return 0

    if equity is None:
        print("\nequity is unreadable, so there is no trustworthy mark to restart from.")
        return 1

    before_reason, before_mark = state.halt_reason, state.high_water_usd
    state.halted, state.halt_reason = False, ""
    state.high_water_usd = equity          # otherwise the next call re-halts against the old mark
    state.save(state_path)

    record = {
        "ts": int(time.time()),
        "tool": "operator:halt_clear",
        "allowed": True,
        "rule": "halt_clear",
        "reason": f"operator cleared the halt ({before_reason}); high-water mark reset from "
                  f"${before_mark:.2f} to ${equity:.2f}",
        "equity_usd": round(equity, 2),
        "equity_source": "live",
        "policy_verified": True,
    }
    with (home / "tape.jsonl").open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")

    print(f"\ncleared. high-water mark reset from ${before_mark:.2f} to ${equity:.2f}")
    print(f"written to {home / 'tape.jsonl'} so the decision is as visible as the halt was")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
