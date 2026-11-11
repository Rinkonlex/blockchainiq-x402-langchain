# Claim email — DRAFT (do NOT send yet)

**To:** partnerships@blockchainiq.co
**Subject:** BlockchainIQ x402 bounty claim — LangChain tool (brief, $0.01)

> Hi Jeremy,
>
> Claiming the LangChain slot of the x402 build bounties.
>
> Repository: [REPO URL — publish this repo to GitHub first, e.g.
> https://github.com/Rinkonlex/blockchainiq-x402-langchain]
>
> What it is: a LangChain tool (`BlockchainIQTool`) that buys Blockchain IQ
> data via x402 v2 on Base — plain GET, HTTP 402, local EIP-3009 USDC
> authorization, retry with the payment-signature header, settlement tx hash
> returned from the payment-response header. Spend-capped at $0.60/call.
> Resources: `brief` ($0.01), `event-risk` ($0.05), plus the free `catalog`
> and `sample`. MIT licensed.
>
> Verification: `python examples/dry_run.py` exercises the full flow against
> the live API without paying; `python examples/dry_run.py --live` (with
> AGENT_PRIVATE_KEY) makes the $0.01 brief call and prints the settlement
> hash. `python -m pytest tests/ -v` — 18 tests, including a signature
> cross-check proving the Python EIP-3009 signer is byte-identical to the
> official @x402/fetch library.
>
> Settlement transaction hash (paid `brief` call, $0.01 USDC on Base):
> 0x36a56a875f9eab3d8722d371bbf951842799b6daccb8dc331ca8982192f15599
> (Base, block 56078491, status success — verified on-chain; payer
> 0xf5a2c0B6415665828f4f9F5C6a0b1017D8261915, facilitator submitted the
> EIP-3009 authorization gaslessly)
>
> Payout address (USDC on Base):
> 0xf5a2c0B6415665828f4f9F5C6a0b1017D8261915
>
> Thanks,
> xlapt.ai

## Status of this draft

- Repo is built and tested locally (18/18 tests pass) but **not yet
  published** — `gh` is not logged in on this machine. Publish it (e.g.
  `git remote add origin <url> && git push -u origin main`) and paste the
  URL above.
- ✅ **Settlement tx hash EXISTS (2026-11-11 ~21:10 WIB).** The paid `brief`
  call was executed: 0.000024 ETH swapped to 0.049414 USDC on Base, then
  the $0.01 USDC payment was signed and settled via the Binance Agentic
  Wallet's native x402 support (`baw x402-payment preview` + `sign`) —
  the agentic wallet never exposes a raw private key, so the Python
  client's `--live` path (which needs `AGENT_PRIVATE_KEY`) was not used;
  the payment itself is the same EIP-3009 authorization the Python client
  builds. Settlement tx verified on-chain (status 1, block 56078491).
- Do not send this email until the repo URL is filled in: the bounty
  requires both the repo link and the tx hash, and a failed claim goes to
  the back of the line.
