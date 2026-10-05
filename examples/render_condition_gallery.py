"""Render README screenshots from the real renderer with entirely synthetic inputs.

Run with the package installed; writes only to the explicitly supplied output folder.
"""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from PIL import Image
from tidbyt_clock_weather.model import (
    Current,
    Forecast,
    ForecastDay,
    Weather,
    CONDITIONS,
)
from tidbyt_clock_weather.render import render_weather

SAMPLES = [
    ("clear", "Clear day", "day", 20),
    ("clear_night", "Clear night", "night", 20),
    ("partly_cloudy", "Partly cloudy", "day", 20),
    ("overcast", "Overcast", "day", 20),
    ("drizzle", "Drizzle", "day", 20),
    ("rain", "Rain", "day", 20),
    ("heavy_rain", "Heavy rain", "day", 20),
    ("freezing_rain", "Freezing rain", "day", 20),
    ("snow", "Snow", "day", 20),
    ("heavy_snow", "Heavy snow", "day", 20),
    ("fog", "Fog", "day", 20),
    ("storm", "Thunderstorm", "day", 52),
    ("storm_hail", "Thunderstorm with hail", "day", 52),
    ("unknown", "Unavailable weather", "day", 20),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
    records = []
    assert {row[0] for row in SAMPLES} == CONDITIONS
    for condition, label, phase, frame in SAMPLES:
        weather = (
            Weather()
            if condition == "unknown"
            else Weather(
                Current(68, condition, now, 24 if condition.startswith("storm") else 9),
                Forecast(
                    (
                        ForecastDay(now.date(), 72, 54, condition),
                        ForecastDay(now.date() + timedelta(days=1), 74, 56, condition),
                    ),
                    now,
                ),
            )
        )
        native = render_weather(weather, now, frame=frame, phase=phase)
        preview = native.resize((384, 192), Image.Resampling.NEAREST)
        path = args.output / (condition + ".png")
        preview.save(path)
        with Image.open(path) as decoded:
            assert decoded.mode == "RGB" and decoded.size == (384, 192)
            assert (
                decoded.resize((64, 32), Image.Resampling.NEAREST).tobytes()
                == native.tobytes()
            )
        records.append(
            {
                "condition": condition,
                "label": label,
                "phase": phase,
                "frame": frame,
                "file": path.name,
                "native_rgb_sha256": hashlib.sha256(native.tobytes()).hexdigest(),
                "png_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    (args.output / "screenshots.json").write_text(
        json.dumps(
            {
                "input": "synthetic",
                "native_size": [64, 32],
                "screenshot_size": [384, 192],
                "enlargement": "6x nearest-neighbor",
                "at": now.isoformat(),
                "timezone": "UTC",
                "latitude": 0,
                "longitude": 0,
                "screenshots": records,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        f"Rendered {len(records)} conditions; decoded screenshots preserve every native pixel."
    )


if __name__ == "__main__":
    main()
