"""
Conflict detection: double-booking, skill/cert mismatch, equipment-pilot location, drone maintenance.
"""
from typing import List, Optional, Tuple
from datetime import datetime

from src.roster import get_pilot_by_id
from src.fleet import get_drone_by_id
from src.assignments_engine import _parse_date, _dates_overlap, build_assignments_from_roster_and_missions


def _has_token(cell: str, token: str) -> bool:
    parts = [s.strip().lower() for s in (cell or "").split(",")]
    return token.strip().lower() in parts


def detect_all_conflicts(
    pilots: List[dict],
    drones: List[dict],
    missions: List[dict],
    assignments: Optional[List[dict]] = None,
) -> List[dict]:
    """
    Run all conflict checks. Return list of conflict dicts:
    { type, severity, message, pilot_id?, drone_id?, project_id? }
    """
    if assignments is None:
        assignments = build_assignments_from_roster_and_missions(pilots, missions)
    assignments = list(assignments)

    # Merge drone assignments from fleet current_assignment (no duplicates)
    seen_drone_proj = set()
    for a in assignments:
        did, pid = a.get("drone_id"), a.get("project_id")
        if did and pid:
            seen_drone_proj.add((str(did).strip(), str(pid).strip()))
    for d in drones:
        a = (d.get("current_assignment") or "").strip()
        if a and a not in ("–", "-"):
            proj = next((m for m in missions if (m.get("project_id") or "").strip() == a), None)
            if proj:
                did = (d.get("drone_id") or "").strip()
                proj_id = (proj.get("project_id") or a or "").strip()
                if did and (did, proj_id) not in seen_drone_proj:
                    assignments.append({
                        "project_id": a,
                        "pilot_id": None,
                        "drone_id": d.get("drone_id"),
                        "start_date": proj.get("start_date"),
                        "end_date": proj.get("end_date"),
                    })
                    seen_drone_proj.add((did, proj_id))

    out = []
    out.extend(_double_booking_pilot(assignments))
    out.extend(_double_booking_drone(assignments))
    out.extend(_skill_cert_mismatch(pilots, missions, assignments))
    out.extend(_drone_maintenance_assigned(drones, assignments))
    out.extend(_pilot_drone_location_mismatch(pilots, drones, missions, assignments))
    return out


def _double_booking_pilot(assignments: List[dict]) -> List[dict]:
    """Pilot assigned to overlapping project dates."""
    conflicts = []
    pilot_assignments = [a for a in assignments if a.get("pilot_id")]
    for i, a1 in enumerate(pilot_assignments):
        for a2 in pilot_assignments[i + 1 :]:
            if (a1.get("pilot_id") or "").strip() != (a2.get("pilot_id") or "").strip():
                continue
            if _dates_overlap(
                a1.get("start_date") or "",
                a1.get("end_date") or "",
                a2.get("start_date") or "",
                a2.get("end_date") or "",
            ):
                conflicts.append({
                    "type": "double_booking_pilot",
                    "severity": "high",
                    "message": f"Pilot {a1.get('pilot_id')} has overlapping assignments: {a1.get('project_id')} and {a2.get('project_id')}.",
                    "pilot_id": a1.get("pilot_id"),
                    "project_id": a2.get("project_id"),
                })
    return conflicts


def _double_booking_drone(assignments: List[dict]) -> List[dict]:
    """Drone assigned to overlapping project dates."""
    conflicts = []
    drone_assignments = [a for a in assignments if a.get("drone_id")]
    for i, a1 in enumerate(drone_assignments):
        for a2 in drone_assignments[i + 1 :]:
            if (a1.get("drone_id") or "").strip() != (a2.get("drone_id") or "").strip():
                continue
            if _dates_overlap(
                a1.get("start_date") or "",
                a1.get("end_date") or "",
                a2.get("start_date") or "",
                a2.get("end_date") or "",
            ):
                conflicts.append({
                    "type": "double_booking_drone",
                    "severity": "high",
                    "message": f"Drone {a1.get('drone_id')} has overlapping assignments: {a1.get('project_id')} and {a2.get('project_id')}.",
                    "drone_id": a1.get("drone_id"),
                    "project_id": a2.get("project_id"),
                })
    return conflicts


