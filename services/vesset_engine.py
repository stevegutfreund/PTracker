#!/usr/bin/env python3
"""
Vesset (anticipated period) calculations according to Halacha.

Pure logic: takes the period datetimes of the current bloc (oldest first), the
rules to observe and how an older Haflagah is uprooted, and returns
:class:`Suspect` dates. No I/O.

Period datetimes use the app's onah convention: hour 11 = before shkia (day
onah), hour 23 = after shkia (night onah).
"""

import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Sequence

from calendarkit import hebrew

from services.storage import compute_delta

log = logging.getLogger(__name__)

# Rule key -> transliterated label key used in descriptions (see language.py).
RULES = ("Monthly", "Thirty", "ThirtyOne", "LastSkip", "OldSkip", "OrZarua", "KartiUfalti")


class Suspect:
    """An anticipated date/onah for the next period."""

    def __init__(self, date: datetime, description: str, calendar_description: Optional[str] = None):
        self.date = date
        self.description = description
        self._calendar_description = calendar_description or description

    def __str__(self) -> str:
        when = "after shkia" if self.date.hour >= 12 else "before shkia"
        return f"{self.description} -> {self.date.strftime('%d-%m-%Y')} {when}"

    def __repr__(self) -> str:
        return f"Suspect({self.date!r}, {self.description!r})"

    def get_hebrew_description(self) -> str:
        """Description for calendar event titles (Hebrew script when configured)."""
        return self._calendar_description


class VessetCalculator:
    """Calculate Vestot from the periods of the current bloc (oldest first).

    ``haflagah_uprooting`` decides how long an older, longer interval stays a
    Haflagah shelo ne'ekrah (see services/preferences.py):
      * ``"three_shorter"`` - until a later interval at least as long, or until
        three later intervals have passed;
      * ``"longer_only"``   - until a later interval at least as long, however
        many shorter ones come in between.
    """

    def __init__(self, periods: Sequence[datetime], rules: List[dict],
                 labels: dict, calendar_labels: dict, use_calendar_labels: bool,
                 haflagah_uprooting: str = "three_shorter"):
        if haflagah_uprooting not in ("three_shorter", "longer_only"):
            raise ValueError(f"unknown haflagah_uprooting: {haflagah_uprooting!r}")
        self.periods: List[datetime] = list(periods)
        self.haflagah_uprooting = haflagah_uprooting
        # Right-align into a fixed 4-slot window: [oldest .. newest], None-padded.
        recent = self.periods[-4:]
        self.four_last_periods: List[Optional[datetime]] = [None] * (4 - len(recent)) + recent
        self.rules = rules
        self.labels = labels
        self.calendar_labels = calendar_labels
        self.use_calendar_labels = use_calendar_labels

    # -- helpers ----------------------------------------------------------------

    def _suspect(self, date: datetime, label_key: str, suffix: str = "") -> Suspect:
        description = f"{self.labels[label_key]}{suffix}"
        cal = f"{self.calendar_labels[label_key]}{suffix}" if self.use_calendar_labels else description
        return Suspect(date, description, cal)

    @property
    def _last(self) -> Optional[datetime]:
        return self.four_last_periods[3]

    # -- rules ------------------------------------------------------------------

    def or_zarua(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Or Zarua: the onah before the anticipated onah."""
        if not base_date:
            return []
        return [self._suspect(base_date - timedelta(hours=12), "OrZarua")]

    def karti_ufalti(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Karti Ufalti: the other onah of the same Hebrew day."""
        if not base_date:
            return []
        shift = timedelta(hours=12) if base_date.hour >= 12 else timedelta(hours=-12)
        return [self._suspect(base_date + shift, "KartiUfalti")]

    def old_skip(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Haflagah shelo ne'ekrah: older intervals that have not been uprooted.

        An older interval is still in force while every later interval was
        shorter (a later one at least as long uproots it; an equal one would
        also give the same day as Haflagah achronah). With ``three_shorter``
        only the two intervals before the last one are considered, so three
        later intervals uproot an older one. Newest first.
        """
        p = self.periods
        if len(p) < 3:
            return []
        # intervals[i] = days from p[i] to p[i+1], 1-indexed; the last is LastSkip.
        intervals = [compute_delta(p[i + 1], p[i]) for i in range(len(p) - 1)]
        older = intervals[:-1][::-1]                       # newest older interval first
        if self.haflagah_uprooting == "three_shorter":
            older = older[:2]
        suspects = []
        longest_later = intervals[-1]
        for d in older:
            if d > longest_later:
                suspects.append(self._suspect(p[-1] + timedelta(days=d - 1), "OldSkip", f" ({d})"))
                longest_later = d
        return suspects

    def last_skip(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Haflagah achronah: the last interval repeated."""
        p = self.four_last_periods
        if not p[2] or not p[3]:
            return []
        d = compute_delta(p[3], p[2])
        return [self._suspect(p[3] + timedelta(days=d - 1), "LastSkip", f" ({d})")]

    def thirty_day(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Onah beinonit: day 30."""
        return [self._suspect(self._last + timedelta(days=29), "Thirty")] if self._last else []

    def thirty_one_day(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Day 31."""
        return [self._suspect(self._last + timedelta(days=30), "ThirtyOne")] if self._last else []

    def monthly_hebrew(self, base_date: Optional[datetime] = None) -> List[Suspect]:
        """Vesset hachodesh: same Hebrew date next month, same onah.

        Note: the Hebrew date is taken from the civil date as-is (no shkia
        shift for night periods) - unchanged from the original implementation.
        """
        last = self._last
        if not last:
            return []
        try:
            nxt = hebrew.same_day_next_month(hebrew.to_hebrew(last))
        except ValueError as exc:   # day 30 into a 29-day month
            log.info("No %s this month: %s", self.labels["Monthly"], exc)
            return []
        g = nxt.to_pydate()
        return [self._suspect(datetime(g.year, g.month, g.day, last.hour), "Monthly")]

    def rule(self, name: str) -> Optional[Callable[..., List[Suspect]]]:
        return {
            "Monthly": self.monthly_hebrew,
            "Thirty": self.thirty_day,
            "ThirtyOne": self.thirty_one_day,
            "LastSkip": self.last_skip,
            "OldSkip": self.old_skip,
            "OrZarua": self.or_zarua,
            "KartiUfalti": self.karti_ufalti,
        }.get(name)

    # -- main -------------------------------------------------------------------

    def calculate(self) -> List[Suspect]:
        """All configured Vestot, each followed by its Chumrot."""
        out: List[Suspect] = []
        for rule_cfg in self.rules:
            name = rule_cfg.get("Name")
            fn = self.rule(name)
            if fn is None:
                log.warning("Unknown vesset rule in config.json: %s", name)
                continue
            base = fn()
            out.extend(base)
            for chumra in rule_cfg.get("Chumrot", []):
                cfn = self.rule(chumra.get("Name"))
                if cfn is None:
                    log.warning("Unknown chumra in config.json: %s", chumra.get("Name"))
                    continue
                for s in base:
                    out.extend(cfn(s.date))
        return out
