#!/usr/bin/env python3
"""
Halachic preferences: which Vestot to observe, which Chumrot (Or Zarua,
Karti Ufalti) to add to each, and how an older Haflagah is uprooted.

Customs differ, so these are per-user settings, edited on the Settings page
and stored in ``config.json`` (git-ignored; ``config.example.json`` shows the
format). A missing file means the defaults below. The file is re-read on every
calculation, so a change applies immediately.

File format::

    {
      "language": "hebrew",                       # labels; read at startup only
      "vestot": {
        "Monthly": {"enabled": true, "OrZarua": true, "KartiUfalti": false},
        ...
      },
      "haflagah_uprooting": "three_shorter"       # or "longer_only"
    }

The older format (``"Vestot": [{"Name": ..., "Chumrot": [{"Name": ...}]}]``)
is still read, and converted on the next save.
"""

import copy
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

# The Vestot, in display/calculation order.
VESTOT = ("Monthly", "Thirty", "ThirtyOne", "LastSkip", "OldSkip")
CHUMROT = ("OrZarua", "KartiUfalti")

# How an older (longer) interval stops counting as Haflagah shelo ne'ekrah.
#  three_shorter: uprooted by a later longer interval, or once three later
#                 intervals have passed (three shorter ones uproot it).
#  longer_only:   uprooted only by a later interval at least as long; any
#                 number of shorter ones leave it in force.
UPROOTING_MODES = ("three_shorter", "longer_only")

DEFAULTS = {
    "language": "hebrew",
    "vestot": {
        "Monthly":   {"enabled": True, "OrZarua": True,  "KartiUfalti": False},
        "Thirty":    {"enabled": True, "OrZarua": True,  "KartiUfalti": True},
        "ThirtyOne": {"enabled": True, "OrZarua": False, "KartiUfalti": False},
        "LastSkip":  {"enabled": True, "OrZarua": True,  "KartiUfalti": False},
        "OldSkip":   {"enabled": True, "OrZarua": False, "KartiUfalti": False},
    },
    "haflagah_uprooting": "three_shorter",
}


def _from_legacy(rules: list) -> dict:
    """Convert the old ``"Vestot"`` list format to the ``"vestot"`` dict."""
    vestot = {name: {"enabled": False, **{c: False for c in CHUMROT}} for name in VESTOT}
    for rule in rules:
        name = rule.get("Name")
        if name in vestot:
            vestot[name]["enabled"] = True
            for chumra in rule.get("Chumrot", []):
                if chumra.get("Name") in CHUMROT:
                    vestot[name][chumra["Name"]] = True
    return vestot


def normalize(raw: dict) -> dict:
    """Fill in defaults and drop unknown keys; never raises on odd input."""
    prefs = copy.deepcopy(DEFAULTS)
    if not isinstance(raw, dict):
        return prefs
    if isinstance(raw.get("language"), str):
        prefs["language"] = raw["language"]
    vestot = raw.get("vestot")
    if vestot is None and isinstance(raw.get("Vestot"), list):
        vestot = _from_legacy(raw["Vestot"])
    if isinstance(vestot, dict):
        for name in VESTOT:
            given = vestot.get(name)
            if isinstance(given, dict):
                for key in ("enabled",) + CHUMROT:
                    if key in given:
                        prefs["vestot"][name][key] = bool(given[key])
    if raw.get("haflagah_uprooting") in UPROOTING_MODES:
        prefs["haflagah_uprooting"] = raw["haflagah_uprooting"]
    return prefs


def load(path: Path) -> dict:
    """Read preferences from *path* (defaults if it is missing or invalid)."""
    try:
        with open(path, encoding="utf-8") as f:
            return normalize(json.load(f))
    except FileNotFoundError:
        return copy.deepcopy(DEFAULTS)
    except (OSError, ValueError) as exc:
        log.error("Cannot read %s (%s) - using default preferences", path, exc)
        return copy.deepcopy(DEFAULTS)


def save(path: Path, prefs: dict) -> None:
    """Write preferences atomically (normalized first)."""
    data = normalize(prefs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def engine_rules(prefs: dict) -> List[dict]:
    """The enabled Vestot in the engine's ``[{"Name", "Chumrot"}]`` form."""
    rules = []
    for name in VESTOT:
        v = prefs["vestot"][name]
        if v["enabled"]:
            rules.append({"Name": name, "Chumrot": [{"Name": c} for c in CHUMROT if v[c]]})
    return rules
