# Validation — version 0.1.0, 2026-10-05

Windows x64, CPython 3.14.7, Pillow 12.3.0, tzdata 2026.2. This is isolated offline evidence, not live provider or physical-device acceptance.

## Original-design parity

An independent harness imported the current canonical v0.6 renderer read-only and compared its native RGB bytes with a wheel installed in an empty environment outside the candidate checkout. Both received identical synthetic data, timezone and explicit solar inputs. Network and process side effects were blocked. **13,875 checks passed; zero failures.**

- 6,240 weather comparisons: all 13 original condition families × five lighting phases × 96 frames.
- 480 clock frames across all five phases; 864 clock width/time cases and 280 calendar/timezone/DST cases.
- 26 complete weather loops with 96-frame source comparison, decoded WebP pixel comparison and preserved 12,000 ms duration.
- Automatic solar lighting, wind and numeric edges, today/tomorrow aliases, independent freshness and forecast civil-date selection.
- Exact matching aggregate source/candidate RGB hash: `01eb02ac6e9fbfc66df2ed260a5c3fcf664614eb0bba6d08f35475b85cd94960`.

Fresh-input appearance compares directly to original inputs. Freshness cases first remove expired/future current or forecast values independently, then compare the same effective data against the canonical renderer. This deliberately preserves conservative package behavior; it is not a claim of matching the live suite's raw last-known stale values.

The comparison board uses nearest-neighbor enlargement of native pixels, no glow or visual approximation. The original native material maps and lighting JSON are copied without pixel/color changes. Clock labels, glyphs, right-hand weather panel, material geometry and animation instructions are preserved.

## Package behavior

The original 25 installed-wheel tests pass: separate current/forecast timestamps, future/DST/TTL boundaries, all 1,440 clock minutes, extreme/missing values, package-local resources, no-I/O imports, socket-blocked rendering, exact lossless WebP pixels and timing, malformed provider input/response bounds, local forecast dates, CLI no-overwrite and missing/oversized captures. A portable regression test adds 92 fixed canonical RGB-hash cases without importing the original suite. The complete installed-wheel suite contains 26 tests, including these 92 subcases.

The original placeholder renderer, glyphs, icons and palette file are removed. Build/dependency files live outside source. Public imports do not load the private suite, robot, runtime, config, transports or design tools.

## Limits

Finite synthetic input matrix; no claim of every possible date/value. No real weather requests, Tidbyt pushes, startup/service changes, hardware inspection or website changes. Linux/macOS and other supported Python versions remain untested. A static clock phase can encode as a still image when every native frame is identical; animated phases preserve elapsed timing.

The old preparation tests validated the placeholder renderer's internal behavior and did not prove visual fidelity. Those results and the earlier contact sheet are superseded by this faithful candidate and its source comparison.

The public repository uses a fresh history and MIT licensing for the documented original code/artwork. The source-parity verification was completed before publication; public source availability does not imply live provider or hardware acceptance. No website or device deployment was performed.
