#!/usr/bin/env python3
"""
Period CRUD routes.

Handles listing, adding, editing, deleting, and reordering periods.
"""

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

import services.calendar_service as cal
import services.storage as storage

periods_bp = Blueprint("periods", __name__, url_prefix="/periods")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_form_date(iso_date: str) -> str:
    """Convert HTML date-input value (yyyy-mm-dd) to storage format (dd-mm-yyyy)."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%d-%m-%Y")


def _to_iso_date(ddmmyyyy: str) -> str:
    """Convert storage date (dd-mm-yyyy) to HTML date-input value (yyyy-mm-dd)."""
    dt = datetime.strptime(ddmmyyyy, "%d-%m-%Y")
    return dt.strftime("%Y-%m-%d")


def _warn_if_out_of_order(date_str: str, exclude_index: int = None) -> None:
    """Flash a warning if the given date would break chronological order."""
    entries = storage.load_periods()
    if exclude_index is not None:
        entries = [e for i, e in enumerate(entries) if i != exclude_index]
    if not entries:
        return
    last_entry = entries[-1]
    try:
        new_dt = datetime.strptime(date_str, "%d-%m-%Y")
        last_dt = datetime.strptime(last_entry["date"], "%d-%m-%Y")
        if new_dt < last_dt:
            flash(
                "⚠ Warning: this date is earlier than the last stored period "
                f"({last_entry['date']}). Vesset calculations assume chronological "
                "order – check your entries after saving.",
                "warning",
            )
    except ValueError:
        pass


def _calendar_sync(action: str, fn, *args) -> None:
    """Run a calendar operation; flash a warning (never crash) on failure."""
    if not cal.is_available():
        flash(f"Saved locally, but Google Calendar is not available "
              f"({cal.get_error() or 'unknown error'}) – calendar not updated.",
              "warning")
        return
    try:
        fn(*args)
    except Exception as exc:
        flash(f"Saved locally, but failed to {action} the calendar event: {exc}",
              "warning")


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@periods_bp.route("/")
def list_periods():
    blocs = storage.get_blocs()
    stats = storage.get_stats()
    return render_template("periods/list.html", blocs=blocs, stats=stats)


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

@periods_bp.route("/add", methods=["GET", "POST"])
def add_period():
    if request.method == "POST":
        iso_date = request.form.get("date", "").strip()
        after_shkia = {"1": True, "0": False}.get(request.form.get("after_shkia", "").strip())
        clean_start = bool(request.form.get("clean_start"))

        # Validate
        if not iso_date:
            flash("Date is required.", "error")
            return render_template("periods/form.html", action="add", entry=None)

        try:
            date_str = _parse_form_date(iso_date)
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("periods/form.html", action="add", entry=None)

        if after_shkia is None:
            flash("Choose before or after shkia.", "error")
            return render_template("periods/form.html", action="add", entry=None)

        _warn_if_out_of_order(date_str)
        entry = storage.add_period(date_str, after_shkia, clean_start)
        flash("Period added successfully.", "success")
        _calendar_sync("add", cal.add_period_to_calendar,
                       storage.entry_to_datetime(entry), clean_start)
        return redirect(url_for("periods.list_periods"))

    return render_template("periods/form.html", action="add", entry=None)


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

@periods_bp.route("/<int:index>/edit", methods=["GET", "POST"])
def edit_period(index: int):
    entry = storage.get_period(index)
    if entry is None:
        flash("Period not found.", "error")
        return redirect(url_for("periods.list_periods"))

    if request.method == "POST":
        iso_date = request.form.get("date", "").strip()
        after_shkia = {"1": True, "0": False}.get(request.form.get("after_shkia", "").strip())
        clean_start = bool(request.form.get("clean_start"))

        if not iso_date:
            flash("Date is required.", "error")
            return render_template("periods/form.html", action="edit",
                                   entry=entry, index=index)

        try:
            date_str = _parse_form_date(iso_date)
        except ValueError:
            flash("Invalid date format.", "error")
            return render_template("periods/form.html", action="edit",
                                   entry=entry, index=index)

        if after_shkia is None:
            flash("Choose before or after shkia.", "error")
            return render_template("periods/form.html", action="edit",
                                   entry=entry, index=index)

        _warn_if_out_of_order(date_str, exclude_index=index)
        old_dt = storage.entry_to_datetime(entry)
        storage.update_period(index, date_str, after_shkia, clean_start)
        flash("Period updated.", "success")
        new_entry = storage.get_period(index)
        _calendar_sync("remove the old", cal.delete_period_from_calendar, old_dt)
        _calendar_sync("add", cal.add_period_to_calendar,
                       storage.entry_to_datetime(new_entry), clean_start)
        return redirect(url_for("periods.list_periods"))

    # Pre-fill form with existing values (convert date to yyyy-mm-dd for input[type=date])
    form_entry = dict(entry)
    form_entry["iso_date"] = _to_iso_date(entry["date"])
    return render_template("periods/form.html", action="edit",
                           entry=form_entry, index=index)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@periods_bp.route("/<int:index>/delete", methods=["POST"])
def delete_period(index: int):
    entry = storage.get_period(index)
    if entry is not None and storage.delete_period(index):
        flash("Period deleted.", "success")
        _calendar_sync("delete", cal.delete_period_from_calendar,
                       storage.entry_to_datetime(entry))
    else:
        flash("Period not found.", "error")
    return redirect(url_for("periods.list_periods"))


# ---------------------------------------------------------------------------
# Move up / down
# ---------------------------------------------------------------------------

@periods_bp.route("/<int:index>/move", methods=["POST"])
def move_period(index: int):
    direction = int(request.form.get("direction", 0))
    if direction not in (-1, 1):
        flash("Invalid move direction.", "error")
        return redirect(url_for("periods.list_periods"))

    if storage.move_period(index, direction):
        flash("Entry reordered.", "success")
    else:
        flash("Cannot move entry further in that direction.", "warning")
    return redirect(url_for("periods.list_periods"))
