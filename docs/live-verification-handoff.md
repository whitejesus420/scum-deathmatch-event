# Live-Server Verification Handoff (for another Claude)

**Read this if you are an AI agent (or a future session) asked to finalize the SCUM COD-Zombies
deathmatch horde event.** The design is fixed; your job is to replace the "verify on live server"
unknowns with real values pulled from Chris's running SCUM 1.3.x dedicated server, then update the project
artifacts and report what you changed.

**The architecture is LOCKED — and note the 2026-06-23 location-scoping redesign + the 2026-06-23
event-trigger redesign:** the horde is **arena-only** and **event-driven**. `tools/arena_horde_loop.py`
TAILS the server's kill log; when a native in-game-event kill appears (`"IsInGameEvent": true`) it spawns
puppets AT that kill's location via `#SpawnZombie <id> <count> Location <brace>`, keeps waves coming while
the event is live, and clears them on a quiet timeout. The server-wide Encounter Manager is held at
**vanilla** so the rest of the map stays normal. Do **not** "fix" an empty-feeling field by cranking the
global multipliers in `config/serversettings-horde-block.ini` — that re-globalizes the horde and breaks the
whole point (and `tools/validate_horde_block.py` will fail). To make the horde bigger, raise
`COUNT_PER_WAVE` / lower `INTERVAL_SECONDS` in the loop instead. Full rationale:
`docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md`.

The layers: (1) vanilla global baseline + PvP gate, (1b) the event-driven kill-log horde watcher, (2) one
Custom Zone arena (fallback location), (3) printable random-boss cheat-sheet. PvPvE, no pak, no Blueprint.

