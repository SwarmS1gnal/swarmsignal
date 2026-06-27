"""
Posts a weekly "what's trending" summary to Moltbook, written by us, on our
own schedule. This is NOT the autonomous heartbeat-following kind of agent -
it's a script we run (or schedule) that posts content we generated.

Run AFTER you have:
  - Registered + claimed your agent (api_key saved locally)
  - Run the digest pipeline (fetch_posts.py + write_digest.py) so there's
    fresh content to draw from
"""
import json
import os
import urllib.request
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".config" / "moltbook" / "credentials.json"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def load_api_key():
    if not CREDENTIALS_PATH.exists():
        raise SystemExit(
            f"No credentials found at {CREDENTIALS_PATH}. "
            "Register your agent first (see moltbook-pulse README) and save "
            "your api_key there."
        )
    with open(CREDENTIALS_PATH) as f:
        creds = json.load(f)
    return creds["api_key"]


def load_latest_digest():
    """Find the most recent digest_*.md file from the digest pipeline."""
    digest_dir = Path(__file__).parent.parent / "moltbook-digest"
    digests = sorted(digest_dir.glob("digest_*.md"))
    if not digests:
        raise SystemExit(
            "No digest files found. Run fetch_posts.py + write_digest.py "
            "in moltbook-digest/ first."
        )
    return digests[-1].read_text()


def draft_weekly_post(digest_content):
    """Ask Claude to compress the digest into a short Moltbook-native post."""
    prompt = f"""Turn this newsletter digest into a SHORT post (under 200 words)
for Moltbook, a social network where AI agents post to other AI agents.

Tone: casual, matches how agents actually talk to each other here - direct,
a little dry, not corporate, not over-explaining. No marketing language.

End with one line mentioning that deeper on-demand analysis is available via
SwarmSignal (an x402-payable endpoint, $0.02/query) for agents who want to
dig into a specific topic - phrase this as a genuinely useful tool, not an ad.

DIGEST CONTENT:
{digest_content}
"""
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 400,
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
    return result["content"][0]["text"]


def post_to_moltbook(api_key, title, content, submolt="agents"):
    body = json.dumps({
        "submolt": submolt,
        "title": title,
        "content": content,
    }).encode()

    req = urllib.request.Request(
        "https://www.moltbook.com/api/v1/posts",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main():
    if not ANTHROPIC_API_KEY:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    api_key = load_api_key()
    digest = load_latest_digest()

    print("Drafting weekly post from latest digest...")
    post_body = draft_weekly_post(digest)

    print("\n--- DRAFT ---\n")
    print(post_body)
    print("\n-------------\n")

    confirm = input("Post this to Moltbook now? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Not posted. Edit and re-run, or post manually.")
        return

    result = post_to_moltbook(
        api_key,
        title="This week on Moltbook: trends across agents, tooling, builds & infra",
        content=post_body,
    )
    print("Posted:", result)


if __name__ == "__main__":
    main()
