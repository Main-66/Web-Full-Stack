import httpx
from datetime import datetime, timedelta, time
from typing import List, Tuple
from app.config import settings
from app.models import Schedule, Task, SemesterEvent
from app.schemas import LLMStudyBreakdown, SubtopicItem, DailyLoadItem
from app.services.conflict_detector import find_overlapping_schedules
from app.services.ai_nlp import clean_json_text, validate_base_url

async def generate_subtopics_with_ai(
    task_title: str,
    description: str,
    total_hours: float,
    api_key: str = None,
    base_url: str = None,
    model: str = None
) -> List[SubtopicItem]:
    total_minutes = max(60, int(total_hours * 60))

    system_prompt = (
        "You are an academic study planner. Break the given exam or course task into sequential, "
        f"concrete study subtopics whose durations sum to approximately {total_minutes} minutes. "
        "Each session must be between 45 and 90 minutes.\n"
        "Return a JSON object with exactly one key: 'subtopics'.\n"
        "'subtopics' must be a list of objects, where each object has exactly two keys:\n"
        "- topic: string\n"
        "- duration_minutes: integer\n"
        "CRITICAL: Return ONLY raw JSON. Do NOT wrap it in markdown."
    )

    user_prompt = f"Subject/Task: {task_title}\nDetails: {description or 'General exam preparation'}\nTotal study time: {total_minutes} minutes"
    schema = LLMStudyBreakdown.model_json_schema()

    use_cloud = bool(api_key) or settings.LLM_PROVIDER != "ollama"
    active_key = api_key or settings.CLOUD_API_KEY
    active_base = validate_base_url(base_url or settings.CLOUD_BASE_URL)
    active_model = model or settings.CLOUD_MODEL

    try:
        if not use_cloud:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": settings.OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "format": schema,
                        "stream": False,
                        "options": {"temperature": 0.2}
                    }
                )
                res.raise_for_status()
                raw_json = res.json()["message"]["content"]
                parsed = LLMStudyBreakdown.model_validate_json(clean_json_text(raw_json))
                if parsed.subtopics:
                    return parsed.subtopics
        else:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                res = await client.post(
                    f"{active_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {active_key}",
                        "HTTP-Referer": "http://localhost:5173",
                        "X-Title": "Thesis App"
                    },
                    json={
                        "model": active_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.2
                    }
                )
                res.raise_for_status()
                raw_json = res.json()["choices"][0]["message"]["content"]
                parsed = LLMStudyBreakdown.model_validate_json(clean_json_text(raw_json))
                if parsed.subtopics:
                    return parsed.subtopics
    except Exception as e:
        print(f"!!! Study Planner LLM API Error: {e}")

    num_sessions = max(2, round(total_minutes / 60))
    per_session = max(45, total_minutes // num_sessions)
    phases = ["Core Concepts & Theory", "Problem Solving & Practice", "Past Papers & Edge Cases", "Final Active Recall Review"]
    return [
        SubtopicItem(
            topic=f"{task_title} - Part {i+1}: {phases[i % len(phases)]}",
            duration_minutes=per_session
        )
        for i in range(num_sessions)
    ]

def allocate_study_slots(
    existing_schedules: List[Schedule],
    subtopics: List[SubtopicItem],
    deadline: datetime
) -> List[Tuple[SubtopicItem, datetime, datetime]]:
    now = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    cursor_day = now.date()
    end_day = max(cursor_day + timedelta(days=1), deadline.date())

    simulated_schedules = list(existing_schedules)
    allocated: List[Tuple[SubtopicItem, datetime, datetime]] = []

    for sub in subtopics:
        duration = timedelta(minutes=sub.duration_minutes)
        placed = False
        day = cursor_day

        while day <= end_day and not placed:
            slot_start = datetime.combine(day, time(9, 0))
            if slot_start < now:
                slot_start = now

            day_limit = datetime.combine(day, time(21, 0))

            sessions_on_day = sum(1 for _, s_start, _ in allocated if s_start.date() == day)
            if sessions_on_day < 2:
                while slot_start + duration <= day_limit:
                    slot_end = slot_start + duration
                    conflicts = find_overlapping_schedules(simulated_schedules, slot_start, slot_end)
                    if not conflicts:
                        allocated.append((sub, slot_start, slot_end))
                        simulated_schedules.append(
                            Schedule(
                                title=f"Study: {sub.topic}",
                                type="study",
                                start_time=slot_start,
                                end_time=slot_end
                            )
                        )
                        placed = True
                        break
                    slot_start += timedelta(minutes=30)

            day += timedelta(days=1)

        if not placed:
            fallback_start = datetime.combine(end_day, time(18, 0)) + timedelta(days=len(allocated))
            allocated.append((sub, fallback_start, fallback_start + duration))

    return allocated

def balance_weekly_workload(
    existing_schedules: List[Schedule],
    daily_max_hours: float = 5.0
) -> Tuple[int, List[str]]:
    today = datetime.now().date()
    week_days = [today + timedelta(days=i) for i in range(7)]

    def get_day_hours(d):
        total_sec = sum(
            (s.end_time - s.start_time).total_seconds()
            for s in existing_schedules
            if s.start_time.date() == d
        )
        return total_sec / 3600.0

    moved_count = 0
    logs: List[str] = []

    for d in week_days:
        while get_day_hours(d) > daily_max_hours:
            flexible = [
                s for s in existing_schedules
                if s.start_time.date() == d and s.type in ("study", "event")
            ]
            if not flexible:
                break

            item_to_move = flexible[-1]
            duration = item_to_move.end_time - item_to_move.start_time

            candidate_days = sorted(
                [cd for cd in week_days if cd != d],
                key=lambda x: get_day_hours(x)
            )

            relocated = False
            for target_day in candidate_days:
                if get_day_hours(target_day) + (duration.total_seconds() / 3600.0) > daily_max_hours:
                    continue

                cursor = datetime.combine(target_day, time(9, 0))
                day_end = datetime.combine(target_day, time(21, 0))
                while cursor + duration <= day_end:
                    conflicts = find_overlapping_schedules(
                        existing_schedules, cursor, cursor + duration, exclude_id=item_to_move.id
                    )
                    if not conflicts:
                        old_date_str = item_to_move.start_time.strftime("%a %b %d")
                        new_date_str = cursor.strftime("%a %b %d %H:%M")
                        item_to_move.start_time = cursor
                        item_to_move.end_time = cursor + duration
                        moved_count += 1
                        logs.append(f"Moved '{item_to_move.title}' from overloaded {old_date_str} to {new_date_str}")
                        relocated = True
                        break
                    cursor += timedelta(minutes=30)

                if relocated:
                    break

            if not relocated:
                break

    return moved_count, logs

def compute_daily_summary(existing_schedules: List[Schedule], daily_max_hours: float = 5.0) -> List[DailyLoadItem]:
    today = datetime.now().date()
    summary: List[DailyLoadItem] = []
    for i in range(7):
        d = today + timedelta(days=i)
        day_events = [s for s in existing_schedules if s.start_time.date() == d]
        hours = round(sum((s.end_time - s.start_time).total_seconds() for s in day_events) / 3600.0, 2)
        summary.append(
            DailyLoadItem(
                date=d.strftime("%a, %b %d"),
                total_hours=hours,
                event_count=len(day_events),
                overloaded=hours > daily_max_hours
            )
        )
    return summary

def evaluate_semester_risks(events: List[SemesterEvent]) -> List[str]:
    week_Map = {}
    for ev in events:
        iso_year, iso_week, _ = ev.date.isocalendar()
        key = f"{iso_year}-W{iso_week:02d}"
        week_Map.setdefault(key, []).append(ev)

    high_risk_weeks = []
    for week_key, ev_list in week_Map.items():
        if len(ev_list) >= 2:
            for ev in ev_list:
                ev.risk_level = "high"
            monday = datetime.fromisocalendar(int(week_key[:4]), int(week_key[-2:]), 1)
            high_risk_weeks.append(
                f"Week of {monday.strftime('%b %d, %Y')} ({len(ev_list)} overlapping exams/deadlines)"
            )
        else:
            ev_list[0].risk_level = "medium" if ev_list[0].type in ("exam", "midterm") else "low"

    return high_risk_weeks