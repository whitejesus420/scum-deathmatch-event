#!/usr/bin/env python3
"""Validate config/serversettings-horde-block.ini for the SCUM COD-Zombies
deathmatch event. No third-party deps.

The design spawns the horde AT THE ARENA via an RCON loop
(tools/arena_horde_loop.py). The server-wide Encounter Manager is therefore
held at VANILLA so the rest of the map stays normal. This validator is the
guard for that: it FAILS if a scoping-critical global has been cranked away
from its vanilla baseline (which would leak the horde across the whole map and
break the "arena-only" guarantee).

Severity:
  - missing / unparseable required key      -> ERROR (exit 1)
  - a SCOPE-LOCKED global != its baseline    -> ERROR (exit 1)  (re-globalizes the horde)
  - a CEILING key out of its sane range      -> WARN
  - a DEFAULT/housekeeping key != baseline   -> WARN

A key may appear as `scum.<Key>=v` or bare `<Key>=v`; section headers, blank
lines, comment lines (`;`/`#`) and trailing inline comments are ignored.
"""
import re
import sys
from pathlib import Path

# Enforcement kinds.
LOCKED = "locked"    # scoping-critical: must equal baseline or the horde leaks map-wide -> ERROR
CEILING = "ceiling"  # deliberate cap, any sane value is fine -> range WARN only
DEFAULT = "default"  # engine default shipped for clarity -> deviation WARN

# key -> (expected_baseline_value, kind, range_lo, range_hi)
BASELINE = {
    # --- scoping-critical: keep VANILLA so the open map stays normal ---
    "EncounterHordeActivationChanceMultiplier":                (1.0, LOCKED, 0, 10000),
    "EncounterHordePuppetHordeActivationScreamOverrideChance": (-1,  LOCKED, -1, 100),
    "EncounterHordeBaseCharacterAmountMultiplier":             (1.0, LOCKED, 0, 3),
    "EncounterHordeGroupBaseCharacterAmountMultiplier":        (1.0, LOCKED, 0, 3),
    "EncounterHordeSpawnDistanceMultiplier":                   (1.0, LOCKED, 0, 10),
    "EncounterCharacterRespawnTimeMultiplier":                 (1.0, LOCKED, 0, 100),
    "EncounterCharacterRespawnBatchSizeMultiplier":            (1.0, LOCKED, 0, 3),
    "EncounterCharacterAggressiveSpawnChanceOverride":         (-1,  LOCKED, -1, 100),
    "PuppetHealthMultiplier":                                  (1.0, LOCKED, 0.01, 100),
    "PuppetRunningSpeedMultiplier":                            (1.0, LOCKED, 0.5, 2.0),
    "EnableEncounterManagerLowPlayerCountMode":               (0,   LOCKED, 0, 1),
    # --- deliberate non-default / housekeeping: advisory only ---
    "MaxAllowedPuppets":                                       (512, CEILING, -1, 4096),
    "EncounterCanRemoveLowPriorityCharacters":                (1,   DEFAULT, 0, 1),
}

LINE = re.compile(r"^\s*(?:scum\.)?([A-Za-z0-9_]+)\s*=\s*([-+0-9.]+)\s*(?:[;#].*)?$")


def parse(path):
    found, dupes = {}, []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s[0] in ";#[":
            continue
        m = LINE.match(s)
        if m:
            key = m.group(1)
            if key in found:
                dupes.append(key)
            found[key] = m.group(2)
    return found, dupes


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "config/serversettings-horde-block.ini"
    found, dupes = parse(path)
    errors, warns = [], []

    for key in dupes:
        warns.append(f"duplicate key {key} (last value wins)")

    for key, (expected, kind, lo, hi) in BASELINE.items():
        if key not in found:
            errors.append(f"MISSING required key: {key}")
            continue
        try:
            val = float(found[key])
        except ValueError:
            errors.append(f"UNPARSEABLE value for {key}: {found[key]!r}")
            continue

        matches = abs(val - float(expected)) < 1e-9
        in_range = lo <= val <= hi

        if kind == LOCKED:
            if not matches:
                errors.append(
                    f"{key}={found[key]} is CRANKED off its vanilla baseline "
                    f"({expected}). This re-globalizes the horde across the whole "
                    f"map and breaks the arena-only design. Spawn more at the arena "
                    f"via tools/arena_horde_loop.py instead."
                )
            elif not in_range:
                warns.append(f"{key}={found[key]} outside researched range [{lo},{hi}]")
        elif kind == CEILING:
            if not in_range:
                warns.append(f"{key}={found[key]} outside sane range [{lo},{hi}]")
        else:  # DEFAULT
            if not matches:
                warns.append(f"{key}={found[key]} != engine default {expected}")

    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\nFAIL: {len(errors)} error(s), {len(warns)} warning(s)")
        return 1
    print(f"\nOK: all {len(BASELINE)} required keys present, globals held at "
          f"vanilla baseline ({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
