// Mock BlockchainIQ 402 server: serves the REAL captured Payment-Required header,
// captures the retry request headers, and returns a fake 200 + Payment-Response.
// Run: node mock-server.mjs  (writes captured.json, then exits after one paid retry)
import http from "node:http";
import fs from "node:fs";

const PAYMENT_REQUIRED = fs.readFileSync("payment-required.b64", "utf8").trim();

const server = http.createServer((req, res) => {
  const payment = req.headers["x-payment"] || req.headers["payment-signature"];
  if (!payment) {
    res.writeHead(402, {
      "Content-Type": "application/json",
      "Payment-Required": PAYMENT_REQUIRED,
    });
    res.end(JSON.stringify({ error: "Payment required." }));
    return;
  }
  // Paid retry: capture everything, then answer 200.
  const captured = {
    url: req.url,
    method: req.method,
    headers: req.headers,
  };
  fs.writeFileSync("captured.json", JSON.stringify(captured, null, 2));
  res.writeHead(200, {
    "Content-Type": "application/json",
    "Payment-Response": Buffer.from(JSON.stringify({
      success: true,
      transaction: "0x" + "ab".repeat(32),
      network: "eip155:8453",
      payer: "0x0000000000000000000000000000000000000000",
    })).toString("base64"),
  });
  res.end(JSON.stringify({ ok: true, mocked: true }));
  server.close();
});

server.listen(18042, () => console.log("mock listening on 18042"));
