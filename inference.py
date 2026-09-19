"""UsePod x402 client: buy one inference answer, pay for it on Solana, keep the receipt.

STATUS 2026-09-19: quote and payment are proven against the live API on mainnet. Settlement is
currently refused at UsePod's edge with a Cloudflare 403, but only when the referenced payment is
genuine; forged proofs reach the API and get ordinary 400s. Evidence and the ruled-out variables
are in probe/usepod-x402-settle-block-2026-09-19.md. Callers must handle SettleBlocked.

Envelope measured 2026-09-19, saved at probe/usepod-x402-quote-2026-09-19.json:
  POST /proxy/x402/v1/chat/completions with no payment -> 402 + `payment-required` header
  (base64 JSON). `accepts` offers three rails; we take the Solana one. The quote binds
  `body_hash`, so the retry must send byte-identical JSON, and it expires in 60 seconds.
No account and no API key: the wallet is the identity.
"""
from __future__ import annotations
import base64, json, os, subprocess
from pathlib import Path
from typing import Optional

ENDPOINT = os.environ.get("USEPOD_ENDPOINT", "https://api.usepod.ai/proxy/x402/v1/chat/completions")
KEYPAIR = os.environ.get("REDLINE_TAPE_KEYPAIR", str(Path.home() / ".config" / "solana" / "redline-tape.json"))
RPC = os.environ.get("REDLINE_RPC", "https://api.mainnet-beta.solana.com")
SOLANA_MAINNET = "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"
# Cloudflare in front of the API answers 403 (code 1010) to urllib's default agent. Measured 2026-09-19.
UA = "redline/0.1 (+https://github.com/Yonkoo11/redline)"


class SettleBlocked(RuntimeError):
    """Payment landed on chain; the completion could not be retrieved. Carries the receipt so the
    caller can record what was paid for and fall back to a local model."""

    def __init__(self, quote_id: str, payment_signature: str, paid_lamports: int):
        super().__init__(f"settle blocked at the edge after paying {paid_lamports} lamports "
                         f"(tx {payment_signature})")
        self.quote_id, self.payment_signature, self.paid_lamports = quote_id, payment_signature, paid_lamports


def _post(body: bytes, headers: dict) -> tuple[int, dict, bytes]:
    """Sent through curl: the API sits behind Cloudflare, which serves urllib a 403 challenge
    even with a user agent set. Measured 2026-09-19."""
    import tempfile
    hdr_file = tempfile.NamedTemporaryFile(delete=False)
    args = ["curl", "-s", "-D", hdr_file.name, "--max-time", "60", "-X", "POST", ENDPOINT,
            "-H", f"user-agent: {UA}", "-H", "content-type: application/json"]
    for k, v in headers.items():
        if k.lower() not in ("content-type", "user-agent"):
            args += ["-H", f"{k}: {v}"]
    args += ["--data-binary", "@-"]
    out = subprocess.run(args, input=body, capture_output=True, timeout=90)
    raw_headers = open(hdr_file.name, "rb").read().decode("utf-8", "replace")
    os.unlink(hdr_file.name)
    status = int(raw_headers.split()[1]) if raw_headers.split() else 0
    parsed = {}
    for line in raw_headers.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            parsed[k.strip().lower()] = v.strip()
    return status, parsed, out.stdout


def quote(body: bytes) -> dict:
    """Ask the price. Returns the decoded payment-required envelope."""
    status, headers, raw = _post(body, {"content-type": "application/json"})
    if status != 402:
        raise RuntimeError(f"expected 402, got {status}: {raw[:200]!r}")
    hdr = headers.get("payment-required")
    return json.loads(base64.b64decode(hdr + "=="))


def pick_solana_rail(env: dict, asset: str = "SOL") -> dict:
    for a in env["accepts"]:
        if a.get("network") == SOLANA_MAINNET and a.get("asset") == asset:
            return a
    raise RuntimeError(f"no {asset} rail on Solana in this quote")


def payer_pubkey() -> str:
    return subprocess.run(["solana-keygen", "pubkey", KEYPAIR], capture_output=True, text=True, check=True).stdout.strip()


def pay(rail: dict) -> str:
    """Transfer the quoted amount to the seller. `amount_microunits` is the asset's smallest
    unit: lamports for SOL (measured against the USDC rail, which prices the same call)."""
    lamports = int(rail["amount_microunits"])
    out = subprocess.run(
        ["solana", "transfer", rail["pay_to"], f"{lamports / 1e9:.9f}", "--allow-unfunded-recipient",   # never scientific notation: the CLI rejects it
         "--keypair", KEYPAIR, "--url", RPC, "--output", "json"],
        capture_output=True, text=True, timeout=90)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[-300:])
    return json.loads(out.stdout)["signature"]


def settle(body: bytes, rail: dict, signature: str) -> tuple[int, bytes]:
    proof = base64.b64encode(json.dumps({
        "quote_id": rail["quote_id"], "network": rail["network"], "asset": rail["asset"],
        "payer_wallet": payer_pubkey(), "signature": signature,
    }, separators=(",", ":")).encode()).decode()
    status, _, raw = _post(body, {"content-type": "application/json", "PAYMENT-SIGNATURE": proof})
    return status, raw


def ask(prompt: str, model: str = "gpt-4o-mini", max_tokens: int = 64) -> dict:
    """One paid answer. Returns {answer, model, paid_lamports, payment_signature, quote_id}."""
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}, separators=(",", ":")).encode()
    env = quote(body)
    rail = pick_solana_rail(env)
    sig = pay(rail)
    status, raw = settle(body, rail, sig)
    if status == 403 and b"Cloudflare" in raw:
        raise SettleBlocked(quote_id=rail["quote_id"], payment_signature=sig,
                            paid_lamports=int(rail["amount_microunits"]))
    if status != 200:
        raise RuntimeError(f"settle returned {status}: {raw[:300]!r}")
    data = json.loads(raw)
    return {"answer": data["choices"][0]["message"]["content"],
            "model": data.get("model", model),
            "paid_lamports": int(rail["amount_microunits"]),
            "payment_signature": sig,
            "quote_id": rail["quote_id"]}
