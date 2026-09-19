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
        self.p = Policy(max_trade_pct_equity=10, max_daily_loss_pct=5, max_drawdown_pct=15, max_leverage=2,
                        verified=True, unverified_reason="")
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
    """Runs the real signing path: a real key, a real signature, a real pinned public key."""

    def setUp(self):
        import tempfile, pathlib, json, os
        from redline.sign import keygen
        from redline.signing import sign_policy
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        redline.HOME = self.tmp; redline.POLICY_PATH = self.tmp / "policy.json"; redline.STATE_PATH = self.tmp / "state.json"
        self.key = self.tmp / "operator-key.json"
        pub = keygen(self.key)
        redline.POLICY_PATH.write_text(json.dumps({
            "max_trade_pct_equity": 10, "max_daily_loss_pct": 5, "max_drawdown_pct": 15,
            "max_leverage": 2, "equity_floor_usd": 5,
            "allowed_markets": ["SOL", "ETH"], "allowed_tokens": ["SOL", "USDC"],
            "allowed_destinations": [], "refusal_cooldown_count": 5,
            "refusal_cooldown_minutes": 30}))
        sign_policy(redline.POLICY_PATH, self.key)
        self._old_pub = os.environ.get("REDLINE_OPERATOR_PUBKEY")
        os.environ["REDLINE_OPERATOR_PUBKEY"] = pub
        self.tape = []
        redline.configure(equity_reader=lambda: 100.0, price_reader=px, tape=self.tape.append)

    def tearDown(self):
        import os
        if self._old_pub is None:
            os.environ.pop("REDLINE_OPERATOR_PUBKEY", None)
        else:
            os.environ["REDLINE_OPERATOR_PUBKEY"] = self._old_pub

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


class OperatorSignature(unittest.TestCase):
    """The claim on the page is that the limits are the operator's. These prove it."""

    def setUp(self):
        import tempfile, pathlib, json
        from redline.sign import keygen
        from redline.signing import sign_policy
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.key = self.tmp / "k.json"
        self.pub = keygen(self.key)
        self.path = self.tmp / "policy.json"
        self.limits = {"max_trade_pct_equity": 10, "max_daily_loss_pct": 5,
                       "max_drawdown_pct": 15, "max_leverage": 2, "equity_floor_usd": 5,
                       "allowed_markets": ["SOL"], "allowed_tokens": ["SOL", "USDC"],
                       "allowed_destinations": [], "refusal_cooldown_count": 5,
                       "refusal_cooldown_minutes": 30}
        self.path.write_text(json.dumps(self.limits))
        sign_policy(self.path, self.key)

    def test_a_signed_policy_verifies(self):
        p = Policy.load(self.path, self.pub)
        self.assertTrue(p.verified)
        self.assertEqual(p.max_trade_pct_equity, 10)

    def test_raising_your_own_cap_breaks_the_signature(self):
        """The whole point: an agent that edits the file cannot re-sign it."""
        import json
        d = json.loads(self.path.read_text())
        d["max_trade_pct_equity"] = 100            # the agent helps itself
        self.path.write_text(json.dumps(d))
        p = Policy.load(self.path, self.pub)
        self.assertFalse(p.verified)
        self.assertIn("altered", p.unverified_reason)

    def test_an_unverified_policy_refuses_everything(self):
        import json
        d = json.loads(self.path.read_text())
        d["max_drawdown_pct"] = 99
        self.path.write_text(json.dumps(d))
        p = Policy.load(self.path, self.pub)
        v = evaluate(p, State(), Intent("perp", 0.01, market="SOL"), 100.0, time.time())
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "unsigned_policy")

    def test_no_pinned_key_refuses(self):
        p = Policy.load(self.path, None)
        self.assertFalse(p.verified)
        self.assertIn("no operator public key pinned", p.unverified_reason)

    def test_a_different_key_does_not_pass(self):
        other = self.tmp / "other.json"
        from redline.sign import keygen
        other_pub = keygen(other)
        p = Policy.load(self.path, other_pub)
        self.assertFalse(p.verified)

    def test_signature_survives_reformatting_but_not_reordering_values(self):
        """Canonical form means whitespace is irrelevant and values are not."""
        import json
        d = json.loads(self.path.read_text())
        self.path.write_text(json.dumps(d, indent=4))          # same values, new layout
        self.assertTrue(Policy.load(self.path, self.pub).verified)
        d["allowed_tokens"] = ["SOL", "USDC", "BONK"]          # one extra token
        self.path.write_text(json.dumps(d))
        self.assertFalse(Policy.load(self.path, self.pub).verified)


