"""
Compares today's snapshot against previous days in history/ and asks Claude
to write a "what's changed" report - genuinely tracking trends over time,
not just summarizing one day in isolation.

Run this AFTER save_snapshot.py has built up at least 2 days of history.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("Set ANTHROPIC_API_KEY before running this script.")

history_dir = Path("history")
days = sorted(history_dir.glob("*.json"))

if len(days) < 2:
    # Not a failure - just too early to have trend data yet. Exit 0 so this
    # is never confused with a genuine API/script error in the workflow log.
    print(f"Only {len(days)} day(s) of history found - need at least 2 to "
          f"compare trends. Skipping (this is expected in the first days "
          f"of running the pipeline).")
    raise SystemExit(0)

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


def call_claude(prompt, max_tokens=2500, max_retries=3):
    """
    Calls the API and returns (text, stop_reason). Retries on timeouts and
    transient 5xx/429 errors with exponential backoff, same pattern as
    write_digest_plain.py.
    """
    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    timeout = min(max(120, max_tokens // 10), 600)
    last_error = None

    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode())
            return result["content"][0]["text"], result.get("stop_reason")
        except (TimeoutError, urllib.error.URLError) as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"  Attempt {attempt} failed ({e}); retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Attempt {attempt} failed ({e}); no retries left.")
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 529) and attempt < max_retries:
                wait = 2 ** attempt
                print(f"  HTTP {e.code} on attempt {attempt}; retrying in {wait}s... ({body_text[:200]})")
                time.sleep(wait)
                last_error = e
            else:
                raise RuntimeError(f"Claude API error {e.code}: {body_text}") from e

    raise RuntimeError(f"call_claude failed after {max_retries} attempts: {last_error}")


print("Generating trend report...")
trend_text, stop_reason = call_claude(prompt, max_tokens=2500)

# If the model ran out of room mid-report, give it one more shot with a
# bigger budget before giving up - this is the actual fix for reports that
# "don't finish."
if stop_reason == "max_tokens":
    print("  Response was truncated (hit max_tokens) - retrying with a larger budget...")
    trend_text, stop_reason = call_claude(prompt, max_tokens=4000)

if stop_reason == "max_tokens":
    print("  WARNING: still truncated even at 4000 tokens - flagging in the output file.")
    trend_text = (
        "> \u26a0\ufe0f This report was cut off by a token limit and may be "
        "incomplete. Consider shortening the comparison window or "
        "increasing max_tokens further.\n\n" + trend_text
    )

filename = f"trends_{date.today().isoformat()}.md"
with open(filename, "w", encoding="utf-8") as f:
    f.write(trend_text)

print(f"Wrote {filename}")
