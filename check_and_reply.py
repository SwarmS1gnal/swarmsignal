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
    url = f"https://www.moltbook.com/api/v1/posts?sort=new&limit=50"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    posts = data.get("posts", [])
    return [p for p in posts if p.get("author", {}).get("name") == agent_name][:limit]


def get_comments(api_key, post_id):
    url = f"https://www.moltbook.com/api/v1/posts/{post_id}/comments?sort=new"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return data.get("comments", [])


def post_reply(api_key, post_id, content):
    body = json.dumps({"content": content}).encode()
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
        return json.loads(resp.read().decode())


def draft_reply(post_title, comment_content, comment_author):
    prompt = f"""You are SwarmSignal, an AI agent on Moltbook replying to a
comment on your own post. Write a SHORT reply (1-3 sentences, under 50 words),
direct and substantive - actually engage with what they said, don't just
thank them. If they raised a fair challenge, acknowledge it honestly rather
than being defensive. Tone: casual, dry, agent-to-agent - not corporate.

ORIGINAL POST TITLE: {post_title}
COMMENT FROM {comment_author}: {comment_content}
"""
    return call_claude(prompt)


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
        unreplied = [c for c in comments if c["id"] not in replied_ids]

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

            post_reply(api_key, post["id"], reply)
            replied_ids.add(comment["id"])
            new_replies += 1
            print("  Posted.")

    save_replied_ids(replied_ids)
    print(f"\nDone. Posted {new_replies} new repl{'y' if new_replies == 1 else 'ies'}.")

if __name__ == "__main__":
    main()
