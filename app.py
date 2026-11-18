#!/usr/bin/env python3
"""
PTracker – local web application entry point.

Run:
    python app.py

Access at:  http://127.0.0.1:5001

Host/port come from .env (default 5001, next to BDays on 5000).
"""

import logging

from flask import Flask, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

import settings  # first: explains a missing CalendarKit package
from calendarkit.gcal import calendar_view_url


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # Behind the login gateway (dashboard/gateway/gateway.py) the app lives under a path
    # prefix such as /ptracker; X-Forwarded-Prefix makes url_for() include it.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=0, x_host=0, x_port=0, x_prefix=1)

    app.secret_key = settings.SECRET_KEY

    from routes.periods import periods_bp
    from routes.vestot import vestot_bp
    from routes.calendar_routes import calendar_bp
    from routes.settings_routes import settings_bp

    app.register_blueprint(periods_bp)
    app.register_blueprint(vestot_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(settings_bp)

    @app.template_filter("shkia")
    def shkia_label(dt) -> str:
        """'Before shkia' / 'After shkia' for a period or vesset datetime (onah)."""
        from services.storage import is_night_onah
        return "After shkia" if is_night_onah(dt) else "Before shkia"

    @app.context_processor
    def calendar_link():
        """`calendar_link`: browser link to the configured Google calendar (or None)."""
        cal_id = settings.CALENDAR_ID
        return {"calendar_link": calendar_view_url(cal_id, timezone=settings.CALENDAR_TIMEZONE) if cal_id else None}

    @app.route("/")
    def index():
        return redirect(url_for("periods.list_periods"))

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = create_app()
    app.run(host=settings.HOST, port=settings.PORT, debug=settings.DEBUG)
