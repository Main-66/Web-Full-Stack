from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
from jose import jwt, JWTError

from app.config import settings
from app.database import engine, Base, get_db, AsyncSessionLocal
from app.models import (
    User, Schedule, Task, Conflict,
    StudyPlan, StudySession, SemesterPlan, SemesterEvent
)
from app.schemas import (
    UserRegister, UserLogin, TokenResponse,
    ScheduleCreate, ScheduleUpdate, ScheduleResponse,
    TaskCreate, TaskResponse, NLPRequest, NLPParsedOutput, ConflictAlert,
    StudyPlanGenerateRequest, StudyPlanResponse, StudySessionResponse,
    WorkloadBalanceResponse, DailyLoadItem,
    SemesterPlanCreate, SemesterEventCreate, SemesterPlanResponse, SemesterEventResponse
)
from app.auth import hash_password, verify_password, create_access_token
from app.services.conflict_detector import find_overlapping_schedules, suggest_resolution_slots
from app.services.ai_nlp import parse_natural_language_command
from app.services.study_planner import (
    generate_subtopics_with_ai,
    allocate_study_slots,
    balance_weekly_workload,
    compute_daily_summary,
    evaluate_semester_risks
)

app = FastAPI(title="Web-Based AI-Assisted Schedule Management System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_EMAIL = "student@unideb.hu"

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db)
) -> User:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            email = payload.get("email")
            if email:
                res = await db.execute(select(User).where(User.email == email))
                user = res.scalar_one_or_none()
                if user:
                    return user
        except JWTError:
            pass

    # Demo Fallback
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    return result.scalar_one()

# ==================== 1. AUTHENTICATION (JWT) ====================

@app.post("/api/auth/register", response_model=TokenResponse)
async def register_user(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id), "email": new_user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(new_user.id), "name": new_user.name, "email": new_user.email}
    }

@app.post("/api/auth/login", response_model=TokenResponse)
async def login_user(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "name": user.name, "email": user.email}
    }

# ==================== 2. SCHEDULES & CONFLICT ENGINE ====================

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

    start_naive = payload.start_time.replace(tzinfo=None)
    end_naive = payload.end_time.replace(tzinfo=None)

    overlaps = find_overlapping_schedules(existing, start_naive, end_naive)

    if overlaps and not payload.force:
        suggestions = suggest_resolution_slots(existing, start_naive, end_naive)
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
        start_time=start_naive,
        end_time=end_naive
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

# ==================== 3. TASKS & NATURAL LANGUAGE INPUT ====================

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

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    task = res.scalar_one_or_none()
    if task:
        await db.delete(task)
        await db.commit()
    return {"status": "deleted"}

@app.post("/api/ai/parse", response_model=NLPParsedOutput)
async def ai_parse_input(
    payload: NLPRequest,
    x_llm_api_key: str = Header(None),
    x_llm_base_url: str = Header(None),
    x_llm_model: str = Header(None)
):
    return await parse_natural_language_command(
        payload.prompt, 
        api_key=x_llm_api_key, 
        base_url=x_llm_base_url, 
        model=x_llm_model
    )

# ==================== 4. SMART STUDY SESSION GENERATOR ====================

@app.post("/api/study-plans/generate", response_model=StudyPlanResponse)
async def generate_study_plan(
    payload: StudyPlanGenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_llm_api_key: str = Header(None),
    x_llm_base_url: str = Header(None),
    x_llm_model: str = Header(None)
):
    task_res = await db.execute(select(Task).where(Task.id == payload.task_id, Task.user_id == user.id))
    task = task_res.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    sched_res = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    existing_schedules = list(sched_res.scalars().all())

    # 1. LLM breaks exam/task into subtopics & durations
    subtopics = await generate_subtopics_with_ai(
        task.title, 
        task.description or "", 
        task.estimated_hours,
        api_key=x_llm_api_key,
        base_url=x_llm_base_url,
        model=x_llm_model
    )

    # 2. Deterministic slot allocator finds conflict-free slots before task deadline
    allocated_slots = allocate_study_slots(existing_schedules, subtopics, task.deadline)

    # 3. Persist StudyPlan, StudySessions, and corresponding Calendar Schedule blocks
    plan = StudyPlan(task_id=task.id, status="active")
    db.add(plan)
    await db.flush()

    session_records = []
    for sub, start_dt, end_dt in allocated_slots:
        ss = StudySession(
            plan_id=plan.id,
            topic=sub.topic,
            duration_minutes=sub.duration_minutes,
            scheduled_start=start_dt,
            completed=False
        )
        db.add(ss)
        session_records.append(ss)

        cal_block = Schedule(
            user_id=user.id,
            title=f"Study: {sub.topic}",
            type="study",
            start_time=start_dt,
            end_time=end_dt
        )
        db.add(cal_block)

    await db.commit()
    for ss in session_records:
        await db.refresh(ss)

    return StudyPlanResponse(
        id=plan.id,
        task_id=task.id,
        task_title=task.title,
        generated_at=plan.generated_at,
        status=plan.status,
        sessions=[StudySessionResponse.model_validate(s) for s in session_records]
    )

