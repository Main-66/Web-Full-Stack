from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

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

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    estimated_hours: float = 1.0
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