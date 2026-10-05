"""Original v0.6 clock/weather pixels with package-local assets and explicit inputs."""

from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
from . import _glyphs as a
from ._lighting import SPEC, ROLE, canonical_condition, colorize

SIZE = (64, 32)
FRAMES = 96
DURATION_MS = 125
CONDITIONS = tuple(SPEC["weather"])
CLOCK_ROLE = {
    "sky": 1,
    "haze": 2,
    "far": 3,
    "far_light": 4,
    "ridge_shadow": 5,
    "ridge": 6,
    "ridge_light": 7,
    "snow": 8,
    "forest": 9,
    "pine": 10,
    "pine_light": 11,
    "shore": 12,
    "water": 13,
    "water_mid": 14,
    "water_light": 15,
    "roof": 16,
    "roof_light": 17,
    "wall": 18,
    "wall_light": 19,
    "window": 20,
    "window_core": 21,
    "reflection": 22,
    "cloud_shadow": 23,
    "cloud": 24,
    "cloud_light": 25,
    "celestial": 26,
    "precipitation": 27,
}


@lru_cache(maxsize=2)
def base_land(snow=False):
    with (
        files(__package__)
        .joinpath("assets", "landscape_snow.png" if snow else "landscape_materials.png")
        .open("rb") as stream,
        Image.open(stream) as src,
    ):
        if src.mode != "L" or src.size != (42, 32):
            raise ValueError("Invalid native landscape")
        return src.copy()


