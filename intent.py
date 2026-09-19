"""Turn a tool call into an Intent.

Argument shapes verified against the live ClawPump MCP (@clawpump/agents v0.1.27, 132 tools)
on 2026-09-19 with a real key. Two shapes matter and they are NOT the same unit:

  swap_execute   amount  -> a STRING in the token's smallest unit (lamports for SOL, 1e6 for USDC)
  perps_*        quantity-> a NUMBER of base units (0.5 means half a SOL)

Reading a swap amount as base units overstates notional by 10**decimals, which refuses every
swap. Reading it the other way would understate it and let an oversized order through, so the
decimals table is the load-bearing part of this file. A token that is not in the table prices as
None, and None is refused."""
from __future__ import annotations
from typing import Callable, Optional
from .policy import Intent, governed_kind

PriceFn = Callable[[str], Optional[float]]   # symbol -> usd price, None if unknown

_SYM_KEYS = ("market", "symbol", "pair", "asset")
_SIZE_KEYS = ("notional_usd", "notional", "size_usd", "amount_usd")
_BASE_KEYS = ("size", "amount", "base_amount", "quantity")
_SWAP_IN_KEYS = ("input_mint", "input_token", "from_token")

# Smallest-unit decimals for every symbol swap_execute names in its own schema.
# Anything absent here cannot be priced, so it is refused rather than guessed.
_DECIMALS = {"SOL": 9, "USDC": 6, "USDT": 6, "BONK": 5, "WIF": 6, "JUP": 6,
             "JTO": 9, "JITOSOL": 9, "MSOL": 9, "BSOL": 9}


def _first(args: dict, keys) -> Optional[object]:
    for k in keys:
        if k in args and args[k] not in (None, ""):
            return args[k]
    return None


def _symbol(args: dict) -> Optional[str]:
    v = _first(args, _SYM_KEYS)
    return str(v).upper().split("-")[0].split("/")[0] if v else None


def _notional(args: dict, symbol: Optional[str], price: PriceFn,
              raw_units: bool = False) -> Optional[float]:
    usd = _first(args, _SIZE_KEYS)
    if usd is not None:
        return float(usd)
    base = _first(args, _BASE_KEYS)
    if base is None:
        return None
    px = price(symbol) if symbol else None
    if not px:
        return None
    try:
        qty = float(base)
    except (TypeError, ValueError):
        return None
    if raw_units:
        dec = _DECIMALS.get(symbol or "")
        if dec is None:
            return None          # unknown decimals -> unpriceable -> refused
        qty = qty / (10 ** dec)
    return qty * px


def intent_from_call(tool_name: str, args: dict, price: PriceFn) -> Optional[Intent]:
    kind = governed_kind(tool_name)
    if kind is None:
        return None
    args = args or {}
    if kind == "transfer":
        return Intent(kind, None, destination=str(_first(args, ("to", "destination", "recipient", "address")) or ""))
    if kind == "withdraw":
        return Intent(kind, None)
    swap_in = _first(args, _SWAP_IN_KEYS)
    sym = _symbol(args) or (str(swap_in).upper() if swap_in else None)
    lev = float(_first(args, ("leverage",)) or 1.0)
    # A swap names its input token and sizes it in that token's smallest unit.
    raw = kind == "swap" and swap_in is not None
    return Intent(kind, _notional(args, sym, price, raw_units=raw),
                  market=sym, leverage=lev, token=sym)
