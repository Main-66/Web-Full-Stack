from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# --- Auth Schemas ---
class UserRegister(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

# --- Schedule & Conflict Schemas ---
class ScheduleCreate(BaseModel):
    title: str
    type: str = Field(default="event", pattern="^(class|exam|event|study)$")
    start_time: datetime
    end_time: datetime
    force: bool = False

class ScheduleUpdate(BaseModel):
    start_time: datetime
    end_time: datetime
    force: bool = False

class ScheduleResponse(BaseModel):
    id: UUID
    title: str
    type: str
    start_time: datetime
    end_time: datetime

    class Config:
        from_attributes = True

class ResolutionSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    label: str

class ConflictAlert(BaseModel):
    message: str
    conflicting_events: List[ScheduleResponse]
    suggested_resolutions: List[ResolutionSlot]

# --- Task Schemas ---
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    estimated_hours: float = 2.0
    deadline: datetime

class TaskResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    priority: str
    estimated_hours: float
    deadline: datetime

    class Config:
        from_attributes = True

# --- Natural Language Input Schemas ---
class NLPRequest(BaseModel):
    prompt: str

class NLPParsedOutput(BaseModel):
    intent_type: str = Field(description="Either 'schedule' for a specific time block or 'task' for a deadline item")
    title: str = Field(description="Concise title of the class, exam, study block, or task")
    event_type: str = Field(default="study", description="One of: class, exam, event, study")
    priority: str = Field(default="medium", description="One of: low, medium, high")
    start_time: str = Field(description="ISO 8601 start datetime YYYY-MM-DDTHH:MM:SS")
    end_time: str = Field(description="ISO 8601 end datetime YYYY-MM-DDTHH:MM:SS")
    estimated_hours: float = Field(default=1.0, description="Duration in hours")

# --- Smart Study Session Generator Schemas ---
class SubtopicItem(BaseModel):
    topic: str = Field(description="Specific subtopic or chapter to study")
    duration_minutes: int = Field(description="Recommended study session length in minutes, between 30 and 120")

class LLMStudyBreakdown(BaseModel):
    subtopics: List[SubtopicItem]

class StudyPlanGenerateRequest(BaseModel):
    task_id: UUID

class StudySessionResponse(BaseModel):
    id: UUID
    plan_id: UUID
    topic: str
    duration_minutes: int
    scheduled_start: datetime
    completed: bool

    class Config:
        from_attributes = True

class StudyPlanResponse(BaseModel):
    id: UUID
    task_id: UUID
    task_title: str
    generated_at: datetime
    status: str
    sessions: List[StudySessionResponse]

# --- Workload Balancing Schemas ---
class DailyLoadItem(BaseModel):
    date: str
    total_hours: float
    event_count: int
    overloaded: bool

class WorkloadBalanceResponse(BaseModel):
    moved_events_count: int
    details: List[str]
    daily_summary: List[DailyLoadItem]

# --- Semester Planner Schemas ---
class SemesterPlanCreate(BaseModel):
    semester_start: datetime
    semester_end: datetime

class SemesterEventCreate(BaseModel):
    semester_plan_id: UUID
    title: str
    type: str = Field(default="exam", description="exam, midterm, project, or deadline")
    date: datetime

class SemesterEventResponse(BaseModel):
    id: UUID
    semester_plan_id: UUID
    title: str
    type: str
    date: datetime
    risk_level: str

    class Config:
        from_attributes = True

class SemesterPlanResponse(BaseModel):
    id: UUID
    semester_start: datetime
    semester_end: datetime
    created_at: datetime
    events: List[SemesterEventResponse]
    high_risk_weeks: List[str]