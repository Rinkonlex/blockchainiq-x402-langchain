// Run the OFFICIAL @x402/fetch client against the mock server and print the
// decoded payment payload it sends, so the Python implementation can be
// compared field-for-field. Uses Hardhat account #0 (throwaway test key).
import { privateKeyToAccount } from "viem/accounts";
import { wrapFetchWithPayment, x402Client, decodePaymentResponseHeader } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm/exact/client";

const account = privateKeyToAccount(
  "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f3ff80"
);

const client = x402Client.fromConfig({
  schemes: [{ network: "eip155:*", client: new ExactEvmScheme(account) }],
  spendControls: { maxAmountPerPayment: 0.6 },
});

const payFetch = wrapFetchWithPayment(fetch, client);
const res = await payFetch("http://127.0.0.1:18042/api/x402/v1/brief");
console.log("status:", res.status);
console.log("payment-response:", decodePaymentResponseHeader(res.headers.get("payment-response")));
console.log("body:", await res.text());
