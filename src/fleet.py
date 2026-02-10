"""
Drone fleet inventory: query by capability, availability, location; maintenance flags.
"""
from typing import List, Optional
from datetime import datetime


def query_drones(
    drones: List[dict],
    capability: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    exclude_maintenance: bool = False,
    maintenance_due_before: Optional[str] = None,
) -> List[dict]:
    """
    Filter drones by capability, status, location.
    capability: substring in comma-separated capabilities.
    exclude_maintenance: only return status != Maintenance.
    maintenance_due_before: ISO date string; flag if maintenance_due <= that date.
    """
    result = list(drones)
    if capability:
        result = [d for d in result if _has_cap(d.get("capabilities", ""), capability)]
    if status:
        result = [d for d in result if (d.get("status") or "").strip().lower() == status.strip().lower()]
    if location:
        result = [d for d in result if (d.get("location") or "").strip().lower() == location.strip().lower()]
    if exclude_maintenance:
        result = [d for d in result if (d.get("status") or "").strip().lower() != "maintenance"]
    if maintenance_due_before:
        result = [_add_maintenance_flag(d, maintenance_due_before) for d in result]
    else:
        result = [_add_maintenance_flag(d, None) for d in result]
    return result


def _has_cap(cell: str, cap: str) -> bool:
    if not cell:
        return False
    parts = [s.strip().lower() for s in str(cell).split(",")]
    return cap.strip().lower() in parts


def _add_maintenance_flag(drone: dict, before_date: Optional[str]) -> dict:
    """Add maintenance_flagged=True if maintenance_due is past or before given date."""
    d = dict(drone)
    due = (d.get("maintenance_due") or "").strip()
    if not before_date or not due:
        d["maintenance_flagged"] = False
        return d
    try:
        due_dt = datetime.strptime(due[:10], "%Y-%m-%d")
        ref_dt = datetime.strptime(before_date[:10], "%Y-%m-%d")
        d["maintenance_flagged"] = due_dt <= ref_dt
    except Exception:
        d["maintenance_flagged"] = False
    return d


def get_drone_by_id(drones: List[dict], drone_id: str) -> Optional[dict]:
    """Return drone dict by drone_id."""
    for d in drones:
        if (d.get("drone_id") or "").strip() == drone_id.strip():
            return d
    return None


def get_current_deployments_from_fleet(drones: List[dict]) -> List[dict]:
    """From fleet, return list of {drone_id, current_assignment} for assigned drones."""
    out = []
    for d in drones:
        a = (d.get("current_assignment") or "").strip()
        if a and a != "–" and a != "-":
            out.append({"drone_id": d.get("drone_id"), "current_assignment": a})
    return out


def valid_drone_statuses() -> List[str]:
    """Allowed drone status values for sync."""
    return ["Available", "Maintenance", "Assigned", "Unavailable"]
