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
