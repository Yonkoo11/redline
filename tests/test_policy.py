import time, unittest
from redline.policy import Policy, State, Intent, evaluate
from redline.intent import intent_from_call
import redline

NOW = 1_800_000_000.0
PRICE = {"SOL": 200.0, "ETH": 4000.0}


def px(sym):
    return PRICE.get(sym)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.p = Policy(max_trade_pct_equity=10, max_daily_loss_pct=5, max_drawdown_pct=15, max_leverage=2)
        self.s = State()

    def test_in_policy_perp_allowed(self):
        v = evaluate(self.p, self.s, Intent("perp", 8.0, market="SOL"), 100.0, NOW)
        self.assertTrue(v.allowed, v.reason)

    def test_over_cap_refused(self):
        v = evaluate(self.p, self.s, Intent("perp", 12.0, market="SOL"), 100.0, NOW)
        self.assertFalse(v.allowed); self.assertEqual(v.rule, "trade_cap")

    def test_unreadable_equity_refused(self):
        v = evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), None, NOW)
        self.assertFalse(v.allowed); self.assertEqual(v.rule, "equity")

    def test_unpriceable_order_refused(self):
        v = evaluate(self.p, self.s, Intent("perp", None, market="SOL"), 100.0, NOW)
        self.assertFalse(v.allowed); self.assertEqual(v.rule, "price")

    def test_leverage_refused(self):
        v = evaluate(self.p, self.s, Intent("perp", 5.0, market="SOL", leverage=5), 100.0, NOW)
        self.assertFalse(v.allowed); self.assertEqual(v.rule, "leverage")

    def test_market_not_allowed(self):
        v = evaluate(self.p, self.s, Intent("perp", 5.0, market="DOGE"), 100.0, NOW)
        self.assertFalse(v.allowed); self.assertEqual(v.rule, "market")

    def test_drawdown_halts_and_stays_halted(self):
        evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 100.0, NOW)
        v = evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 84.0, NOW + 60)
        self.assertEqual(v.rule, "drawdown"); self.assertTrue(self.s.halted)
        v2 = evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 100.0, NOW + 120)
        self.assertEqual(v2.rule, "halt")

    def test_daily_loss_refuses_new_risk(self):
        evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 100.0, NOW)
        v = evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 94.0, NOW + 60)
        self.assertEqual(v.rule, "daily_loss")

    def test_withdraw_always_refused(self):
        v = evaluate(self.p, self.s, Intent("withdraw", None), 100.0, NOW)
        self.assertEqual(v.rule, "withdraw")

    def test_transfer_allowlist(self):
        self.p.allowed_destinations = ["OK1"]
        self.assertTrue(evaluate(self.p, self.s, Intent("transfer", None, destination="OK1"), 100.0, NOW).allowed)
        self.assertFalse(evaluate(self.p, self.s, Intent("transfer", None, destination="BAD"), 100.0, NOW).allowed)

    def test_cooldown_after_repeated_refusals(self):
        for i in range(5):
            self.s.refusals.append(NOW - i)
        v = evaluate(self.p, self.s, Intent("perp", 1.0, market="SOL"), 100.0, NOW)
        self.assertEqual(v.rule, "cooldown")


class IntentMapping(unittest.TestCase):
    def test_ungoverned_tool_ignored(self):
        self.assertIsNone(intent_from_call("mcp_clawpump_get_portfolio", {}, px))

    def test_perp_notional_from_base_size(self):
        i = intent_from_call("mcp_clawpump_perps_order_execute", {"market": "SOL-PERP", "size": 0.05, "leverage": 1}, px)
        self.assertEqual(i.kind, "perp"); self.assertEqual(i.market, "SOL"); self.assertAlmostEqual(i.notional_usd, 10.0)

    def test_unknown_shape_prices_none(self):
        i = intent_from_call("mcp_clawpump_perps_order_execute", {"foo": 1}, px)
        self.assertIsNone(i.notional_usd)

    def test_stdio_prefix_also_governed(self):
        self.assertIsNotNone(intent_from_call("mcp_clawpump-stdio_swap_execute", {"input_token": "SOL", "amount": 0.01}, px))


