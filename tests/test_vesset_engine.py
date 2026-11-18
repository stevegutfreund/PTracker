import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import settings  # noqa: E402
from services.storage import compute_delta  # noqa: E402
from services import preferences  # noqa: E402
from services.vesset_engine import VessetCalculator  # noqa: E402


def calc(periods, rules, uprooting="three_shorter"):
    return VessetCalculator(periods, rules, settings.LANGUAGE, settings.LANGUAGE_CALENDAR,
                            settings.LANGUAGE_NAME == "hebrew", uprooting).calculate()


def bloc(*intervals, start=datetime(2026, 1, 1, 11)):
    """Day-onah periods with the given 1-indexed intervals between them."""
    out = [start]
    for d in intervals:
        out.append(out[-1] + timedelta(days=d - 1))
    return out


def old_skips(periods, uprooting):
    return [int(s.description.rsplit("(", 1)[1].rstrip(")"))
            for s in calc(periods, [{"Name": "OldSkip"}], uprooting)]


class ComputeDelta(unittest.TestCase):
    def test_same_hebrew_day_is_one(self):
        self.assertEqual(compute_delta(datetime(2026, 1, 2, 11), datetime(2026, 1, 1, 23)), 1)

    def test_pm_on_last_day_of_month(self):
        # Legacy utils.delta crashed on day+1 here and returned 0.
        self.assertEqual(compute_delta(datetime(2026, 3, 1, 11), datetime(2026, 1, 31, 23)), 29)
        self.assertEqual(compute_delta(datetime(2026, 2, 28, 23), datetime(2026, 1, 31, 11)), 30)


class Rules(unittest.TestCase):
    def test_last_skip_across_month_end_pm(self):
        p = [datetime(2026, 1, 31, 23), datetime(2026, 2, 28, 23)]   # both month-end, night onah
        (s,) = calc(p, [{"Name": "LastSkip"}])
        self.assertIn("(29)", s.description)                         # 1 Feb -> 1 Mar, 1-indexed
        self.assertEqual(s.date, datetime(2026, 3, 28, 23))

    def test_thirty_and_chumra(self):
        p = [datetime(2026, 1, 1, 11)]
        out = calc(p, [{"Name": "Thirty", "Chumrot": [{"Name": "OrZarua"}]}])
        self.assertEqual([s.date for s in out], [datetime(2026, 1, 30, 11), datetime(2026, 1, 29, 23)])

    def test_unknown_rule_is_skipped(self):
        self.assertEqual(calc([datetime(2026, 1, 1, 11)], [{"Name": "Nope"}]), [])

    def test_needs_two_periods_for_skips(self):
        self.assertEqual(calc([datetime(2026, 1, 1, 11)], [{"Name": "LastSkip"}, {"Name": "OldSkip"}]), [])


class HaflagahUprooting(unittest.TestCase):
    def test_longer_interval_uproots_in_both_modes(self):
        # 35 then a longer 40: the 35 is gone; 40 is the last interval (LastSkip).
        for mode in preferences.UPROOTING_MODES:
            self.assertEqual(old_skips(bloc(35, 40), mode), [])

    def test_older_longer_interval_stays(self):
        for mode in preferences.UPROOTING_MODES:
            self.assertEqual(old_skips(bloc(35, 28), mode), [35])
            self.assertEqual(old_skips(bloc(40, 35, 28), mode), [35, 40])   # newest first

    def test_three_shorter_uproot_only_in_three_shorter_mode(self):
        p = bloc(40, 28, 27, 26)              # 40 followed by three shorter intervals
        self.assertEqual(old_skips(p, "three_shorter"), [27, 28])
        self.assertEqual(old_skips(p, "longer_only"), [27, 28, 40])

    def test_equal_interval_is_not_listed_twice(self):
        # An older interval equal to the last one gives the LastSkip day itself.
        for mode in preferences.UPROOTING_MODES:
            self.assertEqual(old_skips(bloc(28, 28), mode), [])
            self.assertEqual(old_skips(bloc(35, 35, 28), mode), [35])

    def test_unknown_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            calc(bloc(30, 30), [], "sometimes")


class Preferences(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        self.assertEqual(preferences.load(Path("does-not-exist.json")), preferences.DEFAULTS)

    def test_legacy_format_is_converted(self):
        legacy = {"language": "english", "Vestot": [
            {"Name": "Thirty", "Chumrot": [{"Name": "KartiUfalti"}]}, {"Name": "LastSkip"}]}
        prefs = preferences.normalize(legacy)
        self.assertEqual(prefs["language"], "english")
        self.assertEqual(preferences.engine_rules(prefs), [
            {"Name": "Thirty", "Chumrot": [{"Name": "KartiUfalti"}]},
            {"Name": "LastSkip", "Chumrot": []}])

    def test_bad_values_fall_back(self):
        prefs = preferences.normalize({"haflagah_uprooting": "never", "vestot": {"Monthly": "yes"}})
        self.assertEqual(prefs["haflagah_uprooting"], "three_shorter")
        self.assertEqual(prefs["vestot"]["Monthly"], preferences.DEFAULTS["vestot"]["Monthly"])

    def test_save_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "config.json")
            prefs = preferences.normalize({})
            prefs["vestot"]["Thirty"]["KartiUfalti"] = False
            prefs["haflagah_uprooting"] = "longer_only"
            preferences.save(path, prefs)
            self.assertEqual(preferences.load(path), prefs)


if __name__ == "__main__":
    unittest.main()
