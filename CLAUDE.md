# CLAUDE.md

Guidance for Claude Code when working on this repo.

## What this is

A self-hosted FastAPI + SQLite web app that replicates a physical whiteboard
family chore/activity board as a digital weekly view, for display on a
wall/fridge-mounted Android tablet running Fully Kiosk Browser. Greenfield
project.

The board it replicates: a 7-day week view with rows grouped into
categories (Daily, Weekly, Sports, etc.), each row a task or activity,
each cell showing who it's assigned to ("Both" or a specific kid) and
optionally a time range (e.g. sports practice). Chores get tapped/checked
off when done. Sports/activities are just displayed, not checkable.

## Stack

- **FastAPI** (async web framework)
- **SQLAlchemy 2.x** ORM with **SQLite** (file at `data/family.db`)
- **Jinja2** templates (server-rendered HTML, no JS framework)
- **SessionMiddleware** (Starlette) for the parent PIN session, if/when
  parent-only editing is added
- **Docker** for deployment (`Dockerfile` + `docker-compose.yml`), deployed
  on Tower (Unraid, 10.40.2.11) alongside the rest of the homelab stack

## Project layout

```
app/
  main.py          # ALL routes live here
  database.py      # engine, SessionLocal, get_db, init_db
  models.py        # SQLAlchemy tables
  seed.py          # example data on empty DB
  static/          # style.css, app.js, icons/
  templates/       # Jinja2 pages
```

## Categories are user-editable

Categories (Daily, Weekly, Sports on the current board) are a real table,
not a hardcoded list — `Category` (id, name, sort_order). Tasks and Events
both reference a `category_id`. Build the seed data with these three, but
the app must support adding/renaming/reordering categories from the start,
not as a deferred feature.

## Key conventions

1. **Single-file routing.** All FastAPI routes are in `app/main.py`. Split
   out per-resource routers only if this gets big.

