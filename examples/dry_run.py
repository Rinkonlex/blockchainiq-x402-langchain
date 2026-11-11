"""Dry run: exercise the full paid-call flow against production WITHOUT paying.

Steps performed (all read-only / local):
  1. GET the free catalogue (no payment).
  2. GET /brief -> HTTP 402; parse the real PAYMENT-REQUIRED header.
  3. Build + EIP-712-sign the USDC authorization with a THROWAWAY test key.
  4. Build the payment payload and print it (truncated).
  5. STOP — the retry is NOT sent, so no money moves.

Run:  python examples/dry_run.py
With a real funded wallet, add --live to actually send the retry and print
the settlement transaction hash (costs $0.01 USDC on Base):
  AGENT_PRIVATE_KEY=0x... python examples/dry_run.py --live
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from blockchainiq_x402.x402_client import (
    BlockchainIQClient,
    amount_usd,
    build_authorization,
    build_payment_payload,
    decode_payment_required,
    select_base_accept,
    sign_authorization,
)

# Hardhat account #0 — a public throwaway test key. NEVER fund it.
TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f3ff80"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="Actually send the paid retry ($0.01 USDC). Needs AGENT_PRIVATE_KEY.")
    args = parser.parse_args()

    client = BlockchainIQClient()
    catalog = client.catalog()
    print(f"catalog OK: {len(catalog['data'])} resources, source={catalog['source']}")

    # 1-2. Unpaid GET -> 402 with the real header.
    resp = requests.get(f"{client.base_url}/brief", timeout=30)
    print(f"GET /brief -> HTTP {resp.status_code}")
    assert resp.status_code == 402, "expected HTTP 402 for /brief"
    payment = decode_payment_required(resp.headers["payment-required"])
    accepted = select_base_accept(payment)
    print(f"402 offer: {accepted['scheme']}/{accepted['network']} "
          f"amount={accepted['amount']} (${amount_usd(accepted):.2f}) "
          f"payTo={accepted['payTo']}")

    # 3. Sign with the throwaway key (dry run) or the real key (--live).
    key = None
    if args.live:
        import os
        key = os.environ.get("AGENT_PRIVATE_KEY")
        if not key:
            print("ERROR: --live needs AGENT_PRIVATE_KEY in the environment.")
            return 2
    else:
        key = TEST_KEY
    payer = BlockchainIQClient(private_key=key).address
    extra = accepted.get("extra") or {}
    auth = build_authorization(accepted, payer)
    sig = sign_authorization(
        key, accepted["asset"], 8453, auth,
        token_name=extra.get("name", "USD Coin"),
        token_version=extra.get("version", "2"),
    )
    payload = build_payment_payload(payment, accepted, auth, sig)
    print(f"signed authorization: from={auth['from']} to={auth['to']} "
          f"value={auth['value']} validBefore={auth['validBefore']}")
    print(f"signature: {sig[:20]}...{sig[-8:]}")
    print(f"payment payload bytes: {len(json.dumps(payload))}")

    if not args.live:
        print("DRY RUN: retry NOT sent, no money moved. "
              "Re-run with --live + AGENT_PRIVATE_KEY to pay $0.01 and get the data.")
        return 0

    # Live path: the client does the retry and returns the settlement proof.
    live = BlockchainIQClient(private_key=key)
    data, settlement = live.brief()
    print("PAID CALL SUCCEEDED")
    print(f"settlement tx: {settlement.transaction_hash}")
    print(f"settlement network: {settlement.network}")
    print(f"data keys: {list(data.keys())[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
