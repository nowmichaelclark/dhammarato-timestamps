#!/usr/bin/env python3
"""
sync_to_sheets.py
=================
Pushes data/timestamps.csv to a Google Sheet.

First-time setup:
    python sync_to_sheets.py --setup

Every run after that (also called automatically by main.py):
    python sync_to_sheets.py
"""

import csv
import sys
import json
import argparse
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    sys.exit(
        "\n[ERROR] Google libraries not found.\n"
        "They are installed automatically by run.bat / run.sh.\n"
        "Or install manually:  pip install google-api-python-client "
        "google-auth-httplib2 google-auth-oauthlib\n"
    )

from config import GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB

SCOPES         = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS    = Path("credentials.json")
TOKEN          = Path("token.json")
CSV_FILE       = Path("data/timestamps.csv")

HEADERS = [
    "Video ID", "Video Title", "Author",
    "Comment", "Timestamp", "Timestamp Link", "Date Added",
]

# Column index (0-based) of the Timestamp Link — will become a clickable formula
LINK_COL = HEADERS.index("Timestamp Link")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def get_service():
    creds = None

    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS.exists():
                sys.exit(
                    "\n[ERROR] credentials.json not found.\n"
                    "Run  python sync_to_sheets.py --setup  for instructions.\n"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN.write_text(creds.to_json())

    return build("sheets", "v4", credentials=creds)


# ---------------------------------------------------------------------------
# Sheet helpers
# ---------------------------------------------------------------------------

def ensure_tab_exists(service, sheet_id: str, tab_name: str) -> None:
    """Creates the tab if it doesn't already exist."""
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id, body=body
        ).execute()
        print(f"  Created tab: {tab_name}")


def format_sheet(service, sheet_id: str, tab_name: str, num_rows: int) -> None:
    """Freezes the header row, bolds it, and auto-resizes columns."""
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    tab_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == tab_name
    )

    requests = [
        # Freeze header row
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        # Bold header row
        {
            "repeatCell": {
                "range": {
                    "sheetId": tab_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        },
        # Auto-resize all columns
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": tab_id,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": len(HEADERS),
                }
            }
        },
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id, body={"requests": requests}
    ).execute()


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def read_csv() -> list[list]:
    """Returns all rows (including header) as a list of lists."""
    if not CSV_FILE.exists():
        sys.exit(f"[ERROR] {CSV_FILE} not found — run main.py first.")

    rows = []
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            rows.append(row)
    return rows


def build_values(rows: list[list]) -> list[list]:
    """
    Converts the raw CSV rows into the values to write to Sheets.
    The Timestamp Link column becomes a HYPERLINK formula so it's clickable.
    """
    out = []
    for i, row in enumerate(rows):
        if i == 0:
            out.append(row)   # header as-is
            continue

        new_row = list(row)
        if LINK_COL < len(row):
            url = row[LINK_COL]
            if url.startswith("http"):
                ts = row[HEADERS.index("Timestamp")] if HEADERS.index("Timestamp") < len(row) else ""
                label = f"▶ {ts}" if ts else "▶ Watch"
                new_row[LINK_COL] = f'=HYPERLINK("{url}","{label}")'
        out.append(new_row)
    return out


def sync():
    if not GOOGLE_SHEET_ID:
        print("  Google Sheets sync skipped (no GOOGLE_SHEET_ID in config.py).")
        return

    print("  Connecting to Google Sheets …")
    try:
        service = get_service()
    except Exception as e:
        print(f"  [WARNING] Could not authenticate with Google: {e}")
        print("  Skipping Sheets sync.")
        return

    rows   = read_csv()
    values = build_values(rows)

    try:
        ensure_tab_exists(service, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB)

        # Clear the tab and rewrite everything (clean approach; avoids stale rows)
        range_ref = f"'{GOOGLE_SHEET_TAB}'!A1"
        service.spreadsheets().values().clear(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_ref,
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_ref,
            valueInputOption="USER_ENTERED",   # lets HYPERLINK formulas evaluate
            body={"values": values},
        ).execute()

        format_sheet(service, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB, len(values))

        print(f"  Google Sheet updated: {len(values) - 1} rows written.")
        print(f"  https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit")

    except HttpError as e:
        print(f"  [WARNING] Google Sheets API error: {e}")
        print("  Skipping Sheets sync — your CSV and xlsx are still fine.")


# ---------------------------------------------------------------------------
# Setup guide
# ---------------------------------------------------------------------------

SETUP_GUIDE = """
==============================================================
  Google Sheets — First-Time Setup
==============================================================

You only need to do this once.

STEP 1: Create a Google Cloud project
  1. Go to https://console.cloud.google.com/
  2. Click "Select a project" at the top → "New Project"
  3. Name it anything (e.g. "Dhammarato Timestamps") → Create

STEP 2: Enable the Google Sheets API
  1. In the left menu: APIs & Services → Library
  2. Search "Google Sheets API" → click it → Enable

STEP 3: Create OAuth credentials
  1. APIs & Services → Credentials → Create Credentials
     → OAuth client ID
  2. If prompted, configure the consent screen:
     - User type: External → Create
     - App name: anything → Save and Continue through all steps
  3. Back at Create OAuth client ID:
     - Application type: Desktop app
     - Name: anything → Create
  4. Click "Download JSON" on the popup
  5. Rename the downloaded file to:  credentials.json
  6. Put it in this project folder (next to main.py)

STEP 4: Create your Google Sheet
  1. Go to https://sheets.google.com → create a blank sheet
  2. Name it "Dhammarato Timestamps" (or anything you like)
  3. Copy the ID from the URL:
       https://docs.google.com/spreadsheets/d/THIS_PART_HERE/edit
  4. Open config.py and paste it:
       GOOGLE_SHEET_ID = "THIS_PART_HERE"
  5. Share the sheet with anyone you want to be able to view it
     (Share → Anyone with the link → Viewer)

STEP 5: Authenticate
  Run this command:
    python sync_to_sheets.py

  A browser window will open asking you to sign in to Google
  and grant permission. Do that, then close the browser tab.
  A token.json file will be saved — future runs are automatic.

That's it! The sheet will now update every time you run main.py.
==============================================================
"""

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--setup", action="store_true",
        help="Print the first-time setup instructions"
    )
    args = parser.parse_args()

    if args.setup:
        print(SETUP_GUIDE)
    else:
        print("Syncing to Google Sheets …")
        sync()
        print("Done.")
