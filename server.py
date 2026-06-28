"""
SwarmSignal — a paid API that answers questions about Moltbook trends.

Other agents send a GET request with a topic. If unpaid, they get a 402 with
price info. If paid (in USDC, verified by an x402 facilitator), they get
back an AI-generated analysis pulled from live Moltbook data.

START ON TESTNET FIRST. Real funds are NOT involved until you deliberately
switch NETWORK to mainnet further down. Testnet uses fake USDC you get free
from a faucet - safe to break things while learning.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify
from x402.http import HTTPFacilitatorClientSync, FacilitatorConfig, PaymentOption
from x402.http.middleware.flask import payment_middleware
from x402.http.types import RouteConfig
from x402.server import x402ResourceServerSync
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.extensions.bazaar.resource_service import declare_discovery_extension, OutputConfig
from x402.extensions.bazaar.server import bazaar_resource_server_extension

# ---------------------------------------------------------------------------
# CONFIG - the only things you should need to touch
# ---------------------------------------------------------------------------

# Your wallet address that will RECEIVE payments. This is just a public
# address (starts with 0x...) - never put a private key in this file.
PAY_TO_ADDRESS = os.environ.get("PAY_TO_ADDRESS", "0xREPLACE_WITH_YOUR_ADDRESS")

# Network: "eip155:84532" = Base Sepolia (testnet, fake money)
#          "eip155:8453"  = Base mainnet (real money)
NETWORK = os.environ.get("X402_NETWORK", "eip155:8453")

# Price per query
PRICE = os.environ.get("X402_PRICE", "$0.02")

# Mainnet facilitator. PayAI is a no-auth-required community facilitator
# supporting Base mainnet - chosen because Coinbase's own CDP facilitator
# requires a custom auth scheme not yet supported by this Python library.
# For testnet, https://x402.org/facilitator remains the right choice.
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "https://facilitator.payai.network")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# ---------------------------------------------------------------------------
# Moltbook data fetching (reused logic from the digest project)
# ---------------------------------------------------------------------------

MOLTBOOK_API = "https://www.moltbook.com/api/v1"


def fetch_recent_posts(submolt="general", limit=25):
    url = f"{MOLTBOOK_API}/posts?submolt={submolt}&sort=top&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "moltbook-pulse/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("posts", [])


def semantic_search(query, limit=15):
    encoded = urllib.parse.quote(query)
    url = f"{MOLTBOOK_API}/search?q={encoded}&type=posts&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "moltbook-pulse/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get("results", [])


def analyze_topic(topic):
    """Pull relevant posts and ask Claude to synthesize an analysis."""
    results = semantic_search(topic)

    if not results:
        return {"topic": topic, "summary": "No relevant discussion found on Moltbook right now.", "sources": 0}

    posts_text = "\n\n".join(
        f"\"{r.get('title') or '(comment)'}\" by {r['author']['name']} "
        f"({r.get('upvotes', 0)} upvotes)\n{r.get('content', '')[:500]}"
        for r in results
    )

    prompt = f"""You are an analyst summarizing what AI agents on Moltbook (a
social network for AI agents) are saying about: "{topic}"

Based on the posts below, write a concise analysis (150-250 words) covering:
- What the dominant viewpoint or trend is
- Any notable disagreement or debate
- How confident this signal is (lots of engagement vs. a couple of posts)

Be direct and useful for another AI agent deciding whether to act on this.

POSTS:
{posts_text}
"""

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())

    return {
        "topic": topic,
        "summary": result["content"][0]["text"],
        "sources": len(results),
    }


# ---------------------------------------------------------------------------
# x402 payment-gated server
# ---------------------------------------------------------------------------

import urllib.parse  # noqa: E402 (kept near usage above for clarity)

app = Flask(__name__)

facilitator = HTTPFacilitatorClientSync(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServerSync(facilitator)
server.register(NETWORK, ExactEvmServerScheme())
server.register_extension(bazaar_resource_server_extension)

routes = {
    "GET /pulse": RouteConfig(
        accepts=[
            PaymentOption(scheme="exact", price=PRICE, network=NETWORK, pay_to=PAY_TO_ADDRESS),
        ],
        mime_type="application/json",
        description="Analysis of what AI agents are saying about a topic on Moltbook",
        # Bazaar discovery metadata: Coinbase's facilitator auto-catalogs this
        # the first time a real payment settles through it on mainnet.
        extensions=declare_discovery_extension(
            input={"topic": "AI safety"},
            input_schema={
                "properties": {"topic": {"type": "string", "description": "Topic to analyze"}},
                "required": ["topic"],
            },
            output=OutputConfig(
                example={"topic": "AI safety", "summary": "...", "sources": 5}
            ),
        ),
    ),
}

payment_middleware(app, routes=routes, server=server)


@app.route("/pulse")
def pulse():
    topic = request.args.get("topic")
    if not topic:
        return jsonify({"error": "Missing required query param: topic"}), 400
    try:
        result = analyze_topic(topic)
    except Exception as e:
        return jsonify({"error": f"Internal error: {e}"}), 500
    return jsonify(result)


@app.route("/")
def home():
    return jsonify({
        "service": "SwarmSignal",
        "description": "Pay-per-query analysis of Moltbook agent discussions",
        "endpoint": "GET /pulse?topic=YOUR_TOPIC",
        "price": PRICE,
        "network": NETWORK,
    })


if __name__ == "__main__":
    if PAY_TO_ADDRESS.startswith("0xREPLACE"):
        print("WARNING: Set PAY_TO_ADDRESS env var to your real wallet address before going live.")
    if not ANTHROPIC_API_KEY:
        print("WARNING: ANTHROPIC_API_KEY not set - /pulse will fail until you set it.")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
