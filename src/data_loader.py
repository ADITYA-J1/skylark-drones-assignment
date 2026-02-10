"""
Unified data loader: Google Sheets or local CSV fallback.
Provides pilots, drones, missions, assignments to the rest of the app.
"""
import os
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

import config
from src.sheets_client import (
    get_sheets_client,
    read_sheet_as_dicts,
)

# Base path for CSV fallback (project root)
BASE_DIR = Path(__file__).resolve().parent.parent


def _csv_path(name: str) -> str:
    return str(BASE_DIR / f"{name}.csv")


def _sheet_name_pilots() -> Optional[str]:
    """Worksheet name for pilots; use whenever configured, not only for single workbook."""
    s = (config.SHEET_NAME_PILOTS or "").strip()
    return s if s else None


def _sheet_name_drones() -> Optional[str]:
    s = (config.SHEET_NAME_DRONES or "").strip()
    return s if s else None


def _sheet_name_missions() -> Optional[str]:
    s = (config.SHEET_NAME_MISSIONS or "").strip()
    return s if s else None


def _sheet_name_assignments() -> Optional[str]:
    s = (config.SHEET_NAME_ASSIGNMENTS or "").strip()
    return s if s else None


def load_pilots(client: Any = None) -> List[dict]:
    """Load pilot roster from Sheets or CSV."""
    if not config.USE_LOCAL_CSV and client:
        sheet_id = config.GOOGLE_SHEET_ID_PILOTS or config.SINGLE_SHEET_ID
        if sheet_id:
            data = read_sheet_as_dicts(client, sheet_id, _sheet_name_pilots())
            if data:
                return data
    path = _csv_path("pilot_roster")
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df.replace({pd.NA: None}).to_dict("records")
    return []


def load_drones(client: Any = None) -> List[dict]:
    """Load drone fleet from Sheets or CSV."""
    if not config.USE_LOCAL_CSV and client:
        sheet_id = config.GOOGLE_SHEET_ID_DRONES or config.SINGLE_SHEET_ID
        if sheet_id:
            data = read_sheet_as_dicts(client, sheet_id, _sheet_name_drones())
            if data:
                return data
    path = _csv_path("drone_fleet")
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df.replace({pd.NA: None}).to_dict("records")
    return []


def load_missions(client: Any = None) -> List[dict]:
    """Load missions/projects from Sheets or CSV."""
    if not config.USE_LOCAL_CSV and client:
        sheet_id = config.GOOGLE_SHEET_ID_MISSIONS or config.SINGLE_SHEET_ID
        if sheet_id:
            data = read_sheet_as_dicts(client, sheet_id, _sheet_name_missions())
            if data:
                return data
    path = _csv_path("missions")
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df.replace({pd.NA: None}).to_dict("records")
    return []


def load_assignments(client: Any = None) -> List[dict]:
    """
    Load assignments (project_id, pilot_id, drone_id, start_date, end_date).
    If no sheet/CSV, returns [] (caller can derive from roster + missions).
    """
    if not config.USE_LOCAL_CSV and client:
        sheet_id = config.GOOGLE_SHEET_ID_ASSIGNMENTS or config.SINGLE_SHEET_ID
        if sheet_id:
            try:
                data = read_sheet_as_dicts(client, sheet_id, _sheet_name_assignments())
                if data:
                    return data
            except RuntimeError:
                pass  # fall back to CSV or []
    path = _csv_path("assignments")
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df.replace({pd.NA: None}).to_dict("records")
    return []


def get_sheets_client_cached():
    """Return sheets client if credentials exist; else None."""
    if config.USE_LOCAL_CSV and not (config.SINGLE_SHEET_ID or config.GOOGLE_SHEET_ID_PILOTS):
        return None
    return get_sheets_client()
