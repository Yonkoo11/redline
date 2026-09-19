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

    def test_transfer_to_an_address_not_on_the_allowlist_is_refused(self):
        self.p.allowed_destinations = ["OK1"]
        v = evaluate(self.p, self.s, Intent("transfer", 1.0, destination="BAD"), 100.0, NOW)
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "destination")

    def test_an_allowlisted_destination_is_not_a_blank_cheque(self):
        """The allowlist says where funds may go. It never said how much, and one transfer to a
        trusted address used to be the entire wallet."""
        self.p.allowed_destinations = ["OK1"]
        self.p.max_transfer_usd = 25.0
        v = evaluate(self.p, self.s, Intent("transfer", 100.0, destination="OK1"), 100.0, NOW)
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "transfer_cap")

    def test_a_transfer_within_the_limit_passes(self):
        self.p.allowed_destinations = ["OK1"]
        self.p.max_transfer_usd = 25.0
        self.assertTrue(evaluate(self.p, self.s, Intent("transfer", 10.0, destination="OK1"), 100.0, NOW).allowed)

    def test_transfers_are_off_until_an_operator_sets_a_limit(self):
        """Default zero, to match the default empty allowlist."""
        self.p.allowed_destinations = ["OK1"]
        v = evaluate(self.p, self.s, Intent("transfer", 0.01, destination="OK1"), 100.0, NOW)
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "transfer_cap")

    def test_an_unpriceable_transfer_is_refused(self):
        self.p.allowed_destinations = ["OK1"]
        self.p.max_transfer_usd = 25.0
        v = evaluate(self.p, self.s, Intent("transfer", None, destination="OK1"), 100.0, NOW)
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "transfer_unpriced")

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


class UnknownFields(unittest.TestCase):
    """A misspelled limit is a limit that is not enforced, so it must refuse, not be ignored."""

    def setUp(self):
        import tempfile, pathlib, json
        from redline.sign import keygen
        from redline.signing import sign_policy
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.key = self.tmp / "k.json"
        self.pub = keygen(self.key)
        self.path = self.tmp / "policy.json"
        self.base = {"max_trade_pct_equity": 10, "max_daily_loss_pct": 5, "max_drawdown_pct": 15,
                     "max_leverage": 2, "equity_floor_usd": 5, "allowed_markets": ["SOL"],
                     "allowed_tokens": ["SOL"], "allowed_destinations": [],
                     "refusal_cooldown_count": 5, "refusal_cooldown_minutes": 30}

    def _write(self, extra):
        import json
        from redline.signing import sign_policy
        self.path.write_text(json.dumps({**self.base, **extra}))
        sign_policy(self.path, self.key)

    def test_a_misspelled_limit_refuses(self):
        self._write({"max_trade_pct": 50})
        p = Policy.load(self.path, self.pub)
        self.assertFalse(p.verified)
        self.assertIn("max_trade_pct", p.unverified_reason)

    def test_schema_and_date_metadata_are_allowed(self):
        self._write({"schema": 1, "generated": "2026-09-19"})
        self.assertTrue(Policy.load(self.path, self.pub).verified)


class DayReset(unittest.TestCase):
    """A deliberate outflow looks exactly like a trading loss. The operator can say which it was,
    and the rebaseline can only ever forgive a fall that already happened."""

    def setUp(self):
        import tempfile, pathlib
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.state_path = self.tmp / "state.json"

    def test_reset_moves_the_day_start_down_to_current_equity(self):
        from redline.day import reset
        st = State(day_start_usd=100.0, high_water_usd=120.0, day_key="2026-09-19")
        reset(st, 94.0, self.state_path, self.tmp)
        self.assertEqual(st.day_start_usd, 94.0)

    def test_reset_never_raises_the_baseline(self):
        """Otherwise it would create headroom for a future loss instead of forgiving a past outflow."""
        from redline.day import reset
        st = State(day_start_usd=100.0, high_water_usd=120.0, day_key="2026-09-19")
        reset(st, 110.0, self.state_path, self.tmp)
        self.assertEqual(st.day_start_usd, 100.0)

    def test_reset_leaves_the_drawdown_high_water_alone(self):
        """The drawdown halt exists for the worst day and must survive a rebaseline."""
        from redline.day import reset
        st = State(day_start_usd=100.0, high_water_usd=120.0, day_key="2026-09-19")
        reset(st, 94.0, self.state_path, self.tmp)
        self.assertEqual(st.high_water_usd, 120.0)

    def test_reset_is_written_to_the_tape(self):
        import json
        from redline.day import reset
        st = State(day_start_usd=100.0, high_water_usd=120.0, day_key="2026-09-19")
        reset(st, 94.0, self.state_path, self.tmp)
        rec = json.loads((self.tmp / "tape.jsonl").read_text().strip())
        self.assertEqual(rec["rule"], "day_reset")
        self.assertIn("outflow", rec["reason"])


class EquityCountsEverything(unittest.TestCase):
    """Value the reader cannot see is indistinguishable from value that was lost. A swap into a
    token the old reader ignored reported a 9.4% daily loss, and a larger one latched the drawdown
    halt at 76%, while the money sat in the wallet."""

    def setUp(self):
        from redline import equity
        self.eq = equity
        equity.clear_cache()          # a reading is cached for a few seconds; tests must not share one
        self._sol, self._hold, self._px = equity.sol_balance, equity.token_holdings, equity.prices_usd

    def tearDown(self):
        self.eq.sol_balance, self.eq.token_holdings, self.eq.prices_usd = self._sol, self._hold, self._px
        self.eq.clear_cache()

    def _wallet(self, sol, holdings, prices):
        self.eq.sol_balance = lambda addr, rpc=None: sol
        self.eq.token_holdings = lambda addr, rpc=None: holdings
        self.eq.prices_usd = lambda mints: prices

    def test_a_token_that_is_not_usdc_still_counts(self):
        BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        self._wallet(0.1, {BONK: 1_000_000.0},
                     {self.eq.SOL_MINT: 100.0, BONK: 0.00002})
        self.assertAlmostEqual(self.eq.wallet_equity_usd("x"), 10.0 + 20.0, places=6)

    def test_an_unpriceable_holding_fails_the_whole_reading(self):
        """Skipping it would under-count, and under-counting reads as a loss that never happened."""
        MYSTERY = "MysteryMint1111111111111111111111111111111"
        self._wallet(0.1, {MYSTERY: 5.0}, {self.eq.SOL_MINT: 100.0})
        with self.assertRaises(self.eq.Unpriceable):
            self.eq.wallet_equity_usd("x")

    def test_dust_does_not_fail_the_reading(self):
        """Wallets collect abandoned accounts; a fraction of a cent must not stop trading."""
        DUST = "DustMint111111111111111111111111111111111"
        self._wallet(0.1, {DUST: 1e-12}, {self.eq.SOL_MINT: 100.0})
        self.assertAlmostEqual(self.eq.wallet_equity_usd("x"), 10.0, places=6)

    def test_no_sol_price_is_still_a_hard_failure(self):
        self._wallet(0.1, {}, {})
        with self.assertRaises(RuntimeError):
            self.eq.wallet_equity_usd("x")


class HaltClear(unittest.TestCase):
    """A latched halt needs a supported way out, or operators learn to edit the state file."""

    def setUp(self):
        import tempfile, pathlib
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.state_path = self.tmp / "state.json"

    def _halted(self):
        return State(halted=True, halt_reason="drawdown 20.0% >= 15.0%",
                     high_water_usd=120.0, day_start_usd=100.0, day_key="2026-09-19")

    def test_clearing_resets_the_high_water_mark_to_now(self):
        """Leaving the old mark would re-halt on the very next call."""
        import redline.halt as H
        st = self._halted()
        H._paths = lambda: (self.tmp, self.state_path)
        H._equity_now = lambda: 96.0
        st.save(self.state_path)
        H.main(["halt", "clear"])
        after = State.load(self.state_path)
        self.assertFalse(after.halted)
        self.assertEqual(after.high_water_usd, 96.0)

    def test_clearing_is_written_to_the_tape(self):
        import json, redline.halt as H
        st = self._halted()
        H._paths = lambda: (self.tmp, self.state_path)
        H._equity_now = lambda: 96.0
        st.save(self.state_path)
        H.main(["halt", "clear"])
        rec = json.loads((self.tmp / "tape.jsonl").read_text().strip())
        self.assertEqual(rec["rule"], "halt_clear")

    def test_unreadable_equity_will_not_clear_a_halt(self):
        import redline.halt as H
        st = self._halted()
        H._paths = lambda: (self.tmp, self.state_path)
        H._equity_now = lambda: None
        st.save(self.state_path)
        self.assertEqual(H.main(["halt", "clear"]), 1)
        self.assertTrue(State.load(self.state_path).halted)
