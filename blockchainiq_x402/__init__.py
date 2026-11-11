"""BlockchainIQ x402 client + LangChain tool.

Pay-per-call crypto data from Blockchain IQ (https://www.blockchainiq.co),
paid in USDC on Base over the open x402 v2 protocol. No account, no API key:
a plain GET returns HTTP 402 with a PAYMENT-REQUIRED header, the client signs
a USDC (EIP-3009) authorization locally, retries with a PAYMENT-SIGNATURE
header, and the server settles gaslessly via the CDP facilitator.
"""

from .x402_client import (
    BlockchainIQClient,
    PaymentRequired,
    Settlement,
    decode_payment_required,
    select_base_accept,
    build_authorization,
    sign_authorization,
    build_payment_payload,
)
from .langchain_tool import BlockchainIQTool, create_blockchainiq_tool

__all__ = [
    "BlockchainIQClient",
    "PaymentRequired",
    "Settlement",
    "decode_payment_required",
    "select_base_accept",
    "build_authorization",
    "sign_authorization",
    "build_payment_payload",
    "BlockchainIQTool",
    "create_blockchainiq_tool",
]

__version__ = "0.1.0"
