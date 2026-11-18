#!/usr/bin/env python3
"""
Settings page: which Vestot and Chumrot to observe, and how a Haflagah is
uprooted. Saved to config.json (git-ignored); applies to the next calculation.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

import settings
from services import preferences

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

# Shown on the page (Hebrew name, transliteration, explanation).
VESSET_INFO = {
    "Monthly":   ("החודש", "Vesset Hachodesh", "Same Hebrew date next month, same onah."),
    "Thirty":    ("עונה בינונית", "Onah Beinonit", "Day 30 from the last period."),
    "ThirtyOne": ("יום ל\"א", "Day 31", "Day 31 from the last period."),
    "LastSkip":  ("הפלגה אחרונה", "Haflagah Achronah", "The last interval, repeated."),
    "OldSkip":   ("הפלגה שלא נעקרה", "Haflagah shelo ne'ekrah",
                  "Older, longer intervals that have not yet been uprooted."),
}
CHUMRA_INFO = {
    "OrZarua":     ("אור זרוע", "Or Zarua", "Also the onah before."),
    "KartiUfalti": ("כרתי ופלתי", "Karti Ufalti", "Also the other onah of the same day (the whole day)."),
}
UPROOTING_INFO = {
    "three_shorter": ("Longer interval, or three shorter ones",
                      "An older interval is uprooted by a later interval at least as long, "
                      "or once three later intervals have passed."),
    "longer_only":   ("Only a longer interval",
                      "An older interval is uprooted only by a later interval at least as long; "
                      "it stays in force however many shorter intervals follow."),
}


@settings_bp.route("/", methods=["GET"])
def index():
    return render_template(
        "settings/index.html",
        prefs=preferences.load(settings.APP_CONFIG_FILE),
        vestot=preferences.VESTOT, chumrot=preferences.CHUMROT,
        modes=preferences.UPROOTING_MODES,
        vesset_info=VESSET_INFO, chumra_info=CHUMRA_INFO, uprooting_info=UPROOTING_INFO,
    )


@settings_bp.route("/", methods=["POST"])
def save():
    prefs = preferences.load(settings.APP_CONFIG_FILE)   # keeps "language"
    form = request.form
    for name in preferences.VESTOT:
        cfg = prefs["vestot"][name]
        cfg["enabled"] = form.get(f"{name}.enabled") == "1"
        if cfg["enabled"]:  # an unticked Vesset's (greyed-out) Chumrot keep their values
            for chumra in preferences.CHUMROT:
                cfg[chumra] = form.get(f"{name}.{chumra}") == "1"
    mode = form.get("haflagah_uprooting")
    if mode in preferences.UPROOTING_MODES:
        prefs["haflagah_uprooting"] = mode
    try:
        preferences.save(settings.APP_CONFIG_FILE, prefs)
    except OSError as exc:
        flash(f"Could not save settings: {exc}", "error")
        return redirect(url_for("settings.index"))
    flash("Settings saved. Vestot are calculated with them from now on; "
          "sync again from the Vestot page to update the calendar.", "success")
    return redirect(url_for("settings.index"))
