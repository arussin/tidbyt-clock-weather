"""Optional Open-Meteo adapter. No network request occurs until explicitly called."""

from datetime import datetime, timezone
import json
from math import isfinite
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo
from .model import Current, Forecast, ForecastDay, Weather, aware

MAX_RESPONSE_BYTES = 1048576
WMO = {0: "clear", 1: "clear", 2: "partly_cloudy", 3: "overcast", 45: "fog", 48: "fog"}
WMO.update(
    {
        51: "drizzle",
        53: "drizzle",
        55: "drizzle",
        56: "freezing_rain",
        57: "freezing_rain",
        61: "rain",
        63: "rain",
        65: "heavy_rain",
        66: "freezing_rain",
        67: "freezing_rain",
        80: "rain",
        81: "rain",
        82: "heavy_rain",
        71: "snow",
        73: "snow",
        75: "heavy_snow",
        77: "snow",
        85: "snow",
        86: "heavy_snow",
        95: "storm",
        96: "storm_hail",
        99: "storm_hail",
    }
)


def _code(value):
    return WMO.get(value, "unknown") if type(value) is int else "unknown"


def _timestamp(value):
    # Fetch requests Unix time to avoid ambiguous local times during DST folds.
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("Expected finite Unix observation time")
    try:
        return datetime.fromtimestamp(value, timezone.utc)
    except (ValueError, OverflowError, OSError) as exc:
        raise ValueError("Invalid observation time") from exc


def parse_open_meteo(raw: dict, fetched_at: datetime, timezone_name: str) -> Weather:
    """Parse the documented Fahrenheit/mph, Unix-time query contract only.

    The current timestamp comes from the provider. Forecast freshness is the
    caller's actual retrieval timestamp, so persisted captures must preserve it.
    """
    aware(fetched_at)
    zone = ZoneInfo(timezone_name)
    try:
        units, daily_units = raw["current_units"], raw["daily_units"]
        if units["temperature_2m"] != "°F" or units["wind_speed_10m"] != "mp/h":
            raise ValueError("Expected Fahrenheit and mph")
        if (
            daily_units["temperature_2m_max"] != "°F"
            or daily_units["temperature_2m_min"] != "°F"
        ):
            raise ValueError("Expected Fahrenheit forecast")
        if daily_units["precipitation_probability_max"] != "%":
            raise ValueError("Expected percentage probability")
        if units["time"] != "unixtime" or daily_units["time"] != "unixtime":
            raise ValueError("Expected Unix timestamps")
        c, d = raw["current"], raw["daily"]
        current = Current(
            c["temperature_2m"],
            _code(c["weather_code"]),
            _timestamp(c["time"]),
            c["wind_speed_10m"],
        )
        keys = (
            "time",
            "temperature_2m_max",
            "temperature_2m_min",
            "weather_code",
            "precipitation_probability_max",
        )
        values = [d[key] for key in keys]
        if (
            not all(isinstance(v, list) for v in values)
            or len({len(v) for v in values}) != 1
        ):
            raise ValueError("Forecast columns must have equal lengths")
        days = tuple(
            ForecastDay(
                _timestamp(t).astimezone(zone).date(), high, low, _code(code), rain
            )
            for t, high, low, code, rain in zip(*values)
        )
        return Weather(current, Forecast(days, fetched_at))
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid Open-Meteo schema") from exc


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_open_meteo(
    latitude: float, longitude: float, timezone_name: str, timeout: float = 10
) -> Weather:
    for value, maximum in ((latitude, 90), (longitude, 180)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not isfinite(value)
            or abs(value) > maximum
        ):
            raise ValueError("Invalid location")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (float, int))
        or not isfinite(timeout)
        or not 0 < timeout <= 30
    ):
        raise ValueError("Timeout must be in (0, 30] seconds")
    ZoneInfo(timezone_name)
    query = urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone_name,
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timeformat": "unixtime",
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "forecast_days": 2,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        }
    )
    request = Request(
        "https://api.open-meteo.com/v1/forecast?" + query,
        headers={"User-Agent": "tidbyt-clock-weather/0.1"},
    )
    with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("Provider response unavailable")
        data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Provider response too large")
    raw = json.loads(
        data,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("Non-finite JSON")
        ),
    )
    return parse_open_meteo(raw, datetime.now(timezone.utc), timezone_name)
