"""The state file is not signed. The tape is append-only and its refusals are anchored on chain.

Until 2026-09-19 an agent that could write ~/.hermes/redline/state.json could clear a latched
drawdown halt or a cooldown and carry on. Fixing the `halted` flag alone would have been theatre:
lowering `high_water_usd` to today's equity escapes the same halt one field earlier, and the same
trick works on `day_start_usd` against the daily loss limit and on `day_notional_usd` against the
turnover limit. All four are now re-derived from the tape on load.

The rule the reconciliation obeys is that it can only ever TIGHTEN. That is what makes it safe to
read a file which sits in the same directory as the state and is no harder to attack: a tape that
is missing, truncated, corrupt or rewritten downward cannot weaken anything.
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

from redline.policy import Intent, Policy, State, evaluate

SMALL = Intent("swap", 0.50, market="SOL", token="SOL")
EQUITY = 60.0
# The day window is derived from the clock, because the reconciliation reads "today" from it.
# Anchoring to the middle of the current UTC day keeps the test away from a midnight boundary.
_MIDNIGHT = (time.time() // 86400) * 86400
DAY = _MIDNIGHT + 3600
NOW = _MIDNIGHT + 43200


def _daykey():
    import datetime
    return datetime.datetime.fromtimestamp(NOW, datetime.UTC).strftime("%Y-%m-%d")


def row(**kw):
    base = {"ts": DAY, "allowed": True, "rule": "", "equity_source": "live", "equity_usd": 100.0}
    base.update(kw)
    return base


def load_with(state_fields, tape_rows):
    """Write a state file and a tape beside it, exactly as an agent with a shell would find them."""
    home = Path(tempfile.mkdtemp())
    (home / "state.json").write_text(json.dumps(state_fields))
    (home / "tape.jsonl").write_text("\n".join(json.dumps(r) for r in tape_rows) + "\n")
    return State.load(home / "state.json")


def allowed(state, policy=None):
    return evaluate(policy or Policy(verified=True), state, SMALL, EQUITY, NOW).allowed


TAMPERED = {"high_water_usd": 60.0, "day_start_usd": 60.0, "day_key": None,
            "refusals": [], "day_notional_usd": 0.0, "halted": False, "halt_reason": ""}
TAMPERED["day_key"] = _daykey()


class WhatTheSignatureAlreadyProtected(unittest.TestCase):
    def test_an_unsigned_policy_refuses_everything(self):
        self.assertFalse(allowed(State(), Policy(verified=False)))

    def test_the_per_order_cap_never_came_from_the_state_file(self):
        big = Intent("swap", 14.0, market="SOL", token="SOL")
        v = evaluate(Policy(verified=True), State(), big, 15.85, NOW)
        self.assertEqual(v.rule, "trade_cap")


class TamperingIsUndoneByTheTape(unittest.TestCase):
    def test_a_cleared_halt_comes_back(self):
        st = load_with(TAMPERED, [row(allowed=False, rule="drawdown",
                                      reason="drawdown 40.0% >= 15.0%")])
        self.assertTrue(st.halted)
        self.assertFalse(allowed(st))

    def test_an_operator_who_really_cleared_it_stays_cleared(self):
        """Clearing writes its own record, so a genuine clear is distinguishable from a deletion."""
        st = load_with(TAMPERED, [
            row(allowed=False, rule="drawdown", reason="drawdown 40.0% >= 15.0%"),
            row(ts=DAY + 10, rule="halt_clear", tool="operator:halt_clear", equity_usd=60.0),
        ])
        self.assertFalse(st.halted)

    def test_a_lowered_high_water_mark_comes_back(self):
        st = load_with(TAMPERED, [row(equity_usd=100.0)])
        self.assertEqual(st.high_water_usd, 100.0)
        v = evaluate(Policy(verified=True), st, SMALL, EQUITY, NOW)
        self.assertEqual(v.rule, "drawdown")

    def test_emptied_refusals_come_back(self):
        rows = [row(ts=NOW - 60 - i, allowed=False, rule="trade_cap") for i in range(5)]
        st = load_with(TAMPERED, rows)
        self.assertEqual(len(st.refusals), 5)
        v = evaluate(Policy(verified=True), st, SMALL, EQUITY, NOW)
        self.assertEqual(v.rule, "cooldown")

    def test_a_lowered_day_start_comes_back(self):
        st = load_with(dict(TAMPERED, day_key=_daykey()), [row(ts=DAY, equity_usd=100.0)])
        self.assertGreaterEqual(st.day_start_usd, 100.0)

    def test_a_zeroed_turnover_comes_back(self):
        st = load_with(TAMPERED, [row(ts=DAY + i, allowed=True,
                                      intent={"kind": "swap", "notional_usd": 9.0})
                                  for i in range(3)])
        self.assertAlmostEqual(st.day_notional_usd, 27.0)

    def test_an_operator_day_reset_is_honoured_over_the_opening_row(self):
        st = load_with(TAMPERED, [
            row(ts=DAY, equity_usd=100.0),
            row(ts=DAY + 5, rule="day_reset", tool="operator:day_reset", equity_usd=60.0),
        ])
        self.assertEqual(st.day_start_usd, 60.0)


class ReconciliationCanOnlyTighten(unittest.TestCase):
    def test_a_missing_tape_changes_nothing(self):
        home = Path(tempfile.mkdtemp())
        (home / "state.json").write_text(json.dumps({"high_water_usd": 100.0, "halted": True,
                                                     "halt_reason": "drawdown"}))
        st = State.load(home / "state.json")
        self.assertTrue(st.halted)
        self.assertEqual(st.high_water_usd, 100.0)

    def test_a_corrupt_tape_cannot_weaken_anything(self):
        home = Path(tempfile.mkdtemp())
        (home / "state.json").write_text(json.dumps({"high_water_usd": 100.0, "halted": True,
                                                     "halt_reason": "drawdown"}))
        (home / "tape.jsonl").write_text("not json\n{\"half\": \n\n")
        st = State.load(home / "state.json")
        self.assertTrue(st.halted, "a torn tape must not clear a halt")
        self.assertEqual(st.high_water_usd, 100.0)

    def test_a_tape_rewritten_downward_cannot_lower_the_mark(self):
        st = load_with({"high_water_usd": 100.0, "halted": False, "refusals": []},
                       [row(equity_usd=5.0)])
        self.assertEqual(st.high_water_usd, 100.0)

    def test_a_fixture_balance_can_never_move_a_real_limit(self):
        """An integration run hands the plugin a made-up $100 balance and writes to this tape.
        On 2026-09-19 exactly that contaminated the real high-water mark and halted the wallet."""
        st = load_with({"high_water_usd": 17.02, "halted": False, "refusals": []},
                       [row(equity_source="fixture", equity_usd=100.0),
                        row(equity_source="fixture", allowed=False, rule="drawdown")])
        self.assertEqual(st.high_water_usd, 17.02)
        self.assertFalse(st.halted)


if __name__ == "__main__":
    unittest.main()
