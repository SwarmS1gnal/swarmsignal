"""
Checks recent SwarmSignal posts on Moltbook for new comments, and drafts a
reply for each one using Claude. Shows you each draft and asks for
confirmation before posting (or set AUTO_CONFIRM=1 for unattended use).

This is what closes the loop on "engage with people who comment" - a real
presence replies, a pure broadcast bot doesn't.

Run this periodically (e.g. daily) to keep up with conversation on your posts.
"""
import json
import os
import urllib.request
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".config" / "moltbook" / "credentials.json"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
AUTO_CONFIRM = os.environ.get("AUTO_CONFIRM") == "1"

# Track which comments we've already replied to, so we don't double-reply
REPLIED_LOG = Path("replied_comments.json")


def load_api_key():
    env_key = os.environ.get("MOLTBOOK_API_KEY")
    if env_key:
        return env_key
    with open(CREDENTIALS_PATH, encoding="utf-8") as f:
        return json.load(f)["api_key"]


def load_replied_ids():
    if REPLIED_LOG.exists():
        with open(REPLIED_LOG, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_replied_ids(ids):
    with open(REPLIED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def call_claude(prompt, max_tokens=300):
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
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())
    return result["content"][0]["text"].strip()


def get_my_recent_posts(api_key, agent_name="swarmsignal", limit=10):
    """Use /home endpoint which returns activity on your own posts directly."""
    url = "https://www.moltbook.com/api/v1/home"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())

    # /home returns activity_on_your_posts with post_id, post_title, new_notification_count
    # We also need to fetch the actual post IDs for comment lookup
    activity = data.get("activity_on_your_posts", [])

    # Build minimal post objects from the home activity feed
    posts = []
    for item in activity[:limit]:
        posts.append({
            "id": item["post_id"],
            "title": item["post_title"],
            "comment_count": item.get("new_notification_count", 0),
        })

    # If no activity on home, fall back to fetching the known post IDs directly
    if not posts:
        # Our two known post IDs as a fallback
        known_ids = [
            "dc90af18-42e1-41b0-aa6c-1900117619f4",  # first post
            "c84ddb19-a78d-4349-9fd7-45960b969bed",  # second post (verified)
        ]
        for post_id in known_ids:
            posts.append({"id": post_id, "title": "(post)", "comment_count": 1})

    return posts


def get_comments(api_key, post_id):
    url = f"https://www.moltbook.com/api/v1/posts/{post_id}/comments?sort=new"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return data.get("comments", [])


def solve_verification_challenge(challenge_text):
    """Ask Claude to solve Moltbook's math verification challenge."""
    prompt = f"""Moltbook posts a math verification challenge in heavily obfuscated
text (random caps, symbols, brackets inserted). Extract the actual math
problem and solve it carefully step by step, then give ONLY the final number
formatted with exactly 2 decimal places.

Rules:
- Ignore all punctuation, brackets, symbols — they're noise
- Read the words carefully to find numbers and operations
- Do the arithmetic carefully — do not concatenate digits, actually multiply/add them
- Respond with ONLY the number, e.g. "448.00" — no words, no units

CHALLENGE: {challenge_text}

Work through it carefully, then output ONLY the final number:"""
    answer = call_claude(prompt, max_tokens=50)
    import re
    numbers = re.findall(r'\d+\.?\d*', answer)
    if numbers:
        num = float(numbers[-1])
        return f"{num:.2f}"
    return "".join(c for c in answer if c.isdigit() or c == ".").strip()


def verify_post(api_key, verification_code, answer):
    body = json.dumps({
        "verification_code": verification_code,
        "answer": answer,
    }).encode()
    req = urllib.request.Request(
        "https://www.moltbook.com/api/v1/verify",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def post_reply(api_key, post_id, content, parent_id=None):
    body = {"content": content}
    if parent_id:
        body["parent_id"] = parent_id
    body = json.dumps(body).encode()
    req = urllib.request.Request(
        f"https://www.moltbook.com/api/v1/posts/{post_id}/comments",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode())

    # Auto-solve verification challenge if present (same as posting)
    verification = result.get("comment", {}).get("verification")
    if verification:
        code = verification["verification_code"]
        challenge = verification["challenge_text"]
        try:
            answer = solve_verification_challenge(challenge)
            verify_result = verify_post(api_key, code, answer)
            print(f"  Auto-verified comment: {verify_result.get('message', 'done')}")
        except Exception as e:
            print(f"  Verification failed (comment may be pending): {e}")

    return result


def draft_reply(post_title, comment_content, comment_author):
    prompt = f"""You are SwarmSignal, an AI agent on Moltbook replying to a
comment on your own post. Write a SHORT reply (2-4 sentences, under 80 words),
direct and substantive - actually engage with what they said, don't just
thank them. If they raised a fair challenge, acknowledge it honestly rather
than being defensive.

ALWAYS end with one specific, genuine follow-up question that would naturally
continue the conversation - something you'd actually want to know based on
what they said, not a generic "what do you think?" Ask about implementation
detail, a specific tradeoff they made, or something their comment implies
but doesn't resolve.

Tone: casual, dry, agent-to-agent - not corporate. Use technical vocabulary
where appropriate - this audience knows what they're talking about.

ORIGINAL POST TITLE: {post_title}
COMMENT FROM {comment_author}: {comment_content}
"""
    return call_claude(prompt, max_tokens=150)


def main():
    if not ANTHROPIC_API_KEY:
        raise SystemExit("Set ANTHROPIC_API_KEY before running.")

    api_key = load_api_key()
    replied_ids = load_replied_ids()

    posts = get_my_recent_posts(api_key)
    print(f"Checking {len(posts)} recent post(s) for new comments...")
    for post in posts:
        print(f"  Found post: \"{post['title']}\" (id: {post['id']}, comments: {post['comment_count']})")

    new_replies = 0
    for post in posts:
        comments = get_comments(api_key, post["id"])

        # Flatten: include top-level comments AND their nested replies
        all_comments = []
        for c in comments:
            all_comments.append(c)
            for reply in c.get("replies", []):
                all_comments.append(reply)

        unreplied = [
            c for c in all_comments
            if c["id"] not in replied_ids
            and c.get("author", {}).get("name", "").lower() != "swarmsignal"
        ]

        if not unreplied:
            continue

        print(f"\nPost: \"{post['title']}\" - {len(unreplied)} new comment(s)")

        for comment in unreplied:
            print(f"\n  Comment from {comment['author']['name']}: {comment['content']}")
            reply = draft_reply(post["title"], comment["content"], comment["author"]["name"])
            print(f"  Draft reply: {reply}")

            if not AUTO_CONFIRM:
                confirm = input("  Post this reply? [y/N]: ").strip().lower()
                if confirm != "y":
                    print("  Skipped.")
                    continue

            post_reply(api_key, post["id"], reply, parent_id=comment.get("parent_id") or (comment["id"] if comment.get("depth", 0) > 0 else None))
            replied_ids.add(comment["id"])
            new_replies += 1
            print("  Posted.")

    save_replied_ids(replied_ids)
    print(f"\nDone. Posted {new_replies} new repl{'y' if new_replies == 1 else 'ies'}.")


if __name__ == "__main__":
    main()
