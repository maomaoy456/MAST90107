"""Small, reusable conversions. Errors contain codes only, never source values."""
import hashlib
import hmac
import math
from numbers import Real

import pandas as pd

LOCAL_ZONE = "Australia/Melbourne"


class InvalidValue(ValueError):
    pass


def empty(value):
    return value is None or bool(pd.isna(value)) or (isinstance(value, str) and not value.strip())


def string(value, *, required=False):
    if empty(value):
        if required:
            raise InvalidValue("missing_required")
        return None
    # Excel may infer numeric identifier columns as floating-point numbers.
    if isinstance(value, Real) and float(value).is_integer():
        return str(int(value))
    return str(value).strip()


def number(value, *, integer=False, minimum=None):
    if empty(value):
        return None
    try:
        result = float(value)
        if not math.isfinite(result) or (integer and not result.is_integer()):
            raise ValueError
        if minimum is not None and result < minimum:
            raise ValueError
        return int(result) if integer else result
    except (TypeError, ValueError):
        raise InvalidValue("invalid_number") from None


def boolean(value):
    if empty(value):
        return None
    token = str(value).strip().lower()
    if token in {"true", "1", "1.0"}:
        return True
    if token in {"false", "0", "0.0"}:
        return False
    raise InvalidValue("invalid_row")


def timestamp(value):
    """Assume Melbourne for naive timestamps; explicit Z/offsets retain their instant.

    MySQL stores UTC without an offset. DST gaps/overlaps are rejected for review.
    """
    if empty(value):
        return None
    try:
        t = pd.to_datetime(value, unit="D", origin="1899-12-30") if isinstance(value, Real) else pd.Timestamp(value)
        if pd.isna(t):
            raise ValueError
        if t.tzinfo is None:
            t = t.tz_localize(LOCAL_ZONE, ambiguous="raise", nonexistent="raise")
        return t.tz_convert("UTC").tz_localize(None).round("ms").to_pydatetime()
    except Exception:
        raise InvalidValue("invalid_date") from None


def calendar_date(value):
    """A date label is not midnight as an event instant: apply no timezone shift."""
    if empty(value):
        return None
    try:
        t = pd.to_datetime(value, unit="D", origin="1899-12-30") if isinstance(value, Real) else pd.Timestamp(value)
        if pd.isna(t):
            raise ValueError
        return t.date()
    except Exception:
        raise InvalidValue("invalid_date") from None


def identity(value, key):
    token = string(value)
    return hmac.new(key.encode(), token.encode(), hashlib.sha256).hexdigest() if token else None


def json_value(value):
    if empty(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value
