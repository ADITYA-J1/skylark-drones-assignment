# Drone Operations Coordinator AI Agent

An AI agent that handles core responsibilities of a drone operations coordinator: roster management, assignment coordination, drone inventory, and conflict detection. Built for Skylark Drones with a conversational interface and 2-way Google Sheets sync.

## Features

- **Roster management** — Query pilots by skill, certification, location, status; view assignments; update pilot status (synced to Google Sheet or CSV).
- **Assignment tracking** — Match pilots and drones to projects; suggest assignments; handle reassignments; support urgent reassignments with conflict explanation.
- **Drone inventory** — Query fleet by capability, availability, location; track deployment; flag maintenance; update status (synced to sheet/CSV).
- **Conflict detection** — Double-booking (pilot/drone), skill/certification mismatch, drone in maintenance but assigned, pilot/drone location vs project.
- **Conversational UI** — Streamlit chat interface; rule-based intent routing; no OpenAI required (optional for richer NL).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit UI (app.py)                                           │
│  Chat input → run_agent() → Markdown reply                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────┐
│  Agent (src/agent.py)                                            │
│  Intent detection → Roster / Fleet / Assignments / Conflicts /    │
│  Urgent reassign / Status update / Confirm reassign              │
└───┬─────────┬─────────────┬──────────────┬────────────┬───────────┘
    │         │             │              │            │
    ▼         ▼             ▼              ▼            ▼
┌───────┐ ┌───────┐  ┌──────────────┐ ┌──────────┐ ┌──────┐
│roster │ │fleet  │  │assignments_  │ │conflicts │ │sync  │
│       │ │       │  │engine        │ │          │ │      │
└───┬───┘ └───┬───┘  └──────┬───────┘ └────┬─────┘ └──┬───┘
    │         │             │              │          │
┌───▼─────────▼─────────────▼──────────────▼──────────▼───┐
│  data_loader → Google Sheets (gspread) or local CSV      │
└──────────────────────────────────────────────────────────┘
```

- **Data:** Single source from `data_loader` (pilots, drones, missions, assignments). Reads from Google Sheets when configured, else CSV. Writes (pilot/drone status and assignment) go through `sync` to Sheet or CSV.
- **Logic:** Rule-based matching and conflict checks; no ML model required. Urgent reassignment uses least-impact selection (e.g. reassign pilot whose current project ends soonest).
- **Edge cases:** Overlapping dates, missing cert/skill, drone in maintenance assigned, location mismatch — all detected and reported.

## Project Structure

| Path | Purpose |
|------|--------|
| `app.py` | Streamlit entry point; chat UI and sidebar. |
| `config.py` | Env-based config (sheet IDs, credentials path, `USE_LOCAL_CSV`). |
| `src/agent.py` | Conversational agent; intent routing and orchestration. |
| `src/assignments_engine.py` | Match pilots/drones to missions; suggest assignment; urgent reassign. |
| `src/conflicts.py` | Detect double-booking, skill/cert, maintenance, location conflicts. |
| `src/roster.py` | Pilot queries (skill, cert, location, status). |
| `src/fleet.py` | Drone queries (capability, status, location, maintenance). |
| `src/data_loader.py` | Load pilots, drones, missions, assignments (Sheets or CSV). |
| `src/sheets_client.py` | Google Sheets read/write; worksheet by name; normalized headers. |
| `src/sync.py` | Write pilot/drone status and assignment back to Sheet or CSV. |
| `scripts/test_sheets_integration.py` | Tests CSV and (if configured) Google Sheets read/write. |
| `scripts/test_assignment_and_conflicts.py` | Tests assignment engine and all conflict edge cases. |
| `pilot_roster.csv`, `drone_fleet.csv`, `missions.csv` | Sample/local data. |

## Setup

### Local (CSV only)

1. Clone the repo.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`; keep `USE_LOCAL_CSV=true` (default).
4. Run: `streamlit run app.py`

### Google Sheets (2-way sync)

1. Create a Google Cloud project; enable **Google Sheets API**.
2. Create a service account; download JSON key; save as `credentials.json` in the project root (or set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`).
3. Create spreadsheets (or one workbook with multiple sheets) for Pilot Roster, Drone Fleet, Missions. Share with the service account email (Editor). Optionally create an Assignments sheet.
4. In `.env`: set `USE_LOCAL_CSV=false`, set `GOOGLE_SHEET_ID_PILOTS`, `GOOGLE_SHEET_ID_DRONES`, `GOOGLE_SHEET_ID_MISSIONS` (or a single `GOOGLE_SHEET_ID` with sheet names). See `.env.example` for sheet name vars.
5. Tab names must match (e.g. `Pilot Roster`, `Drone Fleet`, `Missions`). Headers can have spaces/casing; the app normalizes them.

## Usage

- **Run app:** `streamlit run app.py`
- **Tests:**  
  - `python scripts/test_sheets_integration.py`  
  - `python scripts/test_assignment_and_conflicts.py`

Example prompts: *Who is available in Bangalore?*, *Suggest assignment for PRJ001*, *Urgent reassignment for PRJ002*, *Check conflicts*, *Set pilot P001 status to On Leave*, *Confirm reassignment PRJ002 to P002 and D003*.

## Hosting

The app can be deployed to **Hugging Face Spaces** (Streamlit) or **Streamlit Community Cloud**. Set secrets for `GOOGLE_SHEET_ID_*`, `GOOGLE_APPLICATION_CREDENTIALS` (content of credentials JSON), and `USE_LOCAL_CSV=false` as needed. For CSV-only demo, use the included CSVs and `USE_LOCAL_CSV=true`.

## License

Assignment project for Skylark Drones.
