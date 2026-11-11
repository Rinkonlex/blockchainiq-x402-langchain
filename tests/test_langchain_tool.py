"""Tests for the LangChain tool wrapper."""

import json

import pytest

from blockchainiq_x402 import create_blockchainiq_tool
from blockchainiq_x402.langchain_tool import RESOURCES


def test_tool_registers_resources():
    assert set(RESOURCES) == {"brief", "event-risk", "catalog", "sample"}
    assert RESOURCES["brief"]["price_usd"] == 0.01
    assert RESOURCES["event-risk"]["price_usd"] == 0.05


def test_tool_catalog_live_free():
    tool = create_blockchainiq_tool()
    out = json.loads(tool.invoke({"resource": "catalog"}))
    assert out["price_usd"] == 0.0
    assert out["settlement_tx"] is None
    assert out["data"]["source"] == "Blockchain IQ"


def test_tool_rejects_unknown_resource():
    tool = create_blockchainiq_tool()
    with pytest.raises(ValueError, match="unknown resource"):
        tool.invoke({"resource": "moon"})


def test_tool_paid_without_key_returns_clean_error():
    tool = create_blockchainiq_tool()
    out = json.loads(tool.invoke({"resource": "brief"}))
    assert "error" in out
    assert "private key" in out["error"]
