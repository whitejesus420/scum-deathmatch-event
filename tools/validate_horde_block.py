#!/usr/bin/env python3
"""Validate config/serversettings-horde-block.ini against researched SCUM 1.3.x
Encounter Manager settings (workflow wgi0fcimj). No third-party deps.

A key may appear as `scum.<Key>=v` or bare `<Key>=v`; section headers and
comment lines (`;` or `#`) are ignored. Range bounds are the single-sourced
server-settings.com values and are advisory — a value outside them is a WARN,
a missing/unparseable required key is an ERROR.
"""
import re
import sys
from pathlib import Path

# key -> (min, max, expected_value_in_block, kind)  kind in {"int","float","bool"}
REQUIRED = {
    "MaxAllowedPuppets":                                   (-1, 1024, 512,  "int"),
    "EncounterHordeActivationChanceMultiplier":            (0, 10000, 10000, "float"),
    "EncounterHordePuppetHordeActivationScreamOverrideChance": (-1, 100, 100, "float"),
    "EncounterHordeBaseCharacterAmountMultiplier":         (0, 3, 3.0,   "float"),
    "EncounterHordeGroupBaseCharacterAmountMultiplier":    (0, 3, 3.0,   "float"),
    "EncounterHordeSpawnDistanceMultiplier":               (0, 10, 0.5,  "float"),
    "EncounterCharacterRespawnTimeMultiplier":             (0, 100, 0.1, "float"),
    "EncounterCharacterRespawnBatchSizeMultiplier":        (0, 3, 3.0,   "float"),
    "EncounterCharacterAggressiveSpawnChanceOverride":     (-1, 100, 100, "float"),
    "PuppetHealthMultiplier":                              (0.01, 100, 2.0, "float"),
    "PuppetRunningSpeedMultiplier":                        (0.5, 2.0, 1.3, "float"),
    "EnableEncounterManagerLowPlayerCountMode":            (0, 1, 1,    "bool"),
    "EncounterCanRemoveLowPriorityCharacters":             (0, 1, 1,    "bool"),
}

LINE = re.compile(r"^\s*(?:scum\.)?([A-Za-z]+)\s*=\s*([-+0-9.]+)\s*$")


def parse(path):
    found = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s[0] in ";#[":
            continue
        m = LINE.match(s)
        if m:
            found[m.group(1)] = m.group(2)
    return found


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "config/serversettings-horde-block.ini"
    found = parse(path)
    errors, warns = [], []
    for key, (lo, hi, _expected, kind) in REQUIRED.items():
        if key not in found:
            errors.append(f"MISSING required key: {key}")
            continue
        try:
            val = float(found[key])
        except ValueError:
            errors.append(f"UNPARSEABLE value for {key}: {found[key]!r}")
            continue
        if kind == "bool" and val not in (0, 1):
            errors.append(f"{key} must be 0 or 1 (got {found[key]})")
        if not (lo <= val <= hi):
            warns.append(f"{key}={found[key]} outside researched range [{lo},{hi}]")
    for w in warns:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    if errors:
        print(f"\nFAIL: {len(errors)} error(s), {len(warns)} warning(s)")
        return 1
    print(f"\nOK: all {len(REQUIRED)} required keys present and in range "
          f"({len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
