"""Tape writer: every verdict becomes a signed record; refusals also become a Solana memo.
The memo transaction IS the signature: the tape wallet signs a self-transfer carrying the record hash.
Uses the solana CLI (installed here) so no extra Python dependencies are needed."""
from __future__ import annotations
import hashlib, json, os, subprocess, time
from pathlib import Path

TAPE_FILE = Path(os.environ.get("REDLINE_TAPE", Path.home() / ".hermes" / "redline" / "tape.jsonl"))
KEYPAIR = os.environ.get("REDLINE_TAPE_KEYPAIR", str(Path.home() / ".config" / "solana" / "redline-tape.json"))
RPC = os.environ.get("REDLINE_RPC", "https://api.mainnet-beta.solana.com")
MEMO_ON = {"refused": True, "allowed": False}   # only refusals go on-chain in V1


def record_hash(record: dict) -> str:
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


def tape_pubkey() -> str:
    return subprocess.run(["solana-keygen", "pubkey", KEYPAIR], capture_output=True, text=True, check=True).stdout.strip()


def post_memo(memo: str, rpc: str = RPC, keypair: str = KEYPAIR) -> str:
    """Self-transfer of 1 lamport carrying the memo. Returns the transaction signature."""
    out = subprocess.run(
        ["solana", "transfer", tape_pubkey(), "0.000000001", "--allow-unfunded-recipient",
         "--with-memo", memo, "--keypair", keypair, "--url", rpc, "--output", "json"],
        capture_output=True, text=True, timeout=90)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[-300:])
    return json.loads(out.stdout)["signature"]


def write(record: dict) -> dict:
    """Append to the local tape; post a memo for refusals. Never raises past the caller's guard."""
    rec = dict(record)
    rec["hash"] = record_hash(record)
    status = "allowed" if rec.get("allowed") else "refused"
    if MEMO_ON[status]:
        try:
            rec["memo_sig"] = post_memo(f"redline:{status}:{rec['hash'][:32]}")
        except Exception as e:      # the tape must never block the refusal itself
            rec["memo_error"] = str(e)[:200]
    rec["written_at"] = int(time.time())
    TAPE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TAPE_FILE.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec
