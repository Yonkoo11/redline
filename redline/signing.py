"""Operator signatures over the policy.

Why this exists: without it the policy is a plain file in a directory the agent's own process can
write. An agent able to run shell commands could raise its own ceiling and then trade inside it,
and every limit on the page would be decoration. Signing means the bytes that the engine enforces
are the bytes the operator approved.

What it does and does not buy you, stated plainly:

  it does  stop an agent that can write files from editing its own limits, because it cannot
           produce a signature without the operator's private key
  it does  make an altered policy fail closed rather than silently take effect
  it does not stop an operator who keeps the signing key on the same machine the agent can read.
           Keep the key somewhere the agent cannot reach, and back it up.

Format: Ed25519 over the canonical JSON of the policy with the `signature` field removed, keys
sorted, no spaces. Keys and signatures are base58, the same alphabet Solana uses, so an operator
can reuse a `solana-keygen` keypair file directly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = _B58[rem] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + (out or "1")


def b58decode(text: str) -> bytes:
    n = 0
    for ch in text:
        i = _B58.find(ch)
        if i < 0:
            raise ValueError(f"not base58: {ch!r}")
        n = n * 58 + i
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\0" * pad + body


def canonical_bytes(policy: dict) -> bytes:
    """The exact bytes that get signed. Any change to any limit changes these."""
    body = {k: v for k, v in policy.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()


def load_keypair(path: Path) -> Ed25519PrivateKey:
    """Read a solana-keygen keypair file: a JSON array of 64 bytes, seed first."""
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list) or len(raw) != 64:
        raise ValueError("expected a 64-byte solana-keygen keypair array")
    return Ed25519PrivateKey.from_private_bytes(bytes(raw[:32]))


def public_key_b58(private: Ed25519PrivateKey) -> str:
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return b58encode(
        private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )


def sign_policy(policy_path: Path, keypair_path: Path) -> str:
    """Sign a policy file in place. Returns the operator public key to pin."""
    policy = json.loads(Path(policy_path).read_text())
    private = load_keypair(keypair_path)
    policy["signature"] = b58encode(private.sign(canonical_bytes(policy)))
    Path(policy_path).write_text(json.dumps(policy, indent=1) + "\n")
    return public_key_b58(private)


def verify_policy(policy: dict, pubkey_b58: Optional[str]) -> Tuple[bool, str]:
    """Return (verified, why-not). Every failure path is a refusal, never a default."""
    if not pubkey_b58:
        return False, "no operator public key pinned (set REDLINE_OPERATOR_PUBKEY)"
    sig = policy.get("signature")
    if not sig:
        return False, "policy carries no signature"
    try:
        public = Ed25519PublicKey.from_public_bytes(b58decode(pubkey_b58))
    except Exception as exc:
        return False, f"pinned public key is unreadable: {exc}"
    try:
        public.verify(b58decode(sig), canonical_bytes(policy))
    except InvalidSignature:
        return False, "signature does not match these limits — the policy was altered"
    except Exception as exc:
        return False, f"signature unreadable: {exc}"
    return True, ""
