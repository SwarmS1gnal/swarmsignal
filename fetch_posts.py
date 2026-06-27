"""
Combines posts from all configured sources into raw_posts.json, ready for
write_digest.py to summarize.

To add a new platform later:
  1. Create sources/<platform>.py with a fetch() function returning posts in
     the common format (see sources/moltbook.py for the shape + an example).
  2. Import it below and add it to ACTIVE_SOURCES.
That's the entire integration - no other file needs to change.
"""
import json

from sources import moltbook
# from sources import clawnews  # <- add once we confirm their API shape

ACTIVE_SOURCES = [
    moltbook,
    # clawnews,
]


def main():
    all_posts = []
    for source in ACTIVE_SOURCES:
        try:
            posts = source.fetch()
            all_posts.extend(posts)
        except Exception as e:
            print(f"  [warn] {source.__name__} failed: {e}")

    # Dedupe by id, sort by score (highest engagement first)
    seen = {p["id"]: p for p in all_posts}
    deduped = sorted(seen.values(), key=lambda p: p["score"], reverse=True)

    with open("raw_posts.json", "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=2)

    print(f"\nSaved {len(deduped)} posts from {len(ACTIVE_SOURCES)} source(s) to raw_posts.json")


if __name__ == "__main__":
    main()
