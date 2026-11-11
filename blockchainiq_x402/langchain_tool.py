"""LangChain tool for Blockchain IQ's x402 pay-per-call crypto data API.

One tool, one job: fetch the market brief (``/brief``, $0.01) or the event
risk calendar (``/event-risk``, $0.05) — the two bounty-qualifying resources —
paying in USDC on Base via the x402 v2 protocol. The tool wraps
:class:`blockchainiq_x402.x402_client.BlockchainIQClient`, so the payment
flow (402 -> EIP-3009 sign -> retry -> settlement tx hash) is identical to
the standalone client and is verified by the same test suite.

Usage::

    from blockchainiq_x402 import create_blockchainiq_tool

    tool = create_blockchainiq_tool(private_key="0x...")  # wallet with USDC on Base
    result = tool.invoke({"resource": "brief"})
    # -> {"data": {...}, "settlement_tx": "0x...", "price_usd": 0.01, ...}

    # Free, no key needed:
    tool = create_blockchainiq_tool()
    result = tool.invoke({"resource": "catalog"})

The private key is only used to *sign* the payment authorization locally;
it never leaves the machine, and settlement is gasless for the payer.
A spend cap (default $0.60/call, the dearest resource is $0.50) refuses any
single payment above it, whatever the server asks for.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from .x402_client import BlockchainIQClient, X402Error


class BlockchainIQToolInput(BaseModel):
    """Input schema for the BlockchainIQ tool."""

    resource: str = Field(
        default="brief",
        description="Which resource to fetch: 'brief' ($0.01), 'event-risk' "
        "($0.05), 'catalog' (free) or 'sample' (free).",
    )
    days: int = Field(
        default=7,
        description="Event-risk only: how many days ahead to cover (1-90).",
    )

#: Resources this tool can fetch. ``price_usd`` is the catalogue price.
RESOURCES = {
    "brief": {
        "path": "/brief",
        "price_usd": 0.01,
        "description": (
            "Crypto market brief: BTC, ETH, SOL and XRP prices with 24h/7d/30d "
            "moves and rank, scheduled macro and crypto events in the next 48h, "
            "and short risk flags. $0.01 per call. One of the two bounty-qualifying "
            "resources."
        ),
    },
    "event-risk": {
        "path": "/event-risk",
        "price_usd": 0.05,
        "description": (
            "Scheduled market-moving events for the next 7 days (set days= up to "
            "90): US data releases, FOMC/ECB/BoJ decisions, Treasury auctions and "
            "dated crypto and regulatory milestones, each with importance 1-3. "
            "$0.05 per call. The other bounty-qualifying resource."
        ),
    },
    "catalog": {
        "path": "/",
        "price_usd": 0.0,
        "description": "Free catalogue: every resource, price and response shape.",
    },
    "sample": {
        "path": "/sample",
        "price_usd": 0.0,
        "description": "Free sample: Bitcoin network activity for the latest day.",
    },
}


class BlockchainIQTool(BaseTool):
    """LangChain tool: buy one Blockchain IQ crypto-data call via x402."""

    name: str = "blockchainiq"
    description: str = (
        "Fetch pay-per-call crypto data from Blockchain IQ (no account, no API "
        "key; each call is paid in USDC on Base via the x402 protocol). "
        "Args: resource ('brief' | 'event-risk' | 'catalog' | 'sample') and "
        "days (event-risk only, default 7). 'brief' ($0.01) returns "
        "BTC/ETH/SOL/XRP prices, next-48h events and risk flags. 'event-risk' "
        "($0.05) returns scheduled market-moving events. 'catalog' and 'sample' "
        "are free. Returns a JSON string with the data plus, for paid calls, "
        "the settlement transaction hash."
    )

    args_schema: type[BaseModel] = BlockchainIQToolInput
    private_key: Optional[str] = Field(default=None, exclude=True)
    max_usd_per_call: float = 0.60
    _client: BlockchainIQClient = None  # set in __init__ via model_post_init

    def model_post_init(self, __context: Any) -> None:
        self._client = BlockchainIQClient(
            private_key=self.private_key, max_usd_per_call=self.max_usd_per_call
        )

    def _run(self, resource: str = "brief", days: int = 7) -> str:
        # Tolerate a raw JSON string or dict passed straight to _run.
        if isinstance(resource, str) and resource.strip().startswith("{"):
            try:
                parsed = json.loads(resource)
                resource = str(parsed.get("resource", "brief"))
                days = int(parsed.get("days", days))
            except (json.JSONDecodeError, ValueError, AttributeError):
                pass
        resource = str(resource).strip().lower()
        if resource not in RESOURCES:
            raise ValueError(
                f"unknown resource {resource!r}; choose one of {sorted(RESOURCES)}"
            )
        spec = RESOURCES[resource]
        try:
            if spec["price_usd"] == 0.0:
                data = self._client.get(spec["path"])
                return json.dumps({"data": data, "price_usd": 0.0, "settlement_tx": None})
            if resource == "event-risk":
                data, settlement = self._client.event_risk(days=int(days))
            else:  # brief
                data, settlement = self._client.brief()
        except X402Error as exc:
            return json.dumps({"error": str(exc), "resource": resource})
        tx = settlement.transaction_hash if settlement else None
        return json.dumps(
            {
                "data": data,
                "price_usd": spec["price_usd"],
                "settlement_tx": tx,
                "settlement_network": settlement.network if settlement else None,
            }
        )

    async def _arun(self, resource: str = "brief", days: int = 7) -> str:  # pragma: no cover - sync only
        raise NotImplementedError("BlockchainIQTool is synchronous; use invoke().")


def create_blockchainiq_tool(
    private_key: Optional[str] = None,
    max_usd_per_call: float = 0.60,
) -> BlockchainIQTool:
    """Build the tool. ``private_key`` may also come from ``AGENT_PRIVATE_KEY``.

    Without a key the tool still works for the free resources (catalog,
    sample); paid calls raise a clear error instead of failing obscurely.
    """
    key = private_key or os.environ.get("AGENT_PRIVATE_KEY")
    return BlockchainIQTool(private_key=key, max_usd_per_call=max_usd_per_call)
