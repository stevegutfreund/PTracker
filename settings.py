"""PTracker runtime settings.

Two sources:
  * ``.env`` (git-ignored, template ``.env.example``) - secrets and personal /
    machine-specific values: calendar id, OAuth file paths, port, secret key.
  * ``config.json`` (git-ignored, template ``config.example.json``) - halachic
    preferences: display language, the Vestot / Chumrot to observe and how a
    Haflagah is uprooted. Edited on the Settings page; see services/preferences.py.
"""

import secrets
from datetime import datetime
from pathlib import Path

try:
    from calendarkit import env
except ImportError as exc:  # the shared package is a separate repo
    raise SystemExit(
        "PTracker needs the shared CalendarKit package. Clone the CalendarKit repo next to this "
        "folder (so that ../CalendarKit exists), then run: pip install -r requirements.txt "
        f"({exc})"
    ) from exc
from language import language_dict
from services import preferences

BASE_DIR = Path(__file__).resolve().parent
env.load_dotenv(BASE_DIR / ".env")

# -- web server ---------------------------------------------------------------
HOST = env.get("HOST", "127.0.0.1")
PORT = env.get_int("PORT", 5001)
DEBUG = env.get_bool("FLASK_DEBUG", False)
SECRET_KEY = env.get("SECRET_KEY") or secrets.token_hex(32)

# -- storage ------------------------------------------------------------------
DATA_DIR = env.get_path("DATA_DIR", "data", base_dir=BASE_DIR)

# -- Google Calendar ----------------------------------------------------------
CALENDAR_ID = env.get("CALENDAR_ID")            # None -> calendar features disabled
GOOGLE_CREDENTIALS_FILE = env.get_path("GOOGLE_CREDENTIALS_FILE", "credentials.json", base_dir=BASE_DIR)
GOOGLE_TOKEN_FILE = env.get_path("GOOGLE_TOKEN_FILE", "token.json", base_dir=BASE_DIR)
GOOGLE_ALLOW_BROWSER_AUTH = env.get_bool("GOOGLE_ALLOW_BROWSER_AUTH", True)
CALENDAR_TIMEZONE = env.get("CALENDAR_TIMEZONE", "Asia/Jerusalem")
# Earliest date bulk "clear" operations search from.
HISTORY_START = datetime.strptime(env.get("HISTORY_START", "2000-01-01"), "%Y-%m-%d")

# -- halachic preferences (config.json, git-ignored) --------------------------
# Which Vestot / Chumrot to observe is edited on the Settings page and re-read
# on every calculation (services/preferences.py). Only the label language is
# fixed at startup: calendar event titles depend on it.
APP_CONFIG_FILE = env.get_path("APP_CONFIG_FILE", "config.json", base_dir=BASE_DIR)

LANGUAGE_NAME = preferences.load(APP_CONFIG_FILE)["language"]
if LANGUAGE_NAME not in ("english", "hebrew"):
    LANGUAGE_NAME = "english"
LANGUAGE = language_dict[LANGUAGE_NAME]                                   # UI labels
LANGUAGE_CALENDAR = language_dict.get(f"{LANGUAGE_NAME}_calendar", LANGUAGE)  # event titles

# Delta shown for the first period of a counting bloc.
CLEAN_PERIOD = "-"
