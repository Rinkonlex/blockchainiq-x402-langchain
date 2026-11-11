# Cross-check harness (development only)

Proves the Python EIP-3009 signer in `../blockchainiq_x402/` produces a
**byte-identical signature** to the official `@x402/fetch` 2.30.0 library
for the same authorization inputs.

How the reference was captured (2026-11-11):
1. `payment-required.b64` — the real `PAYMENT-REQUIRED` header from a live
   unpaid GET to https://www.blockchainiq.co/api/x402/v1/brief.
2. `mock-server.mjs` serves that exact header on first GET (HTTP 402), then
   captures the retry and answers 200 with a fake `PAYMENT-RESPONSE`.
3. `run-paid.mjs` runs the official `@x402/fetch` client (Hardhat account #0,
   a public throwaway test key) against the mock server.

Reproduce:
```bash
npm install @x402/fetch @x402/evm viem
node mock-server.mjs & sleep 1; node run-paid.mjs
```
Then compare the captured signature with the Python signer:
`tests/test_signature_crosscheck.py` (uses `tests/fixtures/x402_fetch_reference.json`,
extracted from the captured retry).
