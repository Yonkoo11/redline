"""What happens when Redline itself is broken, starved, or raced.

The finding that produced this file: when the hook raises, the installed Hermes runtime logs the
exception and lets the tool call through. The state file lives in a directory the agent can write,
so one broken byte was a complete bypass. Everything here holds that door shut.
"""
import json
import os
import pathlib
import tempfile
import threading
import time
import unittest

import redline
from redline.sign import keygen
from redline.signing import sign_policy

LIMITS = {"max_trade_pct_equity": 10, "max_daily_loss_pct": 5, "max_drawdown_pct": 15,
          "max_leverage": 2, "equity_floor_usd": 5, "allowed_markets": ["SOL"],
          "allowed_tokens": ["SOL", "USDC"], "allowed_destinations": [],
          "refusal_cooldown_count": 5, "refusal_cooldown_minutes": 30}
OVER = {"input_mint": "SOL", "output_mint": "USDC", "amount": str(int(0.5e9))}   # $50 against a $10 cap
UNDER = {"input_mint": "SOL", "output_mint": "USDC", "amount": str(int(0.01e9))}  # $1


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        redline.HOME = self.tmp
        redline.POLICY_PATH = self.tmp / "policy.json"
        redline.STATE_PATH = self.tmp / "state.json"
        pub = keygen(self.tmp / "k.json")
        redline.POLICY_PATH.write_text(json.dumps(LIMITS))
        sign_policy(redline.POLICY_PATH, self.tmp / "k.json")
        self._old = os.environ.get("REDLINE_OPERATOR_PUBKEY")
        os.environ["REDLINE_OPERATOR_PUBKEY"] = pub
        self.tape = []
        redline.configure(equity_reader=lambda: 100.0, price_reader={"SOL": 100.0}.get,
                          tape=self.tape.append, equity_source="fixture")

    def tearDown(self):
        os.environ.pop("REDLINE_OPERATOR_PUBKEY", None)
        if self._old is not None:
            os.environ["REDLINE_OPERATOR_PUBKEY"] = self._old

    def call(self, args=None, tool="mcp_clawpump_swap_execute"):
        return redline.pre_tool_call(tool, args if args is not None else OVER, "t")


class BrokenOwnFiles(Harness):
    def test_baseline_blocks(self):
        self.assertEqual(self.call()["action"], "block")

    def test_corrupt_state_blocks_rather_than_letting_the_order_through(self):
        redline.STATE_PATH.write_text("{{{ not json")
        out = self.call()
        self.assertIsNotNone(out, "a corrupt state file must not allow the order")
        self.assertIn("internal_error", out["message"])

    def test_state_with_wrong_types_blocks(self):
        redline.STATE_PATH.write_text('{"high_water_usd": "not a number"}')
        self.assertIsNotNone(self.call())

    def test_corrupt_policy_blocks(self):
        redline.POLICY_PATH.write_text("<<<broken")
        self.assertIsNotNone(self.call())

    def test_a_missing_policy_blocks(self):
        redline.POLICY_PATH.unlink()
        out = self.call()
        self.assertIsNotNone(out)

    def test_an_internal_error_is_written_to_the_log(self):
        redline.STATE_PATH.write_text("{{{ not json")
        self.call()
        self.assertEqual(self.tape[-1]["rule"], "internal_error")

    def test_a_read_only_tool_is_not_blocked_by_a_broken_state_file(self):
        """Refusing every read because a file is damaged would be its own kind of damage."""
        redline.STATE_PATH.write_text("{{{ not json")
        self.assertIsNone(self.call(tool="mcp_clawpump_get_portfolio", args={"x": 1}))

    def test_a_read_only_tool_with_hostile_arguments_is_not_blocked(self):
        self.assertIsNone(self.call(tool="mcp_clawpump_get_price", args={"tokens": object()}))


class StarvedResources(Harness):
    def test_an_unwritable_home_still_refuses(self):
        """If the verdict cannot be recorded, the verdict still stands."""
        redline.STATE_PATH.write_text(json.dumps({}))
        os.chmod(self.tmp, 0o500)
        try:
            self.assertIsNotNone(self.call())
        finally:
            os.chmod(self.tmp, 0o700)

    def test_a_tape_that_throws_does_not_lose_the_refusal(self):
        def boom(_):
            raise OSError("disk full")
        redline.configure(tape=boom)
        out = self.call()
        self.assertIsNotNone(out)
        self.assertIn("trade_cap", out["message"])

    def test_an_equity_reader_that_hangs_then_fails_refuses(self):
        def slow():
            time.sleep(0.05)
            raise TimeoutError("rpc timeout")
        redline.configure(equity_reader=slow)
        out = self.call(args=UNDER)
        self.assertIsNotNone(out)
        self.assertIn("equity", out["message"])

    def test_a_price_source_that_fails_makes_the_order_unpriceable(self):
        def dead(_sym):
            raise ConnectionError("price source down")
        redline.configure(price_reader=dead)
        out = self.call(args=UNDER)
        self.assertIsNotNone(out, "no price means no size check, which means refuse")


class ConcurrentCalls(Harness):
    def test_parallel_calls_never_allow_an_over_cap_order(self):
        """Two tool calls landing together must not race the state file into allowing one."""
        results = []
        lock = threading.Lock()

        def worker():
            out = redline.pre_tool_call("mcp_clawpump_swap_execute", OVER, "t")
            with lock:
                results.append(out)

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 12)
        self.assertTrue(all(r is not None for r in results),
                        "every over-cap call must be refused, however they interleave")

    def test_the_state_file_survives_parallel_writes(self):
        threads = [threading.Thread(
            target=lambda: redline.pre_tool_call("mcp_clawpump_swap_execute", UNDER, "t"))
            for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        json.loads(redline.STATE_PATH.read_text())     # raises if the file was torn


class SustainedRun(Harness):
    def test_a_long_run_is_stopped_by_the_turnover_budget(self):
        """Every one of these is inside the per-order cap, so the per-order cap never fires.
        What stops the run is the daily turnover budget, which is the point of having one."""
        allowed = refused = 0
        rules = set()
        for _ in range(400):
            out = redline.pre_tool_call("mcp_clawpump_swap_execute", UNDER, "t")
            if out is None:
                allowed += 1
            else:
                refused += 1
                rules.add(out["message"].split("(")[1].split(")")[0])
        self.assertEqual(allowed + refused, 400)
        self.assertEqual(len(self.tape), 400, "every decision is recorded, none dropped")
        # equity $100, budget 300% of it, orders of $1: the brake lands at about 300.
        self.assertLess(allowed, 400)
        self.assertGreater(refused, 0, "an agent in a loop has to be stopped by something")
        self.assertIn("daily_turnover", rules)

    def test_turnover_only_counts_orders_that_went_through(self):
        for _ in range(5):
            redline.pre_tool_call("mcp_clawpump_swap_execute", OVER, "t")   # all refused
        import json as _json
        state = _json.loads(redline.STATE_PATH.read_text())
        self.assertEqual(state["day_notional_usd"], 0.0)
