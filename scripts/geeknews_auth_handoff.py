#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--vnc-password", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    start = json.loads(Path(args.start).read_text(encoding="utf-8"))
    pem_b64 = start.get("handoff_public_key_pem_b64")
    if not pem_b64:
        raise SystemExit("start.json is missing handoff_public_key_pem_b64")
    public_key = serialization.load_pem_public_key(base64.b64decode(pem_b64))
    payload = json.dumps(
        {
            "novnc_url": args.url.rstrip("/") + "/vnc.html?autoconnect=true&resize=remote",
            "vnc_password": args.vnc_password,
            "note": "Temporary GeekNews login browser. Session expires with the hosted runner.",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    ciphertext = public_key.encrypt(
        payload,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(base64.b64encode(ciphertext).decode("ascii") + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
