# Family Chore & Activity Board — Requirements

## Overview

Replace the physical whiteboard family chore/activity board with a
self-hosted digital version, displayed on a wall/fridge-mounted tablet.
The board shows a week-at-a-glance grid of chores and activities per
family member, with tap-to-check-off for chores.

## Background

Current state is a physical dry-erase board, week-of-Monday layout,
7 day columns, rows grouped into categories (Daily, Weekly, Sports today).
Each row is either:
- A checklist item assigned to "Both" kids or one specific kid, checked
  off by hand when done
- A timed activity (sports practice, etc.) with a start/end time, just
  informational, not checked off

## Goals

- Digital equivalent of the board, viewable and usable from across the
  kitchen on a wall/fridge-mounted tablet
- Kids can tap to check off their own chores, no login required
- Parents can edit tasks, categories, and assignments
- Self-hosted, no cloud dependency, runs on existing home lab (Tower)
- Tablet can toggle between this app and a second general web app

## Functional Requirements

### Software app

1. **Week grid view** — current week (Monday–Sunday) as the default/home
   view, matching the physical board's layout: rows grouped by category,
   columns are days.
2. **Categories are editable** — parents can add, rename, and reorder
   categories (not hardcoded to Daily/Weekly/Sports).
3. **Tasks** — recurring checklist items, each with a name, category,
   and recurrence pattern (which days it appears each week). Assigned to
   one person or "Both."
   - **Data model must support individual attribution later**, even
     though v1 behavior is "one tap on a Both task completes it for
     everyone." Store completions per-person (not one row per task), so
     a future change to "each kid checks their own" doesn't require a
     schema migration — only a UI/behavior change.
   - **Per-day overrides.** Each day a task appears must support
     overriding the default assignee and adding free-text detail for
     that specific day (e.g. "Vacuum" assigned to Rose by default, but
     Monday's instance says "Downstairs" and Thursday's says
     "Upstairs"; "Dog Doo" assigned to Rose on Tuesday and Ethan on
     Friday). A single fixed assignee/detail for the whole recurring
     task is not sufficient to reproduce the current board.
4. **Tap-to-check** — tapping a task cell marks it complete for that
   date; a "Both" task, when checked, marks it complete for both people
   at once (see individual-attribution note above — this is a v1
   behavior choice, not a hard data constraint).
   - **Undo.** Checking off a task must be reversible (un-tap to
     uncheck), same as erasing a mark on the physical board.
5. **Events** — timed sports/activities entered manually (name, person,
   day, start/end time), display-only, no completion tracking.
6. **People** — small fixed list of family members, each with a
   name/color for cell coloring, matching the board's colored-marker
   convention.
7. **Person selector / kid PIN before checking off.** Before tapping a
   task, the tablet requires selecting which person is acting (or a
   short per-kid PIN), so completions are attributable even without
   full login. This adds one step over the current tap-only flow but is
   needed since there's no persistent login session per kid.
8. **Parent PIN** — required for any admin action (editing tasks,
   categories, events, people). A parent PIN can also check off or
   uncheck any task for any kid, bypassing the normal person
   selector/kid PIN step.
9. **No CalDAV in v1** — events are manual entry only for now; CalDAV
   sync is an explicit future phase (see roadmap).
10. **Week rollover.** When a new week starts (Monday), the grid resets
    to fresh/unchecked for the new week, but prior weeks' completions
    are archived, not deleted — kept in the database for history rather
    than wiped. Recurring task definitions (name, category, default
    assignee) persist across weeks and are edited in place, since
    chores are mostly static once set; only per-day overrides and
    Events (sports/activities) are expected to change week to week.

### Hardware / kiosk

1. **Tablet** — Android tablet (e.g. Fire HD 10, Lenovo Tab) primary
   target; iPad is a possible alternative but has no direct equivalent
   to Fully Kiosk Browser (see hardware note below), so Android is the
   reference platform for kiosk behavior.
2. **Kiosk software** — Fully Kiosk Browser (Android), locked to this
   app's URL by default, with the toggle-to-a-second-URL feature and
   auto-reload configured. On iPad, Guided Access or a dedicated
   kiosk-browser App Store app would substitute, but does not support
   the same toggle gesture out of the box — treat iPad as a fallback
   option, not equally capable.
3. **Frontend must be kiosk-optimized, not general-purpose.** Locked
   viewport (no pinch-zoom), disabled text selection/callouts, no
   rubber-band scroll on iOS, large touch targets for check-off cells
   and PIN entry, and an auto-refresh interval so the tablet
   self-recovers from a stale view without manual intervention.
4. **Toggle to a second web app** — Fully Kiosk configured with a
   gesture/button shortcut to switch to a second, general-purpose URL
   and back. This is handled at the kiosk-software level, not built into
   the app itself.
5. **Cabling** — deferred decision; options under consideration are a
   painted/clipped cord along the fridge edge, a cord raceway, or a
   magnetic-dock/removable-charging approach. Not blocking for v1 since
   the app can be developed and tested before the physical mount is
   finalized.

## Non-Functional Requirements

- **Self-hosted** — runs in Docker on Tower (Unraid, 10.40.2.11),
  alongside existing homelab stacks
- **No cloud accounts required** for core functionality
- **Fast local load** — this is a kitchen kiosk, not a general web app;
  the week view should render quickly on tablet-class hardware
- **Readable from a few feet away** — legible at a glance, not a dense
  data table
- **Timezone-aware** — local day boundaries for week/date math
- **Offline/outage behavior** — if the tablet loses connectivity to Tower
  (e.g. during a homelab reboot), it keeps showing the most recently
  loaded view of the dashboard rather than a browser error page. Actual
  interaction (checking things off) will fail until connectivity
  returns, but the display doesn't go blank.

## Out of Scope (v1)

- CalDAV/ICS sync (deferred, see roadmap)
- Multi-family / multi-tenant support
- Real user authentication beyond a parent PIN
- Push notifications / email alerts
- Points, rewards, or gamification (that's the separate summer-chores app)

## Open Questions (not yet decided)

- Final cable-management approach for the tablet mount (not blocking —
  prototyping on an existing spare tablet first, see roadmap)
- Whether individual (non-"Both") attribution is ever actually turned on,
  or if the always-fan-out behavior is fine indefinitely
