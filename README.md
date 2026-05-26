# Dhammarato Timestamp Finder

A small tool that scrapes YouTube comments from the [@DhammaratoDhamma](https://www.youtube.com/@DhammaratoDhamma) channel, finds every comment that links to a specific moment in a video, and keeps them in a shared CSV that anyone with repo access can update and push.

---

## What it produces

`data/timestamps.csv` — one row per timestamp, with these columns:

| Column | Description |
|---|---|
| Video ID | YouTube video ID |
| Video Title | Full title of the video |
| Author | Name of the commenter |
| Comment | Full text of the comment |
| Timestamp | The timestamp as written (e.g. `14:32`) |
| Timestamp Link | Direct YouTube link to that exact moment |
| Date Added | When this row was added to the CSV |

**Chapter comments are automatically ignored.** Any comment containing more than 2 timestamps is treated as a chapter list and skipped. This keeps the CSV focused on moments that resonated with individual viewers.

**No duplicates are ever written.** Running the tool multiple times will only add rows that aren't already in the CSV.

---

## Requirements

- Python 3.9 or later
- That's it — the launcher scripts handle everything else automatically.

---

## Running it

### Linux / macOS

```bash
# First time only — make the script executable:
chmod +x run.sh

./run.sh
```

### Windows

Double-click `run.bat`, or run it from a Command Prompt.

### What happens

The script will:
1. Fetch the full video list from the channel (~10–30 seconds).
2. Ask you to choose a scan mode.
3. Work through the selected videos, pausing briefly between each to avoid rate-limiting.
4. Append any new timestamp rows to `data/timestamps.csv`.
5. Print a reminder to commit and push when done.

---

## Scan modes

**[1] New videos only**
Skips any video that has already been processed. Fast. Good for a routine weekly or monthly update.

**[2] All videos**
Re-scans every video on the channel. Slower, but catches new comments that have appeared on older videos since the last full run. Still safe to run at any time — duplicate rows are never written.

---

## Sharing your results

After running the tool, push the updated `data/` folder:

```bash
git add data/
git commit -m "Update timestamps — $(date +%Y-%m-%d)"
git push
```

Other contributors should `git pull` before running so they start from the latest state and don't duplicate work.

---

## Customisation

Open `config.py` to change:

| Setting | Default | Meaning |
|---|---|---|
| `CHANNEL_URL` | `@DhammaratoDhamma` | The channel to scrape |
| `MAX_TIMESTAMPS_PER_COMMENT` | `2` | Comments with more timestamps than this are treated as chapter lists and ignored |
| `SLEEP_MIN` / `SLEEP_MAX` | `2` / `7` | Random pause range (seconds) between video requests |

---

## If YouTube rate-limits you

You'll see errors like `This content isn't available, try again later`. This means YouTube has temporarily blocked your IP.

Options:
- **Wait ~1 hour**, then re-run. The `--no-overwrites` logic means you pick up exactly where you left off.
- **Switch to a VPN**, then re-run immediately.
- **Increase the sleep values** in `config.py` to be gentler on future runs.

---

## How this helps with Shorts

The `Timestamp Link` column gives you direct one-click access to every moment in your 2,000+ hour library that a viewer found significant enough to mark. Sort the CSV by video, filter by keyword in the comment text, or just browse — it turns 2,000 hours into a curated shortlist.
