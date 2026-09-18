"""Wires the live readers into the plugin when Hermes loads it. Everything here is replaceable in tests."""
from __future__ import annotations
from . import configure
from .equity import wallet_equity_usd, price_usd
from .tape import write as tape_write


def wire() -> None:
    configure(equity_reader=wallet_equity_usd, price_reader=price_usd, tape=tape_write)
