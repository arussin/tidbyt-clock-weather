"""Run against a wheel installed in a clean venv, from outside this checkout."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from PIL import Image
import tidbyt_clock_weather
from tidbyt_clock_weather.model import (
    Current,
    Forecast,
    ForecastDay,
    Weather,
    fresh,
    merge_current,
)
from tidbyt_clock_weather.provider import parse_open_meteo, fetch_open_meteo
from tidbyt_clock_weather.render import (
    encode_webp,
    render_clock,
    render_weather,
    weather_loop,
)
from tidbyt_clock_weather.pixels import resources
from tidbyt_clock_weather.solar import day_events

NOW = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
CAPTURE = Path(__file__).resolve().parents[1] / "examples" / "synthetic-weather.json"


def fixture():
    raw = json.loads(CAPTURE.read_text(encoding="utf-8"))
    return parse_open_meteo(
        raw["response"], datetime.fromisoformat(raw["fetched_at"]), "UTC"
    )


class FreshnessTests(unittest.TestCase):
    def test_fresh_current_never_rejuvenates_stale_forecast(self):
        weather = fixture()
        stale = replace(
            weather,
            forecast=replace(weather.forecast, observed_at=NOW - timedelta(hours=3)),
        )
        merged = merge_current(stale, Current(50, "clear", NOW), NOW)
        self.assertTrue(merged.current.fresh(NOW))
        self.assertIs(merged.forecast, stale.forecast)
        self.assertFalse(merged.forecast.fresh(NOW))
        self.assertIsNone(merged.forecast.day(NOW.date(), NOW))
        missing = replace(merged, forecast=None)
        self.assertEqual(
            render_weather(merged, NOW, page="tomorrow").tobytes(),
            render_weather(missing, NOW, page="tomorrow").tobytes(),
        )

    def test_stale_current_does_not_remove_fresh_forecast(self):
        weather = replace(
            fixture(), current=Current(50, "clear", NOW - timedelta(hours=2))
        )
        self.assertFalse(weather.current.fresh(NOW))
        self.assertTrue(weather.forecast.fresh(NOW))
        self.assertIsNotNone(weather.forecast.day(NOW.date() + timedelta(days=1), NOW))

    def test_boundary_future_and_invalid_ttl(self):
        self.assertTrue(fresh(NOW - timedelta(seconds=100), 100, NOW))
        self.assertFalse(fresh(NOW - timedelta(seconds=101), 100, NOW))
        self.assertFalse(fresh(NOW + timedelta(seconds=1), 100, NOW))
        with self.assertRaises(ValueError):
            fresh(NOW, 0, NOW)
        with self.assertRaises(ValueError):
            Current(10, "clear", NOW.replace(tzinfo=None))

    def test_dst_fold_uses_elapsed_utc_time(self):
        zone = ZoneInfo("America/New_York")
        first = datetime(2026, 11, 1, 1, 15, tzinfo=zone, fold=0)
        second = datetime(2026, 11, 1, 1, 45, tzinfo=zone, fold=1)
        self.assertFalse(fresh(first, 3600, second))
        self.assertTrue(fresh(first, 7200, second))

    def test_stale_overlay_is_ignored(self):
        weather = fixture()
        stale = Current(20, "snow", NOW - timedelta(hours=3))
        self.assertIs(merge_current(weather, stale, NOW), weather)

    def test_validation(self):
        for bad in (True, float("nan"), float("inf"), -121, 161):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Current(bad, "clear", NOW)
        with self.assertRaises(ValueError):
            ForecastDay(NOW.date(), 30, 40, "clear")
        with self.assertRaises(ValueError):
            Forecast((fixture().forecast.days[0],) * 2, NOW)


class ProviderTests(unittest.TestCase):
    def test_synthetic_capture_and_preserved_forecast_age(self):
        weather = fixture()
        self.assertEqual(weather.current.temperature_f, 48)
        self.assertEqual(weather.forecast.days[1].date, date(2026, 1, 16))
        self.assertEqual(weather.forecast.observed_at, NOW)
        self.assertFalse(weather.forecast.fresh(NOW + timedelta(hours=3)))

    def test_malformed_columns_not_silently_zipped(self):
        raw = json.loads(CAPTURE.read_text(encoding="utf-8"))["response"]
        raw["daily"]["temperature_2m_max"].pop()
        with self.assertRaises(ValueError):
            parse_open_meteo(raw, NOW, "UTC")

    def test_units_must_be_explicit(self):
        raw = json.loads(CAPTURE.read_text(encoding="utf-8"))["response"]
        raw["current_units"]["temperature_2m"] = "°C"
        with self.assertRaises(ValueError):
            parse_open_meteo(raw, NOW, "UTC")

    def test_invalid_missing_fields_and_nonfinite_timestamps(self):
        with self.assertRaises(ValueError):
            parse_open_meteo({}, NOW, "UTC")
        raw = json.loads(CAPTURE.read_text(encoding="utf-8"))["response"]
        raw["current"]["time"] = float("nan")
        with self.assertRaises(ValueError):
            parse_open_meteo(raw, NOW, "UTC")

    def test_fetch_validation_happens_before_network(self):
        with patch(
            "tidbyt_clock_weather.provider.build_opener",
            side_effect=AssertionError("network"),
        ):
            for lat, lon, timeout in (
                (91, 0, 10),
                (0, 181, 10),
                (False, 0, 10),
                (0, 0, 31),
                (0, 0, float("nan")),
            ):
                with (
                    self.subTest(lat=lat, lon=lon, timeout=timeout),
                    self.assertRaises(ValueError),
                ):
                    fetch_open_meteo(lat, lon, "UTC", timeout)

    def test_fetch_bounds_and_contract_with_mock_transport(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, limit):
                self.limit = limit
                return b"x" * limit

        response = Response()
        with patch("tidbyt_clock_weather.provider.build_opener") as opener:
            opener.return_value.open.return_value = response
            with self.assertRaisesRegex(ValueError, "too large"):
                fetch_open_meteo(0, 0, "UTC")
            request = opener.return_value.open.call_args.args[0]
            self.assertTrue(
                request.full_url.startswith("https://api.open-meteo.com/v1/forecast?")
            )
            self.assertIn("timeformat=unixtime", request.full_url)
            self.assertEqual(response.limit, 1048577)


class RenderTests(unittest.TestCase):
    def test_offline_render_with_socket_creation_blocked(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            self.assertTrue(encode_webp(*weather_loop(fixture(), NOW)))
            self.assertEqual(render_clock(NOW).size, (64, 32))

    def test_packaged_resources_and_import_boundary(self):
        self.assertIn("palettes", resources())
        self.assertNotIn("tidbyt_suite", sys.modules)
        self.assertNotIn("design", sys.modules)
        self.assertIn("site-packages", str(Path(tidbyt_clock_weather.__file__)))

    def test_import_performs_no_resource_read(self):
        code = "from unittest.mock import patch; import sys;\nwith patch('importlib.resources.files', side_effect=AssertionError('resource I/O')):\n import tidbyt_clock_weather.render\nassert 'tidbyt_suite' not in sys.modules"
        result = subprocess.run(
            [sys.executable, "-B", "-c", code], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clock_dimensions_all_minutes(self):
        for minute in range(1440):
            image = render_clock(
                NOW.replace(hour=0, minute=0) + timedelta(minutes=minute), "UTC"
            )
            self.assertEqual(image.size, (64, 32))
            self.assertEqual(image.mode, "RGB")

    def test_weather_conditions_and_extremes(self):
        for condition in (
            "clear",
            "partly_cloudy",
            "overcast",
            "fog",
            "rain",
            "snow",
            "storm",
            "unknown",
        ):
            for temp in (-120, 0, 160, None):
                weather = replace(fixture(), current=Current(temp, condition, NOW))
                image = render_weather(weather, NOW)
                self.assertEqual(image.size, (64, 32))
        for page in ("current", "today", "tomorrow"):
            self.assertEqual(render_weather(Weather(), NOW, page=page).size, (64, 32))

    def test_local_date_selects_local_forecast(self):
        now = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)
        weather = replace(
            fixture(), forecast=replace(fixture().forecast, observed_at=now)
        )
        image = render_weather(weather, now, "Asia/Tokyo", page="tomorrow")
        missing = render_weather(
            replace(weather, forecast=None), now, "Asia/Tokyo", page="tomorrow"
        )
        self.assertEqual(image.tobytes(), missing.tobytes())
        today = render_weather(weather, now, "Asia/Tokyo", page="today")
        self.assertNotEqual(
            today.tobytes(),
            render_weather(Weather(), now, "Asia/Tokyo", page="today").tobytes(),
        )

    def test_deterministic_render(self):
        frames1, times1 = weather_loop(fixture(), NOW)
        frames2, times2 = weather_loop(fixture(), NOW)
        self.assertEqual(times1, times2)
        self.assertEqual([i.tobytes() for i in frames1], [i.tobytes() for i in frames2])

    def test_exact_pixels_and_variable_durations_roundtrip(self):
        frames = [
            render_weather(fixture(), NOW, page=p, frame=1)
            for p in ("current", "tomorrow")
        ]
        durations = [125, 375]
        data = encode_webp(frames, durations)
        with Image.open(BytesIO(data)) as decoded:
            self.assertEqual(decoded.n_frames, 2)
            self.assertEqual(decoded.info["loop"], 0)
            for i, original in enumerate(frames):
                decoded.seek(i)
                decoded.load()
                self.assertEqual(decoded.convert("RGB").tobytes(), original.tobytes())
                self.assertEqual(decoded.info["duration"], durations[i])

    def test_merged_frames_preserve_timeline(self):
        frames, durations = weather_loop(fixture(), NOW)
        data = encode_webp(frames, durations)
        expected = b"".join(
            frame.tobytes() * (duration // 125)
            for frame, duration in zip(frames, durations)
        )
        with Image.open(BytesIO(data)) as decoded:
            actual = []
            total = 0
            for i in range(decoded.n_frames):
                decoded.seek(i)
                decoded.load()
                duration = decoded.info["duration"]
                self.assertEqual(duration % 125, 0)
                total += duration
                actual.append(decoded.convert("RGB").tobytes() * (duration // 125))
            self.assertEqual(total, 12000)
            self.assertEqual(b"".join(actual), expected)

    def test_encoder_bounds_and_static_pixels(self):
        frame = render_clock(NOW)
        with Image.open(BytesIO(encode_webp([frame], [1000]))) as decoded:
            self.assertEqual(decoded.convert("RGB").tobytes(), frame.tobytes())
        for frames, times in (
            ([], []),
            ([frame], [1]),
            ([frame], [10001]),
            ([frame] * 7, [10000] * 7),
            ([Image.new("RGBA", (64, 32))], [100]),
            ([frame], [True]),
        ):
            with self.assertRaises(ValueError):
                encode_webp(frames, times)

    def test_clock_dst_and_polar_solar(self):
        spring = day_events(date(2026, 3, 8), 40, -74, "America/New_York")
        autumn = day_events(date(2026, 11, 1), 40, -74, "America/New_York")
        self.assertEqual(spring["civil_day_seconds"], 23 * 3600)
        self.assertEqual(autumn["civil_day_seconds"], 25 * 3600)
        self.assertTrue(day_events(date(2026, 6, 21), 89, 0, "UTC")["always_up"])
        self.assertTrue(day_events(date(2026, 12, 21), 89, 0, "UTC")["always_down"])
        for instant in (
            datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc),
            datetime(2026, 3, 8, 7, tzinfo=timezone.utc),
        ):
            self.assertEqual(
                render_clock(instant, "America/New_York", 40, -74).size, (64, 32)
            )


class CliTests(unittest.TestCase):
    def test_offline_cli_outside_checkout_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "weather.webp"
            args = [
                sys.executable,
                "-B",
                "-m",
                "tidbyt_clock_weather.cli",
                "weather",
                "--at",
                NOW.isoformat(),
                "--input",
                str(CAPTURE),
                "--output",
                str(output),
            ]
            with patch("socket.socket", side_effect=AssertionError("No network")):
                # Rendering itself has no network path; subprocess test exercises packaging/CLI.
                result = subprocess.run(
                    args, cwd=folder, capture_output=True, text=True
                )
            self.assertEqual(result.returncode, 0, result.stderr)
            original = output.read_bytes()
            result = subprocess.run(args, cwd=folder, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), original)
            with Image.open(output) as image:
                self.assertEqual(image.size, (64, 32))

    def test_missing_or_oversized_capture_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "out.webp"
            oversized = Path(folder) / "huge.json"
            oversized.write_bytes(b" " * 1048577)
            for capture in (Path(folder) / "missing.json", oversized):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-m",
                        "tidbyt_clock_weather.cli",
                        "weather",
                        "--at",
                        NOW.isoformat(),
                        "--input",
                        str(capture),
                        "--output",
                        str(output),
                    ],
                    cwd=folder,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