class ShadowMode(unittest.TestCase):
    """A new policy should be watched before it is trusted. Shadow judges without blocking."""

    def setUp(self):
        import tempfile, pathlib, json, os
        from redline.sign import keygen
        from redline.signing import sign_policy
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        redline.HOME = self.tmp
        redline.POLICY_PATH = self.tmp / "policy.json"
        redline.STATE_PATH = self.tmp / "state.json"
        self.key = self.tmp / "k.json"
        pub = keygen(self.key)
        redline.POLICY_PATH.write_text(json.dumps({
            "max_trade_pct_equity": 10, "max_daily_loss_pct": 5, "max_drawdown_pct": 15,
            "max_leverage": 2, "equity_floor_usd": 5, "allowed_markets": ["SOL"],
            "allowed_tokens": ["SOL", "USDC"], "allowed_destinations": [],
            "refusal_cooldown_count": 5, "refusal_cooldown_minutes": 30}))
        sign_policy(redline.POLICY_PATH, self.key)
        self._old_pub = os.environ.get("REDLINE_OPERATOR_PUBKEY")
        self._old_mode = os.environ.get("REDLINE_MODE")
        os.environ["REDLINE_OPERATOR_PUBKEY"] = pub
        self.tape = []
        redline.configure(equity_reader=lambda: 100.0, price_reader=px, tape=self.tape.append)

    def tearDown(self):
        import os
        for k, v in (("REDLINE_OPERATOR_PUBKEY", self._old_pub), ("REDLINE_MODE", self._old_mode)):
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v

    def _over_cap(self):
        return redline.pre_tool_call(
            "mcp_clawpump_perps_order_execute", {"market": "SOL", "size": 0.5}, "t")

    def test_enforce_is_the_default(self):
        """A guardrail that is off by accident is worse than none."""
        out = self._over_cap()
        self.assertEqual(out["action"], "block")
        self.assertEqual(self.tape[-1]["mode"], "enforce")

    def test_shadow_lets_the_order_through(self):
        import os
        os.environ["REDLINE_MODE"] = "shadow"
        self.assertIsNone(self._over_cap())

    def test_shadow_still_records_what_it_would_have_refused(self):
        import os
        os.environ["REDLINE_MODE"] = "shadow"
        self._over_cap()
        rec = self.tape[-1]
        self.assertTrue(rec["would_refuse"])
        self.assertEqual(rec["rule"], "trade_cap")
        self.assertEqual(rec["mode"], "shadow")

    def test_shadow_does_not_burn_the_refusal_cooldown(self):
        """Watching must not trip a limit that only enforcing should trip."""
        import os, json
        os.environ["REDLINE_MODE"] = "shadow"
        for _ in range(8):
            self._over_cap()
        state = json.loads(redline.STATE_PATH.read_text())
        self.assertEqual(state["refusals"], [])

    def test_env_overrides_a_signed_shadow_policy_back_to_enforce(self):
        """An operator must always be able to turn enforcement on without re-signing."""
        import os, json
        d = json.loads(redline.POLICY_PATH.read_text())
        d["mode"] = "shadow"
        redline.POLICY_PATH.write_text(json.dumps(d))
        from redline.signing import sign_policy
        sign_policy(redline.POLICY_PATH, self.key)
        self.assertIsNone(self._over_cap())              # signed shadow: allowed
        os.environ["REDLINE_MODE"] = "enforce"
        self.assertEqual(self._over_cap()["action"], "block")
