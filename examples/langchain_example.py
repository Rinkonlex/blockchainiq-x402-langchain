"""Minimal LangChain usage of the BlockchainIQ tool.

Free resources work with no key. Paid calls need AGENT_PRIVATE_KEY set to a
wallet holding USDC on Base (settlement is gasless for the payer).

    python examples/langchain_example.py            # free catalog, no key
    AGENT_PRIVATE_KEY=0x... python examples/langchain_example.py --paid
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blockchainiq_x402 import create_blockchainiq_tool


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paid", action="store_true",
                        help="Also make the $0.01 paid brief call (needs AGENT_PRIVATE_KEY).")
    args = parser.parse_args()

    tool = create_blockchainiq_tool()
    print("catalog:", tool.invoke({"resource": "catalog"})[:200], "...")

    if args.paid:
        if not os.environ.get("AGENT_PRIVATE_KEY"):
            raise SystemExit("ERROR: --paid needs AGENT_PRIVATE_KEY in the environment.")
        print("brief:", tool.invoke({"resource": "brief"})[:500])


if __name__ == "__main__":
    main()
