import logging
import logging.config
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

# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'INFO',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': False
        },
        'app': {
            'handlers': ['default'],
            'level': 'INFO',
            'propagate': False
        },
        'uvicorn.error': {
            'level': 'INFO'
        },
        'uvicorn.access': {
            'level': 'INFO',
            'handlers': ['default'],
            'propagate': False
        },
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger('app')

app = FastAPI()
logger.info("Starting Family Chore & Activity Board application")
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

@app.on_event("startup")
async def startup_event():
    """Run database migrations on startup."""
    logger.info("Running database migrations on startup")
    from .database import init_db
    init_db()
    logger.info("Database migrations completed")

@app.get("/", response_class=HTMLResponse)
async def week_view(
    request: Request,
    db: Session = Depends(get_db)
):
    logger.debug("Rendering week view")
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
    logger.debug("Rendering week view with %d persons, %d categories, %d tasks, %d events", len(persons), len(categories), len(tasks), len(events))
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
    logger.debug("Rendering person selector")
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
    logger.info("PIN verification attempt for person_id=%s", person_id)
    db = database.SessionLocal()
    try:
        person = db.query(models.Person).filter(models.Person.id == person_id).first()
        if not person or person.kid_pin is None or not secrets.compare_digest(person.kid_pin, pin):
            # For security, use constant-time comparison
            logger.warning("Failed PIN verification for person_id=%s", person_id)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PIN")
        # Successful verification
        logger.info("Successful PIN verification for person_id=%s", person_id)
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
    logger.info("Checkoff attempt for task_id=%s, date=%s", task_id, date_str)
    # Determine person_id from session (must be authenticated via PIN)
    person_id = request.session.get("authenticated_person_id")
    if person_id is None:
        logger.warning("Checkoff attempt without person authentication")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Person not authenticated via PIN")
    # Verify task exists
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        logger.warning("Checkoff attempt for non-existent task_id=%s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        date_obj = datetime.date.fromisoformat(date_str)
    except ValueError:
        logger.warning("Invalid date format for checkoff: %s", date_str)
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD")
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
            logger.warning("Task %s has no assignee", task_id)
            raise HTTPException(status_code=400, detail="Task has no assignee")
        if person_id != eff_assignee_id:
            logger.warning("Person %s is not the assignee for task %s", person_id, task_id)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Authenticated person does not match task assignee")
    # For Both tasks, any authenticated kid can tap (all-or-nothing)
    if is_both:
        kid_ids = get_kid_ids(db)
        if not kid_ids:
            logger.warning("No kids defined for Both task checkoff")
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
            logger.info("Unchecking Both task %s for date %s (existing completions for persons: %s)", task_id, date_obj, existing_ids)
            db.query(models.TaskCompletion).filter(
                models.TaskCompletion.task_id == task_id,
                models.TaskCompletion.date == date_obj,
                models.TaskCompletion.person_id.in_(kid_ids)
            ).delete(synchronize_session=False)
            action = "unchecked"
        else:
            # No existing completions -> check (insert all)
            logger.info("Checking Both task %s for date %s for all kids: %s", task_id, date_obj, kid_ids)
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
            logger.info("Unchecking task %s for person %s on date %s", task_id, person_id, date_obj)
            db.delete(existing)
            db.commit()
            action = "unchecked"
        else:
            logger.info("Checking task %s for person %s on date %s", task_id, person_id, date_obj)
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
    logger.info("Checkoff completed: %s for task %s, date %s", action, task_id, date_obj)
    return RedirectResponse(url=referer, status_code=status.HTTP_303_SEE_OTHER)

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    logger.debug("Rendering login form")
    return render_template(request, "login.html", {})

@app.post("/login")
async def login_submit(parent_pin: str = Form(...), response: Response = None):
    logger.info("Login attempt with parent PIN")
    if parent_pin == PARENT_PIN:
        logger.info("Successful parent login")
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="parent_auth", value=PARENT_PIN, httponly=True)
        return response
    else:
        logger.warning("Failed parent login attempt")
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
        logger.warning("Unauthorized attempt to access admin panel")
        return RedirectResponse(url="/login")
    logger.debug("Rendering admin panel")
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

