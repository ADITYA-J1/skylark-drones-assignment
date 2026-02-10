"""
Conversational AI agent: interprets user intent and orchestrates roster, fleet, assignments, conflicts.
Uses rule-based routing + optional OpenAI for natural language. Falls back to rules-only if no API key.
"""
import re
from typing import Any, List, Optional, Tuple

from src.data_loader import load_pilots, load_drones, load_missions, load_assignments, get_sheets_client_cached
from src.roster import query_pilots, get_pilot_by_id
from src.fleet import query_drones, get_drone_by_id
from src.assignments_engine import (
    build_assignments_from_roster_and_missions,
    suggest_assignment,
    urgent_reassign,
)
from src.conflicts import detect_all_conflicts
from src.sync import update_pilot_status, update_pilot_assignment, update_drone_status, update_drone_assignment


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _intent_keywords(user_message: str) -> set:
    t = _normalize(user_message)
    words = set(re.findall(r"\w+", t))
    return words


def get_intent(user_message: str) -> str:
    """
    Classify user intent: roster, assignment, fleet, conflicts, urgent_reassign, status_update, help, unknown.
    """
    msg = _normalize(user_message)
    k = _intent_keywords(user_message)

    if not msg or msg in ("hi", "hello", "hey"):
        return "greeting"

    if any(w in k for w in ("urgent", "emergency", "asap", "reassign", "reassignment")):
        return "urgent_reassign"

    if any(w in k for w in ("conflict", "conflicts", "double", "overlap", "mismatch", "issue", "problem", "warning")):
        return "conflicts"

    # Assignment (project-specific) before generic roster
    if re.search(r"prj\d+", msg) or "project" in k:
        if any(w in k for w in ("assign", "match", "suggest", "who", "which", "pilot", "drone", "for")):
            return "assignment"

    if any(w in k for w in ("pilot", "roster", "availability", "available", "leave", "certification", "skill")):
        return "roster"

    if any(w in k for w in ("drone", "fleet", "inventory", "maintenance", "deploy")):
        return "fleet"

    if any(w in k for w in ("set", "update", "change", "mark", "status")):
        return "status_update"

    if any(w in k for w in ("help", "what can", "how")):
        return "help"

    # List/show missions or projects
    if ("mission" in k or "project" in k or "projects" in k) and (len(msg) < 50 or "list" in k or "show" in k or "all" in k):
        return "missions"

    if "confirm" in k and ("reassign" in k or "assign" in k):
        return "confirm_reassign"

    return "unknown"


