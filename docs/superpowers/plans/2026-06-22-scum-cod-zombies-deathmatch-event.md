# SCUM COD-Zombies Deathmatch Event Implementation Plan

> **⚠ SUPERSEDED IN PART (2026-06-23) — location-scoping redesign.** This plan's Layer 1 cranked the
> server-wide Encounter Manager and bet on combat *noise* to keep the horde at the arena. Verified
> research showed SCUM has no config/zone way to localize a horde, so cranking the globals floods the
> whole map — which fails the hard requirement that the spam only affect specific locations. The shipped
> design now holds the globals at **vanilla** (`config/serversettings-horde-block.ini`) and spawns the
> horde **at the arena** via an RCON loop (`tools/arena_horde_loop.py`, `#SpawnZombie ... Location`).
> The validator (`tools/validate_horde_block.py`) was repurposed to FAIL if a global is cranked.
> Use the as-built artifacts and the design spec / `docs/live-verification-handoff.md` as the source of
> truth — the Task-1 config block and validator code below are kept only as historical record.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the four operator-ready artifacts (a horde-tuning `ServerSettings.ini` block, an arena Custom-Zone setup guide, a random-boss cheat-sheet, and a one-page README) that turn a private SCUM 1.3.x server into a PvPvE COD-Zombies-style deathmatch event — no script, no pak, no Blueprint.

**Architecture:** Three loosely-coupled layers, all plain text/config. Layer 1 tunes SCUM's native Encounter/Horde AI-director server-wide so combat noise summons a relentless swarm; Layer 2 is one named in-game Custom Zone (Admin Panel, real-time, no restart) that keeps PvP damage ON; Layer 3 is a printable numbered boss roster the admin rolls against and types `#SpawnCharacter` for. A separate `docs/live-verification-handoff.md` (already committed) tells a future session how to swap the research-derived names/values for the live server's actual ones.

**Tech Stack:** SCUM 1.3.x dedicated server, `ServerSettings.ini` (Encounter Manager settings group), in-game Admin Panel Custom Zone editor, admin console commands (`#SpawnCharacter`, `#ListCharacters`, `#DestroyZombiesWithinRadius`). Markdown for all docs. Python 3 (already installed globally) is used only as a lightweight validator for the config block.

---

## Source of truth for values

Every setting name, default, range, boolean encoding, command syntax, and boss code in this plan comes from the adversarially-verified research run (workflow `wgi0fcimj`, three dimensions: `settings`, `zone`, `commands`). The confidence notes below are **not** decoration — they tell the implementer which values are solid (confirmed verbatim in a real generated file) and which are single-sourced and must be re-checked against the live server via `docs/live-verification-handoff.md`.

**Confirmed verbatim** (CubeCoders AMP template + ≥1 host doc): all key *names* and *defaults* except `PuppetRunningSpeedMultiplier`; all 8 boss `BP_` codes; all command syntaxes; the Custom-Zone 3-way flag model and the 10 flag names.

**Single-sourced (server-settings.com only) → flag for live check:** every numeric min/max *range*; the existence/exact-spelling of `PuppetRunningSpeedMultiplier`; whether `MaxAllowedPuppets` is still present (absent from the official wiki).

**Boolean encoding (confirmed):** the `.ini` stores booleans as `0`/`1`, never `True`/`False`.

**Two file styles (confirmed):** host/AMP files write `scum.<Key>=<value>` under a `[World]` section; the official-wiki style writes the bare `<Key>=<value>` under `[SCUM.WorldSettings]`. They are the same settings rendered two ways. The config block ships the `scum.`-prefixed form (matches how generated dedicated-server files and host panels render it) and documents the bare-key fallback inline.

---

## File Structure

