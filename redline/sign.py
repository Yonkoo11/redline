"""Sign a policy, or make the key that signs it.

    python -m redline.sign keygen  [path]                 make an operator key
    python -m redline.sign sign    <policy.json> [key]    sign a policy in place
    python -m redline.sign check   <policy.json>          verify against the pinned key

The key file is the same shape solana-keygen writes, so an existing Solana keypair works.
The private half never leaves this file and is never printed.
"""
from __future__ import annotations

import json
import os
import secrets
import stat
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from .signing import load_keypair, public_key_b58, sign_policy, verify_policy

DEFAULT_KEY = Path(
    os.environ.get("REDLINE_HOME", Path.home() / ".hermes" / "redline")
) / "operator-key.json"


def keygen(path: Path) -> str:
    if path.exists():
        raise SystemExit(f"refusing to overwrite an existing key at {path}")
    seed = secrets.token_bytes(32)
    private = Ed25519PrivateKey.from_private_bytes(seed)
    public = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(seed + public)))
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)          # owner read/write only
    return public_key_b58(private)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]

    if cmd == "keygen":
        path = Path(argv[2]) if len(argv) > 2 else DEFAULT_KEY
        pub = keygen(path)
        print(f"key written to {path} (owner-only)")
        print("\nBack this file up somewhere the agent cannot read, then pin the public half:\n")
        print(f'  export REDLINE_OPERATOR_PUBKEY="{pub}"\n')
        print("Lose the key and you can still change your limits: make a new key, re-sign, re-pin.")
        return 0

    if cmd == "sign":
        if len(argv) < 3:
            print("usage: python -m redline.sign sign <policy.json> [keypair.json]")
            return 2
        policy_path = Path(argv[2])
        key_path = Path(argv[3]) if len(argv) > 3 else DEFAULT_KEY
        if not key_path.exists():
            print(f"no key at {key_path}. Run:  python -m redline.sign keygen")
            return 1
        pub = sign_policy(policy_path, key_path)
        print(f"signed {policy_path}")
        print(f'pin this if you have not already:  export REDLINE_OPERATOR_PUBKEY="{pub}"')
        return 0

    if cmd == "check":
        if len(argv) < 3:
            print("usage: python -m redline.sign check <policy.json>")
            return 2
        policy = json.loads(Path(argv[2]).read_text())
        pinned = os.environ.get("REDLINE_OPERATOR_PUBKEY")
        ok, why = verify_policy(policy, pinned)
        print("verified: these are the limits the operator signed" if ok
              else f"NOT verified: {why}")
        return 0 if ok else 1

    if cmd == "pubkey":
        key_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_KEY
        print(public_key_b58(load_keypair(key_path)))
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
