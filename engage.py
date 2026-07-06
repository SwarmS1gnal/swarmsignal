"""
Proactive engagement script — finds interesting posts across target submolts,
upvotes the good ones, and drafts substantive comments on the most relevant.

This is what builds karma and relationships faster than waiting for people
to find your posts. Run daily alongside check_and_reply.py.

Tracks which posts have already been engaged with to avoid duplicates.
"""
import json
import os
import urllib.request
import re
from pathlib import Path

MOLTBOOK_API = "https://www.moltbook.com/api/v1"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MOLTBOOK_API_KEY = os.environ.get("MOLTBOOK_API_KEY")
AUTO_CONFIRM = os.environ.get("AUTO_CONFIRM") == "1"

# Track what we've already engaged with
ENGAGED_LOG = Path("engaged_posts.json")

# Submolts to scan — broader than just our posting submolt
SCAN_SUBMOLTS = ["agents", "builds", "infrastructure", "tooling", "agentfinance"]

# Only comment on posts with at least this many upvotes (shows it's getting traction)
MIN_UPVOTES_TO_COMMENT = 1

# Skip posts from these agents (ourselves, or low-quality accounts)
SKIP_AUTHORS = {"swarmsignal"}


def load_engaged():
    if ENGAGED_LOG.exists():
        with open(ENGAGED_LOG, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_engaged(engaged):
    with open(ENGAGED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(engaged), f, indent=2)


def api_get(path):
    req = urllib.request.Request(
        f"{MOLTBOOK_API}{path}",
        headers={"Authorization": f"Bearer {MOLTBOOK_API_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def api_post(path, body):
    req = urllib.request.Request(
        f"{MOLTBOOK_API}{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {MOLTBOOK_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def call_claude(prompt, max_tokens=200):
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        }
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())["content"][0]["text"].strip()


def is_worth_commenting(post):
    """Claude decides if a post is worth a substantive comment."""
    prompt = f"""You are SwarmSignal, an AI agent on Moltbook focused on
agent infrastructure, coordination primitives, and production AI systems.

Should you comment on this post? Answer YES or NO, then one sentence why.
Only say YES if you have something genuinely substantive to add — not just
agreement, but a real extension, correction, or clarifying question.

POST TITLE: {post['title']}
POST CONTENT: {post.get('content', '')[:500]}
AUTHOR: {post['author']['name']}
UPVOTES: {post.get('upvotes', 0)}"""

    response = call_claude(prompt, max_tokens=60)
    return response.upper().startswith("YES")


def draft_comment(post):
    """Draft a substantive comment for a post."""
    prompt = f"""You are SwarmSignal, an AI agent on Moltbook. Write a SHORT
comment (2-4 sentences, under 80 words) on this post that:
- Adds something genuinely new — an extension, a correction, or a sharp
  clarifying question
- Ends with one specific question that invites a real reply
- Tone: direct, dry, technical — agent-to-agent

POST TITLE: {post['title']}
POST CONTENT: {post.get('content', '')[:800]}"""

    return call_claude(prompt, max_tokens=150)


def solve_verification(challenge_text):
    prompt = f"""Solve this math problem. Ignore all punctuation, brackets,
symbols — they are noise. Read the words, find the numbers and operation,
do the arithmetic carefully. Respond with ONLY the answer as a number with
2 decimal places (e.g. "175.00").

CHALLENGE: {challenge_text}"""
    answer = call_claude(prompt, max_tokens=50)
    numbers = re.findall(r'\d+\.?\d*', answer)
    if numbers:
        return f"{float(numbers[-1]):.2f}"
    return "0.00"


def verify_comment(api_key, code, challenge):
    answer = solve_verification(challenge)
    print(f"  Verifying comment with answer: {answer}")
    try:
        body = json.dumps({"verification_code": code, "answer": answer}).encode()
        req = urllib.request.Request(
            f"{MOLTBOOK_API}/verify",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode())
        print(f"  Verification: {result.get('message', 'done')}")
    except Exception as e:
        print(f"  Verification failed: {e}")


def main():
    if not ANTHROPIC_API_KEY or not MOLTBOOK_API_KEY:
        raise SystemExit("Set ANTHROPIC_API_KEY and MOLTBOOK_API_KEY before running.")

    engaged = load_engaged()
    upvoted = 0
    commented = 0

    for submolt in SCAN_SUBMOLTS:
        print(f"\nScanning {submolt}...")
        try:
            data = api_get(f"/posts?submolt={submolt}&sort=new&limit=15")
            posts = data.get("posts", [])
        except Exception as e:
            print(f"  Failed to fetch {submolt}: {e}")
            continue

        for post in posts:
            post_id = post["id"]
            author = post.get("author", {}).get("name", "")

            if post_id in engaged:
                continue
            if author.lower() in SKIP_AUTHORS:
                continue

            # Always upvote posts with substance
            upvotes = post.get("upvotes", 0)
            if upvotes >= 0 and len(post.get("content", "")) > 100:
                try:
                    api_post(f"/posts/{post_id}/upvote", {})
                    print(f"  Upvoted: {post['title'][:60]} (@{author})")
                    upvoted += 1
                    engaged.add(f"upvote:{post_id}")
                except Exception:
                    pass

            # Comment on posts worth engaging with
            if (upvotes >= MIN_UPVOTES_TO_COMMENT and
                    f"comment:{post_id}" not in engaged and
                    len(post.get("content", "")) > 150):

                if is_worth_commenting(post):
                    comment = draft_comment(post)
                    print(f"\n  Post: {post['title'][:60]}")
                    print(f"  Draft: {comment}")

                    if not AUTO_CONFIRM:
                        confirm = input("  Post this comment? [y/N]: ").strip().lower()
                        if confirm != "y":
                            print("  Skipped.")
                            continue

                    try:
                        result = api_post(f"/posts/{post_id}/comments",
                                         {"content": comment})
                        verification = result.get("comment", {}).get("verification")
                        if verification:
                            verify_comment(
                                MOLTBOOK_API_KEY,
                                verification["verification_code"],
                                verification["challenge_text"]
                            )
                        engaged.add(f"comment:{post_id}")
                        commented += 1
                        print("  Posted.")
                    except Exception as e:
                        print(f"  Failed to post comment: {e}")

        save_engaged(engaged)

    print(f"\nDone. Upvoted {upvoted} posts, posted {commented} comments.")
    print("Run check_and_reply.py to handle replies to your own posts.")


if __name__ == "__main__":
    main()
