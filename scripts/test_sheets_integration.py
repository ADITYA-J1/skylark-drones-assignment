"""
Step 2: Test Google Sheets integration (read + write).
- With local CSV only: tests read from CSV and write to CSV (pilot status), then revert.
- With credentials + sheet IDs set: tests Sheet read (with header/row count) and write.
Run from project root: python scripts/test_sheets_integration.py
"""
import os
import sys
from pathlib import Path

# Run from project root so config and imports resolve consistently
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load env before importing config (dotenv in config is loaded on import)
import config
from src.data_loader import (
    load_pilots,
    load_drones,
    load_missions,
    get_sheets_client_cached,
    _sheet_name_pilots,
)
from src.sheets_client import get_sheets_client, read_sheet_as_dicts
from src.sync import update_pilot_status, update_drone_status


def test_csv_read():
    """Test reading pilots, drones, missions from CSV (default when no Sheets configured)."""
    print("--- Test: CSV read ---")
    client = get_sheets_client_cached()
    pilots = load_pilots(client)
    drones = load_drones(client)
    missions = load_missions(client)
    assert len(pilots) >= 1, "Expected at least one pilot from CSV"
    assert len(drones) >= 1, "Expected at least one drone from CSV"
    assert len(missions) >= 1, "Expected at least one mission from CSV"
    print(f"  Pilots: {len(pilots)} rows")
    print(f"  Drones: {len(drones)} rows")
    print(f"  Missions: {len(missions)} rows")
    print("  OK: CSV read passed.\n")
    return pilots, drones, missions


def test_csv_write_and_revert():
    """Test writing pilot status to CSV and reverting (so we don't leave data changed)."""
    print("--- Test: CSV write (pilot status) + revert ---")
    client = get_sheets_client_cached()
    pilots = load_pilots(client)
    pilot_id = None
    original_status = None
    # Prefer a pilot with non-Available status so write/revert is visible (e.g. On Leave)
    for p in pilots:
        pid = (p.get("pilot_id") or "").strip()
        if not pid:
            continue
        st = (p.get("status") or "").strip()
        if st and st != "Available":
            pilot_id, original_status = pid, st
            break
    if not pilot_id:
        for p in pilots:
            pid = (p.get("pilot_id") or "").strip()
            if pid:
                pilot_id, original_status = pid, (p.get("status") or "").strip() or "Available"
                break
    if not pilot_id:
        print("  Skip: no pilot_id in CSV.")
        return
    # Write to "Available" then revert
    ok1, msg1 = update_pilot_status(pilot_id, "Available")
    if not ok1:
        print(f"  FAIL: {msg1}")
        return
    print(f"  {msg1}")
    pilots_after = load_pilots(client)
    new_status = next((p.get("status") for p in pilots_after if (p.get("pilot_id") or "").strip() == pilot_id), None)
    if new_status != "Available":
        print(f"  FAIL: expected status Available after write, got {new_status}")
        return
    # Revert
    ok2, msg2 = update_pilot_status(pilot_id, original_status or "On Leave")
    if not ok2:
        print(f"  WARN: revert failed: {msg2}")
    else:
        print(f"  Reverted: {msg2}")
    print("  OK: CSV write + read-back passed.\n")


def test_sheets_read_if_configured():
    """If credentials and sheet ID are set, test reading from Google Sheet. Never skip silently when IDs are set."""
    print("--- Test: Google Sheets read (if configured) ---")
    client = get_sheets_client()
    if not client:
        print("  Skip: no credentials (GOOGLE_APPLICATION_CREDENTIALS / credentials.json).\n")
        return
    sheet_id = config.GOOGLE_SHEET_ID_PILOTS or config.SINGLE_SHEET_ID
    if not sheet_id:
        print("  Skip: no GOOGLE_SHEET_ID or GOOGLE_SHEET_ID_PILOTS set.\n")
        return
    sheet_name = _sheet_name_pilots()
    print(f"  Using sheet_id={sheet_id[:20]}..., worksheet_name={sheet_name!r}")
    try:
        data = read_sheet_as_dicts(client, sheet_id, sheet_name, _log_headers=True)
    except RuntimeError as e:
        print(f"  FAIL: {e}\n")
        raise
    print(f"  Row count: {len(data)}")
    if not data:
        print("  WARN: Sheet read returned no rows (check worksheet name matches tab exactly).\n")
        return
    print(f"  Detected keys (normalized) on first row: {list(data[0].keys())}")
    print(f"  Sheet read: {len(data)} rows from Pilot Roster.")
    print("  OK: Google Sheets read passed.\n")


def test_sheets_write_if_configured():
    """If Sheets is configured, test one safe write (update then revert)."""
    print("--- Test: Google Sheets write (if configured) ---")
    client = get_sheets_client()
    sheet_id = config.GOOGLE_SHEET_ID_PILOTS or config.SINGLE_SHEET_ID
    if not client or not sheet_id:
        print("  Skip: Sheets not configured.\n")
        return
    sheet_name = _sheet_name_pilots()
    try:
        data = read_sheet_as_dicts(client, sheet_id, sheet_name)
    except RuntimeError as e:
        print(f"  FAIL: {e}\n")
        raise
    if not data:
        print("  Skip: no data in sheet.\n")
        return
    first = data[0]
    pilot_id = (first.get("pilot_id") or "").strip()
    current_status = (first.get("status") or "").strip()
    if not pilot_id:
        print("  Skip: no pilot_id in first row.\n")
        return
    # Write "Available" then revert
    ok1, msg1 = update_pilot_status(pilot_id, "Available")
    if not ok1:
        print(f"  FAIL: {msg1}\n")
        return
    print(f"  {msg1}")
    ok2, _ = update_pilot_status(pilot_id, current_status or "Available")
    if ok2:
        print(f"  Reverted status to '{current_status or 'Available'}'.")
    print("  OK: Google Sheets write passed.\n")


if __name__ == "__main__":
    print("=== Google Sheets integration tests ===\n")
    test_csv_read()
    test_csv_write_and_revert()
    test_sheets_read_if_configured()
    test_sheets_write_if_configured()
    print("=== Done ===")
