# SCUM COD-Zombies Deathmatch Event — Design

**Date:** 2026-06-22
**Status:** Design — approved in brainstorming, pending written-spec review
**Owner:** Chris
**Target:** A private SCUM dedicated server Chris owns/admins (him + friends). Single-player not required.

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
  from continuous noise-triggered spawns + fast refill, not a scripted clock.
- **No external script, no RCON dependency** (no SCUM-RCON / ggCON). Nothing to babysit.
- **No new Blueprint actor / mod loader.** No in-engine logic authoring.
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
- Custom Zone edits require a **server restart** to take effect.

## Architecture — three independent layers

The three layers are loosely coupled: each can be built, changed, or removed without breaking the others.

### Layer 1 — The horde (`ServerSettings.ini`, server-wide)

The bulk of the work. Tune SCUM's native Encounter/Horde AI-director so that **any gunfire summons a
relentless, tanky, sprinting swarm**, and the swarm refills continuously. Settings are server-wide, but
the arena becomes the hot spot because that is where the noise (combat) is; quiet corners of the map stay
comparatively calm, which preserves the "event happens *there*" feel without any per-zone density knob
(SCUM has none).

Recommended **starting** values (tune in playtest):

| Setting (verify exact name on live server) | Start value | Purpose |
|---|---|---|
| `MaxAllowedPuppets` | `512` | Headroom for a real crowd (range −1..1024). |
| `EncounterHordeActivationChanceMultiplier` | `10000` (max) | Hordes trigger reliably (range 0..10000). |
| `EncounterHordePuppetHordeActivationScreamOverrideChance` | `100` | **Any gunshot/scream spawns a wave** — the core "arena lights up when shooting starts" mechanic. |
| `EncounterHordeBaseCharacterAmountMultiplier` | `3.0` | Bigger waves per trigger. |
| `EncounterHordeSpawnDistanceMultiplier` | `0.5` | Spawn closer = more immediate pressure (tune for jank). |
| `EncounterCharacterRespawnTimeMultiplier` | `0.1` | Fast refill = "endless" feel. |
| `EncounterCharacterRespawnBatchSizeMultiplier` | `3.0` | Large refill batches ("respawn waves"). |
| `EncounterCharacterAggressiveSpawnChanceOverride` | `100` | Spawned puppets beeline for players. |
| `PuppetHealthMultiplier` | `2.0` | Tanky enemies (difficulty). |
| `PuppetRunningSpeedMultiplier` | `1.3` | Sprinters (>1 may look janky — tune). |
| `EnableEncounterManagerLowPlayerCountMode` | `true` | Full hordes even with just a few players online. |
| `EncounterCanRemoveLowPriorityCharacters` | `true` | Recycle the puppet budget so spawns never stall. |

Rationale notes:
- The **noise/scream trigger** is the linchpin. It is the only native mechanism that concentrates the
  horde at a chosen location (wherever the shooting is) instead of uniformly across the map.
- Several of these multipliers interact with the global puppet cap and POI caps. Expect to iterate the
  numbers against `MaxAllowedPuppets` during playtest to avoid the field either starving or stalling.

### Layer 2 — The arena (in-game Custom Zone Manager, admin GUI)

A one-time setup:
1. As admin, open the in-game map Custom Zone editor.
2. Draw **one named zone** at the chosen POI (see Open Items — POI TBD). Set center + radius to taste.
3. **Leave PvP damage ON** (free-for-all) — no special flag combo needed for PvPvE. Mark the zone visible
   on the map so players can find the event.
4. Record the zone's **center coordinates** — the admin stands near there to drop bosses (Layer 3).
5. **Restart the server** so the zone takes effect. Define it once and leave it static.

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
  config\serversettings-horde-block.ini      (the Layer-1 settings block to merge into the server's ServerSettings.ini)
  docs\arena-setup.md                          (Layer-2 step-by-step for creating the Custom Zone + restart)
  docs\boss-cheat-sheet.md                     (Layer-3 numbered boss roster + #SpawnCharacter / cleanup commands)
  README.md                                    (one-page operator guide: how to deploy, tune, run an event)
```

All artifacts are text/config. There is no `.pak` and no script in this design.

## Open items (resolve during implementation / playtest)

1. **Arena POI** — which map location hosts the event (town / airfield / a specific POI). Chris to pick;
   needed before `arena-setup.md` can name the spot and record coords.
2. **Exact `ServerSettings.ini` key names + ranges** — verify every Layer-1 key against the live server's
   generated config (names from June-2026 research may have drifted).
3. **Boss roster** — capture real `BP_` codes from `#ListCharacters` on the live server.
4. **Hosting/edit path** — how Chris edits `ServerSettings.ini` and restarts (local dedicated-server tool
   vs. a hosting panel). Affects the README deploy steps, not the design.
5. **Playtest tuning** — dial in the Layer-1 multipliers vs. `MaxAllowedPuppets`; confirm noise-trigger
   actually concentrates the horde at the arena; confirm admin-spawned bosses behave/despawn acceptably;
   confirm `#DestroyZombiesWithinRadius` clears the arena cleanly.

## Success criteria

- Players who gather at the arena and open fire are swarmed within seconds by a dense, fast, tanky horde
  that keeps refilling for as long as combat continues.
- PvP damage works inside the arena (free-for-all holds).
- An admin can, on demand, type one command to drop a random boss into the arena, and one command to
  clear it afterward.
- The whole thing survives a typical SCUM patch with at most: re-verifying a few setting names and the
  boss codes — no pak to rebuild, no script to fix.
