"""
A test "agent" that pays your SwarmSignal server and gets back data.

This simulates what a real paying customer-agent would do. Run this AFTER
server.py is running (in a separate terminal) and AFTER you've got free
testnet USDC/ETH in a test wallet.

This uses a throwaway test private key you generate yourself - NEVER use
a wallet that holds real funds for this script.
"""
import os

from eth_account import Account
from x402 import x402ClientConfig, SchemeRegistration
from x402.http.clients import wrapRequestsWithPaymentFromConfig
from x402.mechanisms.evm.exact import ExactEvmScheme
import requests

# ---------------------------------------------------------------------------
# Generate (or load) a throwaway test wallet
# ---------------------------------------------------------------------------
TEST_PRIVATE_KEY = os.environ.get("TEST_PRIVATE_KEY")

if not TEST_PRIVATE_KEY:
    # Generate a brand-new throwaway wallet for this test
    acct = Account.create()
    print("No TEST_PRIVATE_KEY set - generated a NEW throwaway test wallet.")
    print(f"  Address: {acct.address}")
    print(f"  Private key: {acct.key.hex()}")
    print("\n  Fund THIS address with free testnet USDC + ETH from a Base")
    print("  Sepolia faucet, then re-run with:")
    print(f'  export TEST_PRIVATE_KEY="{acct.key.hex()}"')
    print("\n  (This is a disposable test wallet. Never put real funds in it.)")
    raise SystemExit(0)

account = Account.from_key(TEST_PRIVATE_KEY)
print(f"Paying from test wallet: {account.address}")

# ---------------------------------------------------------------------------
# Configure the x402 client to auto-pay on Base Sepolia (testnet)
# ---------------------------------------------------------------------------
config = x402ClientConfig(
    schemes=[
        SchemeRegistration(
            network="eip155:84532",  # Base Sepolia testnet
            client=ExactEvmScheme(signer=account),
        ),
    ],
)

session = wrapRequestsWithPaymentFromConfig(requests.Session(), config)

# ---------------------------------------------------------------------------
# Make the actual paid request
# ---------------------------------------------------------------------------
SERVER_URL = os.environ.get("PULSE_SERVER_URL", "http://localhost:5000")
topic = "AI safety"

print(f"Requesting analysis for topic: '{topic}'...")
response = session.get(f"{SERVER_URL}/pulse", params={"topic": topic})

print(f"\nStatus: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 200:
    print("\nSUCCESS - the full pay-and-respond loop works.")
else:
    print("\nDid not succeed - check server logs and wallet funding.")
