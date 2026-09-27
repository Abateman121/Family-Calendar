import os
import datetime
import secrets
from typing import List, Optional, Set, Dict, Tuple
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session, selectinload
from . import database, models

app = FastAPI()
# Add session middleware with a secret key (should be from env in production)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", secrets.token_hex(32)))

templates = Jinja2Templates(directory="app/templates")

# Read version from VERSION file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_PATH = os.path.join(BASE_DIR, "..", "VERSION")
with open(VERSION_PATH, "r") as f:
    APP_VERSION = f.read().strip()

def render_template(request: Request, template_name: str, context: dict):
    """Render a template with the app version and CSRF token injected."""
    context.setdefault("version", APP_VERSION)
    # Generate or retrieve CSRF token from session
    if "csrf_token" not in request.session:
        request.session["csrf_token"] = secrets.token_hex(32)
    context.setdefault("csrf_token", request.session["csrf_token"])
    return templates.TemplateResponse(template_name, {**context, "request": request})

def get_kid_ids(db: Session) -> List[int]:
    """Return list of person IDs that have a kid PIN (i.e., are kids)."""
    return [p.id for p in db.query(models.Person).filter(models.Person.kid_pin.isnot(None)).all()]

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Parent PIN from environment (default for dev)
PARENT_PIN = os.getenv("PARENT_PIN", "1234")

# Helper to get Monday of current week (based on local timezone)
def get_current_monday(base_date: Optional[datetime.date] = None) -> datetime.date:
    if base_date is None:
        base_date = datetime.date.today()
    # Monday is weekday 0
    monday = base_date - datetime.timedelta(days=base_date.weekday())
    return monday

def get_week_dates(monday: datetime.date) -> List[datetime.date]:
    return [monday + datetime.timedelta(days=i) for i in range(7)]

# Utility to check parent authentication via session
def parent_authenticated(request: Request):
    return request.session.get("parent_authenticated", False)

