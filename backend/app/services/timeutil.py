"""Local-time helpers. DB stores naive UTC; business days are in the local timezone."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import TIMEZONE

TZ = ZoneInfo(TIMEZONE)


def local_now() -> datetime:
    return datetime.now(TZ)


def local_today() -> date:
    return local_now().date()


def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(UTC).replace(tzinfo=None)


def to_local(dt_utc_naive: datetime) -> datetime:
    return dt_utc_naive.replace(tzinfo=UTC).astimezone(TZ)


def day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    """[start, end) of a local calendar day expressed as naive UTC datetimes."""
    start = datetime.combine(d, time.min, tzinfo=TZ)
    return to_utc_naive(start), to_utc_naive(start + timedelta(days=1))


def range_bounds_utc(start: date, end: date) -> tuple[datetime, datetime]:
    """[start 00:00, end+1 00:00) local, as naive UTC."""
    return day_bounds_utc(start)[0], day_bounds_utc(end)[1]