def _clouds(im, frame, condition):
    """Staged rounded cloud clusters; their edges share a closed, slow timeline."""
    if condition not in {
        "partly_cloudy",
        "overcast",
        "drizzle",
        "rain",
        "heavy_rain",
        "freezing_rain",
        "snow",
        "heavy_snow",
        "storm",
        "storm_hail",
    }:
        return
    P = ROLE
    overlay = Image.new("L", im.size)
    d = ImageDraw.Draw(overlay)
    # Distant bank is independently phased, not a single sticker rocking left/right.
    dx = (0, 0, 1, 1, 1, 0, 0, -1, -1, -1, 0, 0)[frame // 8]
    if condition != "partly_cloudy":
        d.polygon(
            [
                (0, 0),
                (41, 0),
                (41, 4),
                (35, 3),
                (31, 5),
                (26, 4),
                (22, 5),
                (15, 3),
                (9, 4),
                (4, 2),
                (0, 3),
            ],
            fill=P["cloud_shadow"],
        )
        d.polygon(
            [
                (0, 0),
                (41, 0),
                (41, 2),
                (34, 1),
                (29, 3),
                (25, 2),
                (18, 3),
                (13, 1),
                (8, 2),
                (3, 1),
                (0, 2),
            ],
            fill=P["cloud"],
        )
        d.line([(6, 2), (9, 2), (10, 3), (14, 3)], fill=P["far_light"])
    y = 4 if condition == "partly_cloudy" else 1
    pts = [
        (16, 4),
        (17, 2),
        (20, 2),
        (21, 1),
        (22, 0),
        (25, 0),
        (27, 2),
        (30, 2),
        (32, 4),
        (35, 4),
        (36, 5),
        (34, 6),
        (18, 6),
        (15, 5),
    ]
    d.polygon([(x + dx, y + yy) for x, yy in pts], fill=P["cloud_shadow"])
    d.polygon(
        [
            (16 + dx, y + 4),
            (18 + dx, y + 3),
            (21 + dx, y + 3),
            (22 + dx, y + 1),
            (25 + dx, y),
            (27 + dx, y + 3),
            (29 + dx, y + 3),
            (31 + dx, y + 4),
            (34 + dx, y + 5),
            (18 + dx, y + 5),
        ],
        fill=P["cloud"],
    )
    d.line(
        [(22 + dx, y + 1), (24 + dx, y), (25 + dx, y), (26 + dx, y + 2)],
        fill=P["cloud_light"],
    )
    d.line((18 + dx, y + 3, 20 + dx, y + 3), fill=P["cloud_light"])
    d.point((31 + dx, y + 4), fill=P["cloud_light"])
    # The mountain/woodland masks always win over clouds.
    for y in range(10):
        for x in range(42):
            v = overlay.getpixel((x, y))
            if v and 40 <= im.getpixel((x, y)) < 56:
                im.putpixel((x, y), v)


def _water(im, frame, condition):
    P = ROLE
    d = ImageDraw.Draw(im)
    wet = condition in {
        "drizzle",
        "rain",
        "heavy_rain",
        "freezing_rain",
        "storm",
        "storm_hail",
    }
    # Dark bank reflection under near trees; narrow cool ripples only in open water.
    for x, y, w in [
        (0, 26, 8),
        (34, 26, 8),
        (1, 28, 5),
        (37, 28, 5),
        (3, 30, 3),
        (39, 30, 3),
    ]:
        d.line((x, y, x + w - 1, y), fill=P["forest"])
    # Hand-placed reflection paths progress in phase, instead of independent blinking bars.
    paths = [
        (2, 27, 4),
        (7, 29, 3),
        (3, 31, 3),
        (23, 27, 4),
        (28, 28, 5),
        (26, 30, 4),
        (31, 31, 3),
        (35, 29, 3),
    ]
    colors = [
        "ripple_dim",
        "water_mid",
        "water_light",
        "water_mid",
        "ripple_dim",
        "water",
    ]
    for i, (x, y, w) in enumerate(paths):
        phase = (frame // 8 + i * 2) % 12
        ink = colors[min(5, phase)] if phase < 6 else "ripple_dim"
        offset = (0, 0, 0, 1, 1, 0, 0, 0, -1, -1, 0, 0)[(frame // 8 + i) % 12]
        d.line((x + offset, y, x + offset + w - 1, y), fill=P[ink])
        if phase == 2 and w > 3:
            d.point((x + offset + w - 1, y), fill=P["water_mid"])
    # Window reflections share source axes and have an explicit fall-off with distance.
    # They occupy connected broken glints rather than a moving full-height orange stripe.
    for source_x in (14, 18):
        for row, y in enumerate((26, 28, 30)):
            cycle = (frame // 6 + row * 3 + (0 if source_x == 14 else 5)) % 16
            shift = (0, 0, 0, 1, 1, 1, 0, 0, 0, -1, -1, 0, 0, 0, 1, 0)[cycle]
            x = source_x + shift
            bright = cycle in {1, 2, 3, 8, 9}
            role = (
                ("reflection_core" if bright else "reflection")
                if row == 0
                else ("reflection" if bright else "reflection_dim")
            )
            width = 2 if row < 2 else 3
            d.line((x - (row == 2), y, x - (row == 2) + width - 1, y), fill=P[role])
            if row == 0 and source_x == 14:
                d.point((x, y), fill=P["reflection_core"])
    if wet:
        for off, x, y in [(0, 29, 29), (24, 5, 30), (48, 25, 31)]:
            t = (frame + off) % 48
            if 6 <= t < 12:
                half = (t - 6) // 2
                d.line(
                    (x - half, y, x + half, y),
                    fill=P["water_mid" if half == 0 else "ripple_dim"],
                )


def landscape_indices(frame=0, condition="clear", wind=0):
    condition = canonical_condition(condition)
    if condition not in CONDITIONS:
        raise ValueError("Unknown weather condition")
    if condition == "unknown":
        return Image.new("L", (42, 32))
    f = frame % FRAMES
    snow = condition in {"snow", "heavy_snow"}
    im = base_land(snow).copy()
    P = ROLE
    _clouds(im, f, condition)
    _water(im, f, condition)
    d = ImageDraw.Draw(im)
    # Smoke: thinning plume, with a long rest. Roof and sky remain registered.
    if condition in {"clear", "partly_cloudy", "snow", "heavy_snow", "overcast"}:
        t = (f + 16) % 48
        if t < 24:
            k = t // 4
            x = 21 + (0, 0, 1, 1, 2, 2)[k]
            y = 14 - k
            d.point((x, y), fill=P["smoke"])
            if k in (1, 2, 3):
                d.point((x - 1, y - 1), fill=P["smoke"])
    wet = condition in {
        "drizzle",
        "rain",
        "heavy_rain",
        "freezing_rain",
        "storm",
        "storm_hail",
    }
    if wet or snow:
        count = {
            "drizzle": 4,
            "rain": 7,
            "heavy_rain": 12,
            "freezing_rain": 7,
            "snow": 8,
            "heavy_snow": 13,
        }.get(condition, 10)
        for i in range(count):
            if snow:
                y = (i * 9 + f // 3) % 32
                drift = (0, 0, 1, 1, 0, 0, -1, -1)[(f // 12 + i) % 8]
                x = (i * 13 + drift + 3) % 42
            else:
                y = (i * 11 + f * (1 if condition == "drizzle" else 2)) % 32
                x = (i * 13 + 7 - y // 7) % 42
            # Depth-aware occlusion: behind cabin/near trees, with quiet lake splashes.
            code = base_land(snow).getpixel((x, y))
            if code in {
                P[r]
                for r in [
                    "roof",
                    "roof_light",
                    "wall",
                    "wall_light",
                    "window",
                    "window_core",
                    "window_spill",
                    "pine",
                    "pine_light",
                    "bark",
                    "leaf_tip",
                ]
            }:
                continue
            if y >= 26:
                continue
            if snow or (condition == "storm_hail" and i % 3 == 0):
                d.point((x, y), fill=P["precipitation"])
            else:
                d.line(
                    (x, y, max(0, x - 1), min(25, y + 1)),
                    fill=P["precipitation"] if i % 3 == 0 else P["far_light"],
                )
        if condition == "freezing_rain":
            d.line((10, 20, 12, 18), fill=P["snow"])
            d.line((23, 21, 23, 22), fill=P["precipitation"])
    if condition == "fog":
        # Interrupted, subdued mist wisps in two depth bands, not opaque straight rules.
        dx = (0, 0, 1, 1, 0, 0, -1, -1)[f // 12]
        for x, y, w in [(0, 14, 5), (6, 15, 4), (28, 18, 5), (34, 17, 4)]:
            d.line((x + dx, y, x + dx + w, y), fill=P["haze"])
    if condition in {"storm", "storm_hail"} and 52 <= f < 54:
        d.line([(30, 7), (28, 10), (30, 10), (28, 13)], fill=P["celestial"])
    # Wind is a real overlay condition, not an invented change in forecast.
    if wind >= 20 and 20 <= f < 28:
        d.line((3 + (f - 20) // 2, 11, 5 + (f - 20) // 2, 11), fill=P["smoke"])
    return im


def clock_indices():
    im = Image.new("L", SIZE)
    # The clock retains open space and right-aligned figures. Use a low-value full sky
    # so the date never sits beside an abrupt rectangular lighting boundary.
    d = ImageDraw.Draw(im)
    for y in range(32):
        d.line((0, y, 63, y), fill=40 + min(7, y * 8 // 26))
    d.polygon(
        [
            (0, 28),
            (5, 25),
            (8, 25),
            (13, 21),
            (17, 25),
            (20, 25),
            (24, 28),
            (29, 25),
            (34, 28),
            (36, 31),
            (0, 31),
        ],
        fill=CLOCK_ROLE["ridge_shadow"],
    )
    d.line(
        [(0, 28), (5, 25), (8, 25), (13, 21), (16, 24)], fill=CLOCK_ROLE["ridge_light"]
    )
    d.line(
        [(18, 26), (20, 25), (24, 28), (29, 25), (31, 26)], fill=CLOCK_ROLE["far_light"]
    )
    d.polygon(
        [(15, 30), (19, 26), (22, 29), (21, 31), (16, 31)], fill=CLOCK_ROLE["wall"]
    )
    d.point((18, 29), fill=CLOCK_ROLE["window"])
    d.point((19, 29), fill=CLOCK_ROLE["window_core"])
    d.point((19, 30), fill=CLOCK_ROLE["reflection"])
    return im


def weather_ui(w, frame):
    f = frame % FRAMES
    condition = w.get("condition", "unknown")
    im = Image.new("RGB", SIZE)
    val = a.n(w.get("temperature"))
    table = a.FIGURES if a.width(val, a.FIGURES) <= 17 else a.SMALL
    a.text(im, (44, 2), val, a.WHITE, table, 20)
    end = 44 + a.width(val, table)
    if val != "--" and end + 3 < 64:
        d = ImageDraw.Draw(im)
        d.rectangle((end + 1, 2, end + 2, 3), outline=a.SOFT)
    forecast = f >= 48
    day = w.get("tomorrow" if forecast else "today", {})
    names = {
        "clear": "Sun",
        "clear_night": "Clear",
        "partly_cloudy": "Mix",
        "overcast": "Cloud",
        "fog": "Fog",
        "drizzle": "Driz",
        "rain": "Rain",
        "heavy_rain": "Rain",
        "freezing_rain": "Ice",
        "snow": "Snow",
        "heavy_snow": "Snow",
        "storm": "Storm",
        "storm_hail": "Hail",
        "unknown": "--",
    }
    a.text(
        im,
        (44, 14),
        "Tmr" if forecast else names.get(condition, "--"),
        a.SOFT,
        limit=20,
    )
    if forecast:
        a.hint(im, 58, 14, day.get("condition", "unknown"))
    high = "H " + a.n(day.get("high"))
    low = "L " + a.n(day.get("low"))
    if a.width(high) > 20:
        high = high.replace(" ", "")
    if a.width(low) > 20:
        low = low.replace(" ", "")
    a.text(im, (44, 21), high, a.CORAL, limit=20)
    a.text(im, (44, 27), low, a.BLUE, limit=20)
    if f < 48 and condition == "partly_cloudy":
        ImageDraw.Draw(im).rectangle((44, 14, 63, 18), fill=(0, 0, 0))
        a.text(im, (44, 14), "P.cld", a.SOFT, limit=20)
    return im


def clock_frame(now, zone, frame, light):
    ids = clock_indices()
    for y in range(32):
        for x in range(64):
            if 40 <= ids.getpixel((x, y)) < 48:
                ids.putpixel((x, y), 40 + min(15, y * 16 // 30))
    im = colorize(ids, light, "clock", "clear", frame)
    local = now.astimezone(ZoneInfo(zone))
    val = local.strftime("%I:%M").lstrip("0")
    a.text(im, (63 - a.width(val, a.FIGURES), 10), val, a.WHITE, a.FIGURES, 29)
    date = local.strftime("%a") + " " + str(local.day)
    a.text(im, (63 - a.width(date), 23), date, a.SOFT, limit=28)
    return im


def weather_frame(w, frame, light, stale_label=None):
    cond = canonical_condition(w.get("condition", "unknown"))
    ids = Image.new("L", SIZE)
    ids.paste(landscape_indices(frame, cond, w.get("wind_mph") or 0), (0, 0))
    im = colorize(ids, light, "weather", cond, frame)
    ui = weather_ui(w, frame)
    im.paste(ui.crop((43, 0, 64, 32)), (43, 0))
    if cond == "clear" and frame % FRAMES < 48:
        ImageDraw.Draw(im).rectangle((44, 14, 63, 18), fill=(0, 0, 0))
        a.text(
            im, (44, 14), "Sun" if light["elevation"] > 1 else "Clear", a.SOFT, limit=20
        )
    if cond == "unknown":
        a.text(im, (12, 11), "?", a.SOFT, a.FIGURES)
        a.text(im, (2, 23), "No data", a.SOFT)
    if stale_label is not None:
        ImageDraw.Draw(im).rectangle((0, 0, 13, 6), fill=(0, 0, 0))
        a.text(im, (1, 1), stale_label, a.AMBER)
    return im
