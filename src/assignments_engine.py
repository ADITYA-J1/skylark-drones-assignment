"""
Assignment coordination: match pilots/drones to projects, track and reassign.
Handles urgent reassignments with priority override and least-impact selection.
"""
from typing import List, Optional, Tuple
from datetime import datetime

from src.roster import get_pilot_by_id, query_pilots
from src.fleet import get_drone_by_id, query_drones


def _parse_date(s: Optional[str]):
    """Parse date string; supports YYYY-MM-DD and DD/MM/YYYY. Returns None on failure."""
    if not s:
        return None
    s = (s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _cap_match(drone_capabilities: str, required: str) -> bool:
    """True if required capability appears in drone's comma-separated capabilities (case-insensitive)."""
    if not required or not drone_capabilities:
        return False
    parts = [p.strip().lower() for p in str(drone_capabilities).split(",")]
    return required.strip().lower() in parts


def _dates_overlap(s1: str, e1: str, s2: str, e2: str) -> bool:
    """True if [s1,e1] overlaps [s2,e2]."""
    a, b = _parse_date(s1), _parse_date(e1)
    c, d = _parse_date(s2), _parse_date(e2)
    if not all([a, b, c, d]):
        return False
    return not (b < c or d < a)


def build_assignments_from_roster_and_missions(
    pilots: List[dict], missions: List[dict]
) -> List[dict]:
    """
    Build assignment list from pilot current_assignment and mission dates.
    Each item: project_id, pilot_id, start_date, end_date (drone optional).
    """
    assignments = []
    for p in pilots:
        proj = (p.get("current_assignment") or "").strip()
        if not proj or proj in ("–", "-"):
            continue
        for m in missions:
            if (m.get("project_id") or "").strip() == proj:
                assignments.append({
                    "project_id": proj,
                    "pilot_id": p.get("pilot_id"),
                    "drone_id": None,
                    "start_date": m.get("start_date"),
                    "end_date": m.get("end_date"),
                })
                break
    return assignments


def match_pilots_to_mission(
    pilots: List[dict],
    mission: dict,
    assignments: List[dict],
    exclude_pilot_ids: Optional[List[str]] = None,
) -> List[dict]:
    """
    Return pilots that can do this mission: same location, required skills/certs,
    available in date range, not double-booked.
    """
    loc = (mission.get("location") or "").strip()
    skills = (mission.get("required_skills") or "").strip()
    certs = (mission.get("required_certs") or "").strip()
    start, end = mission.get("start_date"), mission.get("end_date")
    project_id = (mission.get("project_id") or "").strip()

    exclude = set(exclude_pilot_ids or [])

    # Filter by location, then by skill/cert
    candidates = query_pilots(pilots, location=loc if loc else None)
    if skills:
        for skill in [s.strip() for s in skills.split(",") if s.strip()]:
            candidates = query_pilots(candidates, skill=skill)
    if certs:
        for cert in [c.strip() for c in certs.split(",") if c.strip()]:
            candidates = query_pilots(candidates, certification=cert)

    # Must be Available or we allow override for urgent
    available_only = [p for p in candidates if (p.get("status") or "").strip().lower() == "available"]
    if not available_only:
        available_only = [p for p in candidates if (p.get("status") or "").strip().lower() in ("available", "assigned")]

    out = []
    for p in available_only:
        pid = (p.get("pilot_id") or "").strip()
        if pid in exclude:
            continue
        # Check overlap with existing assignments
        if _pilot_busy(pid, start, end, assignments, exclude_project=project_id):
            continue
        out.append(p)
    return out


def _pilot_busy(
    pilot_id: str, start: str, end: str, assignments: List[dict], exclude_project: Optional[str] = None
) -> bool:
    for a in assignments:
        if (a.get("pilot_id") or "").strip() != pilot_id:
            continue
        if exclude_project and (a.get("project_id") or "").strip() == exclude_project:
            continue
        if _dates_overlap(
            a.get("start_date") or "",
            a.get("end_date") or "",
            start or "",
            end or "",
        ):
            return True
    return False


def match_drones_to_mission(
    drones: List[dict],
    mission: dict,
    assignments: List[dict],
    exclude_drone_ids: Optional[List[str]] = None,
) -> List[dict]:
    """
    Return drones that can support this mission: same location, capability match,
    not in maintenance, not double-booked.
    """
    loc = (mission.get("location") or "").strip()
    # Mission may not list required capability; use required_skills as proxy (e.g. Thermal -> Thermal drone)
    cap = (mission.get("required_skills") or "").strip()
    start, end = mission.get("start_date"), mission.get("end_date")
    project_id = (mission.get("project_id") or "").strip()

    exclude = set(exclude_drone_ids or [])

    candidates = query_drones(
        drones,
        location=loc if loc else None,
        status="Available",
        exclude_maintenance=True,
    )
    # Match capability: mission required_skills may be comma-separated; drone must have at least one
    if cap:
        caps = [c.strip() for c in cap.split(",") if c.strip()]
        if caps:
            matched = []
            for d in candidates:
                drone_caps = (d.get("capabilities") or "").strip()
                if any(c and _cap_match(drone_caps, c) for c in caps):
                    matched.append(d)
            candidates = matched if matched else candidates
    if not candidates:
        candidates = query_drones(drones, location=loc if loc else None, exclude_maintenance=False)

    out = []
    for d in candidates:
        did = (d.get("drone_id") or "").strip()
        if did in exclude:
            continue
        if _drone_busy(did, start, end, assignments, exclude_project=project_id):
            continue
        out.append(d)
    return out


def _drone_busy(
    drone_id: str, start: str, end: str, assignments: List[dict], exclude_project: Optional[str] = None
) -> bool:
    for a in assignments:
        did = (a.get("drone_id") or "").strip()
        if not did or did != drone_id:
            continue
        if exclude_project and (a.get("project_id") or "").strip() == exclude_project:
            continue
        if _dates_overlap(
            a.get("start_date") or "",
            a.get("end_date") or "",
            start or "",
            end or "",
        ):
            return True
    return False


def suggest_assignment(
    pilots: List[dict],
    drones: List[dict],
    missions: List[dict],
    assignments: List[dict],
    project_id: str,
    is_urgent: bool = False,
) -> Tuple[Optional[dict], Optional[dict], List[str]]:
    """
    Suggest best pilot and drone for project_id. Returns (pilot, drone, reasons).
    For urgent: allow reassignment (least-impact); reasons explain overrides.
    """
    reasons = []
    mission = next((m for m in missions if (m.get("project_id") or "").strip() == project_id), None)
    if not mission:
        return None, None, ["Project not found."]

    pilot_candidates = match_pilots_to_mission(pilots, mission, assignments)
    drone_candidates = match_drones_to_mission(drones, mission, assignments)

    if not pilot_candidates and is_urgent:
        # Urgent: consider currently assigned pilots and suggest least-impact reassignment
        all_at_location = query_pilots(pilots, location=(mission.get("location") or "").strip())
        for p in all_at_location:
            if p not in pilot_candidates:
                pilot_candidates.append(p)
        reasons.append("Urgent: expanded to assigned pilots for possible reassignment.")

    if not pilot_candidates:
        return None, None, ["No suitable pilot found for this project."]

    # Prefer available over assigned
    pilot = None
    for p in pilot_candidates:
        if (p.get("status") or "").strip().lower() == "available":
            pilot = p
            break
    if not pilot:
        pilot = pilot_candidates[0]
        if (pilot.get("status") or "").strip().lower() == "assigned":
            reasons.append(f"Pilot {pilot.get('name')} is currently assigned; urgent reassignment may be needed.")

    drone = drone_candidates[0] if drone_candidates else None
    if not drone:
        reasons.append("No suitable drone available at location; check maintenance or assign manually.")

    return pilot, drone, reasons


def urgent_reassign(
    pilots: List[dict],
    drones: List[dict],
    missions: List[dict],
    assignments: List[dict],
    project_id: str,
) -> Tuple[Optional[dict], Optional[dict], List[str]]:
    """
    Urgent reassignment: pick best pilot/drone even if it requires unassigning from another project.
    Returns (pilot, drone, list of conflict explanations).
    """
    mission = next((m for m in missions if (m.get("project_id") or "").strip() == project_id), None)
    if not mission:
        return None, None, ["Project not found."]

    reasons = []
    # Get all pilots at location with skills/certs (allow assigned)
    loc = (mission.get("location") or "").strip()
    skills = (mission.get("required_skills") or "").strip()
    certs = (mission.get("required_certs") or "").strip()
    start, end = mission.get("start_date"), mission.get("end_date")

    candidates = query_pilots(pilots, location=loc if loc else None)
    if skills:
        for skill in [s.strip() for s in skills.split(",") if s.strip()]:
            candidates = query_pilots(candidates, skill=skill)
    if certs:
        for cert in [c.strip() for c in certs.split(",") if c.strip()]:
            candidates = query_pilots(candidates, certification=cert)

    # Sort: Available first, then by current assignment (least impact = assigned to project ending soonest)
    available = [p for p in candidates if (p.get("status") or "").strip().lower() == "available"]
    assigned = [p for p in candidates if p not in available]

    def impact_key(p):
        """Lower = less impact to reassign."""
        pid = (p.get("pilot_id") or "").strip()
        for a in assignments:
            if (a.get("pilot_id") or "").strip() != pid:
                continue
            ed = _parse_date(a.get("end_date"))
            return (ed or datetime.max).strftime("%Y-%m-%d")
        return "9999-99-99"

    assigned.sort(key=impact_key)
    pilot_order = available + assigned
    pilot = pilot_order[0] if pilot_order else None

    if pilot and (pilot.get("status") or "").strip().lower() == "assigned":
        cur = pilot.get("current_assignment") or ""
        reasons.append(f"Urgent override: {pilot.get('name')} will be reassigned from {cur} to {project_id}.")

    # Drone: prefer Available, same location
    drone_candidates = match_drones_to_mission(drones, mission, assignments)
    drone = drone_candidates[0] if drone_candidates else None
    if not drone:
        drone_candidates = query_drones(drones, location=loc, exclude_maintenance=False)
        drone = drone_candidates[0] if drone_candidates else None
        if drone and (drone.get("status") or "").strip().lower() == "maintenance":
            reasons.append(f"Warning: drone {drone.get('drone_id')} is in maintenance; verify before use.")

    return pilot, drone, reasons
