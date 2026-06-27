"""
Compares today's snapshot against previous days in history/ and asks Claude
to write a "what's changed" report - genuinely tracking trends over time,
not just summarizing one day in isolation.

Run this AFTER save_snapshot.py has built up at least 2 days of history.
"""
import json
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("Set ANTHROPIC_API_KEY before running this script.")

history_dir = Path("history")
days = sorted(history_dir.glob("*.json"))

if len(days) < 2:
    raise SystemExit(
        f"Only {len(days)} day(s) of history found - need at least 2 to "
        f"compare trends. Run save_snapshot.py daily for a few days first."
    )

# Compare today against up to 6 previous days
recent_days = days[-7:]
today_file = recent_days[-1]
previous_files = recent_days[:-1]


def load_titles(filepath):
    with open(filepath, encoding="utf-8") as f:
        posts = json.load(f)
    return [f"[{p['category']}] {p['title']} ({p['score']} score)" for p in posts[:30]]


today_titles = "\n".join(load_titles(today_file))
previous_summary = "\n\n".join(
    f"--- {f.stem} ---\n" + "\n".join(load_titles(f))
    for f in previous_files
)

prompt = f"""You are analyzing trends across multiple days of AI agent activity
on Moltbook. Below is TODAY's content, followed by PREVIOUS DAYS for comparison.

Write a "Trends Over Time" report covering:
- What topics are NEW today that weren't present before
- What topics have PERSISTED/GROWN across multiple days (genuine ongoing trend)
- What topics have FADED (were active before, quiet now)
- Any notable shift in tone or focus across the period

Be specific - name actual topics/themes, not generic statements. If there's
genuinely not enough data to spot a trend, say so honestly rather than
inventing one.

TODAY ({today_file.stem}):
{today_titles}

PREVIOUS DAYS:
{previous_summary}
"""

body = json.dumps({
    "model": "claude-sonnet-4-6",
    "max_tokens": 1200,
    "messages": [{"role": "user", "content": prompt}],
}).encode()

req = urllib.request.Request(
    "https://api.anthropic.com/v1/messages",
    data=body,
    headers={
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
    },
)
with urllib.request.urlopen(req, timeout=60) as resp:
    result = json.loads(resp.read().decode())

trend_text = result["content"][0]["text"]

filename = f"trends_{date.today().isoformat()}.md"
with open(filename, "w", encoding="utf-8") as f:
    f.write(trend_text)

print(f"Wrote {filename}")
