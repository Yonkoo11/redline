"""Equity reader: what the agent wallet is worth in USD, read straight from Solana and priced live.

It counts SOL plus **every** token the wallet holds, not a fixed list. That is not a nicety. The
limits are all expressed against equity, so anything the reader cannot see looks exactly like money
that was lost:

  a single allowed swap of SOL into a token the reader ignored reported a 9.4% daily loss and
  refused further trading, and a larger one reported a 76% drawdown and latched the halt,
  while the value sat untouched in the wallet the whole time

So a token that cannot be priced is not skipped and it is not guessed. It makes the whole reading
unusable, which raises `Unpriceable` and refuses, because trading on an equity figure known to be
wrong is worse than not trading.

Phoenix collateral and open positions are still outside this reading. The account has no Phoenix
trader registered, so today that total is zero; if one is opened, this under-counts again and the
same class of bug returns. Named in INVARIANTS.md rather than left implicit.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.request
from typing import Optional

_CFG = pathlib.Path(os.environ.get("REDLINE_HOME", pathlib.Path.home() / ".hermes" / "redline")) / "config.json"
_cfg = json.loads(_CFG.read_text()) if _CFG.exists() else {}
RPC = os.environ.get("REDLINE_RPC", _cfg.get("rpc", "https://solana-rpc.publicnode.com"))
AGENT = os.environ.get("REDLINE_AGENT_WALLET", _cfg.get("agent_wallet", ""))

SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ETH_MINT = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"   # Wormhole ETH, for pricing only
MINTS = {"SOL": SOL_MINT, "USDC": USDC_MINT, "ETH": ETH_MINT}

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# Dust: an account holding a fraction of a cent is not worth failing a reading over, and wallets
# collect empty or abandoned accounts. Anything at or above this must price or the reading fails.
DUST_UI_AMOUNT = 1e-9

_UA = {"User-Agent": "redline/0.2 (+https://useredline.xyz)"}   # Jupiter 403s Python's default

# Every governed call reads a balance, its token accounts and a price. An agent in a loop would
# make three network round trips per tool call, which is slow and is how a price source starts
# rate limiting, and a rate limited price source refuses every order. A few seconds of cache keeps
# the reading honest (equity does not move meaningfully in that window) and keeps the agent alive.
CACHE_SECONDS = float(os.environ.get("REDLINE_EQUITY_CACHE_SECONDS", "5"))
HTTP_TIMEOUT = float(os.environ.get("REDLINE_HTTP_TIMEOUT", "8"))
_cache: dict = {}


def clear_cache() -> None:
    """Drop the cached reading. Used by tests, and by anything that must not trust a stale one."""
    _cache.clear()


class Unpriceable(RuntimeError):
    """The wallet holds something this reader cannot value. Refuse rather than under-count."""


def _rpc(method: str, params: list, rpc: str = RPC) -> dict:
    req = urllib.request.Request(
        rpc,
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"content-type": "application/json", **_UA})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        body = json.load(r)
    if "error" in body:
        raise RuntimeError(f"rpc {method}: {body['error']}")
    return body["result"]


def sol_balance(addr: str, rpc: str = RPC) -> float:
    return _rpc("getBalance", [addr], rpc)["value"] / 1e9


def token_balance(addr: str, mint: str, rpc: str = RPC) -> float:
    accts = _rpc("getTokenAccountsByOwner", [addr, {"mint": mint}, {"encoding": "jsonParsed"}], rpc)["value"]
    return sum(float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0) for a in accts)


def token_holdings(addr: str, rpc: str = RPC) -> dict:
    """Every mint the wallet holds, with its UI amount. Both token programs."""
    out: dict[str, float] = {}
    for program in (TOKEN_PROGRAM, TOKEN_2022):
        try:
            accts = _rpc("getTokenAccountsByOwner",
                         [addr, {"programId": program}, {"encoding": "jsonParsed"}], rpc)["value"]
        except Exception:
            if program == TOKEN_PROGRAM:
                raise                      # the main program failing means we know nothing
            continue                       # token-2022 unsupported on some endpoints
        for a in accts:
            info = a["account"]["data"]["parsed"]["info"]
            amt = float(info["tokenAmount"]["uiAmount"] or 0)
            if amt > 0:
                out[info["mint"]] = out.get(info["mint"], 0.0) + amt
    return out


def _jupiter(ids: list[str]) -> dict:
    """Jupiter price v3: {mint: {usdPrice: float, ...}}. Two hosts, because one source for every
    limit in the system is a single point of refusal."""
    last = None
    for host in ("https://lite-api.jup.ag", "https://api.jup.ag"):
        try:
            req = urllib.request.Request(f"{host}/price/v3?ids={','.join(ids)}", headers=_UA)
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return json.load(r)
        except Exception as exc:
            last = exc
    raise RuntimeError(f"no price source answered: {last}")


def prices_usd(mints: list[str]) -> dict:
    if not mints:
        return {}
    data = _jupiter(mints)
    return {m: float(v["usdPrice"]) for m, v in data.items()
            if isinstance(v, dict) and v.get("usdPrice")}


def price_usd(symbol: str) -> Optional[float]:
    mint = MINTS.get(symbol.upper())
    if not mint:
        return None
    return prices_usd([mint]).get(mint)


def wallet_equity_usd(addr: str = AGENT, rpc: str = RPC) -> float:
    """Raises on any failure. The policy treats an exception as unreadable and refuses.

    A failure is never cached, so an outage means every call retries and every call refuses, which
    is the behaviour wanted. Only a good reading is held, and only briefly."""
    if not addr:
        raise RuntimeError("REDLINE_AGENT_WALLET not set")

    hit = _cache.get(addr)
    if hit and (time.monotonic() - hit[0]) < CACHE_SECONDS:
        return hit[1]

    sol = sol_balance(addr, rpc)
    holdings = token_holdings(addr, rpc)

    wanted = [SOL_MINT] + [m for m, amt in holdings.items() if amt >= DUST_UI_AMOUNT]
    px = prices_usd(sorted(set(wanted)))

    if SOL_MINT not in px:
        raise RuntimeError("SOL price unavailable")

    total = sol * px[SOL_MINT]
    missing = []
    for mint, amt in holdings.items():
        if amt < DUST_UI_AMOUNT:
            continue
        if mint not in px:
            missing.append(mint)
            continue
        total += amt * px[mint]

    if missing:
        raise Unpriceable(
            "wallet holds a token with no price: " + ", ".join(sorted(missing)[:3]) +
            ". Refusing rather than reporting equity that is known to be too low.")
    _cache[addr] = (time.monotonic(), total)
    return total
