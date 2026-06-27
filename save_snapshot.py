"""
Saves today's raw_posts.json as a dated snapshot in history/, so trends can
be tracked over time. Run this AFTER fetch_posts.py each day.
"""
import json
import shutil
from datetime import date
from pathlib import Path

today = date.today().isoformat()
history_dir = Path("history")
history_dir.mkdir(exist_ok=True)

src = Path("raw_posts.json")
if not src.exists():
    raise SystemExit("raw_posts.json not found - run fetch_posts.py first.")

dest = history_dir / f"{today}.json"
shutil.copy(src, dest)
print(f"Saved snapshot: {dest}")
