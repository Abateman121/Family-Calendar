import pytest
from app.models import Person, Category, Task, TaskDay, TaskCompletion, Event
from datetime import date, time

def test_login_success(client):
    """Test login with correct parent PIN."""
    response = client.post("/login", data={"parent_pin": "1234"}, follow_redirects=True)
    assert response.status_code == 200
    # Check that we are redirected to the home page
    # The login route sets a cookie named "parent_auth" with the PIN value
    cookies = response.cookies
    assert "parent_auth" in cookies
    assert cookies["parent_auth"] == "1234"

def test_login_failure(client):
    """Test login with incorrect parent PIN."""
    response = client.post("/login", data={"parent_pin": "wrong"}, follow_redirects=True)
    assert response.status_code == 200
    # Should show error message
    assert "Invalid PIN" in response.text
    # No auth cookie should be set (or not set to wrong value)
    cookies = response.cookies
    # The cookie might not be present at all on failure
    if "parent_auth" in cookies:
        assert cookies["parent_auth"] != "wrong"

def test_checkoff_requires_auth(client, db_session):
    """Test that /checkoff requires person authentication via session."""
    # Create a person and a task for testing
    person = Person(name="Test Kid", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([person, category, task])
    db_session.commit()

    # Try to check off without authentication -> should return 403
    response = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": "2026-09-27"},
        follow_redirects=False  # Don't follow redirects to see the exact status
    )
    # The route raises HTTPException with status_code=403
    assert response.status_code == 403
    assert "Person not authenticated via PIN" in response.text

def test_checkoff_success(client, db_session):
    """Test successful checkoff of a task."""
    # Setup: create persons, category, task
    person = Person(name="Test Kid", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([person, category, task])
    db_session.commit()

    # First, we need to authenticate the person via the /verify_pin endpoint.
    login_response = client.post(
        "/verify_pin",
        data={"person_id": person.id, "pin": "1234"},
        follow_redirects=False
    )
    # The verify_pin endpoint redirects to the referer or home (303)
    assert login_response.status_code == 303
    # Check that the cookie is set
    cookies = login_response.cookies
    assert "person_id" in cookies
    assert cookies["person_id"] == str(person.id)

    # Now we can try to check off the task
    checkoff_date = date(2026, 9, 27)
    response = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": checkoff_date.isoformat()},
        follow_redirects=False
    )
    # Should be successful (redirect back to referring page) -> 303
    assert response.status_code == 303
    # We can also check that a TaskCompletion was created
    completion = db_session.query(TaskCompletion).filter(
        TaskCompletion.task_id == task.id,
        TaskCompletion.date == checkoff_date,
        TaskCompletion.person_id == person.id
    ).first()
    assert completion is not None
    assert completion.completed_at is not None

def test_checkoff_double_checkoff(client, db_session):
    """Test that checking off an already checked-off task unchecks it (toggle)."""
    # Setup
    person = Person(name="Test Kid", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([person, category, task])
    db_session.commit()

    # Authenticate the person
    client.post(
        "/verify_pin",
        data={"person_id": person.id, "pin": "1234"},
        follow_redirects=False
    )

    checkoff_date = date(2026, 9, 27)

    # First checkoff -> should create a completion
    response1 = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": checkoff_date.isoformat()},
        follow_redirects=False
    )
    assert response1.status_code == 303

    completion = db_session.query(TaskCompletion).filter(
        TaskCompletion.task_id == task.id,
        TaskCompletion.date == checkoff_date,
        TaskCompletion.person_id == person.id
    ).first()
    assert completion is not None

    # Second checkoff on the same task/date -> should delete the completion (toggle off)
    response2 = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": checkoff_date.isoformat()},
        follow_redirects=False
    )
    assert response2.status_code == 303

    # Now the completion should be gone
    completion_after = db_session.query(TaskCompletion).filter(
        TaskCompletion.task_id == task.id,
        TaskCompletion.date == checkoff_date,
        TaskCompletion.person_id == person.id
    ).first()
    assert completion_after is None

def test_checkoff_both_task(client, db_session):
    """Test checking off a task assigned to both."""
    # Setup: two kids and a task assigned to both
    person1 = Person(name="Kid 1", color="#FF0000", kid_pin="1111")
    person2 = Person(name="Kid 2", color="#00FF00", kid_pin="2222")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Both Task",
        category_id=category.id,
        default_assignee_person_id=None,
        assigned_to_both=True
    )
    db_session.add_all([person1, person2, category, task])
    db_session.commit()

    # Add a task day for Monday (we'll use Monday for the test)
    task_day = TaskDay(
        task_id=task.id,
        day_of_week=0,  # Monday
        assignee_person_id=None,
        detail=None
    )
    db_session.add(task_day)
    db_session.commit()

    # Authenticate as person1
    client.post(
        "/verify_pin",
        data={"person_id": person1.id, "pin": "1111"},
        follow_redirects=False
    )

    checkoff_date = date(2026, 9, 28)  # 2026-09-28 is a Monday

    # First checkoff by person1 -> should create completions for both persons (since it's a Both task)
    response1 = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": checkoff_date.isoformat()},
        follow_redirects=False
    )
    assert response1.status_code == 303

    completions = db_session.query(TaskCompletion).filter(
        TaskCompletion.task_id == task.id,
        TaskCompletion.date == checkoff_date
    ).all()
    # Should have two completions, one for each person
    assert len(completions) == 2
    person_ids = {c.person_id for c in completions}
    assert person_ids == {person1.id, person2.id}

    # Now checkoff by person2 -> should toggle off (remove both completions)
    # We need to authenticate as person2
    client.post(
        "/verify_pin",
        data={"person_id": person2.id, "pin": "2222"},
        follow_redirects=False
    )

    response2 = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": checkoff_date.isoformat()},
        follow_redirects=False
    )
    assert response2.status_code == 303

    # Now there should be no completions
    completions_after = db_session.query(TaskCompletion).filter(
        TaskCompletion.task_id == task.id,
        TaskCompletion.date == checkoff_date
    ).all()
    assert len(completions_after) == 0

def test_checkoff_invalid_task(client, db_session):
    """Test checkoff with invalid task ID."""
    # Authenticate a person (we need a person to be authenticated)
    person = Person(name="Test Kid", color="#FF0000", kid_pin="1234")
    db_session.add(person)
    db_session.commit()

    client.post(
        "/verify_pin",
        data={"person_id": person.id, "pin": "1234"},
        follow_redirects=False
    )

    # Try to check off a non-existent task
    response = client.post(
        "/checkoff",
        data={"task_id": 99999, "date": "2026-09-27"},
        follow_redirects=False
    )
    # Should return 404 (task not found)
    assert response.status_code == 404
    assert "Task not found" in response.text

def test_checkoff_invalid_date(client, db_session):
    """Test checkoff with invalid date format."""
    # Authenticate a person
    person = Person(name="Test Kid", color="#FF0000", kid_pin="1234")
    db_session.add(person)
    db_session.commit()

    client.post(
        "/verify_pin",
        data={"person_id": person.id, "pin": "1234"},
        follow_redirects=False
    )

    # Create a task for good measure
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([category, task])
    db_session.commit()

    # Try with invalid date
    response = client.post(
        "/checkoff",
        data={"task_id": task.id, "date": "not-a-date"},
        follow_redirects=False
    )
    # The date conversion will raise a ValueError, which FastAPI will turn into a 422 Unprocessable Entity
    assert response.status_code == 422

if __name__ == "__main__":
    pytest.main([__file__, "-v"])