@app.get("/api/study-plans", response_model=list[StudyPlanResponse])
async def list_study_plans(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    tasks_res = await db.execute(select(Task).where(Task.user_id == user.id))
    user_tasks = {t.id: t.title for t in tasks_res.scalars().all()}
    if not user_tasks:
        return []

    plans_res = await db.execute(select(StudyPlan).where(StudyPlan.task_id.in_(user_tasks.keys())))
    plans = plans_res.scalars().all()

    response = []
    for p in plans:
        sess_res = await db.execute(
            select(StudySession).where(StudySession.plan_id == p.id).order_by(StudySession.scheduled_start)
        )
        sessions = sess_res.scalars().all()
        response.append(
            StudyPlanResponse(
                id=p.id,
                task_id=p.task_id,
                task_title=user_tasks.get(p.task_id, "Task"),
                generated_at=p.generated_at,
                status=p.status,
                sessions=[StudySessionResponse.model_validate(s) for s in sessions]
            )
        )
    return response

@app.patch("/api/study-sessions/{session_id}/toggle", response_model=StudySessionResponse)
async def toggle_study_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(StudySession).where(StudySession.id == session_id))
    sess = res.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=404, detail="Study session not found")
    sess.completed = not sess.completed
    await db.commit()
    await db.refresh(sess)
    return sess

# ==================== 5. WORKLOAD BALANCING MODULE ====================

