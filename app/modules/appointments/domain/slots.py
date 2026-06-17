from datetime import date, datetime, time, timedelta

from app.modules.appointments.domain.exceptions import (
    StartOutOfBoundary,
)

SLOT_MINUTES = 15


def is_aligned_to_slot_boundary(start_at: datetime) -> bool:
    minutes = start_at.minute

    return minutes % SLOT_MINUTES == 0


def build_occupied_slot_starts(
    start_at: datetime,
    duration_minutes: int,
) -> list[datetime]:
    if not is_aligned_to_slot_boundary(start_at):
        raise StartOutOfBoundary("start_at should be into slot minutes boundary")

    return [
        start_at + timedelta(minutes=offset)
        for offset in range(0, duration_minutes, SLOT_MINUTES)
    ]


def build_candidate_slot_starts_for_window(
    date: date,
    start_time: time,
    end_time: time,
    duration_minutes: int,
) -> list[datetime]:
    window_start_at = datetime.combine(date, start_time)
    window_end_at = datetime.combine(date, end_time)

    if not is_aligned_to_slot_boundary(window_start_at):
        raise StartOutOfBoundary("start_time should be into slot minutes boundary")

    if not is_aligned_to_slot_boundary(window_end_at):
        raise StartOutOfBoundary("end_time should be into slot minutes boundary")

    candidate_starts: list[datetime] = []
    candidate_start = window_start_at
    duration = timedelta(minutes=duration_minutes)

    while candidate_start + duration <= window_end_at:
        candidate_starts.append(candidate_start)
        candidate_start += timedelta(minutes=SLOT_MINUTES)

    return candidate_starts
