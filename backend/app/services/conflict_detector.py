from datetime import datetime, timedelta
from typing import List
from app.models import Schedule
from app.schemas import ResolutionSlot

def find_overlapping_schedules(
    existing_schedules: List[Schedule],
    candidate_start: datetime,
    candidate_end: datetime,
    exclude_id=None
) -> List[Schedule]:
    """
    Deterministic interval overlap check:
    Two events A and B overlap iff Start_A < End_B and End_A > Start_B.
    """
    overlaps = []
    for sched in existing_schedules:
        if exclude_id and sched.id == exclude_id:
            continue
        if sched.start_time < candidate_end and sched.end_time > candidate_start:
            overlaps.append(sched)
    return overlaps

def suggest_resolution_slots(
    existing_schedules: List[Schedule],
    desired_start: datetime,
    desired_end: datetime,
    max_suggestions: int = 3
) -> List[ResolutionSlot]:
    """
    Scans forward in 30-minute increments within waking hours (08:00 - 21:00)
    to suggest conflict-free alternative time slots of the exact same duration.
    """
    duration = desired_end - desired_start
    suggestions: List[ResolutionSlot] = []
    cursor = desired_start + timedelta(minutes=30)
    search_limit = desired_start + timedelta(days=5)

    while cursor < search_limit and len(suggestions) < max_suggestions:
        # Keep suggestions inside normal study hours (08:00 to 21:00)
        if 8 <= cursor.hour < 21 and (cursor + duration).hour <= 22:
            candidate_end = cursor + duration
            conflicts = find_overlapping_schedules(existing_schedules, cursor, candidate_end)
            if not conflicts:
                suggestions.append(
                    ResolutionSlot(
                        start_time=cursor,
                        end_time=candidate_end,
                        label=f"{cursor.strftime('%a %b %d, %H:%M')} - {candidate_end.strftime('%H:%M')}"
                    )
                )
                cursor = candidate_end  # Jump past this suggested block
                continue
        cursor += timedelta(minutes=30)

    return suggestions