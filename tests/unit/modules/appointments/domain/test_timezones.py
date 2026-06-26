from datetime import UTC, date, datetime

import pytest

from app.modules.appointments.domain.timezones import (
    InvalidTimezone,
    NaiveDateTime,
    NonexistentLocalTime,
    local_naive_to_utc,
    provider_local_date,
    provider_local_day_bounds_utc,
    resolve_timezone,
    to_utc,
)


def test_resolve_timezone_accepts_valid_iana_name() -> None:
    timezone = resolve_timezone('America/Fortaleza')

    assert timezone.key == 'America/Fortaleza'


def test_resolve_timezone_rejects_invalid_name() -> None:
    with pytest.raises(InvalidTimezone):
        resolve_timezone('Not/AZone')


def test_provider_local_day_bounds_convert_to_utc() -> None:
    timezone = resolve_timezone('America/Fortaleza')

    start_at, end_at = provider_local_day_bounds_utc(date(2026, 6, 10), timezone)

    assert start_at == datetime(2026, 6, 10, 3, 0, tzinfo=UTC)
    assert end_at == datetime(2026, 6, 11, 3, 0, tzinfo=UTC)


def test_provider_local_date_handles_utc_day_boundary() -> None:
    timezone = resolve_timezone('America/Fortaleza')

    local_date = provider_local_date(
        datetime(2026, 6, 10, 2, 30, tzinfo=UTC),
        timezone,
    )

    assert local_date == date(2026, 6, 9)


def test_to_utc_rejects_naive_datetime() -> None:
    with pytest.raises(NaiveDateTime):
        to_utc(datetime(2026, 6, 10, 9, 0))


def test_local_naive_to_utc_uses_first_ambiguous_dst_instant() -> None:
    timezone = resolve_timezone('America/New_York')

    instant = local_naive_to_utc(datetime(2026, 11, 1, 1, 30), timezone)

    assert instant == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_local_naive_to_utc_rejects_nonexistent_dst_time() -> None:
    timezone = resolve_timezone('America/New_York')

    with pytest.raises(NonexistentLocalTime):
        local_naive_to_utc(datetime(2026, 3, 8, 2, 30), timezone)
