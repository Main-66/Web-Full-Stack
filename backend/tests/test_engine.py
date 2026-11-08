from datetime import datetime
from app.models import Schedule
from app.services.conflict_detector import find_overlapping_schedules, suggest_resolution_slots
from app.services.study_planner import balance_weekly_workload

def test_conflict_detection_identifies_overlap():
    existing = [
        Schedule(
            id="1",
            title="Algorithms Lecture",
            type="class",
            start_time=datetime(2026, 11, 10, 10, 0),
            end_time=datetime(2026, 11, 10, 12, 0),
        )
    ]
    overlaps = find_overlapping_schedules(
        existing,
        datetime(2026, 11, 10, 11, 0),
        datetime(2026, 11, 10, 13, 0),
    )
    assert len(overlaps) == 1
    assert overlaps[0].title == "Algorithms Lecture"

def test_resolution_suggestions_are_conflict_free():
    existing = [
        Schedule(
            id="1",
            title="Algorithms Lecture",
            type="class",
            start_time=datetime(2026, 11, 10, 10, 0),
            end_time=datetime(2026, 11, 10, 12, 0),
        )
    ]
    suggestions = suggest_resolution_slots(
        existing,
        datetime(2026, 11, 10, 10, 0),
        datetime(2026, 11, 10, 12, 0),
    )
    assert len(suggestions) == 3
    assert suggestions[0].start_time >= datetime(2026, 11, 10, 12, 0)