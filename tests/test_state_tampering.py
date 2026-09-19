"""What the signature buys, and what it does not.

The policy is signed, so an agent cannot raise its own ceiling. The state file is NOT signed, and
these tests pin exactly what that costs, measured rather than assumed. They assert the CURRENT
behaviour, including the parts that are a limitation, so that a future change to either is
deliberate and visible rather than accidental.

The honest summary, which is also in the README: an agent that can write ~/.hermes/redline/state.json
can clear a latched halt and a cooldown. It cannot change a limit, and it cannot make an over-cap
order pass, because the cap is computed from the signed policy and equity read live from chain.
"""
import json
import tempfile
import unittest
from pathlib import Path

from redline.policy import Intent, Policy, State, evaluate

SMALL = Intent("swap", 0.50, market="SOL", token="SOL")
EQUITY = 15.85


def allowed(state, policy=None):
    return evaluate(policy or Policy(verified=True), state, SMALL, EQUITY, 0).allowed


def roundtrip(state, edit):
    """Save, let something edit the file, load it back. What an agent with a shell can do."""
    with tempfile.TemporaryDirectory() as home:
        path = Path(home) / "state.json"
        state.save(path)
        raw = json.loads(path.read_text())
        edit(raw)
        path.write_text(json.dumps(raw))
        return State.load(path)


class WhatTheSignatureProtects(unittest.TestCase):
    def test_an_unsigned_policy_refuses_everything(self):
        self.assertFalse(allowed(State(), Policy(verified=False)))

    def test_the_cap_holds_regardless_of_state(self):
        big = Intent("swap", 14.0, market="SOL", token="SOL")
        v = evaluate(Policy(verified=True), State(), big, EQUITY, 0)
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "trade_cap")


class WhatTheStateFileDoesNotProtect(unittest.TestCase):
    """Known limitation, measured. Not a claim that this is fine."""

    def test_a_latched_halt_is_lost_if_the_state_file_is_rewritten(self):
        halted = State(halted=True, halt_reason="drawdown 40.0% >= 15.0%")
        self.assertFalse(allowed(halted))
        cleared = roundtrip(halted, lambda raw: raw.update(halted=False, halt_reason=""))
        self.assertTrue(allowed(cleared),
                        "behaviour changed: update the README's honesty table to match")

    def test_a_cooldown_is_lost_if_the_state_file_is_rewritten(self):
        cooling = State(refusals=[0.0] * 5)
        self.assertFalse(allowed(cooling))
        cleared = roundtrip(cooling, lambda raw: raw.update(refusals=[]))
        self.assertTrue(allowed(cleared),
                        "behaviour changed: update the README's honesty table to match")


if __name__ == "__main__":
    unittest.main()
