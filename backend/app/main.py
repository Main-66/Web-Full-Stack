from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.database import engine, Base, get_db, AsyncSessionLocal
from app.models import User, Schedule, Task, Conflict
from app.schemas import (
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
    TaskCreate, TaskResponse, NLPRequest, NLPParsedOutput, ConflictAlert
)
from app.auth import hash_password, create_access_token
from app.services.conflict_detector import find_overlapping_schedules, suggest_resolution_slots
from app.services.ai_nlp import parse_natural_language_command

app = FastAPI(title="AI-Assisted Schedule Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_EMAIL = "student@unideb.hu"

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed a default user so Tier 1 works immediately without login friction
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        user = result.scalar_one_or_none()
        if not user:
            demo_user = User(
                name="Demo Student",
                email=DEMO_EMAIL,
                password_hash=hash_password("thesis2026")
            )
            db.add(demo_user)
            await db.commit()

async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    return result.scalar_one()

@app.get("/api/auth/demo-token")
async def get_demo_jwt(user: User = Depends(get_current_user)):
    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {"access_token": token, "token_type": "bearer", "user": {"name": user.name, "email": user.email}}

@app.get("/api/schedules", response_model=list[ScheduleResponse])
async def list_schedules(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Schedule).where(Schedule.user_id == user.id).order_by(Schedule.start_time))
    return result.scalars().all()

@app.post("/api/schedules")
async def create_schedule(
    payload: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time.")

    result = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    existing = list(result.scalars().all())

    overlaps = find_overlapping_schedules(existing, payload.start_time.replace(tzinfo=None), payload.end_time.replace(tzinfo=None))

    if overlaps and not payload.force:
        suggestions = suggest_resolution_slots(
            existing,
            payload.start_time.replace(tzinfo=None),
            payload.end_time.replace(tzinfo=None)
        )
        # Log conflict in database
        for conflict_sched in overlaps:
            db.add(Conflict(
                user_id=user.id,
                session_a_id=conflict_sched.id,
                session_b_id=conflict_sched.id,
                resolved=False
            ))
        await db.commit()

        alert = ConflictAlert(
            message=f"Time slot conflicts with {len(overlaps)} existing event(s).",
            conflicting_events=[ScheduleResponse.model_validate(o) for o in overlaps],
            suggested_resolutions=suggestions
        )
        return JSONResponse(status_code=409, content=alert.model_dump(mode="json"))

    new_sched = Schedule(
        user_id=user.id,
        title=payload.title,
        type=payload.type,
        start_time=payload.start_time.replace(tzinfo=None),
        end_time=payload.end_time.replace(tzinfo=None)
    )
    db.add(new_sched)
    await db.commit()
    await db.refresh(new_sched)
    return ScheduleResponse.model_validate(new_sched)

@app.patch("/api/schedules/{schedule_id}")
async def move_schedule(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    sched_res = await db.execute(select(Schedule).where(Schedule.id == schedule_id, Schedule.user_id == user.id))
    sched = sched_res.scalar_one_or_none()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    all_res = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    existing = list(all_res.scalars().all())

    start_naive = payload.start_time.replace(tzinfo=None)
    end_naive = payload.end_time.replace(tzinfo=None)

    overlaps = find_overlapping_schedules(existing, start_naive, end_naive, exclude_id=schedule_id)
    if overlaps and not payload.force:
        suggestions = suggest_resolution_slots(existing, start_naive, end_naive)
        alert = ConflictAlert(
            message=f"Rescheduled slot overlaps with '{overlaps[0].title}'.",
            conflicting_events=[ScheduleResponse.model_validate(o) for o in overlaps],
            suggested_resolutions=suggestions
        )
        return JSONResponse(status_code=409, content=alert.model_dump(mode="json"))

    sched.start_time = start_naive
    sched.end_time = end_naive
    await db.commit()
    await db.refresh(sched)
    return ScheduleResponse.model_validate(sched)

@app.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    sched_res = await db.execute(select(Schedule).where(Schedule.id == schedule_id, Schedule.user_id == user.id))
    sched = sched_res.scalar_one_or_none()
    if sched:
        await db.delete(sched)
        await db.commit()
    return {"status": "deleted"}

@app.get("/api/tasks", response_model=list[TaskResponse])
async def list_tasks(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Task).where(Task.user_id == user.id).order_by(Task.deadline))
    return result.scalars().all()

@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    task = Task(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        estimated_hours=payload.estimated_hours,
        deadline=payload.deadline.replace(tzinfo=None)
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@app.post("/api/ai/parse", response_model=NLPParsedOutput)
async def ai_parse_input(payload: NLPRequest):
    return await parse_natural_language_command(payload.prompt)