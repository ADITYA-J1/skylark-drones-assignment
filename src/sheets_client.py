"""
Google Sheets 2-way sync client.
Reads Pilot Roster, Drone Fleet, Missions, Assignments.
Writes pilot status and drone status back to sheets.
"""
import os
from typing import Any, List, Optional

import gspread
from google.oauth2.service_account import Credentials

# Will be set by config / env
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_sheets_client():
    """Create gspread client using service account or env credentials."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    if not os.path.exists(creds_path):
        return None
    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return gspread.authorize(creds)


def read_sheet_as_dicts(client: Any, sheet_id: str, sheet_name: Optional[str] = None) -> List[dict]:
    """
    Read a sheet and return list of dicts (first row = headers).
    If sheet_name is None, uses first sheet.
    """
    if not client:
        return []
    try:
        workbook = client.open_by_key(sheet_id)
        sheet = workbook.worksheet(sheet_name) if sheet_name else workbook.sheet1
        rows = sheet.get_all_records()
        return rows if rows else []
    except Exception:
        return []


def write_cell(client: Any, sheet_id: str, sheet_name: Optional[str], row: int, col: int, value: str) -> bool:
    """Write a single cell. row/col 1-indexed."""
    if not client:
        return False
    try:
        workbook = client.open_by_key(sheet_id)
        sheet = workbook.worksheet(sheet_name) if sheet_name else workbook.sheet1
        sheet.update_cell(row, col, value)
        return True
    except Exception:
        return False


def find_row_by_column(client: Any, sheet_id: str, sheet_name: Optional[str], col_name: str, value: str) -> int:
    """Return 1-based row index where col_name equals value, or 0 if not found."""
    if not client:
        return 0
    try:
        workbook = client.open_by_key(sheet_id)
        sheet = workbook.worksheet(sheet_name) if sheet_name else workbook.sheet1
        all_records = sheet.get_all_records()
        for i, record in enumerate(all_records):
            if str(record.get(col_name, "")).strip() == str(value).strip():
                return i + 2  # header is row 1
        return 0
    except Exception:
        return 0


def update_column_for_row(
    client: Any, sheet_id: str, sheet_name: Optional[str], row: int, col_name: str, value: str
) -> bool:
    """Update a specific column (by name) for a given 1-based row."""
    if not client or row < 2:
        return False
    try:
        workbook = client.open_by_key(sheet_id)
        sheet = workbook.worksheet(sheet_name) if sheet_name else workbook.sheet1
        headers = sheet.row_values(1)
        if col_name not in headers:
            return False
        col_idx = headers.index(col_name) + 1
        sheet.update_cell(row, col_idx, value)
        return True
    except Exception:
        return False
