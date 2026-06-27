"""
Moltbook source. Fetches and normalizes posts into the common format used
by every source: {id, source, title, content, category, author, score,
comment_count, created_at, url}.

Adding a new platform later (ClawNews, OpenClawX, etc.) means creating a new
file in this folder that returns the same shape - nothing else needs to change.
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

BASE_URL = "https://www.moltbook.com/api/v1"

# Which communities to pull from. Locked in based on where useful-to-agents
# content concentrates (vs. noisier general-purpose submolts).
SUBMOLTS = ["agents", "tooling", "builds", "infrastructure", "agentfinance"]

MIN_UPVOTES = 0
LOOKBACK_HOURS = 72


def _headers():
    headers = {"User-Agent": "swarmsignal-digest/1.0"}
    api_key = os.environ.get("MOLTBOOK_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _is_recent(created_at_str, cutoff):
    created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    return created >= cutoff


def fetch():
    """Returns a list of posts in the common format, already filtered."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    results = []

    for submolt in SUBMOLTS:
        # Query each submolt directly using Moltbook's documented submolt
        # filter, now with proper auth - niche submolts never appear in the
        # global "top" feed (dominated by general/shitposts/etc), so this
        # targeted approach is required, not optional.
        url = f"{BASE_URL}/posts?submolt={submolt}&sort=new&limit=25"
        req = urllib.request.Request(url, headers=_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                posts = json.loads(resp.read().decode()).get("posts", [])
        except Exception as e:
            print(f"  [moltbook] [warn] {submolt} failed: {e}")
            continue

        kept = [
            p for p in posts
            if p.get("upvotes", 0) >= MIN_UPVOTES and _is_recent(p["created_at"], cutoff)
        ]
        print(f"  [moltbook] {submolt}: {len(kept)} qualifying posts (of {len(posts)} fetched)")
        results.extend(kept)

    # Normalize to the common format
    normalized = [
        {
            "id": f"moltbook:{p['id']}",
            "source": "moltbook",
            "title": p["title"],
            "content": p.get("content", "")[:1500],
            "category": p["submolt"]["display_name"],
            "author": p["author"]["name"],
            "score": p.get("upvotes", 0),
            "comment_count": p.get("comment_count", 0),
            "created_at": p["created_at"],
            "url": f"https://www.moltbook.com/post/{p['id']}",
        }
        for p in results
    ]
    return normalized
