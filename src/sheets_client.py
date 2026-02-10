"""
Google Sheets 2-way sync client.
Reads Pilot Roster, Drone Fleet, Missions, Assignments.
Writes pilot status and drone status back to sheets.
Explicit worksheet selection by name; normalized headers (strip, lowercase, spaces->underscore).
"""
import os
import re
from typing import Any, List, Optional

import gspread
from google.oauth2.service_account import Credentials

# Will be set by config / env
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _extract_sheet_id(value: str) -> str:
    """Extract sheet ID from URL or return as-is if already an ID."""
    if not value or not value.strip():
        return ""
    value = value.strip()
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)
    return value


def normalize_header(header: str) -> str:
    """Strip and normalize header for consistent key lookup: lowercase, spaces -> underscore."""
    if header is None:
        return ""
    s = str(header).strip()
    s = re.sub(r"\s+", "_", s).lower()
    return s


def get_sheets_client():
    """Create gspread client using service account. Returns None if no credentials file."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    if not creds_path or not os.path.exists(creds_path):
        return None
    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None


def read_sheet_as_dicts(
    client: Any,
    sheet_id: str,
    sheet_name: Optional[str] = None,
    *,
    _log_headers: bool = False,
) -> List[dict]:
    """
    Read a sheet by ID and optional worksheet name. Returns list of dicts with normalized keys.
    - Explicitly opens spreadsheet by ID.
    - If sheet_name is provided, selects that worksheet by name; else first worksheet.
    - Headers are normalized: strip, lowercase, spaces -> underscore. Extra columns and order are OK.
    - Fails loudly if sheet/tab not found.
    """
    if not client or not sheet_id:
        return []
    sid = _extract_sheet_id(sheet_id)
    if not sid:
        return []
    try:
        workbook = client.open_by_key(sid)
        if sheet_name:
            try:
                sheet = workbook.worksheet(sheet_name)
            except Exception as e:
                raise RuntimeError(
                    f"Worksheet not found: sheet_id={sid!r}, worksheet_name={sheet_name!r}. "
                    f"Check SHEET_NAME_* matches the tab name exactly. Original: {e}"
                ) from e
        else:
            sheet = workbook.sheet1
        raw_headers = sheet.row_values(1)
        if not raw_headers:
            return []
        headers_normalized = [normalize_header(h) for h in raw_headers]
        if _log_headers:
            print(f"  [Sheets] Detected headers (raw): {raw_headers}")
            print(f"  [Sheets] Normalized keys: {headers_normalized}")
        all_values = sheet.get_all_values()
        if len(all_values) < 2:
            return []
        records = []
        for row in all_values[1:]:
            row_padded = row + [""] * (len(headers_normalized) - len(row))
            record = {}
            for i, key in enumerate(headers_normalized):
                if i < len(row_padded):
                    val = row_padded[i]
                    record[key] = val.strip() if isinstance(val, str) else val
                else:
                    record[key] = ""
            records.append(record)
        return records
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Google Sheets read failed: sheet_id={sid!r}, worksheet_name={sheet_name!r}. {e}"
        ) from e


def write_cell(client: Any, sheet_id: str, sheet_name: Optional[str], row: int, col: int, value: str) -> bool:
    """Write a single cell. row/col 1-indexed. sheet_id can be URL or raw ID."""
    if not client or not sheet_id:
        return False
    sid = _extract_sheet_id(sheet_id)
    if not sid:
        return False
    try:
        workbook = client.open_by_key(sid)
        sheet = workbook.worksheet(sheet_name) if sheet_name else workbook.sheet1
        sheet.update_cell(row, col, str(value))
        return True
    except Exception:
        return False


def _get_worksheet(client: Any, sheet_id: str, sheet_name: Optional[str]):
    """Open workbook by ID and return worksheet (by name if sheet_name else first)."""
    sid = _extract_sheet_id(sheet_id)
    if not sid:
        return None, None
    workbook = client.open_by_key(sid)
    if sheet_name:
        try:
            sheet = workbook.worksheet(sheet_name)
        except Exception as e:
            raise RuntimeError(
                f"Worksheet not found: sheet_id={sid!r}, worksheet_name={sheet_name!r}. {e}"
            ) from e
    else:
        sheet = workbook.sheet1
    return sheet, sid


def find_row_by_column(client: Any, sheet_id: str, sheet_name: Optional[str], col_name: str, value: str) -> int:
    """Return 1-based row index where column (matched by normalized name) equals value, or 0 if not found."""
    if not client or not sheet_id:
        return 0
    try:
        sheet, _ = _get_worksheet(client, sheet_id, sheet_name)
        if not sheet:
            return 0
        headers = sheet.row_values(1)
        headers_norm = [normalize_header(h) for h in headers]
        col_norm = normalize_header(col_name)
        if col_norm not in headers_norm:
            return 0
        col_idx = headers_norm.index(col_norm)
        all_values = sheet.get_all_values()
        value_stripped = str(value).strip()
        for i, row in enumerate(all_values[1:], start=2):
            row_padded = row + [""] * (len(headers_norm) - len(row))
            if col_idx < len(row_padded) and str(row_padded[col_idx] or "").strip() == value_stripped:
                return i
        return 0
    except RuntimeError:
        raise
    except Exception:
        return 0


def update_column_for_row(
    client: Any, sheet_id: str, sheet_name: Optional[str], row: int, col_name: str, value: str
) -> bool:
    """Update a specific column (by normalized name) for a given 1-based row."""
    if not client or row < 2 or not sheet_id:
        return False
    try:
        sheet, _ = _get_worksheet(client, sheet_id, sheet_name)
        if not sheet:
            return False
        headers = sheet.row_values(1)
        headers_norm = [normalize_header(h) for h in headers]
        col_norm = normalize_header(col_name)
        if col_norm not in headers_norm:
            return False
        col_idx_0based = headers_norm.index(col_norm)
        sheet.update_cell(row, col_idx_0based + 1, str(value))
        return True
    except RuntimeError:
        raise
    except Exception:
        return False
