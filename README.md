# PTracker

A local web application for tracking cycles and calculating Vestot according
to Halacha, with optional Google Calendar sync.

## Requirements

- Python 3.10+
- **The shared [CalendarKit](../CalendarKit) package.** It is a separate repo, so clone
  it next to this one; `requirements.txt` installs it from `../CalendarKit`:

  ```text
  some-folder/
    CalendarKit/   <- git clone .../CalendarKit
    PTracker/      <- this repo
  ```
- Optional: a Google Cloud OAuth client (`credentials.json`, "Desktop app" type)

## Setup

```bash
pip install -r requirements.txt          # includes -e ../CalendarKit
cp .env.example .env                     # set SECRET_KEY, CALENDAR_ID
python app.py
```

Open **http://127.0.0.1:5001**. Without `CALENDAR_ID` / `credentials.json`
everything works except the calendar sync buttons.

## Configuration

| File                | Holds                                                         | In git |
| ------------------- | ------------------------------------------------------------- | ------ |
| `.env`              | calendar id, port, secret key, OAuth paths, time zone, `HISTORY_START` | no (`.env.example` is) |
| `config.json`       | your halachic preferences (Settings page, see below); missing = defaults | no (`config.example.json` is) |
| `data/periods.json` | the periods                                                   | no (`data/periods.sample.json` is) |
| `credentials.json`, `token.json` | Google OAuth client / user token                 | no |

All settings are read in [settings.py](settings.py).

### Halachic preferences (Settings page)

Customs differ, so which rules to observe is a per-user setting, edited at
**`/settings`** and saved to `config.json` (git-ignored). Each calculation
re-reads it, so a change applies immediately; sync again from the Vestot page
to update the calendar.

- **Vestot to observe:** Vesset Hachodesh, Onah Beinonit (day 30), day 31,
  Haflagah Achronah, Haflagah shelo ne'ekrah. Each can be switched off.
- **Chumrot per Vesset:** Or Zarua (also the onah before) and Karti Ufalti
  (also the other onah of the same day).
- **When an older Haflagah is uprooted** (`haflagah_uprooting`):
  - `three_shorter` (default): by a later interval at least as long, or once
    three later intervals have passed;
  - `longer_only`: only by a later interval at least as long, however many
    shorter ones follow.

`language` (`hebrew` / `english`, labels and calendar titles) is in the same
file but read only at startup. The file format is in
[services/preferences.py](services/preferences.py) and
[config.example.json](config.example.json).

## Data format

`data/periods.json` is an ordered array, **oldest first**:

```json
{ "date": "DD-MM-YYYY", "after_shkia": true | false, "clean_start": true | false }
```

- `after_shkia: true` is the night onah – it counts as the next Hebrew day.
  Internally (and in calendar events) after shkia is 23:00, before shkia 11:00.
- `clean_start: true` starts a new counting bloc; Vestot use only the current bloc.

## Features

| Feature                                     | Where                 |
| ------------------------------------------- | --------------------- |
| List periods (grouped by bloc) + statistics | `/periods`            |
| Add / edit / delete / reorder               | `/periods/...`        |
| Calculate Vestot (+ sync to calendar)       | `/vestot/calculate`   |
| Choose Vestot, Chumrot and uprooting rule   | `/settings`           |
| Mark "day N", copy all, clear calendar      | `/calendar`           |

## Project structure

```
PTracker/
  app.py                    Flask entry point
  settings.py               .env + config.json settings
  language.py               labels (transliterated / Hebrew script)
  routes/                   periods, vestot, calendar_routes, settings_routes
  services/
    storage.py              periods.json CRUD, blocs, stats, Hebrew-day deltas
    vesset_engine.py        pure Vesset rules (no I/O)
    preferences.py          halachic preferences: load/save config.json, defaults
    vesset_service.py       storage + preferences -> engine
    calendar_service.py     PTracker events -> calendarkit.gcal
  tests/                    python -m unittest discover -s tests
  templates/, static/, data/
```

Files ending in `.depr` are no longer used and will be deleted; they are git-ignored.
