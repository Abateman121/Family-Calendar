import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Cookie, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from . import database, models

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

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

# Utility to check parent cookie
def parent_authenticated(parent_cookie: Optional[str] = Cookie(None)):
    # In real app, verify signed cookie; for simplicity, compare to PARENT_PIN
    return parent_cookie == PARENT_PIN

@app.get("/", response_class=HTMLResponse)
async def week_view(
    request: Request,
    db: Session = Depends(get_db),
    parent_ok: bool = Depends(parent_authenticated)
):
    monday = get_current_monday()
    week_dates = get_week_dates(monday)
    # Fetch data
    persons = db.query(models.Person).order_by(models.Person.name).all()
    categories = db.query(models.Category).order_by(models.Category.sort_order).all()
    tasks = db.query(models.Task).options(
        # eager load days and relationships
    ).all()
    # For simplicity, fetch all task completions for the week
    completions = db.query(models.TaskCompletion).filter(
        models.TaskCompletion.date >= monday,
        models.TaskCompletion.date < monday + datetime.timedelta(days=7)
    ).all()
    # Map completions for quick lookup: (task_id, date, person_id) -> True
    completion_set = {
        (c.task_id, c.date, c.person_id) for c in completions
    }
    # Build task day instances with overrides
    # We'll prepare a dict: task_id -> list of day info for 0-6
    task_day_map = {}
    for task in tasks:
        day_info = {}
        for day in task.days:
            day_info[day.day_of_week] = {
                "assignee_person_id": day.assignee_person_id,
                "detail": day.detail,
            }
        task_day_map[task.id] = day_info

    # Events for week (recurring by day_of_week)
    events = db.query(models.Event).all()
    # Group events by day_of_week
    events_by_day = {i: [] for i in range(7)}
    for ev in events:
        events_by_day[ev.day_of_week].append(ev)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "monday": monday,
            "week_dates": week_dates,
            "persons": persons,
            "categories": categories,
            "tasks": tasks,
            "task_day_map": task_day_map,
            "completion_set": completion_set,
            "events_by_day": events_by_day,
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
    return templates.TemplateResponse(
        "person.html",
        {"request": request, "persons": persons}
    )

@app.post("/checkoff")
async def checkoff_task(
    request: Request,
    task_id: int = Form(...),
    date_str: str = Form(...),  # YYYY-MM-DD
    person_id: int = Form(None),
    selected_person: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    # Determine person_id: from form if provided, else from cookie
    if person_id is None:
        if selected_person is not None:
            try:
                person_id = int(selected_person)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid person cookie")
        else:
            raise HTTPException(status_code=400, detail="Person not selected")
    # Verify person exists and has PIN? For simplicity, assume valid.
    date_obj = datetime.date.fromisoformat(date_str)
    # Check if completion already exists
    existing = db.query(models.TaskCompletion).filter(
        models.TaskCompletion.task_id == task_id,
        models.TaskCompletion.date == date_obj,
        models.TaskCompletion.person_id == person_id
    ).first()
    if existing:
        # Uncheck (delete)
        db.delete(existing)
        db.commit()
        action = "unchecked"
    else:
        # Create completion
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
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_submit(parent_pin: str = Form(...), response: Response = None):
    if parent_pin == PARENT_PIN:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="parent_auth", value=PARENT_PIN, httponly=True)
        return response
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": Request({"type": "http"}), "error": "Invalid PIN"},
            status_code=status.HTTP_400_BAD_REQUEST
        )

@app.post("/select_person")
async def select_person(request: Request, person_id: int = Form(...)):
    response = RedirectResponse(url=request.headers.get("referer") or "/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="selected_person", value=str(person_id), httponly=True)
    return response

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
    return templates.TemplateResponse(
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