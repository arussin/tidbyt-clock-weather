"""Explicit offline CLI. It neither fetches weather nor sends to a device."""

import argparse
from datetime import datetime
import json
from pathlib import Path
from .provider import parse_open_meteo
from .render import encode_webp, clock_loop, weather_loop

MAX_CAPTURE_BYTES = 1048576


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scene", choices=("clock", "weather"))
    parser.add_argument(
        "--at",
        required=True,
        help="Offset-aware ISO timestamp; explicit for repeatable offline renders",
    )
    parser.add_argument("--timezone", default="UTC", help="IANA zone")
    parser.add_argument(
        "--latitude",
        type=float,
        default=0.0,
        help="Illustrative solar lighting for both scenes",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=0.0,
        help="Illustrative solar lighting for both scenes",
    )
    parser.add_argument(
        "--input", type=Path, help="Weather capture containing fetched_at and response"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--phase",
        choices=("auto", "dawn", "day", "golden", "dusk", "night"),
        default="auto",
        help="auto follows the sun; named phases are preview overrides",
    )
    args = parser.parse_args(argv)
    try:
        now = datetime.fromisoformat(args.at)
        if args.scene == "clock":
            data = encode_webp(
                *clock_loop(
                    now, args.timezone, args.latitude, args.longitude, args.phase
                )
            )
        else:
            if args.input is None:
                parser.error("weather requires --input")
            with args.input.open("rb") as capture:
                raw = capture.read(MAX_CAPTURE_BYTES + 1)
            if len(raw) > MAX_CAPTURE_BYTES:
                raise ValueError("Capture exceeds one MiB")
            envelope = json.loads(raw)
            weather = parse_open_meteo(
                envelope["response"],
                datetime.fromisoformat(envelope["fetched_at"]),
                args.timezone,
            )
            data = encode_webp(
                *weather_loop(
                    weather,
                    now,
                    args.timezone,
                    args.latitude,
                    args.longitude,
                    args.phase,
                )
            )
        # Exclusive create protects existing exports from accidental overwrite.
        with args.output.open("xb") as output:
            output.write(data)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(
            2,
            f"Render failed: {type(exc).__name__}. Check input, timezone, and output path.\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
