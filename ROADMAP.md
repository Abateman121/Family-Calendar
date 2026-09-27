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
- Alembic migrations — `Base.metadata.create_all()` is fine for now but
  won't handle schema changes once real data exists in the DB
- `/health` endpoint for Docker healthcheck
- Basic test coverage: model relationships, `/checkoff` and `/login`
  routes, edge cases (double-checkoff, invalid person/task IDs)
- Structured logging

**Exit criteria:** a parent can fully manage the board (people,
categories, tasks, per-day overrides, events) through the UI with no
direct database/seed edits, parent PIN can override any kid's checkoff,
and the auth/CSRF gaps from the v0.0.2 review are closed. This is the
real Phase 1 exit criteria — treat v0.0.3 as still Phase 1, not Phase 2.

## Phase 2 — Category management & polish

- Category management UI: add/rename/reorder categories, with tasks and
  events correctly re-grouping (reordering affects nested tasks and
  events tied to a category — this may end up partially delivered as
  part of the v0.0.3 admin CRUD work above; confirm reordering
  specifically still needs its own pass)
- Task recurrence editing UI refinements beyond basic CRUD (bulk edits,
  friendlier per-day override editing)
- Visual pass: legibility from across the kitchen, color coding per
  person, category grouping styling
- Week navigation (view past/future weeks, read-only, pulling from
  archived history)
- Full kiosk CSS checklist verification: locked viewport, no
  pinch-zoom, no text-selection/callout popups, no iOS rubber-band
  scroll, auto-refresh interval

**Exit criteria:** you're not touching the database directly to make
any change, including category reordering and bulk task edits; a parent
can manage the board entirely through the UI with kiosk-grade polish.

## Phase 3 — Tablet & kiosk

- Prototype now on the spare/old tablet already on hand — no purchase
  needed to start this phase (Android is the reference platform; if the
  spare tablet is an iPad, note that Fully Kiosk has no direct iPad
  equivalent — see CLAUDE.md platform notes)
- Install Fully Kiosk Browser (Android) or configure Guided Access /
  a kiosk-browser app (iPad), point it at the Phase 1/2 app
- Configure the toggle gesture/button to a second general web app
- Resolve cable management (deferred decision — cord raceway, painted
  cable run, or removable/dock charging; not blocking since the spare
  tablet can be tested unmounted first)
- Confirm always-on behavior (screen timeout disabled, auto-restart on
  power blip, kiosk auto-relaunch if the browser crashes)
- Confirm offline behavior in practice: tablet keeps showing last-loaded
  view during a Tower outage rather than an error page

**Exit criteria:** tablet is mounted on/near the fridge, always showing
the current week, and reliably survives day-to-day kitchen use.

## Phase 4 — CalDAV sync (deferred feature)

- Stand up Nextcloud or Radicale on Tower as a CalDAV backend, if not
  already running
- Add `source` field to `Event` (manual vs. caldav), per CLAUDE.md
- Build the sync (pull schedule vs. on-page-load — decide at this point,
  not before)
- Keep manual event entry working as a permanent fallback

**Exit criteria:** sports/activities added from a phone calendar app show
up on the board automatically, without breaking manually-entered events.

## Not currently planned

- Points/rewards/gamification — that's the separate summer-chores app,
  not this one
- Multi-family support, real auth, push notifications — out of scope per
  requirements
