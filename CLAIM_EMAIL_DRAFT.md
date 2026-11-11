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
> [TX HASH — run the paid call first; see README "Honest status"]
>
> Payout address (USDC on Base): [WALLET THAT MADE THE PAID CALL]
>
> Thanks,
> xlapt.ai

## Status of this draft

- Repo is built and tested locally (18/18 tests pass) but **not yet
  published** — `gh` is not logged in on this machine. Publish it (e.g.
  `git remote add origin <url> && git push -u origin main`) and paste the
  URL above.
- **No settlement tx hash exists yet.** The author's wallet holds 0 USDC on
  Base, so the live $0.01 paid call has not been made. Fund the calling
  wallet with $0.01 USDC on Base, run
  `AGENT_PRIVATE_KEY=0x... python examples/dry_run.py --live`, and paste
  the printed settlement transaction hash above. Settlement is gasless for
  the payer — only the $0.01 USDC is needed, no ETH.
- Do not send this email until the repo URL and the tx hash are filled in:
  the bounty requires both, and a failed claim goes to the back of the line.
