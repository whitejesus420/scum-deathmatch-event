# SCUM COD-Zombies Deathmatch Event — Design

**Date:** 2026-06-22 (revised 2026-06-23: location-scoping redesign)
**Status:** Design — revised so the horde is arena-only (see Revision note)
**Owner:** Chris
**Target:** A private SCUM dedicated server Chris owns/admins (him + friends). Single-player not required.

## Revision note (2026-06-23) — horde is now arena-only

The original design cranked SCUM's **server-wide** Encounter Manager and relied
on combat *noise* to concentrate the horde where the shooting was. Research
(adversarially verified) confirmed SCUM has **no config or zone setting that
scopes a horde to a location** — cranking the globals floods the entire map, and
the noise-localization claim was false as a scoping mechanism. That violates the
hard requirement that the spam only affect specific locations.

So Layer 1 was split:
- **Layer 1 (globals)** now holds the Encounter Manager at **vanilla** — a guard
  that keeps the rest of the map normal, not a crank.
- **Layer 1b (`tools/arena_horde_loop.py`)** spawns the horde **at the arena
  coordinates** over RCON via `#SpawnZombie <id> <count> Location <coords>` —
  the only native lever that targets a location.

Per Chris's decisions: the horde is triggered by an **automatic RCON loop** (not
manual admin spawning), and the tanky/sprinting difficulty is **arena-only** —
the global `PuppetHealthMultiplier`/`PuppetRunningSpeedMultiplier` revert to 1.0;
tougher enemies come from choosing tougher puppet type IDs in the loop. The rest
of this spec is updated to match; sections below marked accordingly.

## Goal

Add a Call-of-Duty-Zombies-style event to a private SCUM server: a **PvPvE free-for-all** in a fixed
arena where an **endless, escalating horde** of puppets pours in while players also fight each other —
last one standing. An admin can drop a **random boss** by hand when they want a spike.

This is the **low-effort, config-first** path chosen during brainstorming. It deliberately does NOT
attempt true numbered "Round N" logic — SCUM has no native round/wave engine, and that would require an
external RCON round-manager script or a custom UE4.27 Blueprint actor, both explicitly rejected in favor
of maintainability.

## Non-goals (YAGNI)

- **No numbered rounds / round counter / between-round breaks.** The "endless escalating horde" feel comes
  from the arena loop's continuous re-spawns, not a scripted clock.
- **No new Blueprint actor / mod loader.** No in-engine logic authoring.
- ~~**No external script, no RCON dependency.**~~ **(Revised 2026-06-23:** location-scoping *requires*
  RCON — there is no config/zone alternative. The design now uses the SCUM-RCON Nexus mod + a small
  stdlib-only Python loop, `tools/arena_horde_loop.py`, the minimum needed to pin the horde to the arena.)
- **No automated round-clear detection.** Not needed without rounds.
- **No data-pak for enemy variety.** Boss variety is handled by the manual boss cheat-sheet instead, so
  there is no `.pak` to re-port on patches.
- **No points/economy/perks/mystery-box.** Out of scope for v1.

## Constraints / ground rules

- Private server only, BattlEye off for any client mods — never official servers. (No client pak is
  shipped in this design, so the only BattlEye concern is whatever else is already in `~mods`.)
- All exact `ServerSettings.ini` key names and value ranges **must be verified against the live SCUM
  1.3.x server's generated `ServerSettings.ini`** before committing values — SCUM renames/retunes settings
  between patches. The names below are from June 2026 research and are a starting point, not gospel.
- Custom Zone edits made in the **in-game Admin Panel apply in real time (no restart)**. Only zones
  defined in a config file need a restart, and this design does not use that path. (The `ServerSettings.ini`
  global baseline in Layer 1 *is* read at world load, so changing it does need a restart.)

## Architecture — three independent layers

The three layers are loosely coupled: each can be built, changed, or removed without breaking the others.

### Layer 1 — The global baseline (`ServerSettings.ini`, server-wide)

**Held at vanilla on purpose.** This layer is *not* a crank — it is the guard
that keeps the rest of the map normal while the arena loop (Layer 1b) does the
spawning. Because SCUM's Encounter Manager is entirely server-wide, raising any
of these multipliers floods the whole map, not the arena. So they all sit at
their engine defaults; the only deliberate non-default is the puppet **cap**,
which gives the arena headroom but spawns nothing itself.

