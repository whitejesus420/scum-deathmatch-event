# SCUM COD-Zombies Deathmatch Event

A Call-of-Duty-Zombies-style event for a **private SCUM 1.3.x server**: a PvPvE
free-for-all in a fixed arena where an endless, escalating horde of puppets
pours in **at the arena only** while players also fight each other — last one
standing. An admin can drop a random boss by hand for a difficulty spike.

**No mod pak, no Blueprint.** It is plain config + admin commands + one small
Python RCON loop, so a SCUM patch costs you at most a quick re-verify of a few
setting names, the spawn syntax, and the boss codes — nothing to rebuild.

> Private server only. Never use on official servers; never bypass anti-cheat.

## Why it's arena-only (the important bit)

SCUM has **no config or zone setting that makes a horde appear at one
location**. The Encounter Manager is entirely server-wide; cranking it (as an
earlier version of this project did) floods the *whole map*, not the arena.

So the horde is spawned directly at the arena over RCON with `#SpawnZombie ...
Location <coords>`, and every server-wide Encounter/Puppet multiplier is left at
**vanilla** so the rest of the map stays normal. That is the only native way to
keep the swarm pinned to the event.

## The layers

1. **Global baseline** — `config/serversettings-horde-block.ini`. Holds SCUM's
   Encounter Manager at vanilla (the opposite of a crank) so the open map stays
   calm, plus the PvP-gate note. The only deliberate non-default is a puppet
   *cap* (headroom for the arena crowd — it spawns nothing itself).
2. **The arena horde** — `tools/arena_horde_loop.py`. A dependency-free Python
   Source-RCON client that, on an interval, spawns puppets **at the arena
   coordinates** and clears them between rounds. This is what actually makes the
   horde, and the only part that targets a location.
3. **The arena zone** — `docs/arena-setup.md`. One named in-game Custom Zone
   with PvP damage left ON. Created live via the Admin Panel (no restart).
4. **Random bosses** — `docs/boss-cheat-sheet.md`. A numbered roster you roll
   against and spawn with one `#SpawnCharacter` command.

## Deploy order

1. **Back up** your server's `ServerSettings.ini` (copy to `ServerSettings.ini.bak`).
2. **Merge** the keys from `config/serversettings-horde-block.ini` into it. Match
   the file style your server already uses (`scum.Key` under `[World]`, or bare
   `Key` under `[SCUM.WorldSettings]` — see the comments in the block). Confirm
   the global human-vs-human damage multiplier is **> 0** so PvP works. Do **not**
   crank the Encounter multipliers — that re-globalizes the horde.
3. Validate the block: `python tools/validate_horde_block.py` (it FAILS if a
   global has been cranked off vanilla).
4. **Restart** the server (the Encounter/puppet settings are read at world load).
5. **Create the arena** following `docs/arena-setup.md` (in-game, no restart).
   Record the center coordinates **as the full `#Location` brace** in that file.
6. **Enable RCON** (SCUM-RCON Nexus mod) and fill in the CONFIG block at the top
   of `tools/arena_horde_loop.py`: RCON host/port/password, `ARENA_LOCATION`
   (the brace from step 5), and `PUPPET_IDS` (from `#ListZombies`).
7. **Print/open** `docs/boss-cheat-sheet.md`.

## Running an event

1. Tell players where/when. They gather in the arena.
2. Start the horde: `python tools/arena_horde_loop.py`. It spawns a wave at the
   arena every `INTERVAL_SECONDS` and keeps refilling. PvP is live, so it's also
   a free-for-all. `--once` fires a single wave; `--reset` clears the arena.
3. When you want a spike, roll 1–8 and type the boss command from the cheat-sheet
   while standing in the arena.
4. Stop the loop with **Ctrl+C** — it clears the arena on the way out (or run
   `python tools/arena_horde_loop.py --reset`).

## Tuning

- **Bigger / more relentless horde** → raise `COUNT_PER_WAVE` or lower
  `INTERVAL_SECONDS` in `tools/arena_horde_loop.py`. Mind the `MaxAllowedPuppets`
  ceiling in the config block (raise it if waves can't reach their count).
- **Tankier / faster enemies** → put tougher puppet **type IDs** in `PUPPET_IDS`.
  Difficulty is arena-only now; the global HP/speed multipliers stay at 1.0 so
  the rest of the map isn't affected.
- **Do NOT** raise the Encounter multipliers in the config block to "make it
  bigger" — that floods the whole map. The validator errors if you do.

## Surviving a SCUM patch / finalizing for YOUR server

The setting names, the `#SpawnZombie ... Location` syntax, and the boss codes
here are from June-2026 research and are mostly confirmed, but a few (the live
PvP-multiplier key name, the exact `#SpawnZombie` argument order, the puppet/boss
codes) should be checked against your actual running server. The full runbook is
in **`docs/live-verification-handoff.md`**. After a major patch, re-run it.

## Files

- `config/serversettings-horde-block.ini` — Layer 1 global baseline (+ inline docs)
- `tools/validate_horde_block.py` — guard that the globals stay vanilla
- `tools/arena_horde_loop.py` — Layer 1b arena horde RCON loop
- `docs/arena-setup.md` — Layer 2 arena Custom Zone guide
- `docs/boss-cheat-sheet.md` — Layer 3 boss roster + commands
- `docs/live-verification-handoff.md` — how to reconcile values with your live server
- `docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md` — the design spec
