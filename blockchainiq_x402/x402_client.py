"""Minimal x402 v2 client for Blockchain IQ's paid API (Base / USDC).

Protocol (verified live against https://www.blockchainiq.co/api/x402/v1/brief
on 2026-11-11, and cross-checked against the official @x402/fetch 2.30.0
library — see tests/test_signature_crosscheck.py):

1. Plain GET -> HTTP 402 with a ``Payment-Required`` header: base64 JSON
   with ``x402Version`` 2, a ``resource`` block, an ``accepts`` list and an
   ``extensions`` block.
2. Pick the ``exact`` / ``eip155:8453`` (Base) entry. The price is in the
   smallest USDC unit (6 decimals): ``"10000"`` == $0.01.
3. Sign a USDC EIP-3009 ``transferWithAuthorization`` (EIP-712) locally.
   Domain: name/version from the accepts entry's ``extra``
   (``"USD Coin"`` / ``"2"``), chainId 8453, verifyingContract = the USDC
   address from the accepts entry.
4. Retry the GET with a ``payment-signature`` header: base64 JSON
   ``{"x402Version": 2, "payload": {"authorization": {...}, "signature": ...},
   "extensions": ..., "resource": ..., "accepted": ...}``.
   (The ``extensions`` / ``resource`` / ``accepted`` blocks are echoed from
   the 402 response, exactly as @x402/fetch does.)
5. HTTP 200 with the data, plus a ``payment-response`` header (base64 JSON)
   carrying the settlement transaction hash.

Settlement is gasless for the payer: the facilitator submits the
authorization on-chain. The payer only needs USDC on Base, no ETH.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from eth_account import Account
from eth_account.messages import encode_typed_data

BASE_URL = "https://www.blockchainiq.co/api/x402/v1"
BASE_CHAIN_ID = 8453
BASE_NETWORK = "eip155:8453"
PAYMENT_HEADER = "payment-signature"
PAYMENT_REQUIRED_HEADER = "payment-required"
PAYMENT_RESPONSE_HEADER = "payment-response"

# EIP-3009 transferWithAuthorization (Circle USDC).
_TRANSFER_TYPE = [
    {"name": "from", "type": "address"},
    {"name": "to", "type": "address"},
    {"name": "value", "type": "uint256"},
    {"name": "validAfter", "type": "uint256"},
    {"name": "validBefore", "type": "uint256"},
    {"name": "nonce", "type": "bytes32"},
]


class X402Error(Exception):
    """Raised for any x402 protocol or payment failure."""


@dataclass
class PaymentRequired:
    """A decoded PAYMENT-REQUIRED (HTTP 402) body."""

    raw: dict
    resource: dict = field(default_factory=dict)
    accepts: list = field(default_factory=list)
    extensions: dict = field(default_factory=dict)

    @property
    def x402_version(self) -> int:
        return int(self.raw.get("x402Version", 2))


@dataclass
class Settlement:
    """Proof of settlement from the PAYMENT-RESPONSE header."""

    transaction_hash: Optional[str]
    network: Optional[str]
    payer: Optional[str]
    raw: dict = field(default_factory=dict)


def _b64decode(data: str) -> dict:
    pad = "=" * (-len(data) % 4)
    return json.loads(base64.b64decode(data + pad))


def _b64encode(obj: Any) -> str:
    return base64.b64encode(json.dumps(obj).encode()).decode()


def decode_payment_required(header_value: str) -> PaymentRequired:
    """Decode a PAYMENT-REQUIRED header value into a PaymentRequired."""
    try:
        raw = _b64decode(header_value.strip())
    except Exception as exc:  # noqa: BLE001 - re-raised as X402Error
        raise X402Error(f"cannot decode PAYMENT-REQUIRED header: {exc}") from exc
    if not isinstance(raw, dict) or "accepts" not in raw:
        raise X402Error("PAYMENT-REQUIRED header is not a valid x402 v2 offer")
    return PaymentRequired(
        raw=raw,
        resource=raw.get("resource", {}),
        accepts=raw.get("accepts", []),
        extensions=raw.get("extensions", {}),
    )


def select_base_accept(payment: PaymentRequired) -> dict:
    """Pick the ``exact`` / Base (eip155:8453) entry from a 402 offer.

    Raises X402Error when no Base entry exists.
    """
    for entry in payment.accepts:
        if entry.get("scheme") == "exact" and entry.get("network") == BASE_NETWORK:
            return entry
    raise X402Error(
        "402 offer has no exact/Base (eip155:8453) payment entry; "
        f"offered networks: {[a.get('network') for a in payment.accepts]}"
    )


def amount_usd(entry: dict, decimals: int = 6) -> float:
    """Human USD amount of an accepts entry (USDC has 6 decimals)."""
    return int(entry["amount"]) / (10 ** decimals)


def build_authorization(
    accepted: dict,
    payer_address: str,
    *,
    valid_before: Optional[int] = None,
    nonce: Optional[bytes] = None,
) -> dict:
    """Build the EIP-3009 authorization fields for an accepts entry.

    ``valid_before`` defaults to now + the entry's ``maxTimeoutSeconds``
    (300 s for Blockchain IQ). ``nonce`` defaults to 32 fresh random bytes.
    """
    timeout = int(accepted.get("maxTimeoutSeconds") or 300)
    if valid_before is None:
        valid_before = int(time.time()) + timeout
    if nonce is None:
        nonce = secrets.token_bytes(32)
    return {
        "from": payer_address,
        "to": accepted["payTo"],
        "value": int(accepted["amount"]),
        "validAfter": 0,
        "validBefore": valid_before,
        "nonce": nonce,
    }


def sign_authorization(
    private_key: str,
    asset_address: str,
    chain_id: int,
    authorization: dict,
    token_name: str = "USD Coin",
    token_version: str = "2",
) -> str:
    """EIP-712 sign a USDC transferWithAuthorization. Returns 0x signature.

    The domain is the USDC token contract itself:
    name/version from the 402 offer's ``extra`` block, chainId, and
    verifyingContract = the USDC asset address.
    """
    domain = {
        "name": token_name,
        "version": token_version,
        "chainId": chain_id,
        "verifyingContract": asset_address,
    }
    message = {
        "from": authorization["from"],
        "to": authorization["to"],
        "value": authorization["value"],
        "validAfter": authorization["validAfter"],
        "validBefore": authorization["validBefore"],
        "nonce": authorization["nonce"],
    }
    # NOTE: eth-account's 3-arg encode_typed_data takes message_types WITHOUT
    # an EIP712Domain key (the domain goes in domain_data separately).
    types = {"TransferWithAuthorization": _TRANSFER_TYPE}
    signable = encode_typed_data(domain, types, message)
    signed = Account.sign_message(signable, private_key=private_key)
    return "0x" + signed.signature.hex()


def authorization_to_json(authorization: dict) -> dict:
    """Serialize an authorization for the payment payload (nonce as 0x hex)."""
    out = dict(authorization)
    nonce = out["nonce"]
    out["nonce"] = "0x" + (nonce.hex() if isinstance(nonce, (bytes, bytearray)) else str(nonce).replace("0x", ""))
    out["value"] = str(out["value"])
    out["validAfter"] = str(out["validAfter"])
    out["validBefore"] = str(out["validBefore"])
    return out


def build_payment_payload(
    payment: PaymentRequired,
    accepted: dict,
    authorization: dict,
    signature: str,
) -> dict:
    """Build the full x402 v2 payment payload (what goes in payment-signature).

    Mirrors @x402/fetch exactly: ``x402Version`` + ``payload`` (authorization
    + signature) + the 402's ``extensions`` and ``resource`` blocks + the
    chosen ``accepted`` entry.
    """
    return {
        "x402Version": payment.x402_version,
        "payload": {
            "authorization": authorization_to_json(authorization),
            "signature": signature,
        },
        "extensions": payment.extensions,
        "resource": payment.resource,
        "accepted": accepted,
    }


def decode_payment_response(header_value: Optional[str]) -> Optional[Settlement]:
    """Decode a PAYMENT-RESPONSE header into a Settlement (or None)."""
    if not header_value:
        return None
    try:
        raw = _b64decode(header_value.strip())
    except Exception:  # noqa: BLE001 - a bad header is not fatal
        return None
    if not isinstance(raw, dict):
        return None
    return Settlement(
        transaction_hash=raw.get("transaction"),
        network=raw.get("network"),
        payer=raw.get("payer"),
        raw=raw,
    )


class BlockchainIQClient:
    """Thin client for Blockchain IQ's x402 API.

    ``private_key`` is only used to *sign* the EIP-3009 authorization
    locally; it never leaves this machine. Free resources (catalog, sample)
    work with no key at all.
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        base_url: str = BASE_URL,
        max_usd_per_call: float = 0.60,
        session: Optional[requests.Session] = None,
        timeout: int = 30,
    ):
        self.private_key = private_key
        self.base_url = base_url.rstrip("/")
        self.max_usd_per_call = max_usd_per_call
        self.session = session or requests.Session()
        self.timeout = timeout
        self.last_settlement: Optional[Settlement] = None

    @property
    def address(self) -> Optional[str]:
        if not self.private_key:
            return None
        return Account.from_key(self.private_key).address

    # -- free resources (no payment, no key) --------------------------------
    def get(self, path: str, params: Optional[dict] = None) -> dict:
        """Plain GET against the API (free resources only)."""
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def catalog(self) -> dict:
        """The free catalogue: every resource, price and response shape."""
        return self.get("/")

    def sample(self) -> dict:
        """Free sample: Bitcoin network activity for the latest day."""
        return self.get("/sample")

    # -- paid resources ------------------------------------------------------
    def fetch_paid(
        self,
        path: str,
        params: Optional[dict] = None,
    ) -> tuple[dict, Settlement]:
        """GET a paid resource, paying via x402 when asked (HTTP 402).

        Returns ``(data, settlement)`` where ``settlement.transaction_hash``
        is the on-chain proof the facilitator settled the payment.
        Raises X402Error on any protocol/payment problem and never pays more
        than ``max_usd_per_call`` for a single call.
        """
        if not self.private_key:
            raise X402Error("a private key is required for paid calls")
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 402:
            resp.raise_for_status()
            raise X402Error(f"expected HTTP 402 for a paid resource, got {resp.status_code}")
        header = resp.headers.get(PAYMENT_REQUIRED_HEADER) or resp.headers.get("Payment-Required")
        if not header:
            raise X402Error("HTTP 402 without a PAYMENT-REQUIRED header")
        payment = decode_payment_required(header)
        accepted = select_base_accept(payment)
        price = amount_usd(accepted)
        if price > self.max_usd_per_call:
            raise X402Error(
                f"price ${price:.2f} exceeds spend cap ${self.max_usd_per_call:.2f}; refusing to pay"
            )
        extra = accepted.get("extra") or {}
        authorization = build_authorization(accepted, self.address)
        signature = sign_authorization(
            self.private_key,
            accepted["asset"],
            BASE_CHAIN_ID,
            authorization,
            token_name=extra.get("name", "USD Coin"),
            token_version=extra.get("version", "2"),
        )
        payload = build_payment_payload(payment, accepted, authorization, signature)
        paid = self.session.get(
            url,
            params=params,
            headers={PAYMENT_HEADER: _b64encode(payload)},
            timeout=self.timeout,
        )
        paid.raise_for_status()
        settlement = decode_payment_response(
            paid.headers.get(PAYMENT_RESPONSE_HEADER) or paid.headers.get("Payment-Response")
        )
        self.last_settlement = settlement
        return paid.json(), settlement

    # -- named paid resources -------------------------------------------------
    def brief(self) -> tuple[dict, Settlement]:
        """Market brief: BTC/ETH/SOL/XRP prices, next-48h events, risk flags.

        The cheapest paid call ($0.01) and one of the two bounty-qualifying
        resources.
        """
        return self.fetch_paid("/brief")

    def event_risk(self, days: int = 7) -> tuple[dict, Settlement]:
        """Scheduled macro/crypto event risk for the next ``days`` days ($0.05).

        The other bounty-qualifying resource.
        """
        return self.fetch_paid("/event-risk", params={"days": days})
