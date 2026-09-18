"""Turn a tool call into an Intent. Envelope-agnostic on purpose: the real ClawPump
argument shapes are an Open Unknown until probed; anything we cannot read prices as None,
and None is refused by the policy."""
from __future__ import annotations
from typing import Callable, Optional
from .policy import Intent, governed_kind

PriceFn = Callable[[str], Optional[float]]   # symbol -> usd price, None if unknown

_SYM_KEYS = ("market", "symbol", "pair", "asset")
_SIZE_KEYS = ("notional_usd", "notional", "size_usd", "amount_usd")
_BASE_KEYS = ("size", "amount", "base_amount", "quantity")


def _first(args: dict, keys) -> Optional[object]:
    for k in keys:
        if k in args and args[k] not in (None, ""):
            return args[k]
    return None


def _symbol(args: dict) -> Optional[str]:
    v = _first(args, _SYM_KEYS)
    return str(v).upper().split("-")[0].split("/")[0] if v else None


def _notional(args: dict, symbol: Optional[str], price: PriceFn) -> Optional[float]:
    usd = _first(args, _SIZE_KEYS)
    if usd is not None:
        return float(usd)
    base = _first(args, _BASE_KEYS)
    px = price(symbol) if symbol else None
    if base is not None and px:
        return float(base) * px
    return None


def intent_from_call(tool_name: str, args: dict, price: PriceFn) -> Optional[Intent]:
    kind = governed_kind(tool_name)
    if kind is None:
        return None
    args = args or {}
    if kind == "transfer":
        return Intent(kind, None, destination=str(_first(args, ("to", "destination", "recipient", "address")) or ""))
    if kind == "withdraw":
        return Intent(kind, None)
    sym = _symbol(args) or (str(_first(args, ("input_token", "from_token", "input_mint")) or "").upper() or None)
    lev = float(_first(args, ("leverage",)) or 1.0)
    return Intent(kind, _notional(args, sym, price), market=sym, leverage=lev, token=sym)