def _skill_cert_mismatch(pilots: List[dict], missions: List[dict], assignments: List[dict]) -> List[dict]:
    """Pilot assigned to job requiring certification/skill they lack."""
    conflicts = []
    for a in assignments:
        pid = (a.get("pilot_id") or "").strip()
        if not pid:
            continue
        proj_id = (a.get("project_id") or "").strip()
        mission = next((m for m in missions if (m.get("project_id") or "").strip() == proj_id), None)
        if not mission:
            continue
        pilot = get_pilot_by_id(pilots, pid)
        if not pilot:
            continue
        req_skills = (mission.get("required_skills") or "").strip()
        req_certs = (mission.get("required_certs") or "").strip()
        for skill in [s.strip() for s in req_skills.split(",") if s.strip()]:
            if not _has_token(pilot.get("skills", ""), skill):
                conflicts.append({
                    "type": "skill_mismatch",
                    "severity": "high",
                    "message": f"Pilot {pid} ({pilot.get('name')}) lacks required skill '{skill}' for {proj_id}.",
                    "pilot_id": pid,
                    "project_id": proj_id,
                })
        for cert in [c.strip() for c in req_certs.split(",") if c.strip()]:
            if not _has_token(pilot.get("certifications", ""), cert):
                conflicts.append({
                    "type": "certification_mismatch",
                    "severity": "high",
                    "message": f"Pilot {pid} ({pilot.get('name')}) lacks required certification '{cert}' for {proj_id}.",
                    "pilot_id": pid,
                    "project_id": proj_id,
                })
    return conflicts


def _drone_maintenance_assigned(drones: List[dict], assignments: List[dict]) -> List[dict]:
    """Drone in maintenance but assigned to a project."""
    conflicts = []
    for d in drones:
        if (d.get("status") or "").strip().lower() != "maintenance":
            continue
        did = (d.get("drone_id") or "").strip()
        for a in assignments:
            if (a.get("drone_id") or "").strip() != did:
                continue
            conflicts.append({
                "type": "drone_maintenance_assigned",
                "severity": "high",
                "message": f"Drone {did} is in maintenance but assigned to {a.get('project_id')}.",
                "drone_id": did,
                "project_id": a.get("project_id"),
            })
    return conflicts


def _pilot_drone_location_mismatch(
    pilots: List[dict],
    drones: List[dict],
    missions: List[dict],
    assignments: List[dict],
) -> List[dict]:
    """Pilot and assigned drone in different locations than project."""
    conflicts = []
    for a in assignments:
        proj_id = (a.get("project_id") or "").strip()
        mission = next((m for m in missions if (m.get("project_id") or "").strip() == proj_id), None)
        if not mission:
            continue
        loc = (mission.get("location") or "").strip().lower()
        if not loc:
            continue
        pid = (a.get("pilot_id") or "").strip()
        did = (a.get("drone_id") or "").strip()
        if pid:
            pilot = get_pilot_by_id(pilots, pid)
            if pilot and (pilot.get("location") or "").strip().lower() != loc:
                conflicts.append({
                    "type": "pilot_location_mismatch",
                    "severity": "medium",
                    "message": f"Pilot {pid} is in {(pilot.get('location') or 'unknown')} but project {proj_id} is in {mission.get('location')}.",
                    "pilot_id": pid,
                    "project_id": proj_id,
                })
        if did:
            drone = get_drone_by_id(drones, did)
            if drone and (drone.get("location") or "").strip().lower() != loc:
                conflicts.append({
                    "type": "drone_location_mismatch",
                    "severity": "medium",
                    "message": f"Drone {did} is in {(drone.get('location') or 'unknown')} but project {proj_id} is in {mission.get('location')}.",
                    "drone_id": did,
                    "project_id": proj_id,
                })
    return conflicts
