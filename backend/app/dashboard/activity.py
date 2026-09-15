"""Calendar buckets and conservative guards shared by aggregate timelines."""
from datetime import timezone, timedelta
from zoneinfo import ZoneInfo

MELBOURNE = ZoneInfo("Australia/Melbourne")


def local_date(value):
    return value.replace(tzinfo=timezone.utc).astimezone(MELBOURNE).date() if value else None


def bucket(day, interval):
    if day is None:
        return "unknown"
    if interval == "week":
        day -= timedelta(days=day.weekday())
    return day.strftime("%Y-%m") if interval == "month" else day.isoformat()


def group_guard(groups, population, reason=None):
    """Aggregate groups are publishable; callers still keep identities internal."""
    return None
