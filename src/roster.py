"""
Pilot roster management: query by skill, certification, location; update status.
"""
from typing import List, Optional


def query_pilots(
    pilots: List[dict],
    skill: Optional[str] = None,
    certification: Optional[str] = None,
    location: Optional[str] = None,
    status: Optional[str] = None,
) -> List[dict]:
    """
    Filter pilots by skill, certification, location, status.
    Skills/certs can be comma-separated in data; we check substring match.
    """
    result = list(pilots)
    if skill:
        result = [p for p in result if _has_token(p.get("skills", ""), skill)]
    if certification:
        result = [p for p in result if _has_token(p.get("certifications", ""), certification)]
    if location:
        result = [p for p in result if (p.get("location") or "").strip().lower() == location.strip().lower()]
    if status:
        result = [p for p in result if (p.get("status") or "").strip().lower() == status.strip().lower()]
    return result


def _has_token(cell: str, token: str) -> bool:
    """Check if token appears in comma-separated cell (case-insensitive)."""
    if not cell:
        return False
    parts = [s.strip().lower() for s in str(cell).split(",")]
    return token.strip().lower() in parts


def get_pilot_by_id(pilots: List[dict], pilot_id: str) -> Optional[dict]:
    """Return pilot dict by pilot_id."""
    for p in pilots:
        if (p.get("pilot_id") or "").strip() == pilot_id.strip():
            return p
    return None


def get_current_assignments_from_roster(pilots: List[dict]) -> List[dict]:
    """From roster, return list of {pilot_id, current_assignment} for assigned pilots."""
    out = []
    for p in pilots:
        a = (p.get("current_assignment") or "").strip()
        if a and a != "–" and a != "-":
            out.append({"pilot_id": p.get("pilot_id"), "current_assignment": a})
    return out


def valid_statuses() -> List[str]:
    """Allowed pilot status values for sync."""
    return ["Available", "On Leave", "Unavailable", "Assigned"]
