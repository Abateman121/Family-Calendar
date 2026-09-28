# Family Chore & Activity Board

A self-hosted FastAPI + SQLite web app that replicates a physical whiteboard family chore/activity board as a digital weekly view, for display on a wall/fridge-mounted Android tablet running Fully Kiosk Browser.

## Table of Contents
- [Overview](#overview)
- [Stack](#stack)
- [Features](#features)
- [Running the Application](#running-the-application)
- [Database Migrations](#database-migrations)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Roadmap](#roadmap)

## Overview

This application is a digital replacement for a physical whiteboard family chore/activity board. It provides a 7-day week view (Monday-Sunday) with rows grouped into categories (e.g., Daily, Weekly, Sports). Each cell shows who a task is assigned to ("Both" for all kids, or a specific kid) and optionally a time range for scheduled activities.

Chores can be tapped/checked off when completed, and sports/activities are displayed for informational purposes.

## Stack

- **FastAPI** - Async web framework for the backend
- **SQLAlchemy 2.x** - ORM with SQLite database (file stored at `data/family.db`)
- **Alembic** - Database migration management
- **Jinja2** - Server-rendered HTML templates (no JavaScript framework)
- **SessionMiddleware** (Starlette) - Handles parent PIN sessions for admin actions
- **Docker** - For easy deployment (see `Dockerfile` and `docker-compose.yml`)

## Features

- Week grid view with tasks grouped by category
- Task completion tracking per person per date (including per-person tracking for "Both" tasks)
- Per-day overrides for task assignee and details
- Event scheduling for timed activities (sports, classes, etc.)
- Kid PIN authentication for task checkoff (ensures accountability)
- Parent PIN authentication for administrative actions
- Admin interface for managing people, categories, tasks, and events
- Responsive design optimized for tablet/kiosk display
- Dockerized for easy deployment

## Running the Application

### Locally (Development)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the application:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. Open your browser to `http://localhost:8000`

### Using Docker

1. Build and start the container:
   ```bash
   docker compose up -d --build
   ```

2. The application will be available at `http://localhost:8000` (or whatever port is mapped)

### Database Initialization

On first start, the application automatically:
1. Runs Alembic migrations to create/upgrade the database schema
2. Seeds initial data if the database is empty (creates sample people, categories, tasks, and events)

## Database Migrations

This project uses Alembic for database schema migrations. The migration scripts are located in the `alembic/versions/` directory.

To create a new migration after modifying models:
```bash
alembic revision --autogenerate -m "Description of changes"
```

To apply migrations:
```bash
alembic upgrade head
```

Migrations are run automatically on application startup via the `init_db()` function in `app/database.py`.

## Testing

The project includes automated test coverage:
- **Unit tests** for model relationships (`tests/test_models.py`)
- **Integration tests** for key routes (`/checkoff`, `/login`) (`tests/test_routes.py`)

Tests are written using `pytest` and require the test dependencies listed in `requirements.txt`.

To run the test suite:
```bash
pytest
```
or
```bash
python -m pytest
```

## Project Structure

```
app/
  main.py          # All FastAPI routes
  database.py      # Database engine, session management, init_db (runs migrations)
  models.py        # SQLAlchemy table definitions
  seed.py          # Sample data population (runs migrations then seeds if empty)
  static/          # CSS, JavaScript, and images
  templates/       # Jinja2 HTML templates
alembic/           # Alembic migration configuration and scripts
  versions/        # Migration scripts
tests/             # Test suite
  conftest.py      # Test fixtures (database setup, test client)
  test_models.py   # Unit tests for models
  test_routes.py   # Integration tests for routes
```

## Configuration

The application can be configured using environment variables:

- `PARENT_PIN` - Parent PIN for administrative access (default: "1234")
- `SESSION_SECRET_KEY` - Secret key for session encryption (default: random)
- `TZ` - Timezone (defaults to system timezone, but set to "America/Los_Angeles" for Docker)

## Deployment

The application is designed for easy deployment via Docker. The `docker-compose.yml` file includes:

- Standard Unraid labels for integration with Docker Manager
- Environment variables for timezone and host identification
- Volume mapping for persistent data storage (`data/family.db`)

To deploy to Unraid or another Docker host:
1. Ensure the data directory is persisted (via volume or bind mount)
2. Set appropriate environment variables
3. Start the container with `docker compose up -d`

## Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed development plans and upcoming features.

## License

This project is open source and available for modification and redistribution.

---
*Built with FastAPI, SQLAlchemy, and Alembic. Designed for family chore management.*