| File | Responsibility |
|---|---|
| `config/serversettings-horde-block.ini` | The Layer-1 settings to paste/merge into the server's `ServerSettings.ini`. Self-documenting: each line has the tuned value + an inline comment giving default, range, confidence, and restart note. |
| `tools/validate_horde_block.py` | A tiny stand-alone checker (no deps) that parses the block and asserts every required key is present, parses numerically, and sits within its researched range. This is the only "executable test" in the project and gives Task 1 a real fail-first rhythm. |
| `docs/arena-setup.md` | Layer-2 step-by-step: create one named Custom Zone via the in-game Admin Panel, keep PvP ON, record center coords, note the global-multiplier gotcha. Real-time, no restart. |
| `docs/boss-cheat-sheet.md` | Layer-3 numbered boss roster (1..8) with ready-to-type `#SpawnCharacter` commands, a roll method, the no-location-arg note, and the `#DestroyZombiesWithinRadius` cleanup command. |
| `README.md` | One-page operator guide: what this is, the 3 layers, deploy order, how to run an event, how to tune, the patch-survival note, and a pointer to the handoff doc. |

Existing files (do **not** modify): `docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md`, `docs/live-verification-handoff.md`.

---

## Task 1: Horde config block + validator

**Files:**
- Create: `config/serversettings-horde-block.ini`
- Create: `tools/validate_horde_block.py`

The validator is written first (fail-first), then the config block makes it pass.

- [ ] **Step 1: Write the validator (the failing test)**

Create `tools/validate_horde_block.py` exactly as below. It hard-codes the researched keys and ranges so it independently checks the block rather than trusting it.

```python
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
```

- [ ] **Step 2: Run the validator to verify it fails**

Run: `python tools/validate_horde_block.py`
Expected: `FAIL` — it errors with `MISSING required key: ...` for every key (the `.ini` does not exist yet, so `Path.read_text` raises `FileNotFoundError`; that non-zero exit is the failing state).

- [ ] **Step 3: Write the config block to make it pass**

Create `config/serversettings-horde-block.ini` exactly as below. Values are the spec's tuned starting points, clamped to the researched ranges; comments carry default/range/confidence/restart so the operator can tune without re-reading the plan.

```ini
; =====================================================================
;  SCUM COD-Zombies Deathmatch — Layer 1: the horde
;  Merge these keys into your server's ServerSettings.ini, then RESTART.
;
;  FILE STYLE: dedicated-server / host-panel files write each key with a
;  "scum." prefix under a [World] section (shown below). If YOUR server's
;  generated file instead uses bracketed section headers like
;  [SCUM.WorldSettings] with BARE keys, drop the "scum." prefix on every
;  line and place them under that section. Same settings, two renderings.
;
;  BOOLEANS are written as 0/1 (NOT True/False).
;  RESTART: treat ALL of these as restart-required (they size spawn pools
;  instantiated at world load). Exiting to main menu + re-entering also
;  re-loads the world on some builds.
;
;  RANGES below are from server-settings.com (single source) — verify the
;  real clamp on your live build via docs/live-verification-handoff.md.
; =====================================================================
[World]

; Global puppet cap. Headroom for a real crowd.  default -1 (engine default)  range -1..1024
scum.MaxAllowedPuppets=512

; How likely puppet hordes are to activate. Max it so hordes trigger reliably.  default 1.0  range 0..10000
scum.EncounterHordeActivationChanceMultiplier=10000

; *** CORE MECHANIC *** chance a horde activates from a scream/noise. 100 = any
; gunfire lights up the arena. -1 = disabled/use default, so MUST be set positive.  default -1  range -1..100
scum.EncounterHordePuppetHordeActivationScreamOverrideChance=100

; Base size of standalone hordes. 3.0 = range max = biggest waves.  default 1.0  range 0..3
scum.EncounterHordeBaseCharacterAmountMultiplier=3.0

; Base size of GROUPED hordes — a SEPARATE real key from the line above
; (both exist; do not drop either). Max it too.  default 1.0  range 0..3
scum.EncounterHordeGroupBaseCharacterAmountMultiplier=3.0

; How far from players hordes may spawn. <1 = spawn closer = more pressure.
; Tune up if close spawns look janky.  default 1.0  range 0..10
scum.EncounterHordeSpawnDistanceMultiplier=0.5

; Time between encounter-character respawns (Base * multiplier). 0.1 = fast
; refill = "endless" feel.  default 1.0  range 0..100
scum.EncounterCharacterRespawnTimeMultiplier=0.1

; How many respawn per batch. 3.0 = range max = big refill waves.  default 1.0  range 0..3
scum.EncounterCharacterRespawnBatchSizeMultiplier=3.0

; Chance spawned puppets are aggressive (beeline for players). 100 = always.
; -1 = disabled, so MUST be set positive.  default -1  range -1..100
scum.EncounterCharacterAggressiveSpawnChanceOverride=100

; Puppet HP. 2.0 = tanky.  default 1.0  range 0.01..100
scum.PuppetHealthMultiplier=2.0

; Puppet run speed. 1.3 = sprinters. >1 may look janky — tune.
; LOW CONFIDENCE: this exact key is single-sourced and was ABSENT from the
; reference generated file — confirm it exists on your build before relying on
; it (grep your ServerSettings.ini for "PuppetRunningSpeed").  default 1.0  range 0.5..2.0
scum.PuppetRunningSpeedMultiplier=1.3

; Keep full hordes even with only a few players online. 1 = on.  default 0 (off)  range 0/1
scum.EnableEncounterManagerLowPlayerCountMode=1

; Let the server recycle distant low-priority NPCs so spawns never stall. 1 = on.  default 1 (on)  range 0/1
scum.EncounterCanRemoveLowPriorityCharacters=1

; ---------------------------------------------------------------------
;  PvP GATE (not a horde key, but REQUIRED for the arena to be lethal):
;  the arena's per-zone Allow flags CANNOT re-enable PvP if the global
;  human-vs-human damage multiplier is 0. Make sure your ServerSettings.ini
;  has it ABOVE 0 (e.g. 1.0) and that ServerPlaystyle is NOT PVE.
;  Read the exact current key name off your live file — SCUM renames it
;  between patches (e.g. HumanToHumanDamageMultiplier or a melee/ranged split).
; ---------------------------------------------------------------------
```

