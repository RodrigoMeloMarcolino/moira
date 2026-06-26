from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezone(ValueError):
    pass


class NaiveDateTime(ValueError):
    pass


class NonexistentLocalTime(ValueError):
    pass


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezone(f'invalid timezone: {timezone_name}') from exc


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDateTime('datetime must include timezone offset')

    return value


def to_utc(value: datetime) -> datetime:
    return ensure_aware(value).astimezone(UTC)


def provider_local_day_bounds_utc(
    target_date: date,
    provider_timezone: ZoneInfo,
) -> tuple[datetime, datetime]:
    local_start = datetime.combine(target_date, time.min, provider_timezone)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def local_naive_to_utc(
    value: datetime,
    provider_timezone: ZoneInfo,
) -> datetime:
    if value.tzinfo is not None:
        raise ValueError('local candidate datetime must be naive')

    local_value = value.replace(tzinfo=provider_timezone, fold=0)
    utc_value = local_value.astimezone(UTC)
    roundtrip = utc_value.astimezone(provider_timezone).replace(tzinfo=None)
    if roundtrip != value:
        raise NonexistentLocalTime(f'nonexistent local time: {value.isoformat()}')

    return utc_value


def provider_local_date(
    value: datetime,
    provider_timezone: ZoneInfo,
) -> date:
    return to_utc(value).astimezone(provider_timezone).date()
