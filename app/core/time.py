"""Datetime helpers.

`datetime.utcnow()` is deprecated in Python 3.12+. This module exposes a
drop-in replacement that returns a naive UTC datetime — matching the naive
`DateTime` columns used throughout the models — so we stay compatible with
future Python versions without having to migrate all existing timestamps.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