- [ ] **Step 4: Run the validator to verify it passes**

Run: `python tools/validate_horde_block.py`
Expected: `OK: all 13 required keys present and in range (0 warning(s))`

- [ ] **Step 5: Commit**

```bash
git add config/serversettings-horde-block.ini tools/validate_horde_block.py
git commit -m "feat: Layer-1 horde ServerSettings block + range validator"
```

---

## Task 2: Arena setup guide

**Files:**
- Create: `docs/arena-setup.md`

No executable test; verification is a content checklist in Step 2.

- [ ] **Step 1: Write the arena guide**

Create `docs/arena-setup.md` exactly as below.

```markdown
# Layer 2 — The Arena (in-game Custom Zone)

One-time setup. Creates a single named zone where the event happens and where
PvP stays ON. Done entirely through the **in-game Admin Panel**, which applies
changes **in real time — no server restart needed.** (Only zones defined in
`ServerSettings.ini` require a restart; we are not using that path.)

## Prerequisites

- Your Steam64 ID is in the server's admin list (`AdminUsers.ini`, next to
  `ServerSettings.ini`). Without admin you cannot open the panel or spawn bosses.
- The global human-vs-human damage multiplier in `ServerSettings.ini` is **> 0**
  and `ServerPlaystyle` is **not** `PVE`. If PvP is off server-wide, no per-zone
  flag can switch it back on inside the arena. (See the PvP-gate note in
  `config/serversettings-horde-block.ini`.)

## Steps

1. Join the server. Press **ESC** → open the **Admin Panel** → open the
   **Custom Zone / Zone Manager** (the live map editor, not the .ini).
2. **Create a new zone.** Set its **center** by X/Y map coordinates — map
   center is `0,0`; valid range is roughly `-600000` to `619200` on each axis.
   You can place it at your current position or type coordinates.
3. **Set the radius** (the arena size). Units: `~300 ≈ 100 m (0.1 km)`; scale up
   for a bigger arena. (The 1.3.x panel may expose this as a slider/draw rather
   than a typed 300=100m value — set it to taste either way.)
4. **Name the zone** (e.g. `DEATHMATCH`). Since 1.2.1 a blank name auto-generates
   one, so always type your own so players can identify the event on the map.
5. **Set the per-zone damage flags.** Each is a 3-way toggle: **Ignore / Allow /
   Block** (default = Allow). The 10 flags are: Boxing Damage, Melee Weapon
   Damage, Throwing Damage, Projectile Damage, Explosive Damage, Damage To Bases,
   Damage To Vehicles, Puppet Damage, Player Lockpicking, World Lockpicking.
   - **For PvPvE free-for-all:** leave **Projectile, Melee Weapon, Boxing,
     Throwing** (and **Explosive** if you want grenades/rockets) on **Allow**.
     There is no single "PvP off" switch — PvP is just these player-damageable
     types, and they default to Allow, so a default zone is already PvP-on.
   - Optionally set **Damage To Bases** and **Damage To Vehicles** to **Block**
     to protect any structures/cars in the arena.
   - Leave **Puppet Damage** on **Allow** so players can kill the horde.
6. **Apply / save.** The zone appears on the map immediately — no restart.
7. **Record the zone's center coordinates** here for the boss step:

       Arena name: ____________________
       Center X / Y: ____________________
       Radius: ____________________

   The admin stands near this center to drop bosses (`#SpawnCharacter` has no
   location argument — it spawns in front of the admin). The same coordinates
   feed the optional `[location]` arg of the cleanup command.

