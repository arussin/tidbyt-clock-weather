"""Offline solar position for an illustrated lighting system, not navigation.

Original implementation of NOAA/Meeus-style solar equations. Geometric elevation
(no atmospheric refraction). Sunrise/set use the conventional -0.833 degree
centre threshold; civil twilight uses -6. Source links and validation in docs.
Naive datetimes, non-finite coordinates and missing locations are rejected.
"""

from __future__ import annotations
from datetime import datetime, date, time, timedelta, timezone
from math import sin, cos, tan, asin, radians, degrees, isfinite
from zoneinfo import ZoneInfo

PHASES = ("dawn", "day", "golden", "dusk", "night")


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(hi, max(lo, v))


def smooth(lo: float, hi: float, x: float) -> float:
    v = clamp((x - lo) / (hi - lo))
    return v * v * (3 - 2 * v)


def position(instant: datetime, latitude: float, longitude: float) -> dict:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("Solar input must be an aware instant")
    for v, limit in ((latitude, 90), (longitude, 180)):
        if (
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not isfinite(v)
            or abs(v) > limit
        ):
            raise ValueError("Invalid solar coordinate")
    utc = instant.astimezone(timezone.utc)
    jd = utc.timestamp() / 86400 + 2440587.5
    t = (jd - 2451545) / 36525
    L = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    M = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = sin(radians(M)) * (1.914602 - t * (0.004817 + 0.000014 * t))
    c += (
        sin(radians(2 * M)) * (0.019993 - 0.000101 * t) + sin(radians(3 * M)) * 0.000289
    )
    omega = 125.04 - 1934.136 * t
    lam = L + c - 0.00569 - 0.00478 * sin(radians(omega))
    eps = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps += 0.00256 * cos(radians(omega))
    dec = asin(sin(radians(eps)) * sin(radians(lam)))
    y = tan(radians(eps) / 2) ** 2
    eq = 4 * degrees(
        y * sin(2 * radians(L))
        - 2 * e * sin(radians(M))
        + 4 * e * y * sin(radians(M)) * cos(2 * radians(L))
        - 0.5 * y * y * sin(4 * radians(L))
        - 1.25 * e * e * sin(2 * radians(M))
    )
    minutes = utc.hour * 60 + utc.minute + (utc.second + utc.microsecond / 1e6) / 60
    hour_angle = ((minutes + eq + 4 * longitude) % 1440) / 4 - 180
    phi = radians(latitude)
    alt = degrees(
        asin(
            clamp(
                sin(phi) * sin(dec) + cos(phi) * cos(dec) * cos(radians(hour_angle)),
                -1,
                1,
            )
        )
    )
    return {
        "elevation": alt,
        "hour_angle": hour_angle,
        "declination": degrees(dec),
        "equation_minutes": eq,
    }


def weights_for(elevation: float, hour_angle: float) -> dict:
    """Art-directed blends. Golden-hour boundaries here are design choices.

    Morning and evening twilight are different color scripts. A smooth solar-noon
    blend avoids an abrupt branch at very high latitudes with a low noon sun.
    """
    if not isfinite(elevation) or not isfinite(hour_angle):
        raise ValueError("Non-finite solar angle")
    night = 1 - smooth(-12, -4, elevation)
    light = 1 - night
    morning = {k: 0.0 for k in PHASES}
    evening = dict(morning)
    morning["night"] = evening["night"] = night
    dg = smooth(0, 5, elevation)
    gd = smooth(6, 16, elevation)
    morning["dawn"] = light * (1 - dg)
    morning["golden"] = light * dg * (1 - gd)
    morning["day"] = light * dg * gd
    evening["dusk"] = light * (1 - smooth(-4, 3, elevation))
    evening["golden"] = light * smooth(-4, 3, elevation) * (1 - gd)
    evening["day"] = light * smooth(-4, 3, elevation) * gd
    branch = smooth(-12, 12, hour_angle)
    return {k: morning[k] * (1 - branch) + evening[k] * branch for k in PHASES}


def context(instant: datetime, latitude: float, longitude: float, phase="auto") -> dict:
    if phase not in ("auto", *PHASES):
        raise ValueError("Unknown lighting state")
    real = position(instant, latitude, longitude)
    if phase == "auto":
        weights = weights_for(real["elevation"], real["hour_angle"])
        return {
            **real,
            "weights": weights,
            "phase": max(weights, key=weights.get),
            "mode": "auto",
        }
    alt, ha = {
        "dawn": (-2, -85),
        "day": (40, 0),
        "golden": (4, 75),
        "dusk": (-3, 88),
        "night": (-30, 135),
    }[phase]
    return {
        "elevation": alt,
        "hour_angle": ha,
        "weights": {k: float(k == phase) for k in PHASES},
        "phase": phase,
        "mode": "manual",
    }


def day_events(day: date, latitude: float, longitude: float, zone: str) -> dict:
    """Find crossings over a local civil day. Missing polar events stay None.

    UTC iteration makes DST days 23/25 hours long correctly. Two-minute bracketing,
    then bisection; no clock-time heuristic is used to choose lighting.
    """
    tz = ZoneInfo(zone)
    start = datetime.combine(day, time(), tz).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(), tz).astimezone(timezone.utc)
    result = {"sunrise": None, "sunset": None, "dawn": None, "dusk": None}
    prev = start
    pe = position(prev, latitude, longitude)["elevation"]
    minimum = maximum = pe
    while prev < end:
        nxt = min(prev + timedelta(minutes=2), end)
        ne = position(nxt, latitude, longitude)["elevation"]
        minimum = min(minimum, ne)
        maximum = max(maximum, ne)
        for target, a, b in ((-0.833, "sunrise", "sunset"), (-6, "dawn", "dusk")):
            if (pe < target <= ne) or (ne < target <= pe):
                lo, hi = prev, nxt
                ascending = ne > pe
                for _ in range(15):
                    mid = lo + (hi - lo) / 2
                    v = position(mid, latitude, longitude)["elevation"]
                    if (v < target) == ascending:
                        lo = mid
                    else:
                        hi = mid
                result[a if ascending else b] = (
                    (lo + (hi - lo) / 2).astimezone(tz).isoformat()
                )
        prev, pe = nxt, ne
    return {
        **result,
        "always_up": minimum > -0.833,
        "always_down": maximum < -0.833,
        "civil_day_seconds": int((end - start).total_seconds()),
        "method": "geometric centre crossings; sunrise/set -0.833 deg",
    }
