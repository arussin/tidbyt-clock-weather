"""Validated, immutable inputs with independent current and forecast freshness."""

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from math import isfinite

CONDITIONS = frozenset(
    {
        "clear",
        "clear_night",
        "partly_cloudy",
        "overcast",
        "fog",
        "drizzle",
        "rain",
        "heavy_rain",
        "freezing_rain",
        "snow",
        "heavy_snow",
        "storm",
        "storm_hail",
        "unknown",
    }
)


def aware(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("An offset-aware datetime is required")
    return value


def number(value, minimum, maximum, name):
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ValueError(f"Invalid {name}")
    return float(value)


def condition(value):
    if not isinstance(value, str) or value not in CONDITIONS:
        raise ValueError("Unsupported condition")
    return value


def ttl(value):
    if type(value) is not int or not 1 <= value <= 86400:
        raise ValueError("TTL must be 1..86400 seconds")
    return value


def fresh(observed_at: datetime, ttl_seconds: int, now: datetime) -> bool:
    # Future-dated observations never count as fresh.
    age = (
        aware(now).astimezone(timezone.utc)
        - aware(observed_at).astimezone(timezone.utc)
    ).total_seconds()
    return 0 <= age <= ttl(ttl_seconds)


@dataclass(frozen=True)
class Current:
    temperature_f: float | None
    condition: str
    observed_at: datetime
    wind_mph: float | None = None
    ttl_seconds: int = 2700

    def __post_init__(self):
        number(self.temperature_f, -120, 160, "temperature")
        number(self.wind_mph, 0, 300, "wind")
        condition(self.condition)
        aware(self.observed_at)
        ttl(self.ttl_seconds)

    def fresh(self, now):
        return fresh(self.observed_at, self.ttl_seconds, now)


@dataclass(frozen=True)
class ForecastDay:
    date: date
    high_f: float | None
    low_f: float | None
    condition: str
    rain_percent: float | None = None

    def __post_init__(self):
        if type(self.date) is not date:
            raise ValueError("Forecast date must be a civil date")
        number(self.high_f, -120, 160, "high")
        number(self.low_f, -120, 160, "low")
        number(self.rain_percent, 0, 100, "rain probability")
        if (
            self.high_f is not None
            and self.low_f is not None
            and self.high_f < self.low_f
        ):
            raise ValueError("High must not be lower than low")
        condition(self.condition)


@dataclass(frozen=True)
class Forecast:
    days: tuple[ForecastDay, ...]
    observed_at: datetime
    ttl_seconds: int = 5400

    def __post_init__(self):
        aware(self.observed_at)
        ttl(self.ttl_seconds)
        if not isinstance(self.days, tuple) or not all(
            isinstance(day, ForecastDay) for day in self.days
        ):
            raise ValueError("Forecast days must be a tuple of ForecastDay")
        if len(self.days) > 16 or len({day.date for day in self.days}) != len(
            self.days
        ):
            raise ValueError("Duplicate or excessive forecast dates")

    def fresh(self, now):
        return fresh(self.observed_at, self.ttl_seconds, now)

    def day(self, wanted, now):
        if not self.fresh(now):
            return None
        return next((day for day in self.days if day.date == wanted), None)


@dataclass(frozen=True)
class Weather:
    current: Current | None = None
    forecast: Forecast | None = None

    def __post_init__(self):
        if self.current is not None and not isinstance(self.current, Current):
            raise ValueError("Invalid current observation")
        if self.forecast is not None and not isinstance(self.forecast, Forecast):
            raise ValueError("Invalid forecast")


def merge_current(weather: Weather, observation: Current, now: datetime) -> Weather:
    """Use fresh current data without changing ANY forecast data, timestamp, or TTL."""
    return replace(weather, current=observation) if observation.fresh(now) else weather