| Setting (verify exact name on live server) | Value | Why |
|---|---|---|
| `MaxAllowedPuppets` | `512` | Ceiling/headroom for the arena crowd — does NOT spawn puppets (range −1..1024). |
| `EncounterHordeActivationChanceMultiplier` | `1.0` | Vanilla. |
| `EncounterHordePuppetHordeActivationScreamOverrideChance` | `-1` | Disabled — no map-wide noise→horde trigger. |
| `EncounterHordeBaseCharacterAmountMultiplier` | `1.0` | Vanilla. |
| `EncounterHordeGroupBaseCharacterAmountMultiplier` | `1.0` | Vanilla (separate real key from the line above). |
| `EncounterHordeSpawnDistanceMultiplier` | `1.0` | Vanilla. |
| `EncounterCharacterRespawnTimeMultiplier` | `1.0` | Vanilla. |
| `EncounterCharacterRespawnBatchSizeMultiplier` | `1.0` | Vanilla. |
| `EncounterCharacterAggressiveSpawnChanceOverride` | `-1` | Disabled — no map-wide hostile-on-sight. |
| `PuppetHealthMultiplier` | `1.0` | Vanilla — difficulty is arena-only (via puppet type). |
| `PuppetRunningSpeedMultiplier` | `1.0` | Vanilla — same reason. |
| `EnableEncounterManagerLowPlayerCountMode` | `0` (off) | Off — would otherwise keep the whole map dense at low pop. |
| `EncounterCanRemoveLowPriorityCharacters` | `1` (on) | Engine default; lets the arena loop reclaim its puppet budget. |

`tools/validate_horde_block.py` enforces this baseline: a scope-critical global
cranked off vanilla is a hard ERROR.

Rationale notes:
- There is **no native config/zone way to localize a horde** (adversarially
  verified). Custom Zones gate damage/base-building/lockpicking/vehicles only —
  no spawn-density flag; LTZ/MTZ/HTZ zone *types* are tunable only by global
  multiplier; the per-location `Zones.json` override architecture is for item
  loot, not spawns. The earlier "combat noise concentrates the horde at the
  arena" idea was wrong — the trigger is real but global, so it heats the whole
  map. The only native location-scoped lever is the admin/RCON `#SpawnZombie ...
  Location` command, which Layer 1b uses.

### Layer 1b — The arena horde loop (`tools/arena_horde_loop.py`, RCON)

What actually makes the horde, and the only part that targets a location. A
dependency-free Python Valve-Source-RCON client (works with the SCUM-RCON Nexus
mod) that, on an interval, fires:

```
#SpawnZombie <id> <count> Location <arena-brace>
```

to drop puppets **at the arena and nowhere else**, and on stop/`--reset` runs
`#DestroyZombiesWithinRadius <r> <arena-brace>` to clear them. Config (RCON
host/port/password, the arena `#Location` brace, puppet type IDs, wave count,
interval) lives in a block at the top of the file.

- **Trigger:** automatic interval loop (Chris's choice over manual admin spawning).
- **Difficulty is arena-only:** with the global HP/speed multipliers back at 1.0,
  tanky/fast enemies come from choosing tougher puppet **type IDs** in
  `PUPPET_IDS` — that buffs only what spawns in the arena.
- **Volume** comes from `<count>` and the interval, bounded by the global
  `MaxAllowedPuppets` cap (heavy arena spawning draws from the shared pool).

### Layer 2 — The arena (in-game Custom Zone Manager, admin GUI)

A one-time setup:
1. As admin, open the in-game map Custom Zone editor.
2. Draw **one named zone** at the chosen POI (see Open Items — POI TBD). Set center + radius to taste.
3. **Leave PvP damage ON** (free-for-all) — no special flag combo needed for PvPvE. Mark the zone visible
   on the map so players can find the event.
4. Record the zone's **center coordinates as the full `#Location` brace** (stand in the arena, run
   `#Location`). This brace feeds `ARENA_LOCATION` in the Layer-1b loop and the admin stands near it to
   drop bosses (Layer 3).
