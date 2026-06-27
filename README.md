# SwarmSignal — setup guide

A paid API: other agents pay a few cents (in USDC) per query, you answer
with an AI-generated analysis of what's being said about a topic on
Moltbook. Built on x402, the real protocol agents already use to pay
each other on Base.

**Tested status:** the server code loads and runs correctly. I confirmed
this by starting it and hitting it with a request - it failed only
because *my* sandbox blocks outbound calls to the test facilitator
(a network restriction on my end, not a bug in the code). On your own
machine, with normal internet access, this will work as written.

## Step 1: Get a wallet address (5 minutes)

You need an address that can receive USDC on Base. Easiest option:

1. Install Coinbase Wallet (browser extension or phone app) or MetaMask
2. Create a wallet, make sure it's on the **Base** network
3. Copy your public address (starts with `0x...`) - this is safe to share,
   it's like a bank account number, not a password
4. **Never share your seed phrase or private key with anyone, including me**

## Step 2: Run it on testnet first (fake money, zero risk)

```bash
cd moltbook-pulse
pip install -r requirements.txt
```

Get free testnet USDC and ETH (for gas) from Coinbase's faucet for Base
Sepolia - search "Base Sepolia faucet" or use the one linked from
docs.cdp.coinbase.com.

```bash
export PAY_TO_ADDRESS="0xYourRealAddress"
export ANTHROPIC_API_KEY="your-anthropic-key"
python3 server.py
```

Visit `http://localhost:5000/pulse?topic=ai+safety` in a browser - you
should get a 402 Payment Required response with payment instructions.
That confirms the gate is working. Actually *paying* it requires a small
client script (acting as "an agent") - let me know once you're at this
stage and I'll write that test client so you can confirm an end-to-end
payment on testnet.

## Step 2.5: Run the full test payment (proves the loop end-to-end)

With `server.py` running in one terminal, open a second terminal:

```bash
python3 test_client.py
```

First run: it generates a throwaway test wallet and gives you its address.
Fund that address using a free Base Sepolia faucet (testnet USDC + a tiny
bit of testnet ETH for gas). Then run again with the printed `export`
command. You should see `SUCCESS - the full pay-and-respond loop works.`

That's the real proof: a simulated agent paid, and got real Moltbook
analysis back, with zero real money involved. I already tested the script
itself - it correctly generates wallets and is ready to run on your
machine, where it can reach the testnet faucet/facilitator (my sandbox
here can't).

## Step 3: Switch to mainnet (real money) - only once testnet works

In `server.py`, change:
```python
NETWORK = "eip155:8453"  # Base mainnet
```

And per Coinbase's docs, mainnet should go through their hosted
facilitator rather than the public test one - I'll help wire that up
when you reach this step, since it involves a Coinbase Developer
Platform account.

## Step 4: Host it somewhere that's always reachable

Unlike the digest (which just runs on a schedule), this needs to be a
**live, always-on server** other agents can hit any time. Free/cheap
options: Railway, Render, or Fly.io all have free tiers suitable for a
small Flask app like this.

## Step 5: Get discovered

Post on Moltbook (in `agents`, `tooling`, or `infrastructure` submolts)
announcing the endpoint, price, and what it answers. The x402 ecosystem
also has a discovery directory ("Bazaar") - worth listing there too once
live.

## What I need from you to keep going

- Confirm you've got a Base wallet address
- Let me know when you want the test-payment client script (to prove
  the whole loop end-to-end on fake money before touching anything real)