## Notes & limits

- Older docs cap custom zones at **10 sectors** at once; one arena is fine.
- `Ignore` is only for overlapping zones (it preserves another zone's value in
  the overlap). For a single standalone arena, use **Allow/Block** only.
- As of 1.2.1, flamethrower and vehicle-dealt damage also respect zone flags.

## Must-verify on the live 1.3.x server (see live-verification-handoff.md)

- That a default/new zone with all flags on Allow actually permits player-vs-
  player projectile/melee kills (confirm the free-for-all behaves as intended).
- The exact current global PvP multiplier key name, and that `0` truly nullifies
  zone Allow flags on your build.
- Whether the panel lets you type X/Y center coords (vs only place-at-position),
  and whether the 300=100m radius scaling / 10-zone cap still hold in 1.3.x.
```

- [ ] **Step 2: Verify content (checklist review)**

Re-read `docs/arena-setup.md` and confirm all of the following are present and correct (these are the verified facts from research dimension `zone`):
- States real-time / no-restart for Admin-Panel zones, and contrasts with the .ini-restart path.
- Lists the 3-way flag model (Ignore/Allow/Block) and the exact 10 flag names.
- Explains there is no master PvP switch; PvP = leaving the player-damageable types on Allow.
- Calls out the global multiplier `> 0` / not-`PVE` prerequisite.
- Coordinate range `-600000..619200`, center `0,0`, radius `300≈100m`, 10-zone cap.
- Has the fill-in block for center coords (used by Layer 3).
- No `TBD`/`TODO`/placeholder text remains.

- [ ] **Step 3: Commit**

```bash
git add docs/arena-setup.md
git commit -m "docs: Layer-2 arena Custom Zone setup guide"
```

---

## Task 3: Boss cheat-sheet

**Files:**
- Create: `docs/boss-cheat-sheet.md`

- [ ] **Step 1: Write the cheat-sheet**

Create `docs/boss-cheat-sheet.md` exactly as below. The 8 codes are confirmed verbatim across two independent sources; the two low-confidence behaviors are flagged.

```markdown
# Layer 3 — Random Boss Cheat-Sheet

Print this or keep it on a second monitor. To drop a boss: **roll 1–8** (any
die/RNG), then type the matching command in in-game chat **while standing in the
arena**. `#SpawnCharacter` has **no location argument** — the NPC spawns in front
of you, which is exactly why you stand in the arena to fire it.

> Command shape: `#SpawnCharacter <code> <amount>`  (amount optional, default 1)

