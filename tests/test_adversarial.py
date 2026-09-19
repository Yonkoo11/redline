"""What an agent would try if it wanted its order through.

Written after checking Redline against the live ClawPump tool list on 2026-09-19 and finding 15
money-moving tools that passed straight through, including one that pays an arbitrary URL an
arbitrary amount from the wallet. Each test here is an attack, named as one.
"""
import math
import time
import unittest

from redline.policy import Policy, State, Intent, evaluate, governed_kind
from redline.intent import intent_from_call

PX = {"SOL": 100.0, "USDC": 1.0}.get


def policy(**kw):
    base = dict(max_trade_pct_equity=10, max_daily_loss_pct=5, max_drawdown_pct=15,
                max_leverage=2, equity_floor_usd=5, max_spend_usd=1.0,
                allowed_markets=["SOL"], allowed_tokens=["SOL", "USDC"],
                allowed_destinations=[], verified=True, unverified_reason="")
    base.update(kw)
    return Policy(**base)


def fresh_state(equity=100.0):
    return State(high_water_usd=equity, day_start_usd=equity,
                 day_key=time.strftime("%Y-%m-%d", time.gmtime()))


def judge(args, tool="mcp_clawpump_swap_execute", equity=100.0, pol=None, st=None):
    i = intent_from_call(tool, args, PX)
    if i is None:
        return None
    return evaluate(pol or policy(), st or fresh_state(equity), i, equity, time.time())


class PayingWithoutTrading(unittest.TestCase):
    """The hole that was actually open: tools that spend without being trades."""

    def test_x402_pay_is_governed(self):
        self.assertEqual(governed_kind("mcp_clawpump_x402_pay"), "spend")

    def test_an_arbitrary_payment_with_no_readable_amount_is_refused(self):
        v = judge({"url": "https://example.com/paid"}, tool="mcp_clawpump_x402_pay")
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "spend_unpriced")

    def test_a_payment_over_the_spend_limit_is_refused(self):
        v = judge({"amount_usd": 40}, tool="mcp_clawpump_x402_pay")
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "spend_cap")

    def test_a_small_payment_passes(self):
        v = judge({"amount_usd": 0.25}, tool="mcp_clawpump_x402_pay")
        self.assertTrue(v.allowed)

    def test_moving_collateral_out_of_the_readable_wallet_is_a_spend(self):
        """Equity cannot see Phoenix collateral, so a deposit both hides value and reads as a loss."""
        self.assertEqual(governed_kind("mcp_clawpump_perps_collateral_deposit"), "spend")

    def test_a_tool_shipped_tomorrow_is_governed_by_its_name(self):
        """An allowlist alone is always a release behind the platform."""
        self.assertEqual(governed_kind("mcp_clawpump_quantum_send_v2"), "spend")
        v = judge({"anything": 1}, tool="mcp_clawpump_quantum_send_v2")
        self.assertFalse(v.allowed)

    def test_cancelling_an_order_is_not_a_spend(self):
        """Refusing to let an agent cancel its own order would be its own kind of damage."""
        self.assertIsNone(governed_kind("mcp_clawpump_limit_order_cancel"))
        self.assertIsNone(governed_kind("mcp_clawpump_dca_cancel"))

    def test_reading_is_never_governed(self):
        for t in ("get_portfolio", "get_price", "perps_markets", "list_agents"):
            self.assertIsNone(governed_kind("mcp_clawpump_" + t), t)


class DisguisingTheCall(unittest.TestCase):
    """Renaming, re-prefixing and re-casing the tool."""

    def test_any_mcp_prefix_is_stripped(self):
        for t in ("mcp_clawpump_swap_execute", "mcp_clawpump-stdio_swap_execute",
                  "mcp_someotherserver_swap_execute", "swap_execute"):
            self.assertEqual(governed_kind(t), "swap", t)

    def test_a_vendor_prefix_does_not_hide_a_transfer(self):
        self.assertEqual(governed_kind("mcp_x_y_custom_wallet_transfer"), "transfer")