**Why the kill log (don't redesign this):** SCUM RCON is request/response — no async push, no event-query
command — and no log line is written when an event starts. Researched + adversarially verified across 5
server-tool codebases (2026-06-23): the per-kill `IsInGameEvent` flag is the ONLY native "an event is
happening" signal. The watcher is therefore REACTIVE (fires after the first event kill, not at start) and
cannot tell which event type is running. These are accepted tradeoffs, not bugs to fix.

## Project location & artifacts you will edit

Project root: `C:\Users\chris\scum-deathmatch-event\`

| File | What you update |
|---|---|
| `config/serversettings-horde-block.ini` | Fix any key NAME that differs on the live server. Keep every value at the VANILLA baseline (don't re-crank); only `MaxAllowedPuppets` is a deliberate non-default. |
| `tools/arena_horde_loop.py` | Confirm `LOG_DIR` + the live kill-log format (`IsInGameEvent` + `ServerLocation`), the `#SpawnZombie` argument order, the RCON port/password, and fill the puppet IDs — sorted into `MILITARY_PUPPET_IDS` / `OTHER_PUPPET_IDS` (+ `ARENA_LOCATION` fallback) — from live captures. |
| `docs/boss-cheat-sheet.md` | Replace the boss roster with real `BP_` codes from `#ListCharacters`. |
| `docs/arena-setup.md` | Correct the Custom Zone steps / PvP-flag wording if the live behavior differs. |
| `docs/live-verification-results.md` | **Create this** — log every confirmed value, its source (file path / in-game output), and confidence. |

## Ground rules (do not violate)

- This is Chris's **own private server**. Never touch official servers; never advise anti-cheat bypass.
- **Back up `ServerSettings.ini`** (copy to `*.bak`) before changing it.
- **Custom Zone changes:** zones created in the in-game **Admin Panel / Custom Zone Manager apply in real
  time (no restart)** — only zones defined in a config file require a restart. The Layer-1 baseline in
  `ServerSettings.ini` IS read at world load, so changing it needs a restart. Never assume a setting
  hot-reloads — note which ones do.
- Confirm Chris's account is in the server's admin list before expecting in-game `#` commands to work.
- If you cannot reach the live server, STOP and tell Chris exactly which of Steps A/B/C/D you could not do —
  do not invent values.

---

## Step A — Confirm the `ServerSettings.ini` key NAMES (values stay vanilla)

1. **Find the file.** For a Windows dedicated server it is typically:
   `...\SCUM\Saved\Config\WindowsServer\ServerSettings.ini` (under the server install dir, NOT the game
   client). If hosted (g-portal/nitrado/etc.), it is in the host panel's config-file editor / FTP.
   Locate it with Glob, e.g. pattern `**/Saved/Config/**/ServerSettings.ini`. If you find more than one,
   prefer the one under `WindowsServer`. The admin list lives next to it as `AdminUsers.ini`.
2. **Confirm the exact key string** (section header / `scum.` prefix / casing) for each of these. We are
   NOT cranking them — we are confirming the names match so the vanilla baseline merges cleanly:
   - `MaxAllowedPuppets` (the one deliberate non-default: a ceiling = 512)
   - `EncounterHordeActivationChanceMultiplier`
   - `EncounterHordePuppetHordeActivationScreamOverrideChance`
   - `EncounterHordeBaseCharacterAmountMultiplier`
   - `EncounterHordeGroupBaseCharacterAmountMultiplier`
   - `EncounterHordeSpawnDistanceMultiplier`
   - `EncounterCharacterRespawnTimeMultiplier`
   - `EncounterCharacterRespawnBatchSizeMultiplier`
   - `EncounterCharacterAggressiveSpawnChanceOverride`
   - `PuppetHealthMultiplier`
   - `PuppetRunningSpeedMultiplier`
   - `EnableEncounterManagerLowPlayerCountMode`
   - `EncounterCanRemoveLowPriorityCharacters`
3. **Reconcile** against `config/serversettings-horde-block.ini`: if a key's real name differs, fix the
   NAME in the block (keep the vanilla value). If a key is absent from the live file, note it for Chris.
   **PvP gate — CONFIRMED LIVE 2026-06-23:** SCUM's **native Tab > Events matches are PvP inside their
   own arena even on an all-PVE server.** Chris's server is `ServerPlaystyle PVE` and the native
   deathmatch is still lethal player-vs-player. So for the default `USE_EVENT_LOCATION=True` path (horde
   spawns at the native event) you need **no** server-wide PvP setting — the event supplies its own PvP.
   The human-vs-human damage multiplier / non-`PVE` playstyle only matters for the
   `USE_EVENT_LOCATION=False` fixed-arena fallback, where the arena Custom Zone must itself allow PvP.
4. Re-run `python tools/validate_horde_block.py` after any edit — it must still print OK.

## Step B — Capture the horde inputs for the event watcher (in-game, as admin)

0. **Confirm the kill-log path + format (this is the event trigger — do it first).**
   - Find the gameplay-log folder: `...\SCUM\Saved\SaveFiles\Logs` (NOT `...\Saved\Logs`, which is the
     engine console log — different subsystem). Locate it with Glob, e.g. `**/Saved/SaveFiles/Logs`. Set
     `LOG_DIR` in `tools/arena_horde_loop.py` to it.
   - Confirm a `kill_<YYYYMMDDHHMMSS>.log` exists there and is **UTF-16-LE** (BOM `FF FE`). Open the newest
     one and confirm a kill line looks like `YYYY.MM.DD-HH.MM.SS: {"Killer":{...},"Victim":{...},...}`.
   - Confirm the JSON has `"IsInGameEvent"` (bool) on the Killer/Victim objects and a
     `"ServerLocation":{"X":..,"Y":..,"Z":..}`. If the field names differ on the live 1.3.x build, fix
     `_event_kill` / `_loc_from` in the watcher. **Best test:** start a real Tab > Events match with a
     second account, get one kill, and confirm that kill line shows `"IsInGameEvent": true`.
   - Validate end-to-end with `python tools/arena_horde_loop.py --dry-run` (no RCON needed): trigger an
     event kill and confirm the watcher prints "in-game-event kill … -> starting horde" with the right
     location. If it stays silent, the field/format assumption is wrong — fix it before going live. Watch
     the periodic `[watch] … parsed N kill line(s), M event-flagged, K located` heartbeat: if ordinary
     kills push **parsed up but event-flagged stays 0** during a real event, the `IsInGameEvent` field name
     is wrong; if flagged climbs but **located stays 0**, the `ServerLocation` field name is wrong.
1. Run `#ListZombies` in admin chat. From it, pick the puppet **type IDs** you want for the arena horde —
   including tougher/faster types if Chris wants tanky enemies (difficulty is arena-only now, so it comes
   from the puppet TYPE, not the global HP/speed multipliers). **Sort them** into `MILITARY_PUPPET_IDS`
   (the military/soldier puppets — these are preferred) and `OTHER_PUPPET_IDS` (everything else): each wave
   is a random, military-leaning mix, with `MILITARY_BIAS` controlling the lean. Record the exact IDs.
2. Stand in the **middle of the arena**, run `#Location`, and copy the WHOLE brace it prints
   (`{X=.. Y=.. Z=..|P=.. Y=.. R=..}`).
3. **Verify the spawn syntax.** Run once by hand:
   `#SpawnZombie <id> 1 Location {<the brace>}` and confirm a puppet appears AT the arena (not in front of
   you). Confirm the argument order is `<id> <count> Location <brace>`; if the live build differs, note the
   real order. Also confirm `#DestroyZombiesWithinRadius <radius> {<brace>}` clears that spot.
4. **Update `tools/arena_horde_loop.py`:** set `MILITARY_PUPPET_IDS` / `OTHER_PUPPET_IDS` to the sorted IDs
   (tune `MILITARY_BIAS`), `ARENA_LOCATION` to the brace (the
   `USE_EVENT_LOCATION=False` fallback), `RCON_HOST`/`RCON_PORT`/`RCON_PASSWORD` to the SCUM-RCON values,
   and fix `SPAWN_TEMPLATE` if the argument order differed (`LOG_DIR` was set in B0). Test the spawn path
   with `python tools/arena_horde_loop.py --once`, then `--reset`. Then test the full trigger: run
   `python tools/arena_horde_loop.py`, start a real Tab > Events match, and confirm waves spawn at the
   fight and clear after it ends. Decide `USE_EVENT_LOCATION` based on whether puppets actually reach
   players in SCUM's native event arena.

## Step C — Capture the real boss NPC codes (in-game, as admin)

1. Run `#ListCharacters` (and `#ListZombies` for reference). Capture the full output.
2. Pick the **boss-tier** entries — mech/sentry, drone, bear, wolf, armed NPC/prisoner, any named boss.
   Record the EXACT `BP_` code for each (the in-game list is authoritative, not any wiki).
3. Sanity-test one: `#SpawnCharacter <code> 1` — confirm it spawns in front of you (no location arg) and is
   actively hostile (especially `BP_Prisoner`/`BP_Zombie2`, flagged in the cheat-sheet).
4. **Update `docs/boss-cheat-sheet.md`**: replace the roster with the confirmed codes.

## Step D — Verify the Custom Zone behavior

1. As admin, open the in-game Admin Panel / Custom Zone Manager. Confirm: zones must be **named**, changes
   apply in **real time (no restart)**, and the per-zone damage flags. Confirm you can create a zone that
   keeps **player-vs-player damage ON** (PvPvE free-for-all) — note the exact flag names/options.
2. **Update `docs/arena-setup.md`** if any step or flag wording is wrong. Leave the chosen arena POI as
   whatever Chris specified (ask him if it's still unset).

---

## When done

1. Write `docs/live-verification-results.md` with a table: setting/code/syntax → confirmed value → source
   (file path or in-game command) → confidence (high/med/low). List anything you could NOT confirm.
2. Commit with a message like `chore: reconcile artifacts with live SCUM 1.3.x server values`.
3. Report back to Chris: a short diff summary (what key names/codes/syntax changed), and any setting that
   was absent or behaved differently so he can decide.
