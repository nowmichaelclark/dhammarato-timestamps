# ============================================================
#  config.py — Edit these settings if needed
# ============================================================

# The YouTube channel to scrape
CHANNEL_URL = "https://www.youtube.com/@DhammaratoDhamma/videos"

# Comments with MORE than this many timestamps are treated as
# chapter lists and ignored entirely.
MAX_TIMESTAMPS_PER_COMMENT = 2

# yt-dlp rate-limit protection: random pause between videos (seconds)
SLEEP_MIN = 2
SLEEP_MAX = 7

# ── Google Sheets sync (optional) ───────────────────────────────────────────
# Leave GOOGLE_SHEET_ID as an empty string to skip Sheets sync entirely.
# To enable: paste the ID from your sheet's URL between the quotes.
# URL looks like: https://docs.google.com/spreadsheets/d/SHEET_ID_HERE/edit
GOOGLE_SHEET_ID = "1O7yhYRbcvt63ZmpFeraWVfqXwHFNkz_m9dhAT3Wh9oo"

# Name of the tab inside the spreadsheet to write to
GOOGLE_SHEET_TAB = "Timestamps"
