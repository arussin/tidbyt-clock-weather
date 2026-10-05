# Provenance

This package extracts the original clock/weather design from the local Tidbyt suite. It is not a new visual interpretation.

| Export | Source and treatment |
| --- | --- |
| `_native.py` | Clock geometry from `tidbyt_suite/art_v05.py`; native weather material animation and composition from `art_v06.py`; right-hand weather panel from `art_v03.py`. Device, robot and runtime branches removed. Inputs and resource lookup parameterized. |
| `_glyphs.py` | Original bitmap drawing instructions from `render_v01.py` and `art_v03.py`. No third-party font binary. |
| `_lighting.py`, `assets/lighting.json` | Original v0.6 material palettes, 16-band sky, celestial pixels and weather attenuation. Unused robot color handling removed. |
| `assets/landscape_materials.png`, `assets/landscape_snow.png` | Exact original 42×32 semantic material maps from `art/sources_v06`. No resampling or regenerated artwork. |
| `solar.py` | Existing suite solar-position/phase logic, with neutral explicit inputs. |
| `model.py`, `provider.py`, `cli.py`, public render wrappers | Release-preparation code for normalized inputs, separate freshness, optional bounded provider access, packaging and offline exports. |
| Examples and previews | Synthetic data at UTC, latitude/longitude zero, or explicitly forced illustration phases. No owner location, actual weather capture or device screenshot. |

The source art README explicitly states that all native source pixels are original to this project and that no third-party sprite or font file is bundled there. The source reference register separately describes concept mockups as comparisons, never source pixels for native artwork. Those references are excluded; their uncertain rights do not justify replacing the original native design.

The code and these documented original native assets are released under the [MIT license](LICENSE). Reference mockups and other third-party or uncertain assets are excluded; their licenses are not inferred or changed.

Excluded: source repository history, reference concept images, generated high-resolution mockups, robot/Codex assets, family/personal artwork, account/device identifiers, geographic configuration, live captures, credentials, private runtime controls, Home integration and deployment files.

Dependencies: Pillow 12.3.0 (MIT-CMU, as declared by the installed distribution), tzdata (Apache-2.0 Python package and IANA database terms), setuptools/wheel for builds. Dependency licenses remain their own. Open-Meteo service/data terms are separate. No dependency source, external font or external image is vendored.
