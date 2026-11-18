#!/usr/bin/env python3
"""
Google Calendar sync for PTracker: period events, Vestot and day markers.

Transport/auth live in calendarkit.gcal. The app works fully without Google
credentials; calendar availability is checked on demand via is_available().
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import dateutil.parser
from dateutil.relativedelta import relativedelta

from calendarkit.gcal import CalendarClient, summary_contains

import settings
from services.storage import (
    compute_delta,
    entry_to_datetime,
    get_last_n_periods_as_datetimes,
    load_periods,
)

log = logging.getLogger(__name__)

PERIOD_LABEL = settings.LANGUAGE_CALENDAR.period
VESSET_LABEL = settings.LANGUAGE_CALENDAR.vesset
MARK_LABEL   = settings.LANGUAGE_CALENDAR.mark


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _make_client() -> CalendarClient:
    return CalendarClient(
        settings.GOOGLE_CREDENTIALS_FILE,
        settings.GOOGLE_TOKEN_FILE,
        timezone=settings.CALENDAR_TIMEZONE,
        allow_browser_flow=settings.GOOGLE_ALLOW_BROWSER_AUTH,
    )


_client: Optional[CalendarClient] = None


def client() -> CalendarClient:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


def is_available() -> bool:
    """True if a calendar is configured and the API is reachable."""
    return bool(settings.CALENDAR_ID) and client().is_available()


def get_error() -> Optional[str]:
    """Why the calendar is unavailable, or None."""
    if not settings.CALENDAR_ID:
        return "CALENDAR_ID is not set in .env"
    return client().last_error


def _calendar_id() -> str:
    if not settings.CALENDAR_ID:
        raise RuntimeError("Google Calendar is not available (CALENDAR_ID is not set in .env).")
    return settings.CALENDAR_ID


def _create_event(when: datetime, summary: str, all_day: bool = False) -> None:
    if all_day:
        client().create_all_day_event(_calendar_id(), when, summary)
    else:
        client().create_timed_event(_calendar_id(), when, summary)


def _delete_events_range(start: datetime, end: Optional[datetime] = None,
                         event_type: Optional[str] = None) -> int:
    """Delete events from *start* to *end* (default: 3 months from now) whose
    title contains *event_type* (all events if None)."""
    if end is None:
        end = datetime.utcnow() + relativedelta(months=3)
    where = summary_contains(event_type) if event_type else None
    return client().delete_events(_calendar_id(), start, end, where=where)


def _period_summary(delta: Optional[int]) -> str:
    return f"{PERIOD_LABEL} ({settings.CLEAN_PERIOD if delta is None else delta})"


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

def add_period_to_calendar(period_dt: datetime, clean_start: bool) -> None:
    """Add a period event, titled with the cycle length since the previous one.

    Call *after* the new period has been written to storage.
    """
    prev_dt: Optional[datetime] = None
    if not clean_start:
        for entry in reversed(load_periods()):
            dt = entry_to_datetime(entry)
            if dt < period_dt:
                prev_dt = dt
                break
            if entry.get("clean_start", False):
                break  # hit a bloc boundary before finding a prior period

    delta = None if (clean_start or prev_dt is None) else compute_delta(period_dt, prev_dt)
    _create_event(period_dt, _period_summary(delta))


def delete_period_from_calendar(period_dt: datetime) -> None:
    """Delete the period event that matches *period_dt* (date + onah; events are timed 11:00 / 23:00)."""
    day_start = period_dt.replace(hour=0)
    wanted = period_dt.strftime("%d-%m-%Y %p")
    for ev in client().iter_events(_calendar_id(), day_start, day_start + timedelta(days=1),
                                   order_by_start=True):
        start = ev.get("start", {}).get("dateTime")
        if PERIOD_LABEL not in ev.get("summary", "") or not start:
            continue
        if dateutil.parser.parse(start).strftime("%d-%m-%Y %p") == wanted:
            client().delete_event(_calendar_id(), ev["id"])
            return
    raise ValueError(f"No calendar event found for {wanted}")


def copy_all_to_calendar() -> dict:
    """Copy every stored period to the calendar. Returns {"success": n, "errors": n}."""
    success = errors = 0
    prev_dt: Optional[datetime] = None
    for entry in load_periods():
        dt = entry_to_datetime(entry)
        if entry.get("clean_start", False):
            prev_dt = None
        delta = compute_delta(dt, prev_dt) if prev_dt else None
        try:
            _create_event(dt, _period_summary(delta))
            success += 1
        except Exception as exc:
            log.warning("Could not copy period %s: %s", entry.get("date"), exc)
            errors += 1
        prev_dt = dt
    return {"success": success, "errors": errors}


# ---------------------------------------------------------------------------
# Clearing
# ---------------------------------------------------------------------------

def clear_last_vestot_from_calendar() -> int:
    """Delete Vesset events from the second-to-last period onwards."""
    periods = get_last_n_periods_as_datetimes(2)
    if not periods:
        return 0
    return _delete_events_range(start=periods[0], event_type=VESSET_LABEL)


def clear_all_events() -> int:
    """Delete every event in the calendar since HISTORY_START."""
    return _delete_events_range(start=settings.HISTORY_START)


def clear_all_periods() -> int:
    return _delete_events_range(start=settings.HISTORY_START, event_type=PERIOD_LABEL)


def clear_all_vestot() -> int:
    return _delete_events_range(start=settings.HISTORY_START, event_type=VESSET_LABEL)


# ---------------------------------------------------------------------------
# Vestot & day markers
# ---------------------------------------------------------------------------

def add_vestot_to_calendar(suspects: list) -> int:
    """Write Vesset suspects to the calendar. Returns the number added."""
    added = 0
    for s in suspects:
        try:
            _create_event(s.date, f"{VESSET_LABEL} - {s.get_hebrew_description()}")
            added += 1
        except Exception as exc:
            log.warning("Could not add vesset '%s': %s", s, exc)
    return added


def mark_day(day_number: int, hebrew_calc: bool = True) -> datetime:
    """Create an all-day 'Day N' event counted from the last period.

    With *hebrew_calc*, an after-shkia period counts from the next day.
    Returns the marked date.
    """
    last = get_last_n_periods_as_datetimes(1)
    if not last:
        raise ValueError("No periods found in storage.")

    last_dt = last[0]
    day_offset = 1 if hebrew_calc and last_dt.hour >= 12 else 0
    mark_date = last_dt + timedelta(days=day_number + day_offset)
    _create_event(mark_date, f"{MARK_LABEL} {day_number}", all_day=True)
    return mark_date
