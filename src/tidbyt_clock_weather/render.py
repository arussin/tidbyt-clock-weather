"""Bounded public API for the original native v0.6 clock and weather design."""

from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo
from .model import Weather, aware
from .solar import context

SIZE = (64, 32)


def _frame(value):
    if type(value) is not int or not 0 <= value < 600:
        raise ValueError("Frame must be 0..599")
    return value % 96


def render_clock(
    now: datetime,
    timezone_name="UTC",
    latitude=0.0,
    longitude=0.0,
    frame=0,
    phase="auto",
):
    """Original right-aligned 12-hour clock, tiny landscape, date, and celestial sky."""
    aware(now)
    from ._native import clock_frame

    return clock_frame(
        now, timezone_name, _frame(frame), context(now, latitude, longitude, phase)
    )


def _effective_weather(weather, now, timezone_name):
    if not isinstance(weather, Weather):
        raise ValueError("Expected Weather")
    today = now.astimezone(ZoneInfo(timezone_name)).date()
    current = weather.current
    usable = current is not None and current.fresh(now)
    w = {
        "temperature": current.temperature_f if usable else None,
        "condition": current.condition if usable else "unknown",
        "wind_mph": current.wind_mph if usable else None,
    }
    for key, day in (("today", today), ("tomorrow", today + timedelta(days=1))):
        forecast = weather.forecast.day(day, now) if weather.forecast else None
        w[key] = {
            "high": forecast.high_f if forecast else None,
            "low": forecast.low_f if forecast else None,
            "condition": forecast.condition if forecast else "unknown",
        }
    return w, None if usable else ("Old" if current or weather.forecast else "--")


def render_weather(
    weather: Weather,
    now: datetime,
    timezone_name="UTC",
    page=None,
    frame=0,
    latitude=0.0,
    longitude=0.0,
    phase="auto",
):
    """Original animated landscape and right-hand current/today/tomorrow panel.

    Frame 0..47 shows today; 48..95 shows tomorrow. A page override selects
    a half of that same design. Current temperature remains above both halves.
    """
    aware(now)
    f = _frame(frame)
    if page not in {None, "current", "today", "tomorrow"}:
        raise ValueError("Invalid page")
    if page is not None:
        f = f % 48 + (48 if page == "tomorrow" else 0)
    from ._native import weather_frame

    w, stale_label = _effective_weather(weather, now, timezone_name)
    return weather_frame(w, f, context(now, latitude, longitude, phase), stale_label)


def weather_loop(
    weather, now, timezone_name="UTC", latitude=0.0, longitude=0.0, phase="auto"
):
    """Original twelve-second loop: six seconds today, six seconds tomorrow."""
    return [
        render_weather(
            weather,
            now,
            timezone_name,
            frame=f,
            latitude=latitude,
            longitude=longitude,
            phase=phase,
        )
        for f in range(96)
    ], [125] * 96


def clock_loop(now, timezone_name="UTC", latitude=0.0, longitude=0.0, phase="auto"):
    """Original twelve-second celestial animation with a fixed displayed time."""
    return [
        render_clock(now, timezone_name, latitude, longitude, f, phase)
        for f in range(96)
    ], [125] * 96


def encode_webp(frames, durations_ms):
    """Opaque lossless WebP; frame merging by codec preserves total timing."""
    frames, durations_ms = list(frames), list(durations_ms)
    if not frames or len(frames) > 600 or len(frames) != len(durations_ms):
        raise ValueError("Expected 1..600 frames and one duration per frame")
    if any(frame.size != SIZE or frame.mode != "RGB" for frame in frames):
        raise ValueError("Frames must be opaque RGB 64x32")
    if any(
        type(duration) is not int or not 20 <= duration <= 10000
        for duration in durations_ms
    ):
        raise ValueError("Duration must be 20..10000 ms")
    if sum(durations_ms) > 60000:
        raise ValueError("Animation must be at most 60 seconds")
    output = BytesIO()
    frames[0].save(
        output,
        format="WEBP",
        lossless=True,
        exact=True,
        method=6,
        save_all=len(frames) > 1,
        append_images=frames[1:],
        duration=durations_ms,
        loop=0,
    )
    return output.getvalue()
