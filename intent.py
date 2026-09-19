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
# A payment names its amount and sometimes its currency. Anything it does not name cannot be
# priced, and an unpriceable payment is refused.
_SPEND_USD_KEYS = ("usd", "price_usd", "max_amount_usd")   # amount_usd lives in _SIZE_KEYS
_SPEND_TOKEN_KEYS = ("token", "mint", "currency", "asset", "pay_with")

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


def _declared_usd(args: dict) -> Optional[float]:
    """A size the CALLER says the order is worth, in dollars."""
    usd = _first(args, _SIZE_KEYS)
    if usd is None:
        return None
    try:
        return float(usd)
    except (TypeError, ValueError):
        return None


def _from_base(args: dict, symbol: Optional[str], price: PriceFn,
               raw_units: bool) -> tuple[bool, Optional[float]]:
    """The size the VENUE will execute, priced. Returns (a base amount was present, its value)."""
    base = _first(args, _BASE_KEYS)
    if base is None:
        return False, None
    px = price(symbol) if symbol else None
    if not px:
        return True, None
    try:
        qty = float(base)
    except (TypeError, ValueError):
        return True, None
    if raw_units:
        dec = _DECIMALS.get(symbol or "")
        if dec is None:
            return True, None    # unknown decimals -> unpriceable -> refused
        qty = qty / (10 ** dec)
    return True, qty * px


def _notional(args: dict, symbol: Optional[str], price: PriceFn,
              raw_units: bool = False) -> Optional[float]:
    """How much this order is worth, judged against the field the venue actually executes.

    The agent writes every key in this dict. It used to be enough to add `notional_usd: 0.5`
    beside a real `amount` of one SOL: this function returned the declared 0.50, the policy
    allowed it, and the venue, whose schema permits unknown keys and ignores them, swapped the
    whole SOL. Verified against the live swap_execute schema on 2026-09-19, which carries no
    `additionalProperties: false`.

    So a declared dollar size is never trusted over an executable one. Where a base amount is
    present it decides, and a declared size can only ever make the order look BIGGER, never
    smaller. Where the base amount cannot be priced the order is unpriceable, and unpriceable is
    refused; falling back to the caller's own number there would hand the bypass straight back.
    """
    declared = _declared_usd(args)
    had_base, from_base = _from_base(args, symbol, price, raw_units)
    if had_base:
        if from_base is None:
            return None
        return max(from_base, declared) if declared is not None else from_base
    return declared


def intent_from_call(tool_name: str, args: dict, price: PriceFn) -> Optional[Intent]:
    kind = governed_kind(tool_name)
    if kind is None:
        return None
    args = args or {}
    if kind == "transfer":
        dest = str(_first(args, ("to", "destination", "recipient", "address")) or "")
        # A transfer names its token and, on every tool checked on 2026-09-19, its amount in that
        # token's smallest unit, the same as a swap. Unpriceable means refused, not unlimited.
        sym = str(_first(args, ("token", "mint", "asset", "currency")) or "") or None
        if sym:
            sym = sym.upper()
        usd = _notional(args, sym, price, raw_units=bool(sym)) if sym else None
        return Intent(kind, usd, destination=dest, token=sym)
    if kind == "withdraw":
        return Intent(kind, None)
    if kind == "spend":
        # Same rule as a trade: the caller's own dollar figure never shrinks a payment that also
        # names an amount. A payment amount is quoted in whole units by every payment tool checked
        # on 2026-09-19, unlike a swap, which quotes the smallest unit.
        sym = str(_first(args, _SPEND_TOKEN_KEYS) or "").upper() or None
        had_base, from_base = _from_base(args, sym, price, raw_units=False)
        declared = _declared_usd(args)
        if declared is None:
            declared = _first(args, _SPEND_USD_KEYS)
            try:
                declared = float(declared) if declared is not None else None
            except (TypeError, ValueError):
                return Intent(kind, None, token=sym)
        if had_base:
            if from_base is None:
                return Intent(kind, None, token=sym)
            worst = max(from_base, declared) if declared is not None else from_base
            return Intent(kind, worst, token=sym)
        return Intent(kind, declared, token=sym)

    swap_in = _first(args, _SWAP_IN_KEYS)
    sym = _symbol(args) or (str(swap_in).upper() if swap_in else None)
    lev = float(_first(args, ("leverage",)) or 1.0)
    # A swap names its input token and sizes it in that token's smallest unit.
    raw = kind == "swap" and swap_in is not None
    return Intent(kind, _notional(args, sym, price, raw_units=raw),
                  market=sym, leverage=lev, token=sym)