5. **Apply/save — no restart.** Admin-Panel zones take effect immediately. Define it once and leave it static.

### Layer 3 — Random boss button (printable cheat-sheet, manual)

No code. A **numbered boss roster** the admin keeps handy; to drop a boss they pick a number at random
(die/RNG of choice) and type the matching command in in-game chat while standing in the arena.

- Boss spawn command: `#SpawnCharacter <NPC_code> <Amount>`. **Important:** this command has **no
  location argument** and spawns in front of the invoking admin — that is why the admin stands in the
  arena to fire it. (For coordinate-targeted spawns one would need `#SpawnZombie`/`#SpawnAnimal`, but
  bosses like the mech/drone are `#SpawnCharacter`-only.)
- The exact roster of valid `BP_` NPC codes (e.g. `BP_Sentry` mech, `BP_Drone`, `BP_Bear`, armed NPCs,
  etc.) **must be confirmed in-game via `#ListCharacters`** on the live 1.3.x server before finalizing the
  sheet — codes drift between patches.
- Reset / cleanup between events: `#DestroyZombiesWithinRadius <radius> [location]` to clear leftover
  puppets in the arena.

The cheat-sheet is delivered as a markdown file (`boss-cheat-sheet.md`) numbered 1..N, one boss per line,
with the ready-to-type command and a one-word difficulty/flavor tag.

## Deliverables / file layout

```
C:\Users\chris\scum-deathmatch-event\
  docs\superpowers\specs\2026-06-22-scum-cod-zombies-deathmatch-event-design.md   (this file)
  config\serversettings-horde-block.ini      (Layer-1 vanilla global baseline to merge into ServerSettings.ini)
  tools\validate_horde_block.py              (guard that the Layer-1 globals stay vanilla)
  tools\arena_horde_loop.py                  (Layer-1b RCON loop that spawns the horde AT the arena)
  docs\arena-setup.md                          (Layer-2 step-by-step for creating the Custom Zone, no restart)
  docs\boss-cheat-sheet.md                     (Layer-3 numbered boss roster + #SpawnCharacter / cleanup commands)
  README.md                                    (one-page operator guide: how to deploy, tune, run an event)
```

All artifacts are text/config/stdlib-Python. There is no `.pak` and no Blueprint in this design.

## Open items (resolve during implementation / playtest)

1. **Arena POI** — which map location hosts the event (town / airfield / a specific POI). Chris to pick;
   needed before `arena-setup.md` can name the spot and record coords.
2. **Exact `ServerSettings.ini` key names** — verify every Layer-1 key against the live server's generated
   config (names from June-2026 research may have drifted). Values stay at vanilla regardless.
3. **Boss / puppet codes** — capture real boss `BP_` codes from `#ListCharacters` and puppet type IDs from
   `#ListZombies` on the live server (the latter feed `PUPPET_IDS` in the loop).
4. **RCON + `#SpawnZombie` syntax** — confirm the SCUM-RCON port/password, that `#SpawnZombie <id> <count>
   Location <brace>` is the live argument order, and that the brace from `#Location` is accepted verbatim.
5. **Hosting/edit path** — how Chris edits `ServerSettings.ini` and restarts. Affects the README deploy
   steps, not the design.
6. **Playtest tuning** — dial in `COUNT_PER_WAVE` / `INTERVAL_SECONDS` vs. `MaxAllowedPuppets`; pick puppet
   type IDs for the right toughness; confirm the loop's spawns land at the arena and NOWHERE else; confirm
   `#DestroyZombiesWithinRadius <r> <brace>` clears the arena cleanly.

## Success criteria

- Players who gather at the arena are swarmed by a dense, fast, tanky horde that keeps refilling while the
  loop runs — and the **rest of the map stays at normal puppet density** (the spam is location-scoped).
- PvP damage works inside the arena (free-for-all holds).
- An admin can, on demand, type one command to drop a random boss into the arena, and the loop/`--reset`
  clears the arena afterward.
- The whole thing survives a typical SCUM patch with at most: re-verifying a few setting names, the
  `#SpawnZombie` syntax, and the boss/puppet codes — no pak to rebuild.
