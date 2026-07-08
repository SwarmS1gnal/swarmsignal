"""
Reads today's human-facing digest (digest_human_<date>.md, produced by
write_digest.py) and writes a plain-English version for people with no
background in AI, "agents," or Moltbook.

This script does NOT modify write_digest.py or its outputs -- it only
reads the human digest file it already wrote and produces a new,
separate file.

Requires ANTHROPIC_API_KEY as an environment variable.
Run this AFTER write_digest.py has produced today's digest_human_<date>.md.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("Set ANTHROPIC_API_KEY before running this script.")

today = date.today().isoformat()
human_filename = f"digest_human_{today}.md"

if not Path(human_filename).exists():
    raise SystemExit(
        f"{human_filename} not found. Run write_digest.py first to generate "
        f"today's human-facing digest."
    )

with open(human_filename, encoding="utf-8") as f:
    human_text = f.read()


def call_claude(prompt, max_tokens=2000, max_retries=3):
    """
    Call the Anthropic API with a timeout that scales with max_tokens
    (longer generations legitimately take longer), plus retry-with-backoff
    for transient timeouts / network hiccups / rate limits.
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
            return result["content"][0]["text"]
        except (TimeoutError, urllib.error.URLError) as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s, 8s...
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


# ---------------------------------------------------------------------------
# PLAIN-ENGLISH version: "explain like I've never heard of this" for people
# with zero context on AI agents, Moltbook, or SwarmSignal itself.
# ---------------------------------------------------------------------------
plain_prompt = f"""You are explaining today's SwarmSignal digest to someone
with NO background in AI, "agents," or Moltbook. Assume they've heard the
term "AI" on the news and that's about it.

Below is today's human-facing newsletter, written for an audience that
already knows this world. Your job is to translate its substance into
plain English for a total newcomer -- a parent, a neighbor, someone's
non-technical relative.

Rules:
- Before anything else, explain in 2-3 sentences what this whole project
  even is: AI programs ("agents") post and talk to each other on a
  platform, and this digest is a daily human write-up of what happened
  and why it might matter.
- No jargon without an immediate, concrete explanation the first time it's
  used (agent, prompt, token, claim-tracking, etc.) -- after that you can
  use the term normally.
- Use everyday comparisons where they genuinely help (e.g. compare an
  agent looping pointlessly to a person re-checking a locked door).
- Keep the actual opinions and skepticism from the newsletter -- don't
  flatten it into neutral mush. If the newsletter was skeptical of
  something, say so, just in simpler words.
- Skip anything too inside-baseball to matter to a newcomer; it's fine to
  cover fewer stories in more depth rather than everything shallowly.
- Structure: a short "What is this?" intro, then 3-5 short sections (no
  need to mirror the newsletter's structure exactly), then one closing
  sentence that sums up why today mattered, if it did.
- Aim for something a smart 12-year-old could follow. Short sentences.
  No paragraph longer than 4-5 sentences.

TODAY'S NEWSLETTER (for substance/opinions to translate -- do not just
reformat this, actually rewrite it in plain language):
{human_text}
"""

print("Generating plain-English explainer...")
plain_text = call_claude(plain_prompt, max_tokens=2000)

plain_filename = f"digest_plain_{today}.md"
with open(plain_filename, "w", encoding="utf-8") as f:
    f.write(plain_text)
print(f"Wrote {plain_filename}")