| Roll | Boss | Flavor | Command |
|---|---|---|---|
| 1 | Mech Sentry | turret | `#SpawnCharacter BP_Sentry 1` |
| 2 | Mech Sentry (3rd-person variant) | turret | `#SpawnCharacter BP_SentryWithThirdPersonView 1` |
| 3 | Recon Drone | aerial | `#SpawnCharacter BP_Drone 1` |
| 4 | Bear | brute | `#SpawnCharacter BP_Bear 1` |
| 5 | Bear (alt model) | brute | `#SpawnCharacter BP_Bear2 1` |
| 6 | Wolf | predator | `#SpawnCharacter BP_Wolf 1` |
| 7 | Armed Prisoner | gunman | `#SpawnCharacter BP_Prisoner 1` |
| 8 | Heavy Puppet | puppet | `#SpawnCharacter BP_Zombie2 1` |

**Want a swarm boss instead of one?** Bump the amount, e.g.
`#SpawnCharacter BP_Bear 3` drops three bears.

## Cleanup between events

Clear leftover puppets/NPCs around you:

    #DestroyZombiesWithinRadius <radius>

Example (radius 100, centered on you): `#DestroyZombiesWithinRadius 100`

To clear a fixed point instead of your position, add the optional location in
SCUM's exact brace format (X/Y/Z world position | P/Y/R rotation):

    #DestroyZombiesWithinRadius 100 {X=-152157.266 Y=287169.562 Z=69696.133|P=341.697937 Y=189.414261 R=0.000000}

