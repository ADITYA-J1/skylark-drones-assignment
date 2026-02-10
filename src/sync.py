"""
Sync pilot and drone status back to Google Sheets (2-way sync).
When using local CSV, write to CSV files.
"""
import os
from pathlib import Path
from typing import Optional

import pandas as pd

import config
from src.data_loader import _sheet_name_pilots, _sheet_name_drones
from src.sheets_client import (
    get_sheets_client,
    find_row_by_column,
    update_column_for_row,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def update_pilot_status(pilot_id: str, new_status: str) -> tuple[bool, str]:
    """
    Update pilot status in Google Sheet or CSV. Returns (success, message).
    """
    if new_status not in ["Available", "On Leave", "Unavailable", "Assigned"]:
        return False, "Invalid status."

    if config.USE_LOCAL_CSV or not (config.SINGLE_SHEET_ID or config.GOOGLE_SHEET_ID_PILOTS):
        # Write to CSV
        path = BASE_DIR / "pilot_roster.csv"
        if not path.exists():
            return False, "pilot_roster.csv not found."
        try:
            df = pd.read_csv(path)
            if "pilot_id" not in df.columns or "status" not in df.columns:
                return False, "CSV must have pilot_id and status columns."
            mask = df["pilot_id"].astype(str).str.strip() == str(pilot_id).strip()
            if not mask.any():
                return False, f"Pilot {pilot_id} not found."
            df.loc[mask, "status"] = new_status
            df.to_csv(path, index=False)
            return True, f"Pilot {pilot_id} status set to {new_status} (saved to CSV)."
        except Exception as e:
            return False, str(e)

    client = get_sheets_client()
    if not client:
        return False, "Google Sheets not configured (no credentials)."

    sheet_id = config.GOOGLE_SHEET_ID_PILOTS or config.SINGLE_SHEET_ID
    sheet_name = _sheet_name_pilots()
    row = find_row_by_column(client, sheet_id, sheet_name, "pilot_id", pilot_id)
    if row == 0:
        return False, f"Pilot {pilot_id} not found in sheet."
    ok = update_column_for_row(client, sheet_id, sheet_name, row, "status", new_status)
    if ok:
        return True, f"Pilot {pilot_id} status set to {new_status} (synced to Google Sheet)."
    return False, "Failed to update sheet."


def update_pilot_assignment(pilot_id: str, project_id: Optional[str]) -> tuple[bool, str]:
    """Update pilot's current_assignment. project_id None or empty = unassign."""
    value = (project_id or "–").strip() or "–"
    status = "Assigned" if value != "–" else "Available"

    if config.USE_LOCAL_CSV or not (config.SINGLE_SHEET_ID or config.GOOGLE_SHEET_ID_PILOTS):
        path = BASE_DIR / "pilot_roster.csv"
        if not path.exists():
            return False, "pilot_roster.csv not found."
        try:
            df = pd.read_csv(path)
            for col in ["current_assignment", "status"]:
                if col not in df.columns:
                    df[col] = "–" if col == "current_assignment" else "Available"
            mask = df["pilot_id"].astype(str).str.strip() == str(pilot_id).strip()
            if not mask.any():
                return False, f"Pilot {pilot_id} not found."
            df.loc[mask, "current_assignment"] = value
            df.loc[mask, "status"] = status
            df.to_csv(path, index=False)
            return True, f"Pilot {pilot_id} assignment set to {value} (CSV)."
        except Exception as e:
            return False, str(e)

    client = get_sheets_client()
    if not client:
        return False, "Google Sheets not configured."
    sheet_id = config.GOOGLE_SHEET_ID_PILOTS or config.SINGLE_SHEET_ID
    sheet_name = _sheet_name_pilots()
    row = find_row_by_column(client, sheet_id, sheet_name, "pilot_id", pilot_id)
    if row == 0:
        return False, f"Pilot {pilot_id} not found."
    ok1 = update_column_for_row(client, sheet_id, sheet_name, row, "current_assignment", value)
    ok2 = update_column_for_row(client, sheet_id, sheet_name, row, "status", status)
    if ok1 and ok2:
        return True, f"Pilot {pilot_id} assignment synced to sheet."
    return False, "Failed to update sheet."


def update_drone_status(drone_id: str, new_status: str) -> tuple[bool, str]:
    """Update drone status in Google Sheet or CSV."""
    if new_status not in ["Available", "Maintenance", "Assigned", "Unavailable"]:
        return False, "Invalid status."

    if config.USE_LOCAL_CSV or not (config.SINGLE_SHEET_ID or config.GOOGLE_SHEET_ID_DRONES):
        path = BASE_DIR / "drone_fleet.csv"
        if not path.exists():
            return False, "drone_fleet.csv not found."
        try:
            df = pd.read_csv(path)
            if "drone_id" not in df.columns or "status" not in df.columns:
                return False, "CSV must have drone_id and status columns."
            mask = df["drone_id"].astype(str).str.strip() == str(drone_id).strip()
            if not mask.any():
                return False, f"Drone {drone_id} not found."
            df.loc[mask, "status"] = new_status
            df.to_csv(path, index=False)
            return True, f"Drone {drone_id} status set to {new_status} (CSV)."
        except Exception as e:
            return False, str(e)

    client = get_sheets_client()
    if not client:
        return False, "Google Sheets not configured."
    sheet_id = config.GOOGLE_SHEET_ID_DRONES or config.SINGLE_SHEET_ID
    sheet_name = _sheet_name_drones()
    row = find_row_by_column(client, sheet_id, sheet_name, "drone_id", drone_id)
    if row == 0:
        return False, f"Drone {drone_id} not found in sheet."
    ok = update_column_for_row(client, sheet_id, sheet_name, row, "status", new_status)
    if ok:
        return True, f"Drone {drone_id} status set to {new_status} (synced to Google Sheet)."
    return False, "Failed to update sheet."


def update_drone_assignment(drone_id: str, project_id: Optional[str]) -> tuple[bool, str]:
    """Update drone's current_assignment. project_id None or empty = unassign."""
    value = (project_id or "–").strip() or "–"
    status = "Assigned" if value != "–" else "Available"

    if config.USE_LOCAL_CSV or not (config.SINGLE_SHEET_ID or config.GOOGLE_SHEET_ID_DRONES):
        path = BASE_DIR / "drone_fleet.csv"
        if not path.exists():
            return False, "drone_fleet.csv not found."
        try:
            df = pd.read_csv(path)
            for col in ["current_assignment", "status"]:
                if col not in df.columns:
                    df[col] = "–" if col == "current_assignment" else "Available"
            mask = df["drone_id"].astype(str).str.strip() == str(drone_id).strip()
            if not mask.any():
                return False, f"Drone {drone_id} not found."
            df.loc[mask, "current_assignment"] = value
            df.loc[mask, "status"] = status
            df.to_csv(path, index=False)
            return True, f"Drone {drone_id} assignment set to {value} (CSV)."
        except Exception as e:
            return False, str(e)

    client = get_sheets_client()
    if not client:
        return False, "Google Sheets not configured."
    sheet_id = config.GOOGLE_SHEET_ID_DRONES or config.SINGLE_SHEET_ID
    sheet_name = _sheet_name_drones()
    row = find_row_by_column(client, sheet_id, sheet_name, "drone_id", drone_id)
    if row == 0:
        return False, f"Drone {drone_id} not found."
    ok1 = update_column_for_row(client, sheet_id, sheet_name, row, "current_assignment", value)
    ok2 = update_column_for_row(client, sheet_id, sheet_name, row, "status", status)
    if ok1 and ok2:
        return True, f"Drone {drone_id} assignment synced to sheet."
    return False, "Failed to update sheet."
