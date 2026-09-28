# Family Chore & Activity Board — Roadmap

No hard deadline. Phased app-first, tablet/kiosk hardware after the app
is usable.

## Phase 1 — App MVP (software only) — v0.0.1–v0.0.2, mostly done

- FastAPI + SQLite + Jinja2 project scaffold (per CLAUDE.md)
- `Person`, `Category`, `Task`, `TaskCompletion`, `Event` models
  - `TaskCompletion` stored per-person even for "Both" tasks, so
    individual attribution can be turned on later without a migration
  - Per-day override support on task instances (assignee + free-text
    detail can differ by day, e.g. "Vacuum: Downstairs" Monday vs
    "Upstairs" Thursday)
- Seed data matching the current physical board (Ethan, Rose; Daily,
  Weekly, Sports categories; today's chores and known sports schedule)
- Week grid view at `/`, Monday-start, current week by default
- Tap-to-check for tasks, with undo (un-tap to uncheck) ✅ fixed in
  v0.0.2 — "Both" tasks now correctly complete/uncomplete for all kids
  together (all-or-nothing), rather than the earlier incomplete handling
- Person selector / short kid PIN gate before a check-off action ✅
  `/select_person` route implemented in v0.0.2 (previously referenced
  but missing), sets an http-only cookie; checkoff now validates the
  selected person matches the task's effective assignee for non-Both
  tasks
- Parent PIN gate for admin actions — **partial**: PIN check exists but
  currently plain cookie comparison, not signed/encrypted (see v0.0.3
  below); parent override-checkoff for any kid not yet built
- Manual create/edit for Events — **not yet built**; only seed/data
  manipulation today (see v0.0.3 below)
- Week rollover: new week starts fresh/unchecked; prior weeks'
  `TaskCompletion` history is retained (not deleted) for archival
- Kiosk-optimized frontend: touch targets ≥44px confirmed in v0.0.2;
  locked viewport / no-zoom / no-callout / no-rubber-band-scroll CSS
  still to verify against the CLAUDE.md kiosk checklist
- Docker deployment to Tower: `docker-compose` configured for GHCR
  (`ghcr.io/abateman121/family-calendar`) with the Unraid volume path;
  GitHub Actions workflow builds/pushes on tag ✅
- Version display (`v{{ version }}`, driven by a `VERSION` file) added
  in v0.0.2, shown on index/person/login/admin pages

**Exit criteria:** you can pull up the app in a browser and it fully
replaces checking the whiteboard for a normal week. **Not yet met** —
admin is currently read-only and Events can't be managed through the UI,
so a normal week still requires touching the database/seed data for
anything beyond checking off existing tasks.

## Phase 1.5 — v0.0.3: close the MVP gaps found in v0.0.2 review

Code review of v0.0.2 surfaced real gaps between "core loop works" and
"actually replaces the whiteboard day to day." These are the v0.0.3
scope, ahead of the previously-planned Phase 2 polish:

**Functional gaps (block real daily use):**
- Admin CRUD for People, Categories, Tasks, Events — admin panel is
  currently read-only; need add/edit/delete with validation and error
  handling
- Task management UI — creating/editing tasks and per-day overrides
  currently requires touching seed data directly
- Event management UI — no way to add/edit sports/activities through
  the UI yet, only via seed/data manipulation
- Parent override-checkoff — parent PIN should be able to check off or
  uncheck any task for any kid, per original requirements; not yet
  implemented

**Security hardening (should land before this is trusted for daily use):**
- Signed/encrypted cookies for parent PIN auth (FastAPI
  `SessionMiddleware` or equivalent) — current implementation is a
  plain cookie comparison
- CSRF protection for state-changing operations (checkoff, admin edits)
- PIN format validation (4–6 digits) on input

**Technical debt (lower urgency, but flagged so it isn't forgotten):**
- Alembic migrations — Implemented to handle schema changes via versioned migrations. [DONE]
- Basic test coverage: Implemented unit tests for model relationships and integration tests for `/checkoff` and `/login` routes, covering edge cases (double-checkoff, invalid inputs). [DONE]
- Structured logging — Implemented to provide structured application logs for debugging and monitoring. [DONE]

**Exit criteria:** a parent can fully manage the board (people,
categories, tasks, per-day overrides, events) through the UI with no
direct database/seed edits, parent PIN can override any kid's checkoff,
and the auth/CSRF gaps from the v0.0.2 review are closed. This is the
real Phase 1 exit criteria — treat v0.0.3 as still Phase 1, not Phase 2.