def run_agent(user_message: str) -> Tuple[str, Optional[dict]]:
    """
    Process user message and return (reply_text, optional_structured_data for UI).
    Handles load/sync errors gracefully with a clear message.
    """
    try:
        client = get_sheets_client_cached()
        pilots = load_pilots(client)
        drones = load_drones(client)
        missions = load_missions(client)
        raw_assignments = load_assignments(client)
        assignments = list(raw_assignments) if raw_assignments else build_assignments_from_roster_and_missions(
            pilots, missions
        )
        # Enrich assignments with drone current_assignment from fleet (no duplicates)
        seen = {(str(x.get("drone_id") or "").strip(), str(x.get("project_id") or "").strip()) for x in assignments if x.get("drone_id")}
        for d in drones:
            a = (d.get("current_assignment") or "").strip()
            if a and a not in ("–", "-"):
                did = (d.get("drone_id") or "").strip()
                if did and (did, a) not in seen:
                    proj = next((m for m in missions if (m.get("project_id") or "").strip() == a), None)
                    if proj:
                        assignments.append({
                            "project_id": a,
                            "pilot_id": None,
                            "drone_id": d.get("drone_id"),
                            "start_date": proj.get("start_date"),
                            "end_date": proj.get("end_date"),
                        })
                        seen.add((did, a))
    except Exception as e:
        return (
            f"**Could not load data.** Please check your connection and sheet/CSV setup.\n\nError: {e!s}",
            None,
        )

    intent = get_intent(user_message)

    if intent == "greeting":
        return (
            "Hi! I'm the Drone Operations Coordinator. I can help you with:\n"
            "- **Roster**: Query pilots by skill, certification, location, or status\n"
            "- **Assignments**: Match pilots and drones to projects, suggest assignments\n"
            "- **Fleet**: Query drones by capability, availability, location, maintenance\n"
            "- **Conflicts**: Detect double-booking, skill mismatch, maintenance/location issues\n"
            "- **Urgent reassignments**: Priority-based reassignment with conflict explanation\n"
            "- **Updates**: Set pilot or drone status (synced to sheet/CSV)\n\n"
            "Try: *Who is available in Bangalore?* or *Check conflicts* or *Suggest assignment for PRJ002*",
            None,
        )

    if intent == "help":
        return (
            "**Commands you can try:**\n"
            "- *List available pilots in Mumbai*\n"
            "- *Pilots with DGCA certification*\n"
            "- *Drones available in Bangalore*\n"
            "- *Suggest assignment for PRJ001*\n"
            "- *Urgent reassignment for PRJ002*\n"
            "- *Check conflicts*\n"
            "- *Set pilot P001 status to On Leave*\n"
            "- *Set drone D002 status to Available*",
            None,
        )

    if intent == "conflicts":
        conflicts = detect_all_conflicts(pilots, drones, missions, assignments)
        if not conflicts:
            return "No conflicts detected. Roster, assignments, and fleet are consistent.", None
        lines = ["**Conflicts detected:**\n"]
        for c in conflicts:
            lines.append(f"- [{c.get('severity', '')}] {c.get('message', '')}")
        return "\n".join(lines), {"conflicts": conflicts}

    if intent == "confirm_reassign":
        # e.g. "Confirm reassignment PRJ002 to P002 and D003"
        proj_match = re.search(r"\b(PRJ\d+)\b", user_message, re.I)
        pilot_match = re.search(r"\b(P\d+)\b", user_message, re.I)
        drone_match = re.search(r"\b(D\d+)\b", user_message, re.I)
        project_id = proj_match.group(1).strip() if proj_match else None
        pilot_id = pilot_match.group(1).upper() if pilot_match else None
        drone_id = drone_match.group(1).upper() if drone_match else None
        if not project_id:
            return "Please specify project ID (e.g. PRJ002).", None
        lines = []
        if pilot_id:
            ok, msg = update_pilot_assignment(pilot_id, project_id)
            lines.append(msg if ok else f"Pilot: Error — {msg}")
        if drone_id:
            ok, msg = update_drone_assignment(drone_id, project_id)
            lines.append(msg if ok else f"Drone: Error — {msg}")
        if not lines:
            return "Specify at least pilot (P001) or drone (D001) to assign.", None
        return "**Reassignment applied:**\n" + "\n".join(lines), None

    if intent == "urgent_reassign":
        # Extract project id (e.g. PRJ002)
        proj_match = re.search(r"\b(PRJ\d+)\b", user_message, re.I)
        project_id = proj_match.group(1) if proj_match else None
        if not project_id:
            return "Please specify a project ID for urgent reassignment (e.g. *Urgent reassignment for PRJ002*).", None
        pilot, drone, reasons = urgent_reassign(pilots, drones, missions, assignments, project_id)
        if not pilot:
            return "Could not find a suitable pilot for urgent reassignment. " + (
                reasons[0] if reasons else ""
            ), None
        lines = [
            f"**Urgent reassignment for {project_id}:**",
            f"- **Pilot:** {pilot.get('name')} ({pilot.get('pilot_id')}) – {pilot.get('location')}",
        ]
        if drone:
            lines.append(f"- **Drone:** {drone.get('drone_id')} – {drone.get('model')} – {drone.get('location')}")
        for r in reasons:
            lines.append(f"- _Note:_ {r}")
        lines.append("\nSay *Confirm reassignment PRJ002 to P002 and D003* to apply (or use status updates).")
        return "\n".join(lines), {"urgent": {"project_id": project_id, "pilot": pilot, "drone": drone, "reasons": reasons}}

    if intent == "assignment":
        proj_match = re.search(r"\b(PRJ\d+)\b", user_message, re.I)
        project_id = proj_match.group(1) if proj_match else None
        if not project_id:
            return "Which project? Please include a project ID (e.g. PRJ001, PRJ002).", None
        is_urgent = "urgent" in _intent_keywords(user_message) or any(
            m.get("priority") == "Urgent" and (m.get("project_id") or "").strip() == project_id
            for m in missions
        )
        pilot, drone, reasons = suggest_assignment(pilots, drones, missions, assignments, project_id, is_urgent=is_urgent)
        if not pilot:
            return (reasons[0] if reasons else "No suggestion."), None
        lines = [
            f"**Suggested assignment for {project_id}:**",
            f"- **Pilot:** {pilot.get('name')} ({pilot.get('pilot_id')}) – {pilot.get('location')}",
        ]
        if drone:
            lines.append(f"- **Drone:** {drone.get('drone_id')} – {drone.get('model')} – {drone.get('location')}")
        for r in reasons:
            lines.append(f"- {r}")
        return "\n".join(lines), {"suggestion": {"project_id": project_id, "pilot": pilot, "drone": drone}}

    if intent == "roster":
        # Parse filters from message
        location = None
        skill = None
        cert = None
        status = None
        if "available" in _intent_keywords(user_message):
            status = "Available"
        if "leave" in _intent_keywords(user_message):
            status = "On Leave"
        if "assigned" in _intent_keywords(user_message):
            status = "Assigned"
        for loc in ["Bangalore", "Mumbai", "Delhi", "Chennai"]:
            if loc.lower() in user_message.lower():
                location = loc
                break
        if "dgca" in user_message.lower():
            cert = "DGCA"
        if "night" in user_message.lower():
            cert = "Night Ops"
        for s in ["Mapping", "Survey", "Inspection", "Thermal"]:
            if s.lower() in user_message.lower():
                skill = s
                break
        result = query_pilots(pilots, skill=skill, certification=cert, location=location, status=status)
        if not result:
            return "No pilots match your criteria.", None
        lines = ["**Pilots:**\n"]
        for p in result:
            lines.append(
                f"- **{p.get('name')}** ({p.get('pilot_id')}) | {p.get('status')} | {p.get('location')} | "
                f"Skills: {p.get('skills')} | Certs: {p.get('certifications')} | Assignment: {p.get('current_assignment') or '–'}"
            )
        return "\n".join(lines), {"pilots": result}

    if intent == "fleet":
        location = None
        cap = None
        status = "Available" if "available" in _intent_keywords(user_message) else None
        for loc in ["Bangalore", "Mumbai", "Delhi", "Chennai"]:
            if loc.lower() in user_message.lower():
                location = loc
                break
        for c in ["LiDAR", "RGB", "Thermal"]:
            if c.lower() in user_message.lower():
                cap = c
                break
        if "maintenance" in user_message.lower():
            status = "Maintenance"
        result = query_drones(drones, capability=cap, status=status, location=location, exclude_maintenance=False)
        if not result:
            return "No drones match your criteria.", None
        lines = ["**Drone fleet:**\n"]
        for d in result:
            flag = " ⚠ Maintenance" if (d.get("status") or "").strip().lower() == "maintenance" else ""
            lines.append(
                f"- **{d.get('drone_id')}** {d.get('model')} | {d.get('status')}{flag} | "
                f"{d.get('location')} | {d.get('capabilities')} | Assignment: {d.get('current_assignment') or '–'}"
            )
        return "\n".join(lines), {"drones": result}

    if intent == "status_update":
        # e.g. "Set pilot P001 status to On Leave" or "Update drone D002 to Available"
        pilot_match = re.search(r"\b(P\d+)\b", user_message, re.I)
        drone_match = re.search(r"\b(D\d+)\b", user_message, re.I)
        new_status = None
        for s in ["Available", "On Leave", "Unavailable", "Assigned", "Maintenance"]:
            if s.lower() in user_message.lower():
                new_status = s
                break
        if pilot_match and new_status:
            pid = pilot_match.group(1).upper()
            ok, msg = update_pilot_status(pid, new_status)
            return msg if ok else f"Error: {msg}", None
        if drone_match and new_status:
            did = drone_match.group(1).upper()
            ok, msg = update_drone_status(did, new_status)
            return msg if ok else f"Error: {msg}", None
        return (
            "Please specify pilot (e.g. P001) or drone (e.g. D002) and the new status, e.g. "
            "*Set pilot P001 status to On Leave* or *Set drone D002 to Available*.",
            None,
        )

    if intent == "missions":
        if not missions:
            return "No missions loaded.", None
        lines = ["**Missions:**\n"]
        for m in missions:
            lines.append(
                f"- **{m.get('project_id')}** {m.get('client')} | {m.get('location')} | "
                f"{m.get('start_date')}–{m.get('end_date')} | Priority: {m.get('priority')}"
            )
        return "\n".join(lines), {"missions": missions}

    return (
        "I didn't quite get that. You can ask me about **pilots**, **drones**, **assignments**, "
        "**conflicts**, or **urgent reassignments**. Type *help* for examples.",
        None,
    )
