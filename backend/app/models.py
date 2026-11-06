import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    preferences = Column(JSON, default={
        "study_day_start": 8,
        "study_day_end": 22
    })

class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    priority = Column(String(20), default="medium")  # low, medium, high
    estimated_hours = Column(Float, default=1.0)
    deadline = Column(DateTime, nullable=False, index=True)

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    type = Column(String(50), default="event")  # class, exam, event, study
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("idx_user_schedule_window", "user_id", "start_time", "end_time"),
    )

class StudyPlan(Base):
    __tablename__ = "study_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="active")

class StudySession(Base):
    __tablename__ = "study_sessions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(255), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    scheduled_start = Column(DateTime, nullable=False, index=True)
    completed = Column(Boolean, default=False)

class SemesterPlan(Base):
    __tablename__ = "semester_plans"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    semester_start = Column(DateTime, nullable=False)
    semester_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SemesterEvent(Base):
    __tablename__ = "semester_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    semester_plan_id = Column(UUID(as_uuid=True), ForeignKey("semester_plans.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    date = Column(DateTime, nullable=False)
    risk_level = Column(String(20), default="low")

class Conflict(Base):
    __tablename__ = "conflicts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_a_id = Column(UUID(as_uuid=True), nullable=False)
    session_b_id = Column(UUID(as_uuid=True), nullable=False)
    resolved = Column(Boolean, default=False)