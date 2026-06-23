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
