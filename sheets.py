import json
import logging
import os
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PRICES_SHEET = "prices"
SUBSCRIPTIONS_SHEET = "subscriptions"


def _get_client() -> gspread.Client:
    """Create authenticated gspread client from env JSON credentials."""
    creds_json = os.environ["GOOGLE_CREDS_JSON"]
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _open_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    return client.open_by_key(spreadsheet_id)


def _ensure_sheet(spreadsheet: gspread.Spreadsheet, title: str, headers: list[str]):
    """Get or create a worksheet with given headers."""
    try:
        sheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
        sheet.append_row(headers)
    return sheet


def save_prices(products: list[dict]):
    """Append a new price snapshot to the prices sheet."""
    spreadsheet = _open_spreadsheet()
    sheet = _ensure_sheet(
        spreadsheet,
        PRICES_SHEET,
        ["timestamp", "rank", "brand", "name", "price", "article", "url"],
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = [
        [now, i + 1, p["brand"], p["name"], p["price"], p["article"], p["url"]]
        for i, p in enumerate(products)
    ]
    sheet.append_rows(rows)
    logger.info(f"Saved {len(rows)} price rows to Google Sheets")


def get_last_prices() -> list[dict]:
    """Return the most recent price snapshot (last 5 rows by timestamp)."""
    spreadsheet = _open_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(PRICES_SHEET)
    except gspread.WorksheetNotFound:
        return []

    all_rows = sheet.get_all_records()
    if not all_rows:
        return []

    # Get the latest timestamp
    latest_ts = all_rows[-1]["timestamp"]
    return [r for r in all_rows if r["timestamp"] == latest_ts]


# ── Subscriptions ──────────────────────────────────────────────────────────────

def get_subscription(user_id: int) -> Optional[dict]:
    """Return subscription dict for user_id or None."""
    spreadsheet = _open_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(SUBSCRIPTIONS_SHEET)
    except gspread.WorksheetNotFound:
        return None

    records = sheet.get_all_records()
    for i, row in enumerate(records, start=2):  # row 1 = headers
        if str(row.get("user_id")) == str(user_id):
            return {"row": i, **row}
    return None


def set_subscription(user_id: int, threshold: int, direction: str):
    """
    Upsert a price alert for user_id.
    direction: 'below' — notify when price drops below threshold.
    """
    spreadsheet = _open_spreadsheet()
    sheet = _ensure_sheet(
        spreadsheet,
        SUBSCRIPTIONS_SHEET,
        ["user_id", "threshold", "direction", "active", "created_at"],
    )

    existing = get_subscription(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing:
        row_num = existing["row"]
        sheet.update(
            f"A{row_num}:E{row_num}",
            [[user_id, threshold, direction, True, now]],
        )
    else:
        sheet.append_row([user_id, threshold, direction, True, now])

    logger.info(f"Subscription set: user={user_id} {direction} {threshold}₽")


def remove_subscription(user_id: int):
    """Deactivate (soft-delete) a user's subscription."""
    spreadsheet = _open_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(SUBSCRIPTIONS_SHEET)
    except gspread.WorksheetNotFound:
        return

    existing = get_subscription(user_id)
    if existing:
        row_num = existing["row"]
        sheet.update_cell(row_num, 4, False)  # column 4 = active
        logger.info(f"Subscription removed for user={user_id}")


def get_active_subscriptions() -> list[dict]:
    """Return all active subscriptions."""
    spreadsheet = _open_spreadsheet()
    try:
        sheet = spreadsheet.worksheet(SUBSCRIPTIONS_SHEET)
    except gspread.WorksheetNotFound:
        return []

    records = sheet.get_all_records()
    return [r for r in records if str(r.get("active")).lower() in ("true", "1")]
