#!/usr/bin/env python3
"""
Vesset calculation routes.
"""

from flask import Blueprint, flash, redirect, render_template, url_for

import services.vesset_service as vsvc
import services.calendar_service as cal

vestot_bp = Blueprint("vestot", __name__, url_prefix="/vestot")


@vestot_bp.route("/calculate")
def calculate():
    """Calculate Vestot and display results (no calendar write)."""
    try:
        suspects = vsvc.calculate_vestot()
    except Exception as exc:
        flash(f"Error calculating Vestot: {exc}", "error")
        suspects = []

    if not suspects:
        flash("Not enough period data to calculate Vestot (need at least 2 periods in the current bloc).", "warning")

    return render_template(
        "vestot/results.html",
        suspects=suspects,
        calendar_available=cal.is_available(),
    )


@vestot_bp.route("/sync-calendar", methods=["POST"])
def sync_calendar():
    """Add the freshly calculated Vestot to Google Calendar (replaces previous)."""
    if not cal.is_available():
        flash("Google Calendar is not configured – cannot sync.", "error")
        return redirect(url_for("vestot.calculate"))

    try:
        suspects = vsvc.calculate_vestot()
        if not suspects:
            flash("No Vestot to sync.", "warning")
            return redirect(url_for("vestot.calculate"))

        removed = cal.clear_last_vestot_from_calendar()
        added = cal.add_vestot_to_calendar(suspects)
        flash(f"Calendar updated: {removed} old event(s) removed, {added} new event(s) added.", "success")
    except Exception as exc:
        flash(f"Error syncing Vestot to calendar: {exc}", "error")

    return redirect(url_for("vestot.calculate"))
