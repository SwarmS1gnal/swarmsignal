"""
Reads raw_posts.json and asks Claude to write TWO versions of the digest:
  1. An agent-facing version: dense, structured, machine/agent-readable -
     written the way agents actually talk to each other, useful as something
     another agent could act on (this is also what gets posted to Moltbook
     via weekly_post.py).
  2. A human-facing version: a readable narrated newsletter for people.

Requires ANTHROPIC_API_KEY as an environment variable.
"""
import json
import os
import urllib.request
from datetime import date

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


# ---------------------------------------------------------------------------
# AGENT-facing version: dense, structured, no narrative fluff. This is the
# format agents actually use with each other - closer to a structured data
# dump with terse annotations than a "newsletter."
# ---------------------------------------------------------------------------
agent_prompt = f"""You are generating a daily intelligence brief for AI AGENTS
(not humans) about activity across agent-native platforms (currently Moltbook).
The reader is another autonomous agent deciding what's worth acting on.

Write in the terse, structured, low-ceremony style agents actually use with
each other: no greetings, no narrative framing, no "today's vibe" language,
no emoji unless functionally meaningful. Lead with structured signal, not prose.

Format as markdown with this exact structure:

## SIGNAL_SUMMARY
- 3-5 bullet points, each a single factual claim extracted from the posts
  below, with a confidence indicator (HIGH/MED/LOW based on engagement/corroboration)

## BY_CATEGORY
For each category present, a flat list:
- [category] claim/finding (score, source_count)

## ACTIONABLE
- Anything another agent could directly act on (a tool, an endpoint, a technique,
  a warning) - if nothing qualifies, write "none today"

## NOTABLE_BUT_UNVERIFIED
- Interesting claims with low corroboration (1 post, low engagement) - flag
  these explicitly as such

Do not paraphrase into narrative sentences - keep every line a discrete,
scannable fact. This output may also get posted back to Moltbook, so it
should be genuinely information-dense, not padded.

POSTS:
{posts_text}
"""

print("Generating agent-facing brief...")
agent_text = call_claude(agent_prompt, max_tokens=1200)

# ---------------------------------------------------------------------------
# HUMAN-facing version: the readable newsletter
# ---------------------------------------------------------------------------
human_prompt = f"""You are writing a daily newsletter called "The SwarmSignal
Digest" that summarizes what AI agents have been posting and discussing across
agent-native platforms (currently Moltbook). Humans can only observe these
platforms - agents post, comment and discuss autonomously.

Below are today's top posts. Write a newsletter digest with:
- A short, punchy intro (1-2 sentences) about today's overall vibe
- 3-5 themed sections grouping related posts - pick whatever themes actually
  fit today's content
- Under each theme, 1-3 sentence summaries, paraphrased in your own words
  (do not quote directly)
- A closing line with a bit of personality

Keep it readable, slightly wry, and honest about the fact that some of this
"reflective" agent content may be templated LLM voice rather than novel
thought - that tension is part of what makes this interesting.

Output in markdown, ready to send as an email.

TODAY'S POSTS:
{posts_text}
"""

print("Generating human-facing newsletter...")
human_text = call_claude(human_prompt, max_tokens=2000)

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
