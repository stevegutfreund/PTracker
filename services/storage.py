#!/usr/bin/env python3
"""
JSON storage service for PTracker.

Data format – a flat, ordered JSON array where each element is a period entry:
    {
        "date":        "DD-MM-YYYY",   # e.g. "14-07-2024"
        "after_shkia": true | false,   # true → after shkia (night onah, next Hebrew day)
        "clean_start": true | false    # true  → this entry begins a new counting
                                       #          bloc (was preceded by "---" in the
                                       #          original text file)
    }

Ordering is critical: entries are always stored oldest-first.  The most
recent bloc (the sequence since the last clean_start entry) is used for all
Vesset calculations.
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

from calendarkit import hebrew

import settings

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = str(settings.DATA_DIR)
PERIODS_FILE = os.path.join(DATA_DIR, "periods.json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _validate_entry(entry: dict) -> bool:
    """Return True if entry has the required shape."""
    try:
        if not isinstance(entry, dict):
            return False
        datetime.strptime(entry["date"], "%d-%m-%Y")
        if not isinstance(entry["after_shkia"], bool):
            return False
        if not isinstance(entry.get("clean_start", False), bool):
            return False
        return True
    except (KeyError, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def load_periods() -> List[dict]:
    """Return all period entries from storage (oldest first).
    Returns an empty list if the file does not exist or is malformed.
    """
    _ensure_data_dir()
    if not os.path.exists(PERIODS_FILE):
        return []
    try:
        with open(PERIODS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, list):
            return []
        # Filter out any malformed entries rather than crashing.
        return [e for e in data if _validate_entry(e)]
    except (json.JSONDecodeError, OSError):
        return []


def save_periods(entries: List[dict]) -> None:
    """Persist the entry list to storage (atomic-ish write)."""
    _ensure_data_dir()
    tmp = PERIODS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, PERIODS_FILE)


# ---------------------------------------------------------------------------
# Datetime conversion
# ---------------------------------------------------------------------------

def entry_to_datetime(entry: dict) -> datetime:
    """Convert a storage entry to a datetime.

    The time only encodes the onah: before shkia → hour 11, after shkia → hour 23.
    """
    dt = datetime.strptime(entry["date"], "%d-%m-%Y")
    hour = 23 if entry["after_shkia"] else 11
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0)


def datetime_to_entry(dt: datetime, clean_start: bool = False) -> dict:
    """Convert a datetime back to a storage entry dict."""
    return {
        "date": dt.strftime("%d-%m-%Y"),
        "after_shkia": is_night_onah(dt),
        "clean_start": bool(clean_start),
    }


# ---------------------------------------------------------------------------
# Delta (Hebrew-aware cycle length)
# ---------------------------------------------------------------------------

def compute_delta(date1: datetime, date2: datetime) -> int:
    """Cycle length from *date2* to *date1*, counted in Hebrew days.

    An after-shkia period belongs to the next Hebrew day. The result is
    1-indexed: two periods on the same Hebrew day give 1.
    """
    return hebrew.hebrew_days_between(date1, is_night_onah(date1),
                                      date2, is_night_onah(date2)) + 1


def is_night_onah(dt: datetime) -> bool:
    """True for an after-shkia period (stored as hour 23)."""
    return dt.hour >= 12


# ---------------------------------------------------------------------------
# Bloc-aware period retrieval (mirrors getLastNPeriodsFromFile)
# ---------------------------------------------------------------------------

def get_last_n_periods_as_datetimes(n: int) -> List[datetime]:
    """Return the last *n* periods as datetime objects from the most recent bloc.

    Mirrors the text-file behaviour of ``utils.getLastNPeriodsFromFile``:
    – Iterates from the newest entry backwards.
    – Stops when it either reaches *n* entries or hits a clean_start boundary
      (i.e., the start of the current bloc – nothing before it is relevant).
    – Returns the result in ascending (oldest-first) order.
    """
    entries = load_periods()
    result: List[datetime] = []
    for entry in reversed(entries):
        result.append(entry_to_datetime(entry))
        if len(result) >= n:
            break
        if entry.get("clean_start", False):
            # This entry is the oldest one in its bloc; don't cross into the
            # previous bloc.
            break
    result.reverse()
    return result


def get_all_periods_with_meta() -> List[dict]:
    """Return all entries enriched with index, datetime, delta, and days_ago."""
    entries = load_periods()
    enriched = []
    prev_dt: Optional[datetime] = None
    prev_clean_start = True  # sentinel: treat beginning of file as bloc boundary

    for i, entry in enumerate(entries):
        dt = entry_to_datetime(entry)
        # Delta is None when this entry starts a new bloc or is the very first.
        if entry.get("clean_start", False) or prev_dt is None:
            delta_val = None
        else:
            delta_val = compute_delta(dt, prev_dt)

        enriched.append(
            {
                "entry": entry,
                "index": i,
                "dt": dt,
                "delta": delta_val,
                "days_ago": (datetime.now() - dt).days,
            }
        )
        prev_dt = dt
        prev_clean_start = entry.get("clean_start", False)

    return enriched


def get_blocs() -> List[List[dict]]:
    """Group enriched entries into blocs (sequences between clean-starts)."""
    enriched = get_all_periods_with_meta()
    blocs: List[List[dict]] = []
    current: List[dict] = []
    for item in enriched:
        if item["entry"].get("clean_start", False) and current:
            blocs.append(current)
            current = []
        current.append(item)
    if current:
        blocs.append(current)
    return blocs


def get_stats() -> dict:
    """Compute summary statistics from the most recent bloc."""
    entries = load_periods()
    total = len(entries)
    blocs = sum(1 for e in entries if e.get("clean_start", False))

    recent = get_last_n_periods_as_datetimes(12)
    cycles: List[int] = []
    for i in range(len(recent) - 1):
        cycles.append(compute_delta(recent[i + 1], recent[i]))

    avg_cycle = round(sum(cycles) / len(cycles), 1) if cycles else None
    min_cycle = min(cycles) if cycles else None
    max_cycle = max(cycles) if cycles else None

    last_period = recent[-1] if recent else None
    predicted_next = None
    days_until_next = None
    if last_period and avg_cycle:
        predicted_next = last_period + timedelta(days=int(avg_cycle) - 1)
        days_until_next = (predicted_next - datetime.now()).days

    return {
        "total_periods": total,
        "total_blocs": blocs,
        "avg_cycle": avg_cycle,
        "min_cycle": min_cycle,
        "max_cycle": max_cycle,
        "last_period": last_period,
        "predicted_next": predicted_next,
        "days_until_next": days_until_next,
        "file_exists": os.path.exists(PERIODS_FILE),
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def add_period(date_str: str, after_shkia: bool, clean_start: bool) -> dict:
    """Append a new period entry (always at the end – chronological order).
    Returns the newly created entry.
    """
    entry = {
        "date": date_str,
        "after_shkia": bool(after_shkia),
        "clean_start": bool(clean_start),
    }
    entries = load_periods()
    entries.append(entry)
    save_periods(entries)
    return entry


def get_period(index: int) -> Optional[dict]:
    """Return the entry at *index*, or None if out of range."""
    entries = load_periods()
    if 0 <= index < len(entries):
        return entries[index]
    return None


def update_period(index: int, date_str: str, after_shkia: bool, clean_start: bool) -> bool:
    """Overwrite the entry at *index*.  Returns False if index is out of range."""
    entries = load_periods()
    if index < 0 or index >= len(entries):
        return False
    entries[index] = {
        "date": date_str,
        "after_shkia": bool(after_shkia),
        "clean_start": bool(clean_start),
    }
    save_periods(entries)
    return True


def delete_period(index: int) -> bool:
    """Remove the entry at *index*.  Returns False if index is out of range.

    When deleting an entry whose ``clean_start`` is True, the flag is simply
    removed along with the entry – the preceding bloc then continues naturally
    into what was the deleted entry's bloc.  This mirrors the text-file
    behaviour where the preceding '---' line was also removed on delete.
    """
    entries = load_periods()
    if index < 0 or index >= len(entries):
        return False
    entries.pop(index)
    save_periods(entries)
    return True


def move_period(index: int, direction: int) -> bool:
    """Swap the entry at *index* with its neighbour.

    direction: -1 = move up (swap with index-1), +1 = move down (swap with index+1).
    Returns False if the move is not possible.
    """
    entries = load_periods()
    target = index + direction
    if index < 0 or index >= len(entries):
        return False
    if target < 0 or target >= len(entries):
        return False
    entries[index], entries[target] = entries[target], entries[index]
    save_periods(entries)
    return True