2. **Week-grid data model, not calendar-event model.** The core view is a
   grid: rows = tasks/activities (grouped by category), columns = the 7
   days of the current week. This is NOT a CalDAV/ICS event model — most
   rows have no fixed date, they recur every week on a pattern (which
   days it appears). Model it as a `Task` (name, category, default
   assignee) plus a `TaskDayInstance`-style concept (which days it
   appears, with optional per-day override of assignee and a free-text
   detail field — e.g. "Vacuum" defaults to Rose, but Monday's instance
   overrides detail to "Downstairs" and Thursday's to "Upstairs"; "Dog
   Doo" overrides assignee to Rose on Tuesday and Ethan on Friday). Then
   `TaskCompletion` (task_id, date, person_id, completed_at) — one row
   per person per date, even for "Both" tasks (see point 4 below) —
   analogous to the summer-app's `Chore` / `ChoreCompletion` split, but
   with per-day override support the summer app doesn't need.
   Timed sports/activities are a separate simpler model: a `family_id`-less
   `Event` (name, person, day-of-week or specific date, start_time,
   end_time) — no completion tracking, just display. Events are entered
   manually for now (see "Deferred: CalDAV sync" below) — do not build
   any CalDAV/ICS integration yet.

3. **Denormalize completion state, don't infer it.** A `TaskCompletion`
   row is written when a kid taps a cell to check it off, one row per
   (task, date, person) — including one row per person for a "Both" task
   (see point 4). Don't try to compute "done" from anything else. Un-
   tapping (undo) deletes the corresponding row(s) rather than soft-
   flagging them — this mirrors the summer-app's rule of capturing state
   at event time, but completion here must also be reversible, unlike
   the summer app's append-only completion log.

4. **Family members are a small fixed table, not full user accounts.**
   `Person` (id, name, color, kid_pin) — used for cell coloring/initials
   (matching the whiteboard's colored-marker convention) and for a short
   PIN selector step before checking off a task, so completions are
   attributable to a specific kid without a persistent login session.

   **"Both" is a UI special case, not a `Person` row.** A `Task` (or a
   given day's instance of it) can be assigned to a specific `Person` or
   flagged `assigned_to_both = True`. When a "Both" task is checked off,
   write a `TaskCompletion` per real person for that date (i.e. one
   check-off action completes it for everyone) — v1 behavior, not a
   data constraint. Because `TaskCompletion` is already per-person (see
   point 2/3), switching "Both" tasks to require each person to check
   off individually later is a UI/behavior change only, not a schema
   migration — don't undermine this by ever writing a single shared
   completion row for a "Both" task.

5. **Parent PIN gates admin actions and can override kid check-offs.** A
   separate, longer parent PIN (distinct from each kid's short PIN)
   gates create/edit/delete of tasks, categories, events, and people.
   The parent PIN can also check off or uncheck any task for any kid,
   bypassing the normal kid-PIN selector step.

6. **Week boundary is Monday-start.** Match the physical board (Monday
   through Sunday, "Week of" a Monday date). `TZ` env var resolves local
   day boundaries, same pattern as the summer app's `_local_tz()`. On
   rollover to a new week, the grid shows fresh/unchecked state, but
   `TaskCompletion` rows from prior weeks are never deleted — they stay
   in SQLite as history/archive (no separate archival store or DB
   engine needed; this data is small and low-write). `Task` definitions
   (name, category, default assignee) persist across weeks and are
   edited in place rather than recreated weekly, since chores are
   mostly static; per-day overrides and `Event` rows are the parts
   expected to change week to week.

7. **Two toggleable views on one tablet.** The tablet runs Fully Kiosk
   Browser and needs to switch between this app's week view and a second
   arbitrary URL (a general web app, TBD). Build the week view as a clean
   standalone page at `/` with no navigation chrome that assumes it's the
   only app — kiosk-level toggling is handled by Fully Kiosk, not by this
   app, so don't build in-app tabs for it unless asked.

8. **Offline/stale-view behavior.** The tablet should keep showing its
   most recently loaded view if it can't reach the server (e.g. during a
   Tower reboot), rather than falling back to a browser error page.
   Simplest approach: rely on the browser tab staying rendered until a
   real navigation/reload happens (Fully Kiosk's reload interval is a
   kiosk-level setting, not something this app needs to implement), but
   keep this in mind if a reload-on-interval or service-worker approach
   is added later — don't add a fetch failure state that blanks the
   page.

9. **Optimize the frontend for kiosk display, not general browsing.**
   This page runs full-screen, unattended, for hours at a time on
   tablet-class hardware (including old/low-spec Android tablets). Keep
   it cheap to render and refresh:
   - No client-side framework, minimal JS. Server-rendered HTML +
     small `app.js` only.
   - Viewport meta tag locked (`width=device-width, initial-scale=1,
     maximum-scale=1, user-scalable=no`) — this is a kiosk display, not
     a page users pinch-zoom.
   - Disable text selection and touch callouts via CSS
     (`user-select: none`, `-webkit-touch-callout: none`) so accidental
     long-presses don't pop up selection handles or context menus.
   - Avoid rubber-band/bounce scroll on iOS Safari
     (`overscroll-behavior: none` / `position: fixed` body pattern) —
     the whole point is a static grid, not a scrolling page.
   - Large touch targets for check-off cells and the PIN pad (kids,
     kitchen, imprecise taps) — minimum ~44px per platform guidance,
     bigger where the layout allows.
   - Auto-refresh the page on an interval (e.g. meta refresh or a small
     JS `setInterval` reload) so the tablet self-recovers from a stale
     view once connectivity returns, rather than relying only on manual
     reload — pair with the offline/stale-view behavior in point 8.
   - Keep the page awake: this is a display appliance, not a device
     someone is holding, so whatever kiosk shell is used (see platform
     notes below) needs to disable screen sleep/timeout at the OS level;
     don't try to solve this in-app with JS wake-lock hacks as the
     primary mechanism, since kiosk-mode apps handle this more reliably.

## Platform notes: Android vs iPad kiosk

The two platforms need different kiosk shells — don't assume one
approach covers both:

- **Android**: Fully Kiosk Browser (as used elsewhere in this project)
  — locks to a URL, disables sleep, supports the toggle-to-a-second-URL
  requirement, auto-reloads on a schedule, auto-relaunches if it
  crashes. This is the primary/reference platform for this project.
- **iPad**: no Fully-Kiosk equivalent. Options if an iPad is ever used
  instead of/alongside the Android tablet:
  - **Guided Access** (built into iOS) locks the iPad to a single app
    (e.g. Safari showing this page) but has no built-in
    auto-reload-on-interval or toggle-to-a-second-app gesture — a
    hardware triple-click is required to exit Guided Access, which
    breaks the "toggle to a general web app" requirement.
  - A dedicated kiosk-browser app from the App Store (e.g. one that
    supports a configured URL + auto-reload + multiple pinned URLs)
    would be needed to match the Android toggle behavior.
  - If the family standardizes on Android, this whole section is moot
    — noting it here so it's not silently forgotten if an iPad is ever
    substituted in.

- Docker: `docker compose up -d --build` then http://localhost:8000
- Local: `pip install -r requirements.txt && uvicorn app.main:app --reload`
- First start auto-creates `data/family.db` and seeds people, categories,
  and example tasks matching the current physical board.

## Docker Compose standards (match existing Tower stacks)

- Omit the top-level `version` attribute (obsolete, causes warnings)
- Include labels: `net.unraid.docker.managed: "dockerman"`,
  `net.unraid.docker.webui`, `net.unraid.docker.icon`, `folder.view2`
- Include env vars: `TZ: "America/Los_Angeles"`, `HOST_OS: "Unraid"`,
  `HOST_HOSTNAME: "Tower"`, `HOST_CONTAINERNAME`
- Appdata path: `/mnt/cache/appdata/` (this isn't a media-stack service, so
  not the `_sp` speedy pool)

## Things NOT to do

- Do NOT model this on CalDAV/ICS events. Most rows are recurring
  checklist items with no real "date," not timed calendar events. Only
  the Sports/Events section has real start/end times.
- Do NOT add a JS framework. Server-rendered pages; a small `app.js` for
  tap-to-check AJAX calls is enough.
- Do NOT build kid PINs as a real auth/session system. It's a short PIN
  used once per check-off action to attribute who tapped it, not a login
  — no session tokens, no "logged in as Rose" persistent state.
- Do NOT write a single shared `TaskCompletion` row for a "Both" task.
  Always write one row per person, even though v1 UI treats a "Both" tap
  as completing it for everyone — this keeps individual attribution
  possible later without a migration.
- Do NOT build kiosk-toggle logic (switching to the second web app) inside
  this app. That's Fully Kiosk Browser's job at the OS/browser level.

## Deferred: CalDAV sync for Events

Not built yet, but planned. Eventually `Event` rows should be able to sync
from a self-hosted CalDAV calendar (Nextcloud or Radicale on Tower) instead
of only manual entry, so sports/activities can be added from a phone
calendar app and show up on the board automatically. When picked up:

- Keep manual `Event` entry working regardless — CalDAV should be an
  additional source, not a replacement.
- Add a `source` field on `Event` (`"manual"` vs `"caldav"`) so synced
  events aren't accidentally hand-edited and overwritten on next sync.
- Sync approach (pull on a schedule vs. on page load) is an open question
  for when this is actually built — don't design it prematurely now.
