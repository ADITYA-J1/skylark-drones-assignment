"""
Configuration for Drone Operations Coordinator.
Google Sheet IDs and env vars are loaded here.
"""
import os
import re
from dotenv import load_dotenv

load_dotenv()


def _extract_sheet_id(value: str) -> str:
    """Extract sheet ID from env value (may be full URL or raw ID)."""
    if not value or not value.strip():
        return ""
    value = value.strip()
    # e.g. https://docs.google.com/spreadsheets/d/1ABC...xyz/edit
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", value)
    if m:
        return m.group(1)
    return value


# Google Sheets: set via env or use placeholder (user must replace)
GOOGLE_SHEET_ID_PILOTS = _extract_sheet_id(os.getenv("GOOGLE_SHEET_ID_PILOTS", ""))
GOOGLE_SHEET_ID_DRONES = _extract_sheet_id(os.getenv("GOOGLE_SHEET_ID_DRONES", ""))
GOOGLE_SHEET_ID_MISSIONS = _extract_sheet_id(os.getenv("GOOGLE_SHEET_ID_MISSIONS", ""))
GOOGLE_SHEET_ID_ASSIGNMENTS = _extract_sheet_id(os.getenv("GOOGLE_SHEET_ID_ASSIGNMENTS", ""))

# Optional: single workbook with multiple sheets (sheet names)
SINGLE_SHEET_ID = _extract_sheet_id(os.getenv("GOOGLE_SHEET_ID", ""))
SHEET_NAME_PILOTS = os.getenv("SHEET_NAME_PILOTS", "Pilot Roster")
SHEET_NAME_DRONES = os.getenv("SHEET_NAME_DRONES", "Drone Fleet")
SHEET_NAME_MISSIONS = os.getenv("SHEET_NAME_MISSIONS", "Missions")
SHEET_NAME_ASSIGNMENTS = os.getenv("SHEET_NAME_ASSIGNMENTS", "Assignments")

# Credentials path (service account JSON or OAuth)
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")

# OpenAI for conversational agent (optional; can run rule-based only)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Fallback: use local CSV when Sheets not configured
USE_LOCAL_CSV = os.getenv("USE_LOCAL_CSV", "true").lower() == "true"