class HookEndToEnd(unittest.TestCase):
    def setUp(self):
        import tempfile, pathlib
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        redline.HOME = self.tmp; redline.POLICY_PATH = self.tmp / "policy.json"; redline.STATE_PATH = self.tmp / "state.json"
        self.tape = []
        redline.configure(equity_reader=lambda: 100.0, price_reader=px, tape=self.tape.append)

    def test_block_shape_and_tape(self):
        out = redline.pre_tool_call("mcp_clawpump_perps_order_execute", {"market": "SOL", "size": 0.5}, "t1")
        self.assertEqual(out["action"], "block"); self.assertIn("trade_cap", out["message"])
        ok = redline.pre_tool_call("mcp_clawpump_perps_order_execute", {"market": "SOL", "size": 0.04}, "t2")
        self.assertIsNone(ok)
        self.assertEqual([r["allowed"] for r in self.tape], [False, True])

    def test_equity_reader_failure_refuses(self):
        def boom(): raise RuntimeError("rpc down")
        redline.configure(equity_reader=boom)
        out = redline.pre_tool_call("mcp_clawpump_swap_execute", {"input_token": "SOL", "amount": 0.001}, "t3")
        self.assertEqual(out["action"], "block"); self.assertIn("equity", out["message"])


if __name__ == "__main__":
    unittest.main()


class RecordLabelling(unittest.TestCase):
    """Every tape record must say what equity it judged against and whether that equity was live."""

    def setUp(self):
        import tempfile, pathlib
        tmp = pathlib.Path(tempfile.mkdtemp())
        redline.HOME = tmp; redline.POLICY_PATH = tmp / "policy.json"; redline.STATE_PATH = tmp / "state.json"
        self.tape = []

    def test_fixture_equity_is_labelled_fixture(self):
        redline.configure(equity_reader=lambda: 100.0, price_reader=px, tape=self.tape.append)
        redline.pre_tool_call("mcp_clawpump_perps_order_execute", {"market": "SOL", "size": 0.5}, "t")
        self.assertEqual(self.tape[-1]["equity_source"], "fixture")
        self.assertEqual(self.tape[-1]["equity_usd"], 100.0)

    def test_live_equity_is_labelled_live(self):
        redline.configure(equity_reader=lambda: 42.0, price_reader=px, tape=self.tape.append, equity_source="live")
        redline.pre_tool_call("mcp_clawpump_perps_order_execute", {"market": "SOL", "size": 0.5}, "t")
        self.assertEqual(self.tape[-1]["equity_source"], "live")

    def test_unreadable_equity_records_none(self):
        def boom(): raise RuntimeError("rpc down")
        redline.configure(equity_reader=boom, price_reader=px, tape=self.tape.append)
        redline.pre_tool_call("mcp_clawpump_swap_execute", {"input_token": "SOL", "amount": 1}, "t")
        self.assertIsNone(self.tape[-1]["equity_usd"])


# --- argument shapes verified against the live ClawPump MCP on 2026-09-19 ---

def _px(sym):
    return {"SOL": 111.56, "USDC": 1.0}.get(sym)


def test_swap_amount_is_smallest_units_not_base_units():
    """swap_execute sizes in lamports. 0.01 SOL must price as ~$1.12, not $1.1e9."""
    from redline.intent import intent_from_call
    i = intent_from_call("mcp_clawpump_swap_execute",
                         {"input_mint": "SOL", "output_mint": "USDC", "amount": "10000000"}, _px)
    assert i is not None and abs(i.notional_usd - 1.1156) < 0.001


def test_swap_of_a_token_with_unknown_decimals_is_unpriceable():
    from redline.intent import intent_from_call
    i = intent_from_call("mcp_clawpump_swap_execute",
                         {"input_mint": "CLAW", "output_mint": "SOL", "amount": "1000000"},
                         lambda s: 0.5)
    assert i is not None and i.notional_usd is None      # -> refused by the policy


def test_usdc_swap_uses_six_decimals():
    from redline.intent import intent_from_call
    i = intent_from_call("mcp_clawpump_swap_execute",
                         {"input_mint": "USDC", "output_mint": "SOL", "amount": "5000000"}, _px)
    assert abs(i.notional_usd - 5.0) < 0.001


def test_perps_quantity_stays_base_units():
    """perps_order_execute quantity is base units: 0.02 SOL is ~$2.23, not 2.2e-8."""
    from redline.intent import intent_from_call
    i = intent_from_call("mcp_clawpump_perps_order_execute",
                         {"symbol": "SOL", "side": "bid", "quantity": 0.02,
                          "confirmRisk": True, "idempotencyKey": "redline-test-0001"}, _px)
    assert abs(i.notional_usd - 2.2312) < 0.001


def test_perps_lots_only_order_is_unpriceable():
    """numBaseLots has no lot size here, so it must refuse rather than guess."""
    from redline.intent import intent_from_call
    i = intent_from_call("mcp_clawpump_perps_order_execute",
                         {"symbol": "SOL", "side": "bid", "numBaseLots": 4,
                          "confirmRisk": True, "idempotencyKey": "redline-test-0002"}, _px)
    assert i.notional_usd is None
