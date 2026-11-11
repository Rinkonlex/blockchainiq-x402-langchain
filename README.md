# BlockchainIQ x402 — LangChain tool

A LangChain tool that buys pay-per-call crypto data from [Blockchain IQ](https://www.blockchainiq.co) (https://www.blockchainiq.co/api/x402/v1), paid in USDC on Base over the open **x402 v2** protocol. No account, no API key: a plain GET returns HTTP 402 with the price, the client signs a USDC authorization locally, retries, and the facilitator settles gaslessly.

Built for the [BlockchainIQ x402 bounties](https://www.blockchainiq.co/blog/x402-build-bounties) (LangChain slot; $525 total, first passing claim $150). One working paid call to `brief` ($0.01) or `event-risk` ($0.05) is enough to qualify.

## What it does

| Resource | Price | What you get |
| --- | --- | --- |
| `brief` | $0.01 | BTC/ETH/SOL/XRP prices (24h/7d/30d), next-48h macro & crypto events, risk flags |
| `event-risk` | $0.05 | Scheduled market-moving events, next 7 days by default (`days=` up to 90) |
| `catalog` | free | Every resource, price and response shape |
| `sample` | free | Bitcoin network activity for the latest day |

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# or: pip install -e .
```

Python 3.10+. No Node needed to use the tool (Node was only used during development to cross-check signatures against the official client — see `node-check/`).

## Use

```python
from blockchainiq_x402 import create_blockchainiq_tool

tool = create_blockchainiq_tool()  # reads AGENT_PRIVATE_KEY from the environment
print(tool.invoke({"resource": "catalog"}))          # free, no key needed
print(tool.invoke({"resource": "brief"}))            # $0.01, needs a funded key
print(tool.invoke({"resource": "event-risk", "days": 14}))  # $0.05
```

Or the standalone client:

```python
from blockchainiq_x402 import BlockchainIQClient

client = BlockchainIQClient(private_key="0x...")  # wallet with USDC on Base
data, settlement = client.brief()
print(data)
print("settlement tx:", settlement.transaction_hash)  # proof of payment
```

Use a dedicated wallet with a small balance, never a main wallet. Settlement is gasless for the payer — the wallet needs USDC on Base, not ETH. A spend cap (default $0.60/call; the dearest Blockchain IQ call is $0.50) refuses any single payment above it, whatever the server asks for.

## How the paid call works

1. Plain GET → HTTP 402 with a `Payment-Required` header (base64 JSON: price, asset, network, pay-to address).
2. The client picks the `exact` / `eip155:8453` (Base) entry — $0.01 is `10000` (USDC has 6 decimals).
3. It signs a USDC EIP-3009 `transferWithAuthorization` (EIP-712) locally. Domain: name/version from the offer (`"USD Coin"` / `"2"`), chainId 8453, verifyingContract = the USDC contract.
4. It retries the GET with a `payment-signature` header (base64 JSON: the authorization + signature, plus the offer's `extensions` / `resource` / `accepted` blocks, exactly as the official client does).
5. HTTP 200 with the data, plus a `payment-response` header carrying the settlement transaction hash.

## Verify it yourself (no key needed for the dry run)

```bash
python examples/dry_run.py
```

This hits the live API: fetches the free catalogue, GETs `/brief` (real HTTP 402), parses the real `PAYMENT-REQUIRED` header, builds and signs the authorization with a throwaway test key, and prints the payment payload — then stops. **No money moves.** To actually pay and see the settlement hash:

```bash
AGENT_PRIVATE_KEY=0x... python examples/dry_run.py --live   # costs $0.01 USDC on Base
```

## Tests

```bash
python -m pytest tests/ -v
```

18 tests, all passing. The strongest one is the signature cross-check: the Python EIP-3009 signer produces a **byte-identical signature** to the official `@x402/fetch` 2.30.0 library for the same authorization inputs (the reference was captured by running the official library against a mock server serving BlockchainIQ's real 402 header — see `node-check/` and `tests/fixtures/x402_fetch_reference.json`). The mocked end-to-end test also drives the full 402 → sign → retry → settlement flow against a fake session. Two tests hit the live free catalogue (no payment).

## Honest status: what was and was not tested with real money

- ✅ The EIP-3009 signature is byte-identical to the official `@x402/fetch` library's output for identical inputs.
- ✅ The full paid flow (402 parse → spend-cap check → sign → retry → settlement-header parse) is tested end-to-end against a mock server.
- ✅ Free endpoints (catalogue) are tested live against production.
- ✅ The 402 parsing uses BlockchainIQ's real, live `PAYMENT-REQUIRED` header.
- ✅ **The live $0.01 paid call HAS been executed (2026-11-11):** the `brief` resource was bought for $0.01 USDC on Base. Settlement tx `0x36a56a875f9eab3d8722d371bbf951842799b6daccb8dc331ca8982192f15599` (block 56078491, status success), payer `0xf5a2c0B6415665828f4f9F5C6a0b1017D8261915`, facilitator submitted the EIP-3009 authorization gaslessly. The payment was signed through the Binance Agentic Wallet's native x402 support (`baw x402-payment preview` + `sign`) rather than this repo's `--live` path, because the agentic wallet never exposes a raw private key — the authorization it signs is the same EIP-3009 authorization this client builds (and the Python signer is proven byte-identical to the official `@x402/fetch` library).

## Bounty claim

To claim: email `partnerships@blockchainiq.co` with this repository's link and the settlement transaction hash from a paid `brief` ($0.01) or `event-risk` ($0.05) call. First passing claim gets $150; the next three get $125 each. Round closes 31 December 2026, 11:59 PM Central.

## License

MIT.
