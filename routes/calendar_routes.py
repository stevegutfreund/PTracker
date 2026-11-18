#!/usr/bin/env python3
"""
Google Calendar operation routes.

All operations are guarded: if the calendar service is unavailable the user
gets a clear error message and is redirected back to the calendar page without
the app crashing.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for

import services.calendar_service as cal
import services.storage as storage

calendar_bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@calendar_bp.route("/")
def index():
    last_periods = storage.get_last_n_periods_as_datetimes(1)
    last_period = last_periods[0] if last_periods else None
    return render_template(
        "calendar/index.html",
        calendar_available=cal.is_available(),
        calendar_error=cal.get_error(),
        last_period=last_period,
    )


@calendar_bp.route("/mark-day", methods=["POST"])
def mark_day():
    if not cal.is_available():
        flash("Google Calendar is not configured.", "error")
        return redirect(url_for("calendar.index"))

    try:
        day_number = int(request.form.get("day_number", 0))
        hebrew_calc = bool(request.form.get("hebrew_calc"))
        if day_number < 1:
            flash("Day number must be at least 1.", "error")
            return redirect(url_for("calendar.index"))

        mark_date = cal.mark_day(day_number, hebrew_calc)
        flash(f"Marked day {day_number} on {mark_date.strftime('%d-%m-%Y')}.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        flash(f"Error marking day: {exc}", "error")

    return redirect(url_for("calendar.index"))


@calendar_bp.route("/copy-all", methods=["POST"])
def copy_all():
    if not cal.is_available():
        flash("Google Calendar is not configured.", "error")
        return redirect(url_for("calendar.index"))

    try:
        result = cal.copy_all_to_calendar()
        flash(
            f"Copied to calendar: {result['success']} succeeded, {result['errors']} failed.",
            "success" if result["errors"] == 0 else "warning",
        )
    except Exception as exc:
        flash(f"Error copying to calendar: {exc}", "error")

    return redirect(url_for("calendar.index"))


@calendar_bp.route("/clear-all", methods=["POST"])
def clear_all():
    if not cal.is_available():
        flash("Google Calendar is not configured.", "error")
        return redirect(url_for("calendar.index"))

    try:
        deleted = cal.clear_all_events()
        flash(f"Cleared {deleted} event(s) from the calendar.", "success")
    except Exception as exc:
        flash(f"Error clearing calendar: {exc}", "error")

    return redirect(url_for("calendar.index"))


@calendar_bp.route("/clear-vestot", methods=["POST"])
def clear_vestot():
    if not cal.is_available():
        flash("Google Calendar is not configured.", "error")
        return redirect(url_for("calendar.index"))

    try:
        deleted = cal.clear_all_vestot()
        flash(f"Cleared {deleted} Vesset event(s) from the calendar.", "success")
    except Exception as exc:
        flash(f"Error clearing Vestot: {exc}", "error")

    return redirect(url_for("calendar.index"))
