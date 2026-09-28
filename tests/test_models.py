import pytest
from app.models import Person, Category, Task, TaskDay, TaskCompletion, Event
from datetime import date, time, datetime

def test_person_creation(db_session):
    """Test creating a person and default values."""
    person = Person(name="Test Person", color="#FF0000", kid_pin="1234")
    db_session.add(person)
    db_session.commit()

    assert person.id is not None
    assert person.name == "Test Person"
    assert person.color == "#FF0000"
    assert person.kid_pin == "1234"
    assert person.task_completions == []
    assert person.events == []

def test_kid_pin_validation(db_session):
    """Test that kid PIN must be 4-6 digits."""
    # Valid PINs
    for pin in ["1234", "12345", "123456"]:
        person = Person(name="Test", color="#FF0000", kid_pin=pin)
        db_session.add(person)
        db_session.commit()
        assert person.kid_pin == pin
        db_session.delete(person)
        db_session.commit()

    # Invalid PINs
    for pin in ["123", "1234567", "abcd", "12 34"]:
        person = Person(name="Test", color="#FF0000", kid_pin=pin)
        db_session.add(person)
        with pytest.raises(Exception):  # ValidationError or IntegrityError
            db_session.commit()
        db_session.rollback()

def test_category_creation(db_session):
    """Test creating a category."""
    category = Category(name="Test Category", sort_order=1)
    db_session.add(category)
    db_session.commit()

    assert category.id is not None
    assert category.name == "Test Category"
    assert category.sort_order == 1
    assert category.tasks == []
    assert category.events == []

def test_category_unique_name(db_session):
    """Test that category names must be unique."""
    category1 = Category(name="Unique Category", sort_order=1)
    db_session.add(category1)
    db_session.commit()

    category2 = Category(name="Unique Category", sort_order=2)
    db_session.add(category2)
    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()
    db_session.rollback()

def test_task_relationships(db_session):
    """Test task relationships with category and default assignee."""
    # Create prerequisite objects
    person = Person(name="Test Person", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    db_session.add_all([person, category])
    db_session.commit()

    # Create task
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add(task)
    db_session.commit()

    # Test relationships
    assert task.category.id == category.id
    assert task.category.name == "Test Category"
    assert task.default_assignee.id == person.id
    assert task.default_assignee.name == "Test Person"
    assert len(task.days) == 0
    assert len(task.task_completions) == 0

def test_task_day_relationships(db_session):
    """Test task day relationships."""
    person = Person(name="Test Person", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([person, category, task])
    db_session.commit()

    # Add a task day
    task_day = TaskDay(
        task_id=task.id,
        day_of_week=0,  # Monday
        assignee_person_id=person.id,
        detail="Test detail"
    )
    db_session.add(task_day)
    db_session.commit()

    # Test relationships
    assert task_day.task.id == task.id
    assert task_day.task.name == "Test Task"
    assert task_day.assignee_person.id == person.id
    assert task_day.assignee_person.name == "Test Person"
    assert task_day.detail == "Test detail"

    # Test backref from task
    assert len(task.days) == 1
    assert task.days[0].id == task_day.id

def test_task_completion_relationships(db_session):
    """Test task completion relationships."""
    person = Person(name="Test Person", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    task = Task(
        name="Test Task",
        category_id=category.id,
        default_assignee_person_id=person.id,
        assigned_to_both=False
    )
    db_session.add_all([person, category, task])
    db_session.commit()

    # Add a task completion
    completion_date = date(2026, 9, 27)
    completion = TaskCompletion(
        task_id=task.id,
        date=completion_date,
        person_id=person.id
    )
    db_session.add(completion)
    db_session.commit()

    # Test relationships
    assert completion.task.id == task.id
    assert completion.task.name == "Test Task"
    assert completion.person.id == person.id
    assert completion.person.name == "Test Person"
    assert completion.date == completion_date
    assert completion.completed_at is not None

    # Test backrefs
    assert len(person.task_completions) == 1
    assert person.task_completions[0].id == completion.id
    assert len(task.task_completions) == 1
    assert task.task_completions[0].id == completion.id

def test_event_relationships(db_session):
    """Test event relationships."""
    person = Person(name="Test Person", color="#FF0000", kid_pin="1234")
    category = Category(name="Test Category", sort_order=1)
    db_session.add_all([person, category])
    db_session.commit()

    event = Event(
        name="Test Event",
        category_id=category.id,
        person_id=person.id,
        day_of_week=0,  # Monday
        start_time=time(9, 0),
        end_time=time(10, 0)
    )
    db_session.add(event)
    db_session.commit()

    # Test relationships
    assert event.category.id == category.id
    assert event.category.name == "Test Category"
    assert event.person.id == person.id
    assert event.person.name == "Test Person"

    # Test backrefs
    assert len(person.events) == 1
    assert person.events[0].id == event.id
    assert len(category.events) == 1
    assert category.events[0].id == event.id

def test_both_task_logic(db_session):
    """Test the logic for tasks assigned to both."""
    person1 = Person(name="Person 1", color="#FF0000", kid_pin="1111")
    person2 = Person(name="Person 2", color="#00FF00", kid_pin="2222")
    category = Category(name="Test Category", sort_order=1)
    db_session.add_all([person1, person2, category])
    db_session.commit()

    # Create a task assigned to both
    task = Task(
        name="Both Task",
        category_id=category.id,
        default_assignee_person_id=None,  # Not used when assigned_to_both=True
        assigned_to_both=True
    )
    db_session.add(task)
    db_session.commit()

    # Add task days for Monday and Tuesday
    for day in [0, 1]:  # Monday, Tuesday
        task_day = TaskDay(
            task_id=task.id,
            day_of_week=day,
            assignee_person_id=None,  # No override, use task default (which is Both)
            detail=None
        )
        db_session.add(task_day)
    db_session.commit()

    # Verify the task days are correctly set
    assert len(task.days) == 2
    for day in task.days:
        assert day.assignee_person_id is None
        assert day.detail is None

    # Test that the task is marked as assigned_to_both
    assert task.assigned_to_both == True
    assert task.default_assignee_person_id is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])