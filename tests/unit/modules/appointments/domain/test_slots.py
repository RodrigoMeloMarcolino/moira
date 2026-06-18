from datetime import date, datetime, time

import pytest

from app.modules.appointments.domain.exceptions import StartOutOfBoundary
from app.modules.appointments.domain.slots import (
    build_candidate_slot_starts_for_window,
    build_occupied_slot_starts,
    is_aligned_to_slot_boundary,
)


def test_should_return_true_to_valid_start_at_boundary() -> None:
    assert is_aligned_to_slot_boundary(datetime(2026, 6, 5, 9, 0)) is True


def test_should_return_false_to_invalid_start_at_boundary() -> None:
    assert is_aligned_to_slot_boundary(datetime(2026, 6, 5, 9, 10)) is False


def test_should_return_one_slot() -> None:
    assert len(build_occupied_slot_starts(datetime(2026, 6, 5, 9, 0), 15)) == 1


def test_should_return_two_slots() -> None:
    assert len(build_occupied_slot_starts(datetime(2026, 6, 5, 9, 0), 30)) == 2


def test_should_return_three_slots() -> None:
    assert len(build_occupied_slot_starts(datetime(2026, 6, 5, 9, 0), 45)) == 3


def test_should_return_four_slots() -> None:
    assert len(build_occupied_slot_starts(datetime(2026, 6, 5, 9, 0), 60)) == 4


def test_should_build_candidate_starts_until_duration_fits_window() -> None:
    candidates = build_candidate_slot_starts_for_window(
        date=date(2026, 6, 5),
        start_time=time(8, 0),
        end_time=time(12, 0),
        duration_minutes=60,
    )

    assert candidates == [
        datetime(2026, 6, 5, 8, 0),
        datetime(2026, 6, 5, 8, 15),
        datetime(2026, 6, 5, 8, 30),
        datetime(2026, 6, 5, 8, 45),
        datetime(2026, 6, 5, 9, 0),
        datetime(2026, 6, 5, 9, 15),
        datetime(2026, 6, 5, 9, 30),
        datetime(2026, 6, 5, 9, 45),
        datetime(2026, 6, 5, 10, 0),
        datetime(2026, 6, 5, 10, 15),
        datetime(2026, 6, 5, 10, 30),
        datetime(2026, 6, 5, 10, 45),
        datetime(2026, 6, 5, 11, 0),
    ]


def test_should_build_one_candidate_when_window_matches_duration() -> None:
    assert build_candidate_slot_starts_for_window(
        date=date(2026, 6, 5),
        start_time=time(8, 0),
        end_time=time(9, 0),
        duration_minutes=60,
    ) == [datetime(2026, 6, 5, 8, 0)]


def test_should_return_no_candidates_when_window_is_shorter_than_duration() -> None:
    assert (
        build_candidate_slot_starts_for_window(
            date=date(2026, 6, 5),
            start_time=time(8, 0),
            end_time=time(8, 45),
            duration_minutes=60,
        )
        == []
    )


def test_should_raise_when_candidate_window_start_is_out_of_boundary() -> None:
    with pytest.raises(StartOutOfBoundary):
        build_candidate_slot_starts_for_window(
            date=date(2026, 6, 5),
            start_time=time(8, 10),
            end_time=time(12, 0),
            duration_minutes=60,
        )


def test_should_raise_when_candidate_window_end_is_out_of_boundary() -> None:
    with pytest.raises(StartOutOfBoundary):
        build_candidate_slot_starts_for_window(
            date=date(2026, 6, 5),
            start_time=time(8, 0),
            end_time=time(12, 10),
            duration_minutes=60,
        )
