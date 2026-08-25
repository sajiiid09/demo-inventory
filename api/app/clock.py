"""The single place the real clock is read.

The domain layer never reads the clock (ADR-011) — `as_of` is always explicit.
Services need "today" only for R5's "no future dates" guard, and they read it
HERE so tests can monkeypatch one function and stay deterministic.
"""

import datetime as dt


def today() -> dt.date:
    return dt.date.today()
