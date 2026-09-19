"""The policy page and the loader have to agree, or the file a stranger downloads does not work.

This is a contract between two languages that no type checker covers: a Svelte page writes JSON,
a Python dataclass reads it, and the loader refuses any field it does not recognise. A limit added
to one side and not the other is silent until someone downloads a policy that refuses everything.
"""
import json
import pathlib
import re
import unittest
from dataclasses import fields

from redline.policy import Policy

PAGE = pathlib.Path(__file__).resolve().parents[1] / "site" / "src" / "Policy.svelte"
META = {"schema", "generated", "signature"}
INTERNAL = {"verified", "unverified_reason"}


def emitted_keys() -> set:
    src = PAGE.read_text()
    block = re.search(r"const policyFile = \$derived\.by\(\(\) => \(\{([\s\S]*?)\}\)\);", src)
    assert block, "could not find the object the policy page writes out"
    return set(re.findall(r"^\s{4}([a-z_]+):", block.group(1), re.M))


class BuilderMatchesLoader(unittest.TestCase):
    def test_the_page_emits_nothing_the_loader_would_reject(self):
        allowed = {f.name for f in fields(Policy)} | META
        self.assertEqual(emitted_keys() - allowed, set())

    def test_every_limit_is_reachable_from_the_page(self):
        """A limit the page cannot set is a limit that silently keeps its default."""
        settable = {f.name for f in fields(Policy)} - INTERNAL
        self.assertEqual(settable - emitted_keys(), set())

    def test_a_file_shaped_like_the_page_output_loads_and_verifies(self):
        import tempfile
        from redline.sign import keygen
        from redline.signing import sign_policy
        tmp = pathlib.Path(tempfile.mkdtemp())
        key = tmp / "k.json"
        pub = keygen(key)
        doc = {"schema": 1, "generated": "2026-09-19", "mode": "shadow",
               "max_trade_pct_equity": 10, "max_daily_loss_pct": 5,
               "max_daily_notional_pct_equity": 300, "max_spend_usd": 1,
               "max_transfer_usd": 0, "max_drawdown_pct": 15, "max_leverage": 2,
               "equity_floor_usd": 5, "allowed_markets": ["SOL", "ETH"],
               "allowed_tokens": ["SOL", "USDC"], "allowed_destinations": [],
               "refusal_cooldown_count": 5, "refusal_cooldown_minutes": 30}
        self.assertEqual(set(doc) - emitted_keys() - META, set(),
                         "this fixture has drifted from what the page emits")
        path = tmp / "policy.json"
        path.write_text(json.dumps(doc))
        sign_policy(path, key)
        loaded = Policy.load(path, pub)
        self.assertTrue(loaded.verified, loaded.unverified_reason)
        self.assertEqual(loaded.mode, "shadow")
        self.assertEqual(loaded.max_transfer_usd, 0)
