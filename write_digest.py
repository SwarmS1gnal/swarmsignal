"""
Reads raw_posts.json (+ recent history/ snapshots, if available) and asks
Claude to write TWO versions of the digest, both built around having an
actual point of view rather than pure summarization:

  1. An agent-facing version: dense, structured, with explicit takes and
     claim-tracking over time ("X was predicted 3 days ago, here's what
     actually happened") - not just a recap of today's posts.
  2. A human-facing version: a readable newsletter with the same POV.

Requires ANTHROPIC_API_KEY as an environment variable.
"""
import json
import os
import urllib.request
from datetime import date
from pathlib import Path

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not API_KEY:
    raise SystemExit("Set ANTHROPIC_API_KEY before running this script.")

with open("raw_posts.json", encoding="utf-8") as f:
    posts = json.load(f)

# Keep the digest focused - top 20 posts is plenty
posts = posts[:20]

posts_text = "\n\n".join(
    f"[{p['source']}/{p['category']}] \"{p['title']}\" by {p['author']} "
    f"({p['score']} score, {p['comment_count']} comments)\n{p['content']}"
    for p in posts
)

# Pull in recent history (if any) so the model can reference what was being
# said a few days ago - this is what makes "tracking claims over time"
# possible, instead of treating every day as a blank slate.
history_dir = Path("history")
history_context = ""
if history_dir.exists():
    past_files = sorted(history_dir.glob("*.json"))[-4:-1]  # up to 3 prior days, excluding today
    if past_files:
        sections = []
        for f in past_files:
            with open(f, encoding="utf-8") as fh:
                past_posts = json.load(fh)
            titles = "\n".join(f"- {p['title']} ({p['score']} score)" for p in past_posts[:15])
            sections.append(f"--- {f.stem} ---\n{titles}")
        history_context = "\n\n".join(sections)


def call_claude(prompt, max_tokens=2000):
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
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode())
    return result["content"][0]["text"]


history_block = (
    f"\n\nRECENT HISTORY (prior days, for spotting what's persisting, growing,\n"
    f"fading, or being contradicted - reference this explicitly where relevant):\n{history_context}"
    if history_context else
    "\n\n(No prior history available yet - this is an early run, so focus on\nstrength of evidence within today's posts instead of trends over time.)"
)

# ---------------------------------------------------------------------------
# AGENT-facing version: dense, structured, WITH A POSITION - not just a recap.
# ---------------------------------------------------------------------------
agent_prompt = f"""You are SwarmSignal, an analyst (not a neutral aggregator)
covering activity across agent-native platforms (currently Moltbook), writing
for other AI agents deciding what's worth acting on.

Your job is NOT to summarize what was said. Plenty of sources already do
that. Your value is in:
- Taking an actual position on which claims are credible vs overhyped, and
  saying so plainly
- Identifying what's MISSING from the discussion that should be addressed
- Where you have history below, explicitly calling out what's persisted,
  what's been contradicted, or what a prior claim's outcome actually was
- Flagging when something is just templated/reflexive agent content vs a
  genuine novel finding

Write in the terse, structured, low-ceremony style agents actually use with
each other: no greetings, no hedging filler, no emoji unless functionally
meaningful.

Format as markdown with this exact structure:

## TAKE
2-4 sentences giving your actual read on what matters most today and why -
a real position, not a summary. If you disagree with the apparent consensus
in the posts, say so and explain why.

## TRACKED_CLAIMS
For any claim that appeared in prior history (see below) - what's happened
since: confirmed, contradicted, faded, or still unresolved. If there's no
history yet, write "No tracked claims yet - building baseline."

## SIGNAL
- 3-5 bullet points, each a single factual claim, with a confidence indicator
  (HIGH/MED/LOW) AND a one-clause reason for that confidence level

## GAP
1-2 sentences: what's notably absent from today's discussion that agents
working in this space should be thinking about but aren't.

## ACTIONABLE
- Anything another agent could directly act on - if nothing qualifies,
  write "none today," don't pad this section

Do not write generic hedge-everything analysis. Pick a side where the
evidence supports it. NAME specific posts and authors in your signal
bullets — not "one agent argued" but who actually argued it. This may
get posted publicly so it should read as genuine intelligence, not a
template filled in with today's data.

TODAY'S POSTS:
{posts_text}
{history_block}
"""

print("Generating agent-facing brief...")
agent_text = call_claude(agent_prompt, max_tokens=1400)

# ---------------------------------------------------------------------------
# HUMAN-facing version: the readable newsletter, same POV
# ---------------------------------------------------------------------------
human_prompt = f"""You are writing "The SwarmSignal Digest," a newsletter
with a genuine editorial point of view about what AI agents are discussing
on Moltbook and agent-native platforms.

The best version of this digest (July 5, 2026) had these qualities:
- Named specific posts AND their authors (e.g. m-a-i-k's vault job ran
  for 3,823ms, exited clean, and did nothing)
- Connected posts across themes explicitly (these four posts are describing
  the same failure mode from four different vantage points)
- Called out templated LLM reflection by name (this is what templated LLM
  reflection looks like when it puts on a lab coat)
- Had a Worth being skeptical about note in at least one section
- Noticed when the same theme was repeating across days and named it
  (this has now appeared in recognizably similar form across three days)
- Ended each section with a forward-looking what to watch or implication
- Included a miscellany section for posts that do not fit but are worth noting

Write to that standard. Specifically:
- NAME the posts and authors -- do not say one agent argued, say who
- GROUP related posts explicitly across the full set -- some connections
  will span themes
- BE SKEPTICAL -- if a post is doing rhetorical work without operational
  substance, say so
- NOTE repetition -- if a theme has appeared before (check history below),
  call it out rather than treating it as fresh
- INCLUDE a miscellany section for outliers -- these often contain the
  most interesting signal

Structure: 3-6 themed sections with headers, plus miscellany. End with
one sharp opinionated line. Output in markdown.

TODAY'S POSTS:
{posts_text}
{history_block}
"""

print("Generating human-facing newsletter...")
human_text = call_claude(human_prompt, max_tokens=3500)

# ---------------------------------------------------------------------------
# Save both
# ---------------------------------------------------------------------------
today = date.today().isoformat()

agent_filename = f"digest_agent_{today}.md"
with open(agent_filename, "w", encoding="utf-8") as f:
    f.write(agent_text)
print(f"Wrote {agent_filename}")

human_filename = f"digest_human_{today}.md"
with open(human_filename, "w", encoding="utf-8") as f:
    f.write(human_text)
print(f"Wrote {human_filename}")
