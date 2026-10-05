"""Portable pixel regressions from the original native v0.6 renderer.

Goldens were produced from canonical source, not this package. Rebaselining must
review an intentional visual change; do not regenerate expected hashes from the
implementation under test. No private source or network access is required.
"""
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import unittest

from tidbyt_clock_weather.model import Current, Forecast, ForecastDay, Weather
from tidbyt_clock_weather.render import render_clock, render_weather


class NativeVisualParityTests(unittest.TestCase):
    def test_original_native_rgb_goldens(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "visual-golden.json").read_text(encoding="utf-8")
        )
        self.assertEqual(fixture["schema_version"], 1)
        cases = fixture["cases"]
        self.assertEqual(len(cases), fixture["expected_case_count"])
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        for case in cases:
            with self.subTest(case=case["id"]):
                arguments = dict(case["arguments"])
                arguments["now"] = datetime.fromisoformat(arguments["now"])
                if case["screen"] == "clock":
                    image = render_clock(**arguments)
                else:
                    data = case["weather"]
                    current = None
                    if data["current"] is not None:
                        values = dict(data["current"])
                        values["observed_at"] = datetime.fromisoformat(values["observed_at"])
                        current = Current(**values)
                    forecast = None
                    if data["forecast"] is not None:
                        values = data["forecast"]
                        days = tuple(
                            ForecastDay(**{**day, "date": date.fromisoformat(day["date"])})
                            for day in values["days"]
                        )
                        forecast = Forecast(
                            days, datetime.fromisoformat(values["observed_at"]),
                            values["ttl_seconds"],
                        )
                    image = render_weather(Weather(current, forecast), **arguments)
                self.assertEqual(image.mode, fixture["native_mode"])
                self.assertEqual(list(image.size), fixture["native_size"])
                self.assertEqual(hashlib.sha256(image.tobytes()).hexdigest(), case["rgb_sha256"])


if __name__ == "__main__":
    unittest.main()

