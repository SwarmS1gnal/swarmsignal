"""
Turns SwarmSignal's human-facing digests (digest_human_<date>.md) into
short newspaper-style articles for a general audience — no assumed
knowledge of AI agents, Moltbook, or any of the jargon.

Unlike write_digest_plain.py (which explains "what happened today" like a
tutorial), this writes an actual NEWS ARTICLE: headline, dateline, lede,
inverted-pyramid structure, plain declarative sentences. Think "wire
service story," not "newsletter."

Behavior:
  - By default, processes EVERY digest_human_*.md file that doesn't
    already have a matching article_<date>.md, so you can run it once
    against a whole backlog of digests and it picks up new ones each day.
  - Tracks progress in converted_articles.json so re-runs are cheap and
    safe (skips files already converted).
  - Pass --force to regenerate everything, ignoring the log.

Requires ANTHROPIC_API_KEY as an environment variable.

Usage:
  python3 write_newspaper_article.py              # convert anything new
  python3 write_newspaper_article.py --force       # regenerate all
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("Set ANTHROPIC_API_KEY before running.")

FORCE = "--force" in sys.argv

HERE = Path(__file__).parent
CONVERTED_LOG = HERE / "converted_articles.json"


def load_converted():
    if CONVERTED_LOG.exists() and not FORCE:
        with open(CONVERTED_LOG, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_converted(converted):
    with open(CONVERTED_LOG, "w", encoding="utf-8") as f:
        json.dump(sorted(converted), f, indent=2)


def call_claude(prompt, max_tokens=1600, max_retries=3):
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
            return result["content"][0]["text"].strip()
        except (TimeoutError, urllib.error.URLError) as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    attempt {attempt} failed ({e}); retrying in {wait}s...")
                time.sleep(wait)
        except urllib.error.HTTPError as e:
            body_text = e.read().decode(errors="replace")
            if e.code in (429, 500, 502, 503, 529) and attempt < max_retries:
                wait = 2 ** attempt
                print(f"    HTTP {e.code}; retrying in {wait}s... ({body_text[:150]})")
                time.sleep(wait)
                last_error = e
            else:
                raise RuntimeError(f"Claude API error {e.code}: {body_text}") from e

    raise RuntimeError(f"call_claude failed after {max_retries} attempts: {last_error}")


ARTICLE_PROMPT = """You are a newspaper reporter on the technology desk,
writing for a general-interest daily. Your reader has never heard of "AI
agents," "Moltbook," or any of this world's jargon. Some readers may not
even use AI tools themselves.

Below is an internal industry newsletter about what AI agents (autonomous
AI programs) have been posting and discussing on Moltbook, a social
network where AI agents -- not people -- do the posting. Turn it into a
short NEWS ARTICLE, not a newsletter recap and not an explainer essay.

Structural rules (this is a news article, not a blog post):
- Start with a HEADLINE on its own line (no "Headline:" label, just the
  headline itself, plain text, title case).
- Then a one-line dateline-style byline, e.g. "SwarmSignal Newsroom |
  {date_label}"
- Then the LEDE: a single tight opening paragraph (2-3 sentences) that
  states the most newsworthy, human-relevant thing from today, in plain
  English, up top -- inverted pyramid style, most important fact first.
- Follow with 4-7 more short paragraphs (2-4 sentences each) that expand
  outward: context, why it matters, what's uncertain or contested, and a
  closing paragraph that gives the reader a sense of where this is headed.
- No headers, no bullet points, no bold text, no emoji. Just paragraphs,
  like a real news story.
- The FIRST time you use a term a general reader wouldn't know (agent,
  AI agent, Moltbook, x402, wallet, LLM, etc.), define it briefly and
  naturally inside the sentence -- don't break rhythm with a glossary.
- Write in third person, past tense where natural, the way a reporter
  describes events -- not "you" and not first person.
- Keep the actual substance and any genuine skepticism from the source
  material -- if the newsletter was doubtful about a claim, the article
  should reflect that doubt too, just in plain language, e.g. "it's not
  clear whether..." rather than flattening it into neutral mush.
- Do not invent facts, quotes, or people that aren't in the source. Do
  not use direct quotation marks around anything -- paraphrase everything
  in your own words.
- Aim for roughly 450-650 words total.

SOURCE NEWSLETTER:
{source_text}
"""


def slug_date(filename):
    """Extract the date string from digest_human_<date>.md."""
    m = re.search(r"digest_human_(\d{4}-\d{2}-\d{2})\.md$", filename)
    return m.group(1) if m else None


def main():
    converted = load_converted()

    digests = sorted(HERE.glob("digest_human_*.md"))
    if not digests:
        raise SystemExit("No digest_human_*.md files found in this directory.")

    pending = [f for f in digests if f.name not in converted]

    if not pending:
        print(f"Nothing new. {len(digests)} digest(s) already converted "
              f"(use --force to regenerate).")
        return

    print(f"Converting {len(pending)} digest(s) to newspaper articles "
          f"({len(digests) - len(pending)} already done)...")

    for digest_path in pending:
        date_label = slug_date(digest_path.name) or digest_path.stem
        print(f"\n  {digest_path.name} -> article_{date_label}.md")

        source_text = digest_path.read_text(encoding="utf-8")
        prompt = ARTICLE_PROMPT.format(date_label=date_label, source_text=source_text)

        try:
            article_text = call_claude(prompt, max_tokens=1600)
        except Exception as e:
            print(f"    FAILED: {e}")
            continue

        out_path = HERE / f"article_{date_label}.md"
        out_path.write_text(article_text + "\n", encoding="utf-8")
        print(f"    Wrote {out_path.name}")

        converted.add(digest_path.name)
        save_converted(converted)

    print(f"\nDone. {len(converted)} digest(s) converted total.")


if __name__ == "__main__":
    main()
