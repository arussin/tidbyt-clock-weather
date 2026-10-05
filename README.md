# Tidbyt Clock & Weather

The original native 64×32 design: a quiet, right-aligned 12-hour clock and an animated cabin, mountain and lake weather scene. The weather panel shows current temperature throughout a 12-second loop: today's range for six seconds, then tomorrow's range for six seconds. Five solar lighting phases preserve the original palettes, tiny bitmap lettering, reflections, clouds and precipitation.

Python 3.11+ with Pillow. Code, native bitmap glyphs and original artwork are available under the [MIT license](LICENSE). See [provenance](PROVENANCE.md) and [validation](VALIDATION.md).

![Original design with synthetic data](review/contact-sheet.png)

## Try it offline

Clone this repository and create a fresh virtual environment:

```powershell
git clone https://github.com/arussin/tidbyt-clock-weather.git
cd tidbyt-clock-weather
python -m venv .venv
.venv\Scripts\python -m pip install .
.venv\Scripts\tidbyt-scenes clock --at 2026-01-15T12:00:00+00:00 --timezone UTC --phase night --output clock.webp
.venv\Scripts\tidbyt-scenes weather --at 2026-01-15T12:00:00+00:00 --input examples/synthetic-weather.json --phase night --output weather.webp
```

Open the WebP files in an animation-capable image viewer. Both render the original 96-frame, 125 ms timeline. A wholly static clock phase can encode as a still image; animated phases retain elapsed timing. These commands read only the synthetic capture and write a new file; they do not fetch weather or contact a device. Existing output files are never overwritten.

`--phase night` is a preview override. Omit it for solar lighting, then set `--latitude`, `--longitude` and `--timezone` for your own display. Defaults are UTC at latitude/longitude zero. Keep the example timestamp for this capture; using a later time correctly hides expired values.

## Connect your data

The public API accepts explicit values and returns Pillow RGB images or lossless WebP bytes:

```python
from datetime import datetime, timezone
from pathlib import Path
from tidbyt_clock_weather.render import clock_loop, encode_webp

now = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)
frames, durations = clock_loop(now, timezone_name="UTC", phase="night")
Path("clock.webp").write_bytes(encode_webp(frames, durations))
```

Use `Current`, `ForecastDay`, `Forecast` and `Weather` from `model` for weather data. `render_weather(weather, now, timezone_name, frame=0)` returns one native frame; `weather_loop` returns frames and durations. Frames 0–47 show today and 48–95 show tomorrow. The current temperature stays above both panels. `page="today"` or `page="tomorrow"` selects the corresponding half for a still preview.

Current and forecast observations retain separate timestamps and expiration limits. Refreshing current weather cannot rejuvenate a stale forecast. Expired or future-dated values become `--`; missing current conditions use the original `No data` scene. The original `Old`/`--` badge is retained. This conservative input handling is separate from visual parity: the original live suite can retain last-known values with an `Old` badge, while this package hides expired values.

The optional `provider.fetch_open_meteo(latitude, longitude, timezone_name)` makes a request only when explicitly called. It rejects redirects and bounds response size and request timeout. It has no polling, credentials or background process. The initial provider supports Fahrenheit/mph and all original weather families, including drizzle, heavy rain, freezing rain, heavy snow and hail. Read [Open-Meteo's terms](https://open-meteo.com/en/terms) before use; provider attribution and data terms are separate from the eventual code license.

The offline CLI expects the capture envelope shown in `examples/synthetic-weather.json`: an original `fetched_at` timestamp plus the provider `response`. Do not replace a saved capture's timestamp with the current time.

## Scope

This is a renderer, not a device scheduler or a Tidbyt Community app. [Pixlet](https://github.com/tidbyt/pixlet) is the established rendering/push ecosystem. This package does not push, install or schedule images, store secrets, change sleep behavior, or connect to Home, analytics or an AI agent. It contains no robot assets, private configuration, reference mockups, artwork inbox or web simulator.

The output is exactly 64×32 opaque RGB. The clock is 12-hour with the original abbreviated weekday/date; weather values are Fahrenheit. The crescent and solar palettes are illustrations, not moon-phase data or calibrated brightness. Localization and extra layout options have not been added.

## Tests and compatibility

Install the package into a fresh environment, change to a directory outside this checkout, and run `python -m unittest discover -s PATH_TO_CHECKOUT/tests -v`. Tests require imports from the installed package. They include 92 fixed canonical pixel hashes. Windows/Python evidence is recorded in [VALIDATION.md](VALIDATION.md); live provider, physical device, Linux and macOS acceptance remain separate.

This repository starts with a clean history and synthetic examples. It contains no private suite history, credentials or personal geographic configuration.
