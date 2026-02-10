# Decision Log — Drone Operations Coordinator

## Key Assumptions

1. **Data shape** — Pilot roster has at least: pilot_id, name, skills, certifications, location, status, current_assignment (and optionally available_from). Drone fleet: drone_id, model, capabilities, status, location, current_assignment, maintenance_due. Missions: project_id, client, location, required_skills, required_certs, start_date, end_date, priority. Extra columns are allowed; headers are normalized (strip, lowercase, spaces → underscore) for Sheets.

2. **Single source of truth** — At runtime, data is read once per user message from Sheets or CSV. There is no in-memory cache layer; each request reflects current sheet/CSV state. Writes (status/assignment updates) go through the sync layer and are persisted immediately.

3. **Assignments** — Assignments can come from (a) an optional Assignments sheet/CSV, or (b) derivation from pilots’ and drones’ current_assignment plus mission dates. Drone assignments from the fleet’s current_assignment are merged in for conflict detection and matching. No separate “assignment store” is required if roster/fleet and missions are enough.

4. **Urgent reassignments** — Interpreted as priority-based overrides: when a mission is Urgent (or the user asks for urgent reassignment), the system may suggest reassigning a pilot or drone already assigned elsewhere. The “least impact” choice (e.g. pilot whose current project ends soonest) is preferred, and all overrides are explained to the user. Applying the reassignment is a separate step (confirm or status update).

5. **No schema changes by the agent** — The agent does not create or rename columns or sheets. It only reads and updates existing cells (status, current_assignment). Evaluators can use their own sheet structure as long as the expected column names (or normalized equivalents) exist.

---

## Trade-offs Chosen and Why

| Decision | Trade-off | Why |
|----------|-----------|-----|
| Rule-based intent instead of LLM | Less flexible phrasing; no open-ended NL | Evaluator can run without API keys; deterministic; fast and cheap. Intent keywords cover the required flows. |
| Google Sheets + CSV fallback | Two code paths; sheet names must match | Lets evaluators run without Sheets (CSV) and still demo 2-way sync when Sheets is configured. Explicit worksheet-by-name avoids “first tab only” bugs. |
| Normalized headers (strip, lowercase, underscores) | Sheet headers like “Pilot ID” become “pilot_id” in code | One consistent key set for roster/fleet/conflicts; tolerates spaces and casing differences across environments. |
| Conflict detection as separate pass | Not blocking assignment suggestion | User sees conflicts and can still request suggestions; urgent reassignment can override. Aligns with “detect and explain” rather than hard blocks. |
| Urgent = suggest + explain, confirm separate | Reassignment not auto-applied | Reduces risk of unintended overwrites; user explicitly confirms or uses status/assignment updates. Decision is logged in this document. |
| Assignments optional sheet | Sometimes only roster + missions used | Works when Assignments tab is missing or empty; derivation from current_assignment is sufficient for matching and conflicts. |

---

## What I’d Do Differently With More Time

1. **Structured assignment store** — Persist suggested/urgent assignments in a small store (e.g. extra sheet or SQLite) so “confirm reassignment” has a single place to read proposed state and apply it, with audit trail.

2. **Richer NL** — Add an optional OpenAI (or local) LLM step to parse free-form requests into structured filters (location, skills, dates) and keep the rest rule-based. Would improve “find me someone in Mumbai who can do thermal and has night ops” without changing core logic.

3. **Availability windows** — Use `available_from` (and optional `available_until`) explicitly in matching so pilots on leave or with future start dates are filtered correctly by date, not only by status.

4. **Tests with real Sheets** — CI job that uses a test Google Sheet (with service account secret) to run integration tests and assert row counts and conflict detection on fixed data.

5. **i18n and validation** — Validate status and assignment values against allowed enums before writing; optional localization for messages.

---

## Interpretation of “Urgent Reassignments”

**Chosen interpretation:** Urgent reassignments are **priority-based overrides** with **explicit conflict explanation** and **least-impact selection**.

- **Priority override:** When a mission is marked Urgent (or the user asks for “urgent reassignment for PRJ002”), the system may suggest a pilot or drone who is already assigned. That suggestion is an override of normal “available only” matching.
- **Least impact:** Among qualified pilots at the right location with skills/certs, we prefer (1) available pilots, then (2) assigned pilots whose current project ends soonest, so the override displaces as little as possible.
- **Conflict explanation:** The agent replies with who is suggested, from which project they would be reassigned, and any caveats (e.g. drone in maintenance). The user then confirms (e.g. “Confirm reassignment PRJ002 to P002 and D003”) or applies changes via status/assignment updates.
- **Decision logged here:** Reassignment is not applied automatically; the agent suggests and explains, and the user or a separate “confirm” step applies the change. This is documented in the Decision Log as required.

This keeps urgent reassignments auditable and safe while still allowing the coordinator to act quickly with one confirmation step.
