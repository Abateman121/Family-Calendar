from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Date, Time, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base
import datetime

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)  # HTML color code
    kid_pin = Column(Integer, nullable=True)  # PIN for kid, None for parents/adults?
    # Relationships
    task_completions = relationship("TaskCompletion", back_populates="person")
    events = relationship("Event", back_populates="person")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    sort_order = Column(Integer, nullable=False, default=0)
    # Relationships
    tasks = relationship("Task", back_populates="category")
    events = relationship("Event", back_populates="category")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    default_assignee_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    assigned_to_both = Column(Boolean, nullable=False, default=False)
    # Relationships
    category = relationship("Category", back_populates="tasks")
    default_assignee = relationship("Person", foreign_keys=[default_assignee_person_id])
    days = relationship("TaskDay", back_populates="task", cascade="all, delete-orphan")

class TaskDay(Base):
    __tablename__ = "task_days"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    assignee_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)  # Override; None means use task default
    detail = Column(String, nullable=True)  # Free-text detail override for this day
    # Relationships
    task = relationship("Task", back_populates="days")
    assignee_person = relationship("Person", foreign_keys=[assignee_person_id])
    __table_args__ = (UniqueConstraint('task_id', 'day_of_week', name='uix_task_day'),)

class TaskCompletion(Base):
    __tablename__ = "task_completions"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    date = Column(Date, nullable=False)  # The date the task was completed
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    completed_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    # Relationships
    task = relationship("Task")
    person = relationship("Person", back_populates="task_completions")
    __table_args__ = (UniqueConstraint('task_id', 'date', 'person_id', name='uix_task_completion'),)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=True)  # Assigned person (if any)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday (recurring weekly)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    # Relationships
    category = relationship("Category", back_populates="events")
    person = relationship("Person", back_populates="events")