@app.get("/api/workload/summary", response_model=list[DailyLoadItem])
async def get_workload_summary(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    schedules = list(res.scalars().all())
    return compute_daily_summary(schedules)

@app.post("/api/workload/balance", response_model=WorkloadBalanceResponse)
async def trigger_workload_balance(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    res = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    schedules = list(res.scalars().all())

    moved_count, logs = balance_weekly_workload(schedules, daily_max_hours=5.0)
    await db.commit()

    updated_summary = compute_daily_summary(schedules, daily_max_hours=5.0)
    return WorkloadBalanceResponse(
        moved_events_count=moved_count,
        details=logs if logs else ["Workload is already balanced across the next 7 days."],
        daily_summary=updated_summary
    )

# ==================== 6. SEMESTER PLANNER MODULE ====================

@app.post("/api/semester-plans", response_model=SemesterPlanResponse)
async def create_semester_plan(
    payload: SemesterPlanCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    plan = SemesterPlan(
        user_id=user.id,
        semester_start=payload.semester_start.replace(tzinfo=None),
        semester_end=payload.semester_end.replace(tzinfo=None)
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return SemesterPlanResponse(
        id=plan.id,
        semester_start=plan.semester_start,
        semester_end=plan.semester_end,
        created_at=plan.created_at,
        events=[],
        high_risk_weeks=[]
    )

@app.get("/api/semester-plans", response_model=list[SemesterPlanResponse])
async def get_semester_plans(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    plans_res = await db.execute(select(SemesterPlan).where(SemesterPlan.user_id == user.id))
    plans = plans_res.scalars().all()

    out = []
    for p in plans:
        ev_res = await db.execute(
            select(SemesterEvent).where(SemesterEvent.semester_plan_id == p.id).order_by(SemesterEvent.date)
        )
        events = list(ev_res.scalars().all())
        high_risk_weeks = evaluate_semester_risks(events)
        await db.commit()

        out.append(
            SemesterPlanResponse(
                id=p.id,
                semester_start=p.semester_start,
                semester_end=p.semester_end,
                created_at=p.created_at,
                events=[SemesterEventResponse.model_validate(e) for e in events],
                high_risk_weeks=high_risk_weeks
            )
        )
    return out

@app.post("/api/semester-events", response_model=SemesterEventResponse)
async def add_semester_event(
    payload: SemesterEventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ev = SemesterEvent(
        semester_plan_id=payload.semester_plan_id,
        title=payload.title,
        type=payload.type,
        date=payload.date.replace(tzinfo=None),
        risk_level="low"
    )
    db.add(ev)
    await db.flush()

    all_ev_res = await db.execute(
        select(SemesterEvent).where(SemesterEvent.semester_plan_id == payload.semester_plan_id)
    )
    all_events = list(all_ev_res.scalars().all())
    evaluate_semester_risks(all_events)

    await db.commit()
    await db.refresh(ev)
    return ev

@app.post("/api/semester-plans/{plan_id}/distribute")
async def distribute_semester_load(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_llm_api_key: str = Header(None),
    x_llm_base_url: str = Header(None),
    x_llm_model: str = Header(None)
):
    ev_res = await db.execute(
        select(SemesterEvent).where(SemesterEvent.semester_plan_id == plan_id).order_by(SemesterEvent.date)
    )
    events = list(ev_res.scalars().all())
    if not events:
        raise HTTPException(status_code=400, detail="Add semester events first.")

    sched_res = await db.execute(select(Schedule).where(Schedule.user_id == user.id))
    existing_schedules = list(sched_res.scalars().all())

    created_sessions = 0
    for ev in events:
        if ev.risk_level in ("high", "medium"):
            subtopics = await generate_subtopics_with_ai(
                ev.title, 
                f"Semester {ev.type} preparation", 
                3.0,
                api_key=x_llm_api_key,
                base_url=x_llm_base_url,
                model=x_llm_model
            )
            allocated = allocate_study_slots(existing_schedules, subtopics, ev.date)
            for sub, s_start, s_end in allocated:
                new_block = Schedule(
                    user_id=user.id,
                    title=f"[Semester Prep] {sub.topic}",
                    type="study",
                    start_time=s_start,
                    end_time=s_end
                )
                db.add(new_block)
                existing_schedules.append(new_block)
                created_sessions += 1

    await db.commit()
    return {"message": f"Pre-emptively distributed {created_sessions} study sessions across free calendar slots."}

@app.post("/api/ai/test")
@app.post("/api/ai/test")
async def test_ai_connection(
    x_llm_api_key: str = Header(None),
    x_llm_base_url: str = Header(None),
    x_llm_model: str = Header(None)
):
    import httpx
    from app.config import settings
    
    base_url = (x_llm_base_url or settings.CLOUD_BASE_URL).rstrip('/')
    api_key = x_llm_api_key or settings.CLOUD_API_KEY
    model = x_llm_model or settings.CLOUD_MODEL

    try:
        async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
            res = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "http://localhost:5173", # Required by OpenRouter free tier
                    "X-Title": "Thesis App"
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "Reply with exactly one word: CONNECTED"}],
                    "max_tokens": 50 # Increased from 10 to give the model room to respond
                }
            )
            if res.status_code == 200:
                data = res.json()
                # Safely get the content, even if the model returns None
                content = data["choices"][0]["message"].get("content")
                reply = content.strip() if content else "(Model returned empty response)"
                return {"status": "success", "message": f"Connection successful! AI replied: '{reply}'"}
            else:
                return {"status": "error", "message": f"API Error {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}

@app.delete("/api/semester-events/{event_id}")
async def delete_semester_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Verify the event belongs to a plan owned by the user
    res = await db.execute(
        select(SemesterEvent).join(SemesterPlan).where(
            SemesterEvent.id == event_id,
            SemesterPlan.user_id == user.id
        )
    )
    ev = res.scalar_one_or_none()
    if ev:
        await db.delete(ev)
        await db.commit()
    return {"status": "deleted"}

@app.delete("/api/semester-plans/{plan_id}")
async def delete_semester_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    res = await db.execute(
        select(SemesterPlan).where(SemesterPlan.id == plan_id, SemesterPlan.user_id == user.id)
    )
    plan = res.scalar_one_or_none()
    if plan:
        # The foreign key on SemesterEvent has ondelete="CASCADE", so deleting the plan deletes its events
        await db.delete(plan)
        await db.commit()
    return {"status": "deleted"}