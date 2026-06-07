from datetime import datetime, timedelta

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