# People CRUD
@app.get("/admin/people", response_class=HTMLResponse)
async def admin_people_list(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering people list")
    persons = db.query(models.Person).order_by(models.Person.name).all()
    return render_template(
        request,
        "admin_people_list.html",
        {"persons": persons}
    )

@app.get("/admin/people/new", response_class=HTMLResponse)
async def admin_people_new_form(request: Request, parent_ok: bool = Depends(get_parent_auth)):
    logger.debug("Rendering new person form")
    return render_template(
        request,
        "admin_people_form.html",
        {"person": None, "action": "/admin/people", "method": "post"}
    )

@app.post("/admin/people", response_class=Response)
async def admin_people_create(
    request: Request,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    color: str = Form(...),
    kid_pin: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    logger.info("Creating new person: %s", name)
    # Validate color format (simple hex check)
    if not color.startswith('#') or len(color) != 7:
        logger.warning("Invalid color format: %s", color)
        raise HTTPException(status_code=400, detail="Invalid color format")
    # Validate kid_pin if provided
    if kid_pin is not None:
        if not kid_pin.isdigit() or not (4 <= len(kid_pin) <= 6):
            logger.warning("Invalid kid PIN: %s", kid_pin)
            raise HTTPException(status_code=400, detail="Kid PIN must be 4 to 6 digits")
    person = models.Person(name=name, color=color, kid_pin=kid_pin)
    db.add(person)
    db.commit()
    logger.info("Created person with id=%s", person.id)
    return RedirectResponse(url="/admin/people", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/people/{person_id}/edit", response_class=HTMLResponse)
async def admin_people_edit_form(
    request: Request,
    person_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.debug("Rendering edit form for person_id=%s", person_id)
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        logger.warning("Person not found for edit: %s", person_id)
        raise HTTPException(status_code=404, detail="Person not found")
    return render_template(
        request,
        "admin_people_form.html",
        {"person": person, "action": f"/admin/people/{person_id}", "method": "post"}
    )

@app.post("/admin/people/{person_id}", response_class=Response)
async def admin_people_update(
    request: Request,
    person_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    color: str = Form(...),
    kid_pin: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    logger.info("Updating person_id=%s with name=%s", person_id, name)
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        logger.warning("Person not found for update: %s", person_id)
        raise HTTPException(status_code=404, detail="Person not found")
    # Validate color format
    if not color.startswith('#') or len(color) != 7:
        logger.warning("Invalid color format: %s", color)
        raise HTTPException(status_code=400, detail="Invalid color format")
    # Validate kid_pin if provided
    if kid_pin is not None:
        if not kid_pin.isdigit() or not (4 <= len(kid_pin) <= 6):
            logger.warning("Invalid kid PIN: %s", kid_pin)
            raise HTTPException(status_code=400, detail="Kid PIN must be 4 to 6 digits")
    person.name = name
    person.color = color
    person.kid_pin = kid_pin
    db.commit()
    logger.info("Updated person_id=%s", person_id)
    return RedirectResponse(url="/admin/people", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/people/{person_id}/delete", response_class=Response)
async def admin_people_delete(
    request: Request,
    person_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.info("Deleting person_id=%s", person_id)
    person = db.query(models.Person).filter(models.Person.id == person_id).first()
    if not person:
        logger.warning("Person not found for deletion: %s", person_id)
        raise HTTPException(status_code=404, detail="Person not found")
    # Check if person has any task completions or events
    if db.query(models.TaskCompletion).filter(models.TaskCompletion.person_id == person_id).first() or \
       db.query(models.Event).filter(models.Event.person_id == person_id).first():
        logger.warning("Cannot delete person_id=%s because they have associated tasks or events", person_id)
        raise HTTPException(status_code=400, detail="Cannot delete person with associated tasks or events")
    db.delete(person)
    db.commit()
    logger.info("Deleted person_id=%s", person_id)
    return RedirectResponse(url="/admin/people", status_code=status.HTTP_303_SEE_OTHER)

# Categories CRUD
@app.get("/admin/categories", response_class=HTMLResponse)
async def admin_categories_list(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering categories list")
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    return render_template(
        request,
        "admin_categories_list.html",
        {"categories": categories}
    )

@app.get("/admin/categories/new", response_class=HTMLResponse)
async def admin_categories_new_form(request: Request, parent_ok: bool = Depends(get_parent_auth)):
    logger.debug("Rendering new category form")
    return render_template(
        request,
        "admin_categories_form.html",
        {"category": None, "action": "/admin/categories", "method": "post"}
    )

@app.post("/admin/categories", response_class=Response)
async def admin_categories_create(
    request: Request,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    sort_order: int = Form(...),
    db: Session = Depends(get_db)
):
    logger.info("Creating new category: %s", name)
    category = models.Category(name=name, sort_order=sort_order)
    db.add(category)
    db.commit()
    logger.info("Created category with id=%s", category.id)
    return RedirectResponse(url="/admin/categories", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/categories/{category_id}/edit", response_class=HTMLResponse)
async def admin_categories_edit_form(
    request: Request,
    category_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.debug("Rendering edit form for category_id=%s", category_id)
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        logger.warning("Category not found for edit: %s", category_id)
        raise HTTPException(status_code=404, detail="Category not found")
    return render_template(
        request,
        "admin_categories_form.html",
        {"category": category, "action": f"/admin/categories/{category_id}", "method": "post"}
    )

@app.post("/admin/categories/{category_id}", response_class=Response)
async def admin_categories_update(
    request: Request,
    category_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    sort_order: int = Form(...),
    db: Session = Depends(get_db)
):
    logger.info("Updating category_id=%s with name=%s", category_id, name)
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        logger.warning("Category not found for update: %s", category_id)
        raise HTTPException(status_code=404, detail="Category not found")
    category.name = name
    category.sort_order = sort_order
    db.commit()
    logger.info("Updated category_id=%s", category_id)
    return RedirectResponse(url="/admin/categories", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/categories/{category_id}/delete", response_class=Response)
async def admin_categories_delete(
    request: Request,
    category_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.info("Deleting category_id=%s", category_id)
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        logger.warning("Category not found for deletion: %s", category_id)
        raise HTTPException(status_code=404, detail="Category not found")
    # Check if category has any tasks or events
    if db.query(models.Task).filter(models.Task.category_id == category_id).first() or \
       db.query(models.Event).filter(models.Event.category_id == category_id).first():
        logger.warning("Cannot delete category_id=%s because they have associated tasks or events", category_id)
        raise HTTPException(status_code=400, detail="Cannot delete category with associated tasks or events")
    db.delete(category)
    db.commit()
    logger.info("Deleted category_id=%s", category_id)
    return RedirectResponse(url="/admin/categories", status_code=status.HTTP_303_SEE_OTHER)

# Tasks CRUD
@app.get("/admin/tasks", response_class=HTMLResponse)
async def admin_tasks_list(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering tasks list")
    tasks = db.query(models.Task).options(
        selectinload(models.Task.category),
        selectinload(models.Task.default_assignee)
    ).all()
    return render_template(
        request,
        "admin_tasks_list.html",
        {"tasks": tasks}
    )

@app.get("/admin/tasks/new", response_class=HTMLResponse)
async def admin_tasks_new_form(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering new task form")
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    persons = db.query(models.Person).order_by(models.Person.name).all()
    return render_template(
        request,
        "admin_tasks_form.html",
        {"task": None, "categories": categories, "persons": persons, "action": "/admin/tasks", "method": "post"}
    )

@app.post("/admin/tasks", response_class=Response)
async def admin_tasks_create(
    request: Request,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    category_id: int = Form(...),
    default_assignee_person_id: Optional[str] = Form(None),
    assigned_to_both: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info("Creating new task: %s", name)
    # Validate assigned_to_both
    assigned_to_both_bool = assigned_to_both.lower() == 'true'
    # Convert default_assignee_person_id to int if provided, else None
    default_assignee_id = int(default_assignee_person_id) if default_assignee_person_id else None
    task = models.Task(
        name=name,
        category_id=category_id,
        default_assignee_person_id=default_assignee_id,
        assigned_to_both=assigned_to_both_bool
    )
    db.add(task)
    db.commit()
    logger.info("Created task with id=%s", task.id)
    return RedirectResponse(url="/admin/tasks", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/tasks/{task_id}/edit", response_class=HTMLResponse)
async def admin_tasks_edit_form(
    request: Request,
    task_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.debug("Rendering edit form for task_id=%s", task_id)
    task = db.query(models.Task).options(
        selectinload(models.Task.category),
        selectinload(models.Task.default_assignee),
        selectinload(models.Task.days)
    ).filter(models.Task.id == task_id).first()
    if not task:
        logger.warning("Task not found for edit: %s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    persons = db.query(models.Person).order_by(models.Person.name).all()
    # Prepare days data for the form (for each day of week)
    days_data = {day.day_of_week: {"assignee_person_id": day.assignee_person_id, "detail": day.detail} for day in task.days}
    return render_template(
        request,
        "admin_tasks_form.html",
        {
            "task": task,
            "categories": categories,
            "persons": persons,
            "days_data": days_data,
            "action": f"/admin/tasks/{task_id}",
            "method": "post"
        }
    )

@app.post("/admin/tasks/{task_id}", response_class=Response)
async def admin_tasks_update(
    request: Request,
    task_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    category_id: int = Form(...),
    default_assignee_person_id: Optional[str] = Form(None),
    assigned_to_both: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info("Updating task_id=%s with name=%s", task_id, name)
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        logger.warning("Task not found for update: %s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    # Validate assigned_to_both
    assigned_to_both_bool = assigned_to_both.lower() == 'true'
    # Convert default_assignee_person_id to int if provided, else None
    default_assignee_id = int(default_assignee_person_id) if default_assignee_person_id else None
    task.name = name
    task.category_id = category_id
    task.default_assignee_person_id = default_assignee_id
    task.assigned_to_both = assigned_to_both_bool
    db.commit()
    logger.info("Updated task_id=%s", task_id)
    return RedirectResponse(url="/admin/tasks", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/tasks/{task_id}/delete", response_class=Response)
async def admin_tasks_delete(
    request: Request,
    task_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.info("Deleting task_id=%s", task_id)
    task = db.query(models.Task).filter(models.Task.task_id == task_id).first()
    if not task:
        logger.warning("Task not found for deletion: %s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    # Check if task has any completions
    if db.query(models.TaskCompletion).filter(models.TaskCompletion.task_id == task_id).first():
        logger.warning("Cannot delete task_id=%s because they have associated completions", task_id)
        raise HTTPException(status_code=400, detail="Cannot delete task with associated completions")
    db.delete(task)
    db.commit()
    logger.info("Deleted task_id=%s", task_id)
    return RedirectResponse(url="/admin/tasks", status_code=status.HTTP_303_SEE_OTHER)

# Events CRUD
@app.get("/admin/events", response_class=HTMLResponse)
async def admin_events_list(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering events list")
    events = db.query(models.Event).options(
        selectinload(models.Event.category),
        selectinload(models.Event.person)
    ).all()
    return render_template(
        request,
        "admin_events_list.html",
        {"events": events}
    )

@app.get("/admin/events/new", response_class=HTMLResponse)
async def admin_events_new_form(request: Request, parent_ok: bool = Depends(get_parent_auth), db: Session = Depends(get_db)):
    logger.debug("Rendering new event form")
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    persons = db.query(models.Person).order_by(models.Person.name).all()
    return render_template(
        request,
        "admin_events_form.html",
        {"event": None, "categories": categories, "persons": persons, "action": "/admin/events", "method": "post"}
    )

@app.post("/admin/events", response_class=Response)
async def admin_events_create(
    request: Request,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    category_id: int = Form(...),
    person_id: Optional[str] = Form(None),
    day_of_week: int = Form(...),
    start_time: str = Form(...),  # HH:MM format
    end_time: str = Form(...),    # HH:MM format
    db: Session = Depends(get_db)
):
    logger.info("Creating new event: %s", name)
    # Convert person_id to int if provided, else None
    person_id_val = int(person_id) if person_id else None
    # Parse times
    try:
        start_time_obj = datetime.time.fromisoformat(start_time)
        end_time_obj = datetime.time.fromisoformat(end_time)
    except ValueError:
        logger.warning("Invalid time format for event: %s-%s", start_time, end_time)
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    event = models.Event(
        name=name,
        category_id=category_id,
        person_id=person_id_val,
        day_of_week=day_of_week,
        start_time=start_time_obj,
        end_time=end_time_obj
    )
    db.add(event)
    db.commit()
    logger.info("Created event with id=%s", event.id)
    return RedirectResponse(url="/admin/events", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/admin/events/{event_id}/edit", response_class=HTMLResponse)
async def admin_events_edit_form(
    request: Request,
    event_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.debug("Rendering edit form for event_id=%s", event_id)
    event = db.query(models.Event).options(
        selectinload(models.Event.category),
        selectinload(models.Event.person)
    ).filter(models.Event.id == event_id).first()
    if not event:
        logger.warning("Event not found for edit: %s", event_id)
        raise HTTPException(status_code=404, detail="Event not found")
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    persons = db.query(models.Person).order_by(models.Person.name).all()
    # Format times for the form (HH:MM)
    start_time_str = event.start_time.strftime("%H:%M")
    end_time_str = event.end_time.strftime("%H:%M")
    return render_template(
        request,
        "admin_events_form.html",
        {
            "event": event,
            "categories": categories,
            "persons": persons,
            "start_time": start_time_str,
            "end_time": end_time_str,
            "action": f"/admin/events/{event_id}",
            "method": "post"
        }
    )

@app.post("/admin/events/{event_id}", response_class=Response)
async def admin_events_update(
    request: Request,
    event_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    name: str = Form(...),
    category_id: int = Form(...),
    person_id: Optional[str] = Form(None),
    day_of_week: int = Form(...),
    start_time: str = Form(...),
    end_time: str = Form(...),
    db: Session = Depends(get_db)
):
    logger.info("Updating event_id=%s with name=%s", event_id, name)
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        logger.warning("Event not found for update: %s", event_id)
        raise HTTPException(status_code=404, detail="Event not found")
    # Convert person_id to int if provided, else None
    person_id_val = int(person_id) if person_id else None
    # Parse times
    try:
        start_time_obj = datetime.time.fromisoformat(start_time)
        end_time_obj = datetime.time.fromisoformat(end_time)
    except ValueError:
        logger.warning("Invalid time format for event: %s-%s", start_time, end_time)
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    event.name = name
    event.category_id = category_id
    event.person_id = person_id_val
    event.day_of_week = day_of_week
    event.start_time = start_time_obj
    event.end_time = end_time_obj
    db.commit()
    logger.info("Updated event_id=%s", event_id)
    return RedirectResponse(url="/admin/events", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/admin/events/{event_id}/delete", response_class=Response)
async def admin_events_delete(
    request: Request,
    event_id: int,
    parent_ok: bool = Depends(get_parent_auth),
    db: Session = Depends(get_db)
):
    logger.info("Deleting event_id=%s", event_id)
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        logger.warning("Event not found for deletion: %s", event_id)
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()
    logger.info("Deleted event_id=%s", event_id)
    return RedirectResponse(url="/admin/events", status_code=status.HTTP_303_SEE_OTHER)