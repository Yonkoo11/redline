"""Equity reader: what the agent wallet is worth in USD, read straight from Solana and Jupiter.
V1 counts SOL and USDC in the wallet. Phoenix collateral and open positions are an Open Unknown
until the perps envelopes are probed; until then the reader under-counts, which errs toward refusing."""
from __future__ import annotations
import json, os, urllib.request
from typing import Optional

import pathlib
_CFG = pathlib.Path(os.environ.get("REDLINE_HOME", pathlib.Path.home() / ".hermes" / "redline")) / "config.json"
_cfg = json.loads(_CFG.read_text()) if _CFG.exists() else {}
RPC = os.environ.get("REDLINE_RPC", _cfg.get("rpc", "https://api.mainnet-beta.solana.com"))
AGENT = os.environ.get("REDLINE_AGENT_WALLET", _cfg.get("agent_wallet", ""))
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ETH_MINT = "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs"   # Wormhole ETH, for pricing only
MINTS = {"SOL": SOL_MINT, "USDC": USDC_MINT, "ETH": ETH_MINT}


def _rpc(method: str, params: list, rpc: str = RPC) -> dict:
    req = urllib.request.Request(rpc, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["result"]


def sol_balance(addr: str, rpc: str = RPC) -> float:
    return _rpc("getBalance", [addr], rpc)["value"] / 1e9


def token_balance(addr: str, mint: str, rpc: str = RPC) -> float:
    accts = _rpc("getTokenAccountsByOwner", [addr, {"mint": mint}, {"encoding": "jsonParsed"}], rpc)["value"]
    return sum(float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0) for a in accts)


def price_usd(symbol: str) -> Optional[float]:
    """Jupiter price v3: {mint: {usdPrice: float, ...}} — probed 2026-09-18."""
    mint = MINTS.get(symbol.upper())
    if not mint:
        return None
    req = urllib.request.Request(f"https://lite-api.jup.ag/price/v3?ids={mint}", headers={"User-Agent": "redline/0.1 (+https://x.com/useredline)"})
    with urllib.request.urlopen(req, timeout=15) as r:   # Jupiter answers 403 to Python's default agent (probed 2026-09-18)
        data = json.load(r)
    px = (data.get(mint) or {}).get("usdPrice")
    return float(px) if px else None


def wallet_equity_usd(addr: str = AGENT, rpc: str = RPC) -> float:
    """Raises on any failure; the policy treats an exception as unreadable and refuses."""
    if not addr:
        raise RuntimeError("REDLINE_AGENT_WALLET not set")
    sol = sol_balance(addr, rpc)
    usdc = token_balance(addr, USDC_MINT, rpc)
    px = price_usd("SOL")
    if px is None:
        raise RuntimeError("SOL price unavailable")
    return sol * px + usdc
