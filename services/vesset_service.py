#!/usr/bin/env python3
"""
Vesset calculation service: feeds the stored periods and the user's
preferences (re-read on every call) into the pure calculation engine.
"""

import sys
from datetime import datetime
from typing import List

import settings
from services import preferences
from services.storage import get_last_n_periods_as_datetimes
from services.vesset_engine import Suspect, VessetCalculator


def calculate_vestot() -> List[Suspect]:
    """All observed Vestot from the current bloc ([] if there is no data)."""
    # The whole bloc: with "longer_only" an old long interval can stay in force
    # however many shorter ones followed it.
    periods = get_last_n_periods_as_datetimes(sys.maxsize)
    if not periods:
        return []
    prefs = preferences.load(settings.APP_CONFIG_FILE)
    return VessetCalculator(
        periods,
        rules=preferences.engine_rules(prefs),
        labels=settings.LANGUAGE,
        calendar_labels=settings.LANGUAGE_CALENDAR,
        use_calendar_labels=settings.LANGUAGE_NAME == "hebrew",
        haflagah_uprooting=prefs["haflagah_uprooting"],
    ).calculate()


def get_last_periods_summary(n: int = 4) -> List[datetime]:
    """Return the most recent *n* period datetimes (current bloc only)."""
    return get_last_n_periods_as_datetimes(n)
