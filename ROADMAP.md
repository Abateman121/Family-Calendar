# Family Chore & Activity Board — Roadmap

No hard deadline. Phased app-first, tablet/kiosk hardware after the app
is usable.

## Phase 1 — App MVP (software only)

Goal: a working week-grid app you can view in a browser on a laptop/phone,
before any tablet purchase or mounting decisions.

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
- Tap-to-check for tasks, including "Both" fan-out to both people, with
  undo (un-tap to uncheck)
- Person selector / short kid PIN gate before a check-off action, so
  completions are attributable
- Parent PIN gate for admin actions (create/edit tasks, events, people);
  parent PIN can also check off or uncheck any task for any kid
- Manual create/edit for Events (name, person, day, start/end time)
- Week rollover: new week starts fresh/unchecked; prior weeks'
  `TaskCompletion` history is retained (not deleted) for archival
- Kiosk-optimized frontend from the start: locked viewport, no
  pinch-zoom, no text-selection/callout popups, no iOS rubber-band
  scroll, large touch targets, auto-refresh interval
- Docker deployment to Tower, matching existing compose conventions

**Exit criteria:** you can pull up the app in a browser and it fully
replaces checking the whiteboard for a normal week.

## Phase 2 — Category management & polish

- Category management UI: add/rename/reorder categories, with tasks and
  events correctly re-grouping (this is more involved than a v1 checkbox
  — reordering affects nested tasks and events tied to a category, so
  it's its own line rather than bundled into Phase 1)
- Task recurrence editing UI (change which days a task appears, edit
  per-day overrides, without touching the database directly)
- Visual pass: legibility from across the kitchen, color coding per
  person, category grouping styling
- Week navigation (view past/future weeks, read-only, pulling from
  archived history)

**Exit criteria:** you're not touching the database directly to make
changes; a parent can manage the board entirely through the UI.

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