# Dependency for parent auth
def get_parent_auth(request: Request):
    if not parent_authenticated(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parent authentication required")
    return True

# CSRF protection dependency
def csrf_protect(request: Request):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        token = request.form.get("csrf_token") if hasattr(request, "form") else None
        # For non-form data, we could also check header; but we rely on form
        if not token or token != request.session.get("csrf_token"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")

@app.get("/", response_class=HTMLResponse)
async def week_view(
    request: Request,
    db: Session = Depends(get_db)
):
    monday = get_current_monday()
    week_dates = get_week_dates(monday)
    # Fetch data with eager loading to avoid N+1
    persons = db.query(models.Person).order_by(models.Person.name).all()
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    tasks = db.query(models.Task).options(
        selectinload(models.Task.days),
        selectinload(models.Task.default_assignee),
        selectinload(models.Task.category)
    ).all()
    # For simplicity, fetch all task completions for the week
    completions = db.query(models.TaskCompletion).filter(
        models.TaskCompletion.date >= monday,
        models.TaskCompletion.date < monday + datetime.timedelta(days=7)
    ).all()
    # Map completions for quick lookup: (task_id, date) -> set of person_ids
    completion_map: Dict[Tuple[int, datetime.date], Set[int]] = {}
    for c in completions:
        key = (c.task_id, c.date)
        if key not in completion_map:
            completion_map[key] = set()
        completion_map[key].add(c.person_id)
    # Build task day instances with overrides and completion status
    # We'll prepare a dict: task_id -> list of day info for 0-6
    task_day_map: Dict[int, List[Dict]] = {}
    completed_set: Set[Tuple[int, datetime.date]] = set()
    for task in tasks:
        day_list = []
        for day_idx in range(7):
            day_override = None
            for day in task.days:
                if day.day_of_week == day_idx:
                    day_override = day
                    break
            # Determine effective assignee for this day
            if day_override and day_override.assignee_person_id is not None:
                eff_assignee_id = day_override.assignee_person_id
                is_both = False
                detail = day_override.detail
            else:
                # No override, use task defaults
                if task.assigned_to_both:
                    eff_assignee_id = None  # signifies Both
                    is_both = True
                else:
                    eff_assignee_id = task.default_assignee_person_id
                    is_both = False
                detail = None
            day_list.append({
                "day_idx": day_idx,
                "eff_assignee_id": eff_assignee_id,
                "is_both": is_both,
                "detail": detail,
            })
            # Determine if this task-date is considered completed
            key = (task.id, monday + datetime.timedelta(days=day_idx))
            completed = False
            if is_both:
                # Both task: completed if any kid has completed it
                kid_ids = set(get_kid_ids(db))
                completed_set_for_task = completion_map.get(key, set())
                completed = len(kid_ids.intersection(completion_set_for_task)) > 0
            else:
                # Specific assignee: completed if that person has completed it
                if eff_assignee_id is not None:
                    completed = eff_assignee_id in completion_map.get(key, set())
                else:
                    # No assignee (should not happen)
                    completed = False
            if completed:
                completed_set.add(key)
        task_day_map[task.id] = day_list

    # Events for week (recurring by day_of_week)
    events = db.query(models.Event).all()
    # Group events by day_of_week
    events_by_day = {i: [] for i in range(7)}
    for ev in events:
        events_by_day[ev.day_of_week].append(ev)

    parent_ok = request.session.get("parent_authenticated", False)
    return render_template(
        request,
        "index.html",
        {
            "request": request,
            "monday": monday,
            "week_dates": week_dates,
            "persons": persons,
            "categories": categories,
            "tasks": tasks,
            "task_day_map": task_day_map,
            "completed_set": completed_set,
            "parent_ok": parent_ok,
        }
    )

@app.get("/person", response_class=HTMLResponse)
async def person_selector(request: Request):
    db = database.SessionLocal()
    try:
        persons = db.query(models.Person).filter(models.Person.kid_pin.isnot(None)).all()
    finally:
        db.close()
    return render_template(
        request,
        "person.html",
        {"persons": persons}
    )

@app.post("/verify_pin")
async def verify_pin(request: Request, person_id: int = Form(...), pin: str = Form(...)):
    db = database.SessionLocal()
    try:
        person = db.query(models.Person).filter(models.Person.id == person_id).first()
        if not person or person.kid_pin is None or not secrets.compare_digest(person.kid_pin, pin):
            # For security, use constant-time comparison
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PIN")
        # Successful verification
        request.session["authenticated_person_id"] = person.id
        # Set a cookie for client-side JS to know the selected person (not secret)
        response = RedirectResponse(url=request.headers.get("referer") or "/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="person_id", value=str(person.id), httponly=False, max_age=60*60*24*30)  # 30 days
        return response
    finally:
        db.close()

@app.post("/checkoff")
async def checkoff_task(
    request: Request,
    task_id: int = Form(...),
    date_str: str = Form(...),  # YYYY-MM-DD
    db: Session = Depends(get_db)
):
    # Determine person_id from session (must be authenticated via PIN)
    person_id = request.session.get("authenticated_person_id")
    if person_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Person not authenticated via PIN")
    # Verify task exists
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    date_obj = datetime.date.fromisoformat(date_str)
    # Get day override for this task/date
    day_override = None
    for day in task.days:
        if day.day_of_week == date_obj.weekday() and day.assignee_person_id is not None:
            day_override = day
            break
    # Determine effective assignee for this day
    if day_override and day_override.assignee_person_id is not None:
        eff_assignee_id = day_override.assignee_person_id
        is_both = False
    else:
        # No override, use task defaults
        if task.assigned_to_both:
            eff_assignee_id = None  # signifies Both
            is_both = True
        else:
            eff_assignee_id = task.default_assignee_person_id
            is_both = False
    # For non-Both tasks, ensure the authenticated person matches the effective assignee
    if not is_both:
        if eff_assignee_id is None:
            raise HTTPException(status_code=400, detail="Task has no assignee")
        if person_id != eff_assignee_id:
            raise HTTPException(status_code=403, detail="Authenticated person does not match task assignee")
    # For Both tasks, any authenticated kid can tap (all-or-nothing)
    if is_both:
        kid_ids = get_kid_ids(db)
        if not kid_ids:
            raise HTTPException(status_code=400, detail="No kids defined")
        # Determine current completion state for this task-date across all kids
        existing = db.query(models.TaskCompletion).filter(
            models.TaskCompletion.task_id == task_id,
            models.TaskCompletion.date == date_obj,
            models.TaskCompletion.person_id.in_(kid_ids)
        ).all()
        existing_ids = {c.person_id for c in existing}
        if existing_ids:
            # There are existing completions -> uncheck (delete all)
            db.query(models.TaskCompletion).filter(
                models.TaskCompletion.task_id == task_id,
                models.TaskCompletion.date == date_obj,
                models.TaskCompletion.person_id.in_(kid_ids)
            ).delete(synchronize_session=False)
            action = "unchecked"
        else:
            # No existing completions -> check (insert all)
            for kid_id in kid_ids:
                completion = models.TaskCompletion(
                    task_id=task_id,
                    date=date_obj,
                    person_id=kid_id,
                    completed_at=datetime.datetime.utcnow()
                )
                db.add(completion)
            action = "checked"
    else:
        # Specific assignee: toggle completion for that person
        existing = db.query(models.TaskCompletion).filter(
            models.TaskCompletion.task_id == task_id,
            models.TaskCompletion.date == date_obj,
            models.TaskCompletion.person_id == person_id
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
            action = "unchecked"
        else:
            completion = models.TaskCompletion(
                task_id=task_id,
                date=date_obj,
                person_id=person_id,
                completed_at=datetime.datetime.utcnow()
            )
            db.add(completion)
            db.commit()
            action = "checked"
    # Redirect back to referring page or home
    referer = request.headers.get("referer") or "/"
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return render_template(request, "login.html", {})

@app.post("/login")
async def login_submit(parent_pin: str = Form(...), response: Response = None):
    if parent_pin == PARENT_PIN:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="parent_auth", value=PARENT_PIN, httponly=True)
        return response
    else:
        return render_template(
            request,
            "login.html",
            {"error": "Invalid PIN"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

# Removed /select_person route as verification is done via /verify_pin

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    parent_ok: bool = Depends(parent_authenticated),
    db: Session = Depends(get_db)
):
    if not parent_ok:
        return RedirectResponse(url="/login")
    persons = db.query(models.Person).all()
    categories = db.query(models.Category).all()
    tasks = db.query(models.Task).all()
    events = db.query(models.Event).all()
    return render_template(
        request,
        "admin.html",
        {
            "request": request,
            "persons": persons,
            "categories": categories,
            "tasks": tasks,
            "events": events,
        }
    )

# Additional CRUD routes can be added later...