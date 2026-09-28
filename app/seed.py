from .database import SessionLocal, init_db
from .models import Person, Category, Task, TaskDay, TaskCompletion, Event
import datetime

def seed_database():
    """Seed initial data if tables are empty."""
    # Run migrations to ensure tables exist
    init_db()

    db = SessionLocal()
    try:
        # Check if we already have people
        if db.query(Person).count() == 0:
            # Create persons
            ethan = Person(name="Ethan", color="#4CAF50", kid_pin="1234")  # Green
            rose = Person(name="Rose", color="#2196F3", kid_pin="5678")   # Blue
            dad = Person(name="Dad", color="#FF9800", kid_pin=None)    # Orange, no PIN
            mom = Person(name="Mom", color="#9C27B0", kid_pin=None)    # Purple, no PIN
            db.add_all([ethan, rose, dad, mom])
            db.commit()

            # Create categories
            daily = Category(name="Daily", sort_order=0)
            weekly = Category(name="Weekly", sort_order=1)
            sports = Category(name="Sports", sort_order=2)
            db.add_all([daily, weekly, sports])
            db.commit()

            # Helper to get IDs
            def get_id(obj):
                return obj.id

            ethan_id = ethan.id
            rose_id = rose.id
            dad_id = dad.id
            mom_id = mom.id
            daily_id = daily.id
            weekly_id = weekly.id
            sports_id = sports.id

            # Define tasks (name, category, default assignee, assigned_to_both, days with overrides)
            tasks_data = [
                # Daily chores
                {
                    "name": "Make Bed",
                    "category_id": daily_id,
                    "default_assignee_person_id": ethan_id,
                    "assigned_to_both": False,
                    "days": [
                        (0, None, None),  # Monday
                        (1, None, None),  # Tuesday
                        (2, None, None),  # Wednesday
                        (3, None, None),  # Thursday
                        (4, None, None),  # Friday
                        (5, None, None),  # Saturday
                        (6, None, None),  # Sunday
                    ]
                },
                {
                    "name": "Brush Teeth",
                    "category_id": daily_id,
                    "default_assignee_person_id": rose_id,
                    "assigned_to_both": False,
                    "days": [(i, None, None) for i in range(7)]
                },
                {
                    "name": "Feed Pets",
                    "category_id": daily_id,
                    "default_assignee_person_id": None,
                    "assigned_to_both": True,
                    "days": [
                        (0, ethan_id, "Downstairs"),   # Monday override assignee Ethan, detail Downstairs
                        (1, None, None),
                        (2, rose_id, "Upstairs"),      # Wednesday override assignee Rose, detail Upstairs
                        (3, None, None),
                        (4, ethan_id, "Downstairs"),   # Friday
                        (5, None, None),
                        (6, None, None),
                    ]
                },
                {
                    "name": "Vacuum Living Room",
                    "category_id": weekly_id,
                    "default_assignee_person_id": rose_id,
                    "assigned_to_both": False,
                    "days": [
                        (0, None, None),  # Monday
                        (1, None, None),
                        (2, None, None),
                        (3, None, None),
                        (4, None, None),
                        (5, rose_id, "Whole house"),  # Saturday
                        (6, None, None),
                    ]
                },
                {
                    "name": "Take Out Trash",
                    "category_id": weekly_id,
                    "default_assignee_person_id": ethan_id,
                    "assigned_to_both": False,
                    "days": [
                        (0, None, None),
                        (1, None, None),
                        (2, None, None),
                        (3, None, None),
                        (4, None, None),
                        (5, ethan_id, "Curb"),  # Saturday
                        (6, None, None),
                    ]
                },
                {
                    "name": "Sports Practice",
                    "category_id": sports_id,
                    "default_assignee_person_id": ethan_id,
                    "assigned_to_both": False,
                    "days": [
                        (1, None, None),  # Tuesday
                        (3, None, None),  # Thursday
                    ]
                },
            ]

            for task_data in tasks_data:
                days_info = task_data.pop("days")
                task = Task(**task_data)
                db.add(task)
                db.commit()  # To get task.id
                for day_of_week, assignee_override, detail in days_info:
                    if assignee_override is not None or detail is not None:
                        day = TaskDay(
                            task_id=task.id,
                            day_of_week=day_of_week,
                            assignee_person_id=assignee_override,
                            detail=detail
                        )
                        db.add(day)
                # Commit after each task to keep transaction small
                db.commit()

            # Seed some events (example sports)
            events_data = [
                {
                    "name": "Soccer Game",
                    "category_id": sports_id,
                    "person_id": ethan_id,
                    "day_of_week": 6,  # Sunday
                    "start_time": datetime.time(9, 0),
                    "end_time": datetime.time(11, 0),
                },
                {
                    "name": "Dance Class",
                    "category_id": sports_id,
                    "person_id": rose_id,
                    "day_of_week": 4,  # Friday
                    "start_time": datetime.time(16, 30),
                    "end_time": datetime.time(18, 0),
                },
            ]
            for ev in events_data:
                event = Event(**ev)
                db.add(event)
            db.commit()

            print("Database seeded successfully.")
        else:
            print("Database already contains data; skipping seed.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()