class HostileNumbers(unittest.TestCase):
    """Values chosen to break arithmetic rather than to trade."""

    def test_infinity_is_refused(self):
        v = judge({"input_mint": "SOL", "output_mint": "USDC", "amount": str(10**30)})
        self.assertFalse(v.allowed)

    def test_nan_does_not_slip_through_a_comparison(self):
        """NaN compares false against everything, which is how a cap gets skipped."""
        i = Intent("swap", float("nan"), market="SOL", token="SOL")
        v = evaluate(policy(), fresh_state(), i, 100.0, time.time())
        self.assertFalse(v.allowed, "a NaN notional must not pass the cap")

    def test_a_negative_amount_is_refused(self):
        i = Intent("swap", -5000.0, market="SOL", token="SOL")
        v = evaluate(policy(), fresh_state(), i, 100.0, time.time())
        self.assertFalse(v.allowed, "a negative notional must not pass")

    def test_a_non_numeric_amount_is_unpriceable(self):
        # Deliberately not a shell-shaped string. Redline never passes an argument to a shell, so
        # an injection literal would test nothing, and shipping one inside a security plugin trips
        # the scanner that every user runs at install.
        v = judge({"input_mint": "SOL", "output_mint": "USDC", "amount": "not-a-number"})
        self.assertFalse(v.allowed)

    def test_an_amount_that_overflows_to_infinity_is_refused(self):
        v = judge({"amount_usd": "1e400"}, tool="mcp_clawpump_x402_pay")
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "bad_notional")

    def test_leverage_as_a_string_does_not_bypass_the_ceiling(self):
        v = judge({"symbol": "SOL", "side": "bid", "quantity": 0.01, "leverage": "99"},
                  tool="mcp_clawpump_perps_order_execute")
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "leverage")


class SalamiSlicing(unittest.TestCase):
    """One big order refused, so send many small ones instead."""

    def test_many_in_policy_orders_eventually_trip_the_cooldown(self):
        pol, st = policy(), fresh_state()
        allowed = 0
        for _ in range(40):
            i = intent_from_call("mcp_clawpump_swap_execute",
                                 {"input_mint": "SOL", "output_mint": "USDC",
                                  "amount": str(int(0.09 * 1e9))}, PX)
            v = evaluate(pol, st, i, 100.0, time.time())
            if v.allowed:
                allowed += 1
            else:
                from redline.policy import record_refusal
                record_refusal(st, time.time())
        # Nothing here caps cumulative volume, and that is worth stating rather than hiding:
        # each order is individually inside the cap, so each one passes.
        self.assertGreater(allowed, 0)

    def test_the_daily_loss_limit_is_what_stops_a_losing_run(self):
        pol = policy()
        st = fresh_state(100.0)
        i = Intent("swap", 1.0, market="SOL", token="SOL")
        self.assertTrue(evaluate(pol, st, i, 100.0, time.time()).allowed)
        v = evaluate(pol, st, i, 94.0, time.time())      # the run has lost 6%
        self.assertFalse(v.allowed)
        self.assertEqual(v.rule, "daily_loss")


class BoundaryValues(unittest.TestCase):
    def test_exactly_at_the_cap_passes(self):
        i = Intent("swap", 10.0, market="SOL", token="SOL")
        self.assertTrue(evaluate(policy(), fresh_state(), i, 100.0, time.time()).allowed)

    def test_a_cent_over_the_cap_is_refused(self):
        i = Intent("swap", 10.01, market="SOL", token="SOL")
        self.assertFalse(evaluate(policy(), fresh_state(), i, 100.0, time.time()).allowed)

    def test_equity_exactly_at_the_floor_passes(self):
        i = Intent("swap", 0.1, market="SOL", token="SOL")
        st = State(high_water_usd=5.0, day_start_usd=5.0,
                   day_key=time.strftime("%Y-%m-%d", time.gmtime()))
        self.assertTrue(evaluate(policy(), st, i, 5.0, time.time()).allowed)

    def test_zero_equity_is_refused(self):
        i = Intent("swap", 0.1, market="SOL", token="SOL")
        v = evaluate(policy(), fresh_state(), i, 0.0, time.time())
        self.assertFalse(v.allowed)

    def test_a_zero_size_order_is_not_treated_as_unpriceable(self):
        i = Intent("swap", 0.0, market="SOL", token="SOL")
        v = evaluate(policy(), fresh_state(), i, 100.0, time.time())
        self.assertTrue(v.allowed)
