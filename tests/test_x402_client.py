"""Unit + mocked-flow tests for the x402 client.

Uses the REAL captured PAYMENT-REQUIRED header from a live unpaid GET to
/api/x402/v1/brief (see fixtures/payment-required.b64, captured 2026-11-11)
so the 402 parsing is tested against production data, not a hand-made fake.
The paid round-trip is tested against a fake HTTP session (no money moves).
"""

import base64
import json
from pathlib import Path

import pytest

from blockchainiq_x402.x402_client import (
    BlockchainIQClient,
    X402Error,
    amount_usd,
    build_authorization,
    build_payment_payload,
    decode_payment_required,
    decode_payment_response,
    select_base_accept,
    sign_authorization,
)

FIXTURES = Path(__file__).parent / "fixtures"
TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f3ff80"  # Hardhat #0, throwaway
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
PAYTO = "0x617dA9383fbA67e86137BC4924b8b7E400fB7C9e"


def _real_402():
    return decode_payment_required(
        (FIXTURES / "payment-required.b64").read_text().strip()
    )


def test_decode_real_402_header():
    payment = _real_402()
    assert payment.x402_version == 2
    assert payment.resource["url"] == "https://www.blockchainiq.co/api/x402/v1/brief"
    assert len(payment.accepts) == 2


def test_select_base_accept_picks_exact_base():
    accepted = select_base_accept(_real_402())
    assert accepted["scheme"] == "exact"
    assert accepted["network"] == "eip155:8453"
    assert accepted["amount"] == "10000"
    assert accepted["asset"] == USDC_BASE
    assert accepted["payTo"] == PAYTO
    assert accepted["extra"] == {"name": "USD Coin", "version": "2"}


def test_brief_costs_one_cent():
    assert amount_usd(select_base_accept(_real_402())) == 0.01


def test_decode_payment_required_rejects_garbage():
    with pytest.raises(X402Error):
        decode_payment_required("not-base64!!!")


def test_select_base_accept_raises_without_base():
    payment = _real_402()
    payment.accepts = [a for a in payment.accepts if a["network"].startswith("solana")]
    with pytest.raises(X402Error, match="no exact/Base"):
        select_base_accept(payment)


def test_payment_payload_shape_matches_official_library():
    """Payload must have the same top-level shape @x402/fetch sends."""
    payment = _real_402()
    accepted = select_base_accept(payment)
    auth = build_authorization(
        accepted,
        "0x7f225583E3bCE24E0DEaA116EcFF1E552Cb74272",
        valid_before=1794405317,
        nonce=bytes.fromhex(
            "5e515af67c3abf76e8e4e654784e37b944c77cd3c6a29797e7a29d25e426246b"
        ),
    )
    sig = sign_authorization(
        TEST_KEY, USDC_BASE, 8453, auth, token_name="USD Coin", token_version="2"
    )
    payload = build_payment_payload(payment, accepted, auth, sig)
    assert payload["x402Version"] == 2
    assert payload["payload"]["authorization"]["from"] == auth["from"]
    assert payload["payload"]["authorization"]["value"] == "10000"
    assert payload["payload"]["signature"] == sig
    assert payload["accepted"] == accepted
    assert payload["resource"] == payment.resource
    # Header round-trips as base64 JSON.
    assert json.loads(base64.b64decode(base64.b64encode(json.dumps(payload).encode())))


def test_decode_payment_response():
    raw = {"success": True, "transaction": "0x" + "ab" * 32, "network": "eip155:8453", "payer": "0x1234"}
    header = base64.b64encode(json.dumps(raw).encode()).decode()
    s = decode_payment_response(header)
    assert s.transaction_hash == raw["transaction"]
    assert s.network == "eip155:8453"
    assert decode_payment_response(None) is None
    assert decode_payment_response("garbage") is None


class _FakeResponse:
    def __init__(self, status_code, headers=None, body=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body if body is not None else {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeSession:
    """First GET -> 402 with the real header; second GET (with payment) -> 200."""

    def __init__(self):
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        if len(self.calls) == 1:
            assert "payment-signature" not in (headers or {})
            return _FakeResponse(
                402,
                headers={"payment-required": (FIXTURES / "payment-required.b64").read_text().strip()},
                body={"error": "Payment required."},
            )
        # Paid retry: the payment-signature header must decode to a valid payload.
        payload = json.loads(base64.b64decode(headers["payment-signature"]))
        assert payload["x402Version"] == 2
        assert payload["payload"]["authorization"]["to"] == PAYTO
        assert payload["payload"]["authorization"]["value"] == "10000"
        tx = "0x" + "cd" * 32
        resp_header = base64.b64encode(
            json.dumps({"success": True, "transaction": tx, "network": "eip155:8453"}).encode()
        ).decode()
        return _FakeResponse(
            200,
            headers={"payment-response": resp_header},
            body={"data": {"asOf": "2026-11-11", "coins": []}},
        )


def test_paid_flow_end_to_end_mocked():
    session = _FakeSession()
    client = BlockchainIQClient(private_key=TEST_KEY, session=session)
    data, settlement = client.brief()
    assert data["data"]["asOf"] == "2026-11-11"
    assert settlement.transaction_hash == "0x" + "cd" * 32
    assert settlement.network == "eip155:8453"
    assert len(session.calls) == 2
    assert client.last_settlement.transaction_hash == settlement.transaction_hash


def test_spend_cap_refuses_expensive_call():
    session = _FakeSession()
    client = BlockchainIQClient(private_key=TEST_KEY, session=session, max_usd_per_call=0.005)
    with pytest.raises(X402Error, match="exceeds spend cap"):
        client.brief()
    assert len(session.calls) == 1  # only the 402 probe, no payment was signed/sent


def test_paid_call_requires_key():
    client = BlockchainIQClient(private_key=None)
    with pytest.raises(X402Error, match="private key is required"):
        client.brief()


def test_live_catalog_is_free_and_current():
    """Live check against production: the catalog needs no payment."""
    client = BlockchainIQClient()
    catalog = client.catalog()
    assert catalog["source"] == "Blockchain IQ"
    ids = {r["id"] for r in catalog["data"]}
    assert "brief" in ids and "event-risk" in ids
