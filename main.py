#!/usr/bin/env python3
"""
dhammarato-timestamps  —  main.py
==================================
Scrapes YouTube comments from the configured channel, extracts
timestamp links, and appends them to data/timestamps.csv.

Usage:
    python main.py
"""

import json
import csv
import re
import subprocess
import sys
import shutil
import os
from pathlib import Path
from datetime import datetime

from config import (
    CHANNEL_URL,
    MAX_TIMESTAMPS_PER_COMMENT,
    SLEEP_MIN,
    SLEEP_MAX,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_DIR   = Path("data")
CSV_FILE   = DATA_DIR / "timestamps.csv"
STATE_FILE = DATA_DIR / "processed_videos.json"
TEMP_DIR   = Path(".temp_json")          # gitignored; cleaned up after each run

CSV_FIELDS = [
    "Video ID",
    "Video Title",
    "Author",
    "Comment",
    "Timestamp",
    "Timestamp Link",
    "Date Added",
]

# Matches  1:23  /  01:23  /  1:23:45  /  01:23:45
TIMESTAMP_RE = re.compile(r'\b(\d{1,2}:\d{2}(?::\d{2})?)\b')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ts_to_seconds(ts: str) -> int:
    parts = list(map(int, ts.split(":")))
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def check_dependencies() -> None:
    if not shutil.which("yt-dlp"):
        sys.exit(
            "\n[ERROR] yt-dlp not found.\n"
            "Install it with:  pip install yt-dlp\n"
            "  or on Arch:     sudo pacman -S yt-dlp\n"
        )


def load_state() -> dict:
    """Returns {video_id: iso_timestamp_of_last_scrape}."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_existing_keys() -> set:
    """
    Returns a set of (video_id, author, link) tuples already present in the CSV.
    Used to avoid writing duplicate rows on re-runs.
    """
    keys = set()
    if not CSV_FILE.exists():
        return keys
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keys.add((row.get("Video ID", ""), row.get("Author", ""), row.get("Timestamp Link", "")))
    return keys


def append_rows(rows: list) -> None:
    """Appends rows to the CSV, writing the header only if the file is new/empty."""
    if not rows:
        return
    is_new = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# yt-dlp wrappers
# ---------------------------------------------------------------------------

def get_channel_videos() -> dict:
    """
    Returns {video_id: video_title} for every video on the channel.
    Uses --flat-playlist so it is very fast (no comment fetching yet).
    """
    print("  Fetching channel video list … (this takes ~10–30 s)")
    result = subprocess.run(
        [
            "yt-dlp",
            "--flat-playlist",
            "--print", "%(id)s|||%(title)s",
            "--no-warnings",
            CHANNEL_URL,
        ],
        capture_output=True,
        text=True,
    )
    videos = {}
    for line in result.stdout.strip().splitlines():
        if "|||" in line:
            vid_id, title = line.split("|||", 1)
            videos[vid_id.strip()] = title.strip()
    return videos


def fetch_comments_for_video(video_id: str) -> None:
    """Downloads the .info.json (with comments) for a single video into TEMP_DIR."""
    subprocess.run(
        [
            "yt-dlp",
            "--write-comments",
            "--write-info-json",
            "--skip-download",
            "--no-warnings",
            "--no-overwrites",
            "--min-sleep-interval", str(SLEEP_MIN),
            "--max-sleep-interval", str(SLEEP_MAX),
            "-o", str(TEMP_DIR / "%(id)s.%(ext)s"),
            f"https://www.youtube.com/watch?v={video_id}",
        ],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def extract_rows_from_video(
    video_id: str,
    title: str,
    existing_keys: set,
) -> list:
    """
    Reads the temp .info.json for a video, finds timestamp comments,
    and returns a list of new CSV row dicts.
    """
    json_file = TEMP_DIR / f"{video_id}.info.json"
    if not json_file.exists():
        return []

    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    rows = []

    for comment in data.get("comments", []):
        text    = comment.get("text", "")
        author  = comment.get("author", "Unknown")
        timestamps = TIMESTAMP_RE.findall(text)

        # Skip chapter-list comments (too many timestamps)
        if len(timestamps) > MAX_TIMESTAMPS_PER_COMMENT:
            continue

        if not timestamps:
            continue

        for ts in timestamps:
            link = f"https://youtu.be/{video_id}?t={ts_to_seconds(ts)}"
            key  = (video_id, author, link)

            if key in existing_keys:
                continue                   # already recorded

            existing_keys.add(key)         # prevent dupes within this run too
            rows.append(
                {
                    "Video ID":       video_id,
                    "Video Title":    title,
                    "Author":         author,
                    "Comment":        text,
                    "Timestamp":      ts,
                    "Timestamp Link": link,
                    "Date Added":     today,
                }
            )

    # Clean up temp file immediately to keep disk usage low
    json_file.unlink(missing_ok=True)
    return rows


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def pick_mode(new_count: int, total_count: int) -> str:
    print()
    print("=" * 52)
    print("  Dhammarato Timestamp Finder")
    print("=" * 52)
    print()
    print(f"  Channel videos found : {total_count}")
    print(f"  Not yet processed    : {new_count}")
    print()
    print("  [1]  Scan only NEW (unprocessed) videos")
    print("       Fast — skips anything already scraped.")
    print()
    print("  [2]  Scan ALL videos")
    print("       Slower — catches new comments on old videos.")
    print("       Duplicate entries are never written.")
    print()
    print("  [q]  Quit")
    print()
    choice = input("  Your choice: ").strip().lower()
    return choice


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    check_dependencies()

    DATA_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)

    all_videos  = get_channel_videos()
    state       = load_state()
    existing    = load_existing_keys()

    new_videos  = {vid: t for vid, t in all_videos.items() if vid not in state}

    choice = pick_mode(len(new_videos), len(all_videos))

    if choice == "q":
        print("\n  Bye!\n")
        return
    elif choice == "1":
        to_process = new_videos
        label = "new"
    elif choice == "2":
        to_process = all_videos
        label = "all"
    else:
        print("\n  Unknown choice — exiting.\n")
        return

    if not to_process:
        print("\n  Nothing to process — everything is already up to date.")
        print("  Try option [2] to re-scan all videos for new comments.\n")
        return

    print()
    print(f"  Scanning {len(to_process)} {label} video(s) …")
    print(f"  (yt-dlp will pause {SLEEP_MIN}–{SLEEP_MAX} s between requests)\n")

    total_new_rows = 0

    for i, (video_id, title) in enumerate(to_process.items(), 1):
        short_title = (title[:55] + "…") if len(title) > 55 else title
        print(f"  [{i:>4}/{len(to_process)}] {short_title}", end="", flush=True)

        fetch_comments_for_video(video_id)
        rows = extract_rows_from_video(video_id, title, existing)
        append_rows(rows)
        total_new_rows += len(rows)

        state[video_id] = datetime.now().isoformat()

        tag = f" → {len(rows)} timestamp(s)" if rows else ""
        print(tag)

    save_state(state)

    # Clean up temp directory
    try:
        TEMP_DIR.rmdir()       # only removes if empty
    except OSError:
        pass

    print()
    print("=" * 52)
    print(f"  Done!  {total_new_rows} new timestamp row(s) added.")
    print(f"  CSV: {CSV_FILE}")
    print()
    print("  Next steps:")
    print("    git add data/")
    print('    git commit -m "Update timestamps"')
    print("    git push")
    print("=" * 52)
    print()


if __name__ == "__main__":
    main()
