"""The agent writes every key in the argument dict, so nothing in it can be taken on trust.

Found 2026-09-19 by stress test, not by review: a swap of one SOL, seven times the per-order cap,
was ALLOWED when the caller added `notional_usd: 0.5` beside the real `amount`. The engine read
the caller's own dollar figure and never looked at the field the venue executes. The live
swap_execute schema carries no `additionalProperties: false`, so the extra key is accepted and
ignored by the venue and the whole SOL moves.
"""
import unittest

from redline.intent import intent_from_call
from redline.policy import Policy, State, evaluate

PRICE = lambda s: {"SOL": 100.0, "USDC": 1.0}.get(s)
EQUITY = 15.85                       # cap is $1.585 at the default 10%
ONE_SOL = str(10 ** 9)               # $100, sixty times the cap


def verdict(tool, args, policy=None):
    i = intent_from_call(tool, args, PRICE)
    if i is None:
        return None, None
    return i, evaluate(policy or Policy(verified=True), State(), i, EQUITY, 0)


class DeclaredSizeNeverShrinksAnOrder(unittest.TestCase):
    def test_honest_swap_is_refused(self):
        i, v = verdict("mcp_clawpump_swap_execute",
                       {"input_mint": "SOL", "output_mint": "USDC", "amount": ONE_SOL})
        self.assertEqual(i.notional_usd, 100.0)
        self.assertFalse(v.allowed)

    def test_every_declared_size_key_is_ignored_when_smaller(self):
        for key in ("notional_usd", "notional", "size_usd", "amount_usd"):
            with self.subTest(key=key):
                i, v = verdict("mcp_clawpump_swap_execute",
                               {"input_mint": "SOL", "output_mint": "USDC",
                                "amount": ONE_SOL, key: 0.5})
                self.assertEqual(i.notional_usd, 100.0, f"{key} shrank the order")
                self.assertFalse(v.allowed, f"{key} got an over-cap swap through")

    def test_a_declared_size_may_still_make_an_order_look_bigger(self):
        i, _ = verdict("mcp_clawpump_swap_execute",
                       {"input_mint": "SOL", "output_mint": "USDC", "amount": "1", "notional_usd": 9.0})
        self.assertEqual(i.notional_usd, 9.0)

    def test_declared_string_number_does_not_shrink_it_either(self):
        i, v = verdict("mcp_clawpump_swap_execute",
                       {"input_mint": "SOL", "output_mint": "USDC",
                        "amount": ONE_SOL, "notional_usd": "0.5"})
        self.assertEqual(i.notional_usd, 100.0)
        self.assertFalse(v.allowed)

    def test_unpriceable_base_is_not_rescued_by_a_declared_size(self):
        """If the real amount cannot be priced, falling back to the caller's number hands the
        bypass straight back. Unpriceable means refused."""
        i, v = verdict("mcp_clawpump_swap_execute",
                       {"input_mint": "MYSTERYCOIN", "output_mint": "USDC",
                        "amount": ONE_SOL, "notional_usd": 0.5})
        self.assertIsNone(i.notional_usd)
        self.assertFalse(v.allowed)

    def test_payments_cannot_be_declared_smaller_than_they_are(self):
        for key in ("amount_usd", "usd", "price_usd", "max_amount_usd"):
            with self.subTest(key=key):
                i, v = verdict("mcp_clawpump_x402_pay", {"token": "SOL", "amount": 1, key: 0.5})
                self.assertEqual(i.notional_usd, 100.0, f"{key} shrank a payment")
                self.assertFalse(v.allowed)

    def test_a_payment_with_only_a_declared_size_still_prices(self):
        i, _ = verdict("mcp_clawpump_x402_pay", {"amount_usd": 0.25})
        self.assertEqual(i.notional_usd, 0.25)

    def test_transfers_cannot_be_declared_smaller_than_they_are(self):
        i, _ = verdict("mcp_clawpump_wallet_transfer",
                       {"to": "Addr", "token": "SOL", "amount": ONE_SOL, "notional_usd": 0.4})
        self.assertEqual(i.notional_usd, 100.0)

    def test_perps_cannot_be_declared_smaller_than_they_are(self):
        i, v = verdict("mcp_clawpump_perps_order_execute",
                       {"market": "SOL-PERP", "quantity": 1, "notional_usd": 0.5})
        self.assertEqual(i.notional_usd, 100.0)
        self.assertFalse(v.allowed)


if __name__ == "__main__":
    unittest.main()
