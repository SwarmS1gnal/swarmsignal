"""
Publishes digest files to Substack as draft posts for you to review and send.

Tracks which files have already been uploaded to prevent duplicates.
Safe to run any time, including with --backfill.

Setup:
  Set SUBSTACK_TOKEN to your connect.sid cookie value
  Set SUBSTACK_PUBLICATION_URL to your publication URL

Usage:
  python publish_to_substack.py              # publish latest digest only
  python publish_to_substack.py --backfill   # publish all not-yet-uploaded digests
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

SUBSTACK_TOKEN = os.environ.get("SUBSTACK_TOKEN")
PUBLICATION_URL = os.environ.get("SUBSTACK_PUBLICATION_URL", "swarms1gnal.substack.com")
BACKFILL = "--backfill" in sys.argv

# Track which files have already been uploaded
UPLOADED_LOG = Path("uploaded_to_substack.json")


def load_uploaded():
    if UPLOADED_LOG.exists():
        with open(UPLOADED_LOG, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_uploaded(uploaded):
    with open(UPLOADED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(uploaded), f, indent=2)


if not SUBSTACK_TOKEN:
    raise SystemExit(
        "Set SUBSTACK_TOKEN before running.\n"
        "Get it from: substack.com -> F12 -> Application -> Cookies -> connect.sid"
    )


def markdown_to_html(md_text):
    lines = md_text.split("\n")
    html = []
    in_list = False
    for line in lines:
        if line.startswith("## "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{line[2:]}</li>")
        elif line.strip() in ("", "---"):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append("<br>")
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            line = line.replace("**", "<strong>", 1).replace("**", "</strong>", 1)
            html.append(f"<p>{line}</p>")
    if in_list:
        html.append("</ul>")
    return "\n".join(html)


def publish_digest(filepath):
    content = filepath.read_text(encoding="utf-8")
    stem = filepath.stem
    parts = stem.split("_")
    date_str = parts[-1]
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%B %d, %Y")
    except ValueError:
        formatted_date = date_str

    title = f"SwarmSignal Digest — {formatted_date}"
    body_html = markdown_to_html(content)

    payload = json.dumps({
        "type": "newsletter",
        "title": title,
        "subtitle": "Daily intelligence from the agent internet",
        "body_html": body_html,
        "audience": "everyone",
        "draft": True,
    }).encode()

    req = urllib.request.Request(
        f"https://{PUBLICATION_URL}/api/v1/posts",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Cookie": f"connect.sid={SUBSTACK_TOKEN}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        post_id = result.get("id", "unknown")
        print(f"  ✓ Draft created: {title} (id: {post_id})")
        return True
    except urllib.error.HTTPError as e:
        print(f"  ✗ Failed {title}: HTTP {e.code} — {e.read().decode()[:200]}")
        return False


def main():
    here = Path(__file__).parent
    uploaded = load_uploaded()

    if BACKFILL:
        digests = sorted(here.glob("digest_human_*.md"))
        pending = [f for f in digests if f.name not in uploaded]
        print(f"Backfilling: {len(pending)} new digest(s) to upload ({len(digests) - len(pending)} already done)...")
        for f in pending:
            if publish_digest(f):
                uploaded.add(f.name)
                save_uploaded(uploaded)
    else:
        digests = sorted(here.glob("digest_human_*.md"))
        if not digests:
            raise SystemExit("No digest files found. Run write_digest.py first.")
        latest = digests[-1]
        if latest.name in uploaded:
            print(f"Already uploaded: {latest.name} — nothing to do.")
            return
        print(f"Publishing latest digest: {latest.name}")
        if publish_digest(latest):
            uploaded.add(latest.name)
            save_uploaded(uploaded)

    print(f"\nDone. Review drafts at: https://{PUBLICATION_URL}/publish/posts")


if __name__ == "__main__":
    main()
