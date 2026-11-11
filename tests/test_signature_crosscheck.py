"""Cross-check: our EIP-3009 signing must be byte-identical to the official
@x402/fetch 2.30.0 library's output for the SAME authorization inputs.

The reference was produced by running the official library against a mock
server serving BlockchainIQ's real captured PAYMENT-REQUIRED header
(see ../node-check/: mock-server.mjs + run-paid.mjs, captured.json).
The fixture holds the library's authorization fields and signature, plus the
throwaway Hardhat test key it signed with.

If this test passes, our Python signer produces exactly the signature the
official client would produce — so a paid call built by this code will
settle on the facilitator's side exactly as the reference implementation's
would.
"""

import json
from pathlib import Path

from eth_account import Account

from blockchainiq_x402.x402_client import sign_authorization

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "x402_fetch_reference.json").read_text()
)


def test_signer_address_matches_library_from():
    """The test key must derive to the address the library signed as."""
    derived = Account.from_key(FIXTURE["private_key"]).address
    assert derived.lower() == FIXTURE["authorization"]["from"].lower()


def test_signature_matches_official_library_byte_for_byte():
    """Same authorization fields + same key => identical signature."""
    auth = FIXTURE["authorization"]
    authorization = {
        "from": auth["from"],
        "to": auth["to"],
        "value": int(auth["value"]),
        "validAfter": int(auth["validAfter"]),
        "validBefore": int(auth["validBefore"]),
        "nonce": bytes.fromhex(auth["nonce"].removeprefix("0x")),
    }
    mine = sign_authorization(
        FIXTURE["private_key"],
        FIXTURE["asset"],
        FIXTURE["chain_id"],
        authorization,
        token_name=FIXTURE["token_name"],
        token_version=FIXTURE["token_version"],
    )
    assert mine.lower() == FIXTURE["signature"].lower()


def test_signature_recovers_to_payer():
    """Independently: the signature must recover to the payer address."""
    auth = FIXTURE["authorization"]
    authorization = {
        "from": auth["from"],
        "to": auth["to"],
        "value": int(auth["value"]),
        "validAfter": int(auth["validAfter"]),
        "validBefore": int(auth["validBefore"]),
        "nonce": bytes.fromhex(auth["nonce"].removeprefix("0x")),
    }
    sig = sign_authorization(
        FIXTURE["private_key"],
        FIXTURE["asset"],
        FIXTURE["chain_id"],
        authorization,
        token_name=FIXTURE["token_name"],
        token_version=FIXTURE["token_version"],
    )
    # Recover via eth-account: re-encode the same typed data and recover.
    from eth_account.messages import encode_typed_data

    domain = {
        "name": FIXTURE["token_name"],
        "version": FIXTURE["token_version"],
        "chainId": FIXTURE["chain_id"],
        "verifyingContract": FIXTURE["asset"],
    }
    types = {
        "TransferWithAuthorization": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
        ],
    }
    signable = encode_typed_data(domain, types, authorization)
    recovered = Account.recover_message(signable, signature=sig)
    assert recovered.lower() == auth["from"].lower()