(Yes, the block legitimately contains two keys both spelled `Y=` — world-Y and
Yaw. That is SCUM's verbatim format, not a typo.) Plug in your arena center from
`arena-setup.md` for the X/Y/Z.

## Useful companion commands

- `#ListCharacters [search]` — list every valid character code (optionally
  filtered by text). **This is the authoritative source for the codes above** —
  codes drift between patches, so re-run it after a SCUM update.
- `#SpawnRandomZombie` — drops one random puppet in front of you (no args). A
  zero-effort "surprise" button if you don't want to roll.

## Must-verify on the live 1.3.x server (see live-verification-handoff.md)

- Run `#ListCharacters` and confirm the exact spelling/capitalization of all 8
  codes on your build.
- **Roll 7 (`BP_Prisoner`)** is a player-character blueprint — confirm it spawns
  an actively HOSTILE armed NPC and not a passive/T-pose dummy. If it's passive,
  drop it from the roster or replace it.
- **Roll 8 (`BP_Zombie2`)** — confirm it spawns a hostile puppet (not a passive
  variant).
- `BP_Bear2` vs `BP_Bear` — confirm it's a real distinct model, not a dead
  duplicate. `BP_SentryWithThirdPersonView` — confirm the long code still valid.
```

- [ ] **Step 2: Verify content (checklist review)**

Re-read `docs/boss-cheat-sheet.md` and confirm:
- All 8 `BP_` codes present and spelled exactly: `BP_Sentry`, `BP_SentryWithThirdPersonView`, `BP_Drone`, `BP_Bear`, `BP_Bear2`, `BP_Wolf`, `BP_Prisoner`, `BP_Zombie2`.
- States `#SpawnCharacter` takes no location arg / spawns in front of admin.
- Cleanup command `#DestroyZombiesWithinRadius <radius> [location]` with the verbatim brace coord format and the "two `Y=` keys is intentional" note.
- Points at `#ListCharacters` as authoritative and flags `BP_Prisoner`/`BP_Zombie2` for hostility verification.
- No placeholder text remains.

- [ ] **Step 3: Commit**

```bash
git add docs/boss-cheat-sheet.md
git commit -m "docs: Layer-3 random-boss cheat-sheet + cleanup commands"
```

---

## Task 4: README operator guide

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

Create `README.md` exactly as below.

```markdown
# SCUM COD-Zombies Deathmatch Event

A Call-of-Duty-Zombies-style event for a **private SCUM 1.3.x server**: a PvPvE
free-for-all in a fixed arena where an endless, escalating horde of puppets
pours in while players also fight each other — last one standing. An admin can
drop a random boss by hand for a difficulty spike.

**No script, no mod pak, no Blueprint.** It's three layers of plain config +
admin commands, so a SCUM patch costs you at most a quick re-verify of a few
setting names and the boss codes — nothing to rebuild.

> Private server only. Never use on official servers; never bypass anti-cheat.

## The three layers

1. **The horde** — `config/serversettings-horde-block.ini`. Tunes SCUM's native
   Encounter/Horde AI-director server-wide so combat noise summons a relentless,
   tanky, sprinting swarm that refills continuously. Because the trigger is
   *noise*, the arena (where the shooting is) becomes the hot spot while quiet
   corners stay calm — no per-zone density knob needed (SCUM has none).
2. **The arena** — `docs/arena-setup.md`. One named in-game Custom Zone with PvP
   damage left ON. Created live via the Admin Panel (no restart).
3. **Random bosses** — `docs/boss-cheat-sheet.md`. A numbered roster you roll
   against and spawn with one `#SpawnCharacter` command.

## Deploy order

1. **Back up** your server's `ServerSettings.ini` (copy to `ServerSettings.ini.bak`).
2. **Merge** the keys from `config/serversettings-horde-block.ini` into it. Match
   the file style your server already uses (`scum.Key` under `[World]`, or bare
   `Key` under `[SCUM.WorldSettings]` — see the comments in the block). Confirm
   the global human-vs-human damage multiplier is **> 0** so PvP works.
3. *(optional but recommended)* Validate the block first:
   `python tools/validate_horde_block.py`
4. **Restart** the server (the Encounter/puppet settings need it).
5. **Create the arena** following `docs/arena-setup.md` (in-game, no restart).
   Record the center coordinates in that file.
6. **Print/open** `docs/boss-cheat-sheet.md`.

## Running an event

1. Tell players where/when. They gather in the arena.
2. Combat noise starts the horde automatically — the more they shoot, the more
   comes. PvP is live, so it's also a free-for-all.
3. When you want a spike, roll 1–8 and type the boss command from the cheat-sheet
   while standing in the arena.
4. Between rounds, clear stragglers with `#DestroyZombiesWithinRadius 100`.

## Tuning

All knobs are in `config/serversettings-horde-block.ini` with inline
default/range/confidence notes. Likely first dials in playtest:
- Field feels empty → raise `MaxAllowedPuppets`, raise
  `EncounterCharacterRespawnBatchSizeMultiplier`, lower
  `EncounterCharacterRespawnTimeMultiplier`.
- Spawns look janky / pop in too close → raise
  `EncounterHordeSpawnDistanceMultiplier`, lower `PuppetRunningSpeedMultiplier`.
- Too easy/hard → `PuppetHealthMultiplier`.
Re-validate after edits with `python tools/validate_horde_block.py`.

## Surviving a SCUM patch / finalizing for YOUR server

The setting names, ranges, and boss codes here are from June-2026 research and
are mostly confirmed, but a few (the numeric ranges, `PuppetRunningSpeedMultiplier`,
`MaxAllowedPuppets` presence, the live PvP-multiplier key name) should be checked
against your actual running server. The full runbook for doing that — and what to
edit afterward — is in **`docs/live-verification-handoff.md`**. After a major
patch, re-run that checklist.

## Files

- `config/serversettings-horde-block.ini` — Layer 1 horde settings (+ inline docs)
- `tools/validate_horde_block.py` — range validator for the block
- `docs/arena-setup.md` — Layer 2 arena Custom Zone guide
- `docs/boss-cheat-sheet.md` — Layer 3 boss roster + commands
- `docs/live-verification-handoff.md` — how to reconcile values with your live server
- `docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md` — the design spec
```

- [ ] **Step 2: Verify content (checklist review)**

Re-read `README.md` and confirm: it names all three layers and their files; gives a deploy order that includes the backup, the file-style match, the global-multiplier check, the validator, and the restart; explains running an event; has a tuning section; points to the handoff doc for finalization; the private-server-only warning is present; no placeholder text.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: operator README for the deathmatch event"
```

---

## Task 5: Cross-artifact consistency pass

**Files:**
- Modify (only if the check finds drift): any of the four artifacts above.

- [ ] **Step 1: Run the validator one final time**

Run: `python tools/validate_horde_block.py`
Expected: `OK: all 13 required keys present and in range (0 warning(s))`

- [ ] **Step 2: Consistency check across all artifacts**

Confirm these names/values are identical wherever they appear (a mismatch is a bug to fix inline):
- The 13 horde key names match between `config/serversettings-horde-block.ini`, `tools/validate_horde_block.py`, and any mention in `README.md`.
- The 8 boss codes match between `docs/boss-cheat-sheet.md` and the verification list in `docs/live-verification-handoff.md`.
- `#SpawnCharacter <code> <amount>`, `#ListCharacters`, and `#DestroyZombiesWithinRadius <radius> [location]` are written the same way in `boss-cheat-sheet.md`, `arena-setup.md`, `README.md`, and `live-verification-handoff.md`.
- The arena coordinate facts (`-600000..619200`, center `0,0`, `300≈100m`) match between `arena-setup.md` and any README mention.
- The "no restart for Admin-Panel zones" statement is consistent (README + arena-setup), and nothing reintroduces the spec's old blanket "Custom Zone needs restart" claim for the Admin-Panel path.

- [ ] **Step 3: Placeholder sweep**

Search the repo for leftover placeholders and fix any hit:
Run: `git grep -nE "TBD|TODO|FIXME|XXX|<fill|placeholder" -- README.md docs/ config/`
Expected: no matches except intentional fill-in blanks in `arena-setup.md` (the `____` coordinate-recording lines, which are deliberate operator inputs — leave those).

- [ ] **Step 4: Commit (only if Step 2/3 changed anything)**

```bash
git add -A
git commit -m "chore: cross-artifact consistency pass for deathmatch event"
```

If nothing changed, skip the commit and note the consistency pass was clean.

---

## Self-Review (completed during plan authoring)

**Spec coverage** — every spec section maps to a task:
- Layer 1 horde (spec §Architecture/Layer 1) → Task 1. All 12 spec settings included; **added** the separate `EncounterHordeGroupBaseCharacterAmountMultiplier` (research proved Group + non-Group are both real) → 13 keys.
- Layer 2 arena (spec §Layer 2) → Task 2. **Corrected** the spec's "restart required" to "Admin-Panel zones are real-time; only .ini zones restart," per verified research.
- Layer 3 boss cheat-sheet (spec §Layer 3) → Task 3, with the real 8-code roster.
- Deliverables/file layout (spec §Deliverables) → all four artifacts + the validator created across Tasks 1–4.
- Open items 2 & 3 (verify keys / boss codes) → carried into each doc's "must-verify" section and the committed `docs/live-verification-handoff.md`. Open items 1 (arena POI), 4 (hosting/edit path), 5 (playtest tuning) are operator decisions, surfaced in `arena-setup.md` (POI fill-in), `README.md` (deploy/tuning), not code tasks — correct to defer.
- Success criteria (spec §Success criteria) → README "Running an event" + tuning describe exactly these outcomes.

**Placeholder scan:** No `TBD`/`TODO`/"add appropriate X" in any task. The only blanks are the intentional operator fill-in lines in `arena-setup.md`, explicitly excluded in Task 5 Step 3.

**Type/name consistency:** Key names are defined once in Task 1 (both the validator dict and the `.ini`) and reused verbatim; boss codes defined once in Task 3; command syntaxes are identical across docs. Task 5 exists specifically to enforce this. The validator expects 13 keys and the `.ini` ships 13 — counts match.

**Boolean encoding:** validator enforces `0`/`1`; the `.ini` ships `1`/`1` for the two booleans — consistent with verified on-disk format.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-22-scum-cod-zombies-deathmatch-event.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
