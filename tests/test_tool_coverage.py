"""Every tool the venue can hand the agent, checked against the venue's own flags.

Captured from the live ClawPump MCP on 2026-09-19: 132 tools, each carrying the platform's own
`readOnly` and `destructive` booleans. Two things this pins, both found by running it rather than
reading the code:

  - Nine tools that move value out of the wallet were ungoverned, among them `predictions_open`
    ("Places a bet on a specific outcome"), `agent_card_create` ("create/buy a card") and
    `usepod_provision` ("if `amount` is given — fund"). Invisible to the plugin.
  - Eight read-only tools were being refused, including `swap_quote` and `perps_order_preview`
    and `x402_pay_check` — the three tools that price a thing before committing to it. The
    venue's own description of swap_execute says "Always get a quote first."
"""
import json
import unittest
from pathlib import Path

from redline.policy import governed_kind

TOOLS = json.loads((Path(__file__).with_name("fixtures-clawpump-tools.json")).read_text())

# Tools whose effect is that value leaves the agent's wallet, or leaves where the equity reader
# can see it. Each one is quoted from the platform's own description.
WALLET_TOUCHING = {
    "swap_execute", "perps_order_execute", "dca_create", "limit_order_create",
    "wallet_transfer", "perps_collateral_withdraw", "agent_card_withdraw",
    "perps_collateral_deposit", "usepod_deposit", "x402_pay", "pay_sh_execute_approved",
    "pay_sh_prepare_call", "launch_token_gasless", "launch_metaplex_genesis_token",
    "predictions_open", "agent_card_create", "agent_card_reveal", "agent_mail_create",
    "agent_mail_send", "usepod_provision", "perps_account_prepare", "create_agent_run",
    "trigger_automation",
}


class ToolCoverage(unittest.TestCase):
    def test_the_fixture_is_the_real_tool_list(self):
        self.assertEqual(len(TOOLS), 132)
        self.assertTrue(all("readOnly" in t and "destructive" in t for t in TOOLS))

    def test_every_wallet_touching_tool_is_governed(self):
        ungoverned = [t["name"] for t in TOOLS
                      if t["name"] in WALLET_TOUCHING
                      and governed_kind("mcp_clawpump_" + t["name"]) is None]
        self.assertEqual(ungoverned, [], f"invisible to the plugin: {ungoverned}")

    def test_no_read_only_tool_is_governed(self):
        """Refusing a read costs the agent its eyes and protects nothing."""
        wrong = [(t["name"], governed_kind("mcp_clawpump_" + t["name"])) for t in TOOLS
                 if t["readOnly"] and governed_kind("mcp_clawpump_" + t["name"]) is not None]
        self.assertEqual(wrong, [], f"read-only tools being refused: {wrong}")

    def test_the_names_the_fixture_expects_still_exist(self):
        """If the platform renames one of these, this fails loudly instead of silently
        ungoverning it."""
        live = {t["name"] for t in TOOLS}
        self.assertEqual(WALLET_TOUCHING - live, set())


class NameShapes(unittest.TestCase):
    def test_a_two_segment_mcp_prefix_is_still_seen(self):
        """Hermes composes mcp_<server>_<tool>. A server called `swap` produces
        `mcp_swap_execute`, which the three-segment stripper reduced to `execute`: not a governed
        suffix, not a money word, and therefore straight through."""
        self.assertEqual(governed_kind("mcp_swap_execute"), "swap")

    def test_longer_prefixes_are_still_seen(self):
        self.assertEqual(governed_kind("mcp_a_b_c_swap_execute"), "swap")
        self.assertEqual(governed_kind("swap_execute"), "swap")

    def test_ordinary_tools_stay_ungoverned(self):
        for t in ("read_file", "web_search", "mcp_clawpump_get_portfolio",
                  "mcp_clawpump_get_price", "mcp_clawpump_perps_markets"):
            with self.subTest(tool=t):
                self.assertIsNone(governed_kind(t))


if __name__ == "__main__":
    unittest.main()
