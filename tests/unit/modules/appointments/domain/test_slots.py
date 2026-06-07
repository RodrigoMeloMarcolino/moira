from datetime import datetime

from app.modules.appointments.domain.slots import (
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
