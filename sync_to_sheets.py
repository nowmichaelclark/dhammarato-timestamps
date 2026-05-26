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

SCOPES      = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS = Path("credentials.json")
TOKEN       = Path("token.json")
CSV_FILE    = Path("data/timestamps.csv")

# Edit this list to reorder, add, or remove columns in the sheet.
HEADERS = [
    "Timestamp Link", "Video Title", "Author",
    "Comment", "Timestamp", "Video ID", "Date Added",
]

LINK_KEY = "Timestamp Link"
TS_KEY   = "Timestamp"


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

def ensure_tab_exists(service, sheet_id, tab_name):
    meta     = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if tab_name not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": tab_name}}}]}
        service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
        print(f"  Created tab: {tab_name}")


def format_sheet(service, sheet_id, tab_name):
    meta   = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    tab_id = next(
        s["properties"]["sheetId"]
        for s in meta["sheets"]
        if s["properties"]["title"] == tab_name
    )
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": tab_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "bold": True,
                            "foregroundColor": {"red": 0.1, "green": 0.25, "blue": 0.1},
                        },
                        "backgroundColor": {"red": 0.56, "green": 0.78, "blue": 0.49},
                    }
                },
                "fields": "userEnteredFormat(textFormat,backgroundColor)",
            }
        },
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
# CSV reading — uses DictReader so column order in the file doesn't matter
# ---------------------------------------------------------------------------

def read_csv_as_dicts() -> list[dict]:
    if not CSV_FILE.exists():
        sys.exit(f"[ERROR] {CSV_FILE} not found — run main.py first.")
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_values(records: list[dict]) -> list[list]:
    """
    Reorders columns to match HEADERS and converts the Timestamp Link
    cell into a clickable HYPERLINK formula.
    """
    out = [HEADERS]  # header row first
    for record in records:
        row = []
        for key in HEADERS:
            val = record.get(key, "")
            if key == LINK_KEY and val.startswith("http"):
                ts    = record.get(TS_KEY, "")
                label = f"▶ {ts}" if ts else "▶ Watch"
                val   = f'=HYPERLINK("{val}","{label}")'
            row.append(val)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

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

    records = read_csv_as_dicts()
    values  = build_values(records)

    try:
        ensure_tab_exists(service, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB)

        range_ref = f"'{GOOGLE_SHEET_TAB}'!A1"
        service.spreadsheets().values().clear(
            spreadsheetId=GOOGLE_SHEET_ID, range=range_ref,
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=range_ref,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

        format_sheet(service, GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB)

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true",
                        help="Print the first-time setup instructions")
    args = parser.parse_args()
    if args.setup:
        print(SETUP_GUIDE)
    else:
        print("Syncing to Google Sheets …")
        sync()
        print("Done.")
