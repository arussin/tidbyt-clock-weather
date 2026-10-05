"""Polished native material lighting, independent of weather and LED display emulation.

Extracted from the original v0.6 material renderer. Integer RGB rounding is explicit.
"""

from __future__ import annotations
from importlib.resources import files
from math import floor
import json
from .solar import clamp, smooth

SPEC = json.loads(
    files(__package__).joinpath("assets/lighting.json").read_text(encoding="utf-8")
)
ROLES = tuple(SPEC["roles"])
ROLE = {r: i + 1 for i, r in enumerate(ROLES)}
PHASES = tuple(SPEC["phases"])


def HEX(h):
    return tuple(bytes.fromhex(h))


def rnd(x):
    return int(floor(clamp(x, 0, 255) + 0.5))


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3))


def canonical_condition(condition):
    return "clear" if condition == "clear_night" else condition


def palette(light: dict, condition="clear") -> list[tuple]:
    condition = canonical_condition(condition)
    if condition not in SPEC["weather"]:
        raise ValueError("Unrecognized condition")
    weights = light["weights"]
    factor, muting = SPEC["weather"][condition]
    colors = {
        r: tuple(
            sum(HEX(SPEC["palettes"][ph][r])[i] * weights[ph] for ph in PHASES)
            for i in range(3)
        )
        for r in ROLES
    }
    # Artistic cloud attenuation affects materials, not the data or window source.
    exposed = {
        "sky",
        "haze",
        "far",
        "far_light",
        "ridge_shadow",
        "ridge",
        "ridge_light",
        "snow",
        "forest",
        "pine",
        "pine_light",
        "shore",
        "water",
        "water_mid",
        "water_light",
        "roof",
        "roof_light",
        "cloud_shadow",
        "cloud",
        "cloud_light",
        "precipitation",
    }
    for r in exposed:
        c = colors[r]
        gray = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722
        muted = mix(c, (gray * 0.90, gray * 0.99, gray * 1.10), muting)
        gain = (
            factor
            if r
            in {
                "sky",
                "haze",
                "far",
                "far_light",
                "cloud_shadow",
                "cloud",
                "cloud_light",
            }
            else 0.65 + 0.35 * factor
        )
        colors[r] = tuple(v * gain for v in muted)
    if condition in {"storm", "storm_hail"}:
        for r in ("cloud", "cloud_shadow", "cloud_light"):
            c = colors[r]
            colors[r] = (c[0] * 1.09, c[1] * 0.83, c[2] * 1.05)
    if condition == "fog":
        for r, t in [
            ("far", 0.78),
            ("far_light", 0.8),
            ("ridge_shadow", 0.40),
            ("ridge", 0.42),
            ("ridge_light", 0.45),
            ("forest", 0.20),
        ]:
            colors[r] = mix(colors[r], colors["haze"], t)
    # Light from windows remains warm; it does not inexplicably become brighter
    # just because a dark weather filter is applied to the rest of the scene.
    lut = [(0, 0, 0)] * 256
    for role, code in ROLE.items():
        lut[code] = tuple(rnd(v) for v in colors[role])
    stops = [
        tuple(
            sum(HEX(SPEC["sky"][ph][j])[i] * weights[ph] for ph in PHASES)
            for i in range(3)
        )
        for j in range(3)
    ]
    bands = SPEC.get("sky_bands", 8)
    for band in range(bands):
        t = band / (bands - 1) * 2
        j = min(1, int(t))
        c = mix(stops[j], stops[j + 1], t - j)
        gray = c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722
        c = mix(c, (gray * 0.9, gray * 0.99, gray * 1.1), muting)
        lut[40 + band] = tuple(rnd(v * factor) for v in c)
    for k, v in SPEC["ui_colors"].items():
        lut[int(k)] = HEX(v)
    # Gentle celestial fade; the crescent is an illustrated emblem, NOT lunar data.
    return lut


def celestial_pixels(
    light: dict, frame: int, screen: str, condition: str = "clear"
) -> list:
    """Return native x,y,color,opacity overlay; occlude against non-sky materials."""
    if screen not in {"weather", "clock"}:
        return []
    cond = canonical_condition(condition)
    if screen == "weather" and cond not in {"clear", "partly_cloudy"}:
        return []
    p = palette(light, cond)
    alt = light["elevation"]
    f = frame % 96
    points = []
    solar = smooth(-1.3, 1, alt)
    lunar = 1 - smooth(-9, -1, alt)
    # Always in the left-hand sky to retain the selected composition.
    sy = 2 + int(floor((1 - clamp(alt / 40)) * 6 + 0.5))
    for name, x, y, a in [("sun", 5, sy, solar), ("moon", 4, 2, lunar)]:
        if a <= 0:
            continue
        for dy, row in enumerate(SPEC[name]):
            for dx, v in enumerate(row):
                if v == "1":
                    points.append((x + dx, y + dy, p[ROLE["celestial"]], a))
    for i, (x, y) in enumerate(SPEC["stars"]):
        color = (
            p[ROLE["snow"]]
            if (f + 13 * i) % 48 in (18, 19, 20)
            else p[ROLE["far_light"]]
        )
        points.append((x, y, color, lunar))
    return points


def colorize(index, light: dict, screen: str, condition="clear", frame=0):
    from PIL import Image

    if index.size != (64, 32) or index.mode != "L":
        raise ValueError("Expected exact native material map")
    lut = palette(light, condition)
    if screen == "clock":
        for i in range(40, 40 + SPEC.get("sky_bands", 8)):
            lut[i] = tuple(rnd(v * 0.36) for v in lut[i])
    pixels = list(index.get_flattened_data())
    out = [lut[i] for i in pixels]
    for x, y, color, alpha in celestial_pixels(light, frame, screen, condition):
        j = y * 64 + x
        if (
            0 <= x < 64
            and 0 <= y < 32
            and 40 <= pixels[j] < 40 + SPEC.get("sky_bands", 8)
        ):
            out[j] = tuple(rnd(v) for v in mix(out[j], color, alpha))
    im = Image.new("RGB", (64, 32))
    im.putdata(out)
    return im
