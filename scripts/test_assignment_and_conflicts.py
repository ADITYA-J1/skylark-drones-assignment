"""
Step 3: Test assignment engine and conflict detection.
Verifies: matching, suggest_assignment, urgent_reassign, and all four edge-case conflicts.
Run from project root: python scripts/test_assignment_and_conflicts.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.data_loader import load_pilots, load_drones, load_missions, load_assignments, get_sheets_client_cached
from src.assignments_engine import (
    build_assignments_from_roster_and_missions,
    match_pilots_to_mission,
    match_drones_to_mission,
    suggest_assignment,
    urgent_reassign,
    _dates_overlap,
)
from src.conflicts import detect_all_conflicts


def load_data():
    client = get_sheets_client_cached()
    pilots = load_pilots(client)
    drones = load_drones(client)
    missions = load_missions(client)
    raw_assignments = load_assignments(client)
    assignments = raw_assignments if raw_assignments else build_assignments_from_roster_and_missions(
        pilots, missions
    )
    return pilots, drones, missions, assignments


def test_date_overlap():
    print("--- Test: date overlap logic ---")
    assert _dates_overlap("2026-02-06", "2026-02-08", "2026-02-07", "2026-02-09") is True
    assert _dates_overlap("2026-02-06", "2026-02-08", "2026-02-10", "2026-02-12") is False
    assert _dates_overlap("2026-02-06", "2026-02-08", "2026-02-08", "2026-02-10") is True  # touching
    print("  OK: _dates_overlap correct.\n")


def test_match_pilots_and_drones():
    print("--- Test: match pilots/drones to mission ---")
    pilots, drones, missions, assignments = load_data()
    assert len(pilots) >= 1 and len(missions) >= 1
    mission = missions[0]
    project_id = (mission.get("project_id") or "").strip()
    pilot_candidates = match_pilots_to_mission(pilots, mission, assignments)
    drone_candidates = match_drones_to_mission(drones, mission, assignments)
    print(f"  Mission {project_id}: {len(pilot_candidates)} pilot(s), {len(drone_candidates)} drone(s).")
    print("  OK: match_pilots_to_mission / match_drones_to_mission ran.\n")


def test_suggest_and_urgent():
    print("--- Test: suggest_assignment and urgent_reassign ---")
    pilots, drones, missions, assignments = load_data()
    for m in missions:
        pid = (m.get("project_id") or "").strip()
        if not pid:
            continue
        pilot, drone, reasons = suggest_assignment(pilots, drones, missions, assignments, pid)
        print(f"  Suggest {pid}: pilot={pilot.get('name') if pilot else None}, drone={drone.get('drone_id') if drone else None}")
        if reasons:
            for r in reasons:
                print(f"    - {r}")
    urgent_project = next((m.get("project_id") for m in missions if (m.get("priority") or "").strip() == "Urgent"), None)
    if urgent_project:
        p, d, reasons = urgent_reassign(pilots, drones, missions, assignments, urgent_project)
        print(f"  Urgent {urgent_project}: pilot={p.get('name') if p else None}, reasons={len(reasons)}")
    print("  OK: suggest_assignment and urgent_reassign ran.\n")


def test_conflicts_with_live_data():
    print("--- Test: detect_all_conflicts (live data) ---")
    pilots, drones, missions, assignments = load_data()
    conflicts = detect_all_conflicts(pilots, drones, missions, assignments)
    print(f"  Found {len(conflicts)} conflict(s).")
    for c in conflicts:
        print(f"  - [{c.get('type')}] {c.get('message')}")
    print("  OK: detect_all_conflicts ran.\n")


def test_edge_case_overlapping_dates():
    print("--- Test: edge case — pilot overlapping project dates ---")
    pilots = [{"pilot_id": "P1", "name": "Test", "skills": "Mapping", "certifications": "DGCA", "location": "BLR", "status": "Assigned"}]
    missions = [
        {"project_id": "PRJ1", "location": "BLR", "required_skills": "Mapping", "required_certs": "DGCA", "start_date": "2026-02-01", "end_date": "2026-02-05"},
        {"project_id": "PRJ2", "location": "BLR", "required_skills": "Mapping", "required_certs": "DGCA", "start_date": "2026-02-03", "end_date": "2026-02-07"},
    ]
    assignments = [
        {"project_id": "PRJ1", "pilot_id": "P1", "drone_id": None, "start_date": "2026-02-01", "end_date": "2026-02-05"},
        {"project_id": "PRJ2", "pilot_id": "P1", "drone_id": None, "start_date": "2026-02-03", "end_date": "2026-02-07"},
    ]
    conflicts = detect_all_conflicts(pilots, [], missions, assignments)
    overlap = [c for c in conflicts if c.get("type") == "double_booking_pilot"]
    assert len(overlap) >= 1, "Expected double_booking_pilot conflict for overlapping dates"
    print(f"  Detected: {overlap[0].get('message')}")
    print("  OK: overlapping dates detected.\n")


def test_edge_case_skill_cert_mismatch():
    print("--- Test: edge case — pilot lacks required certification ---")
    pilots = [{"pilot_id": "P1", "name": "Test", "skills": "Mapping", "certifications": "DGCA", "location": "BLR", "status": "Assigned"}]
    missions = [{"project_id": "PRJ1", "location": "BLR", "required_skills": "Mapping", "required_certs": "Night Ops", "start_date": "2026-02-01", "end_date": "2026-02-05"}]
    assignments = [{"project_id": "PRJ1", "pilot_id": "P1", "drone_id": None, "start_date": "2026-02-01", "end_date": "2026-02-05"}]
    conflicts = detect_all_conflicts(pilots, [], missions, assignments)
    cert_mismatch = [c for c in conflicts if c.get("type") == "certification_mismatch"]
    assert len(cert_mismatch) >= 1, "Expected certification_mismatch"
    print(f"  Detected: {cert_mismatch[0].get('message')}")
    print("  OK: certification mismatch detected.\n")


def test_edge_case_drone_maintenance_assigned():
    print("--- Test: edge case — drone in maintenance but assigned ---")
    drones = [{"drone_id": "D1", "model": "M", "capabilities": "RGB", "status": "Maintenance", "location": "BLR", "current_assignment": "PRJ1", "maintenance_due": "2026-03-01"}]
    missions = [{"project_id": "PRJ1", "location": "BLR", "start_date": "2026-02-01", "end_date": "2026-02-05"}]
    assignments = [{"project_id": "PRJ1", "pilot_id": None, "drone_id": "D1", "start_date": "2026-02-01", "end_date": "2026-02-05"}]
    conflicts = detect_all_conflicts([], drones, missions, assignments)
    maint = [c for c in conflicts if c.get("type") == "drone_maintenance_assigned"]
    assert len(maint) >= 1, "Expected drone_maintenance_assigned conflict"
    print(f"  Detected: {maint[0].get('message')}")
    print("  OK: drone in maintenance assigned detected.\n")


def test_edge_case_location_mismatch():
    print("--- Test: edge case — pilot/drone location vs project ---")
    pilots = [{"pilot_id": "P1", "name": "Test", "skills": "Mapping", "certifications": "DGCA", "location": "Mumbai", "status": "Assigned"}]
    drones = [{"drone_id": "D1", "model": "M", "capabilities": "RGB", "status": "Available", "location": "Mumbai", "current_assignment": "PRJ1", "maintenance_due": "2026-03-01"}]
    missions = [{"project_id": "PRJ1", "location": "Bangalore", "start_date": "2026-02-01", "end_date": "2026-02-05"}]
    assignments = [
        {"project_id": "PRJ1", "pilot_id": "P1", "drone_id": "D1", "start_date": "2026-02-01", "end_date": "2026-02-05"},
    ]
    conflicts = detect_all_conflicts(pilots, drones, missions, assignments)
    pilot_loc = [c for c in conflicts if c.get("type") == "pilot_location_mismatch"]
    drone_loc = [c for c in conflicts if c.get("type") == "drone_location_mismatch"]
    assert len(pilot_loc) >= 1, "Expected pilot_location_mismatch (pilot in Mumbai, project in Bangalore)"
    assert len(drone_loc) >= 1, "Expected drone_location_mismatch (drone in Mumbai, project in Bangalore)"
    print(f"  Detected pilot: {pilot_loc[0].get('message')}")
    print(f"  Detected drone: {drone_loc[0].get('message')}")
    print("  OK: location mismatch detected.\n")


if __name__ == "__main__":
    print("=== Assignment engine & conflict detection tests ===\n")
    test_date_overlap()
    test_match_pilots_and_drones()
    test_suggest_and_urgent()
    test_conflicts_with_live_data()
    test_edge_case_overlapping_dates()
    test_edge_case_skill_cert_mismatch()
    test_edge_case_drone_maintenance_assigned()
    test_edge_case_location_mismatch()
    print("=== All Step 3 tests passed ===")
