# SCUM COD-Zombies Deathmatch Event

A Call-of-Duty-Zombies-style event for a **private SCUM 1.3.x server**: a PvPvE
free-for-all where an endless, escalating horde of puppets pours in **at the
event only** while players also fight each other — last one standing. An admin
can drop a random boss by hand for a difficulty spike.

It hooks SCUM's **native in-game events** (Tab > Events — Deathmatch / TDM / CTF /
Brawl / MMA): a watcher tails the server's kill log, and the moment a
native-event kill appears it starts the horde at that location, then moves the
spawn point to follow each new event kill (and new events). See the caveats under
"Running an event" — the trigger is reactive, not instant.

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
2. **The event-driven horde** — `tools/arena_horde_loop.py`. A dependency-free
   Python tool that tails the server's **kill log**, and when a kill flagged
   `"IsInGameEvent": true` appears (a native Tab > Events match is live), spawns
   puppets at that kill's location over Source-RCON and keeps waves coming until
   the event goes quiet, then clears them. This is what actually makes the horde,
   and the only part that targets a location. (Why the kill log? RCON has no
   event signal and no log line is written at event start — the `IsInGameEvent`
   kill flag is the one native "an event is happening" signal that exists.)
3. **The arena zone** — `docs/arena-setup.md`. One named in-game Custom Zone
   with PvP damage left ON. Created live via the Admin Panel (no restart).
4. **Random bosses** — `docs/boss-cheat-sheet.md`. A numbered roster you roll
   against and spawn with one `#SpawnCharacter` command.

## Deploy order

1. **Back up** your server's `ServerSettings.ini` (copy to `ServerSettings.ini.bak`).
2. **Merge** the keys from `config/serversettings-horde-block.ini` into it. Match
   the file style your server already uses (`scum.Key` under `[World]`, or bare
   `Key` under `[SCUM.WorldSettings]` — see the comments in the block). Do **not**
   crank the Encounter multipliers — that re-globalizes the horde. (PvP note: a
   **native Tab > Events match is PvP inside its own arena even on an all-PVE
   server** — confirmed live — so the global human-vs-human damage multiplier only
   matters for the `USE_EVENT_LOCATION=False` fixed-arena fallback.)
3. Validate the block: `python tools/validate_horde_block.py` (it FAILS if a
   global has been cranked off vanilla).
4. **Restart** the server (the Encounter/puppet settings are read at world load).
5. **Create the arena** following `docs/arena-setup.md` (in-game, no restart).
   Record the center coordinates **as the full `#Location` brace** in that file.
6. **Enable RCON** (SCUM-RCON Nexus mod) and fill in the CONFIG block at the top
   of `tools/arena_horde_loop.py`: `LOG_DIR` (the server's
   `…\Saved\SaveFiles\Logs` folder), RCON host/port/password, and the puppet IDs
   from `#ListZombies` — sorted into `MILITARY_PUPPET_IDS` (preferred) and
   `OTHER_PUPPET_IDS` so each wave is a random, military-leaning mix. Set
   `ARENA_LOCATION` (the brace from step 5) too — it's the fallback if
   `USE_EVENT_LOCATION=False`.
7. **Print/open** `docs/boss-cheat-sheet.md`.

## Running an event

1. Start the watcher: `python tools/arena_horde_loop.py`. It connects to RCON
   and then just watches the kill log — idle until an event happens.
2. Players open **Tab > Events** and start a native match (Deathmatch / TDM / CTF
   / Brawl / MMA). SCUM teleports them into its own arena and the match begins.
3. On the **first kill** of that match, the watcher detects the
   `"IsInGameEvent": true` flag and starts pouring the horde in at that location,
   a wave every `INTERVAL_SECONDS`. The spawn point then **moves to follow the
   fight** — each new event kill (and each new event) relocates the horde to that
   kill's spot — until the event goes quiet (`EVENT_QUIET_TIMEOUT`), then it
   clears the puppets from every spot it spawned at. PvP is live, so it's a
   free-for-all on top of the native match.
4. When you want a spike, roll 1–8 and type the boss command from the cheat-sheet
   while standing where the fight is.
5. Stop the watcher with **Ctrl+C** — it clears the arena on the way out if a
   horde is active. `--reset` clears the fallback arena; `--once` fires one test
   wave there.

**Caveats (live-test these — see `docs/live-verification-handoff.md`):**

- **Reactive, not instant.** The horde starts after the first *kill* of the
  event (a match needs ≥2 players, then a death), not the moment players join.
- **Can't tell which event.** The flag says "in an event," not Deathmatch vs MMA.
- **Engagement is unverified.** Native events teleport players into SCUM's own
  arena; whether RCON-spawned puppets can reach/fight them there isn't confirmed.
  If they can't, set `USE_EVENT_LOCATION=False` to spawn at your fixed
  `ARENA_LOCATION` instead and run the event there.
- **Validate first without RCON:** `python tools/arena_horde_loop.py --dry-run`
  watches the live kill log and prints the spawn commands it *would* send, so you
  can confirm event detection before wiring anything up.

## Tuning

- **Bigger / more relentless horde** → raise `COUNT_PER_WAVE` (now the **total**
  puppets per wave, randomly typed) or lower `INTERVAL_SECONDS` in
  `tools/arena_horde_loop.py`. Mind the `MaxAllowedPuppets` ceiling in the config
  block (raise it if waves can't reach their count). For a tight space like the
  Brawl cage, go the other way — a *lower* count so it doesn't pack instantly.
- **More / less military** → each wave is a random mix drawn from a weighted pool.
  Put military/soldier IDs in `MILITARY_PUPPET_IDS` and the rest in
  `OTHER_PUPPET_IDS`, then set `MILITARY_BIAS` (how many times likelier a military
  type is). `OTHER` empty = military only; `MILITARY` empty = no preference.
- **Tankier / faster enemies** → put tougher puppet **type IDs** in those buckets.
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
- `tools/arena_horde_loop.py` — Layer 1b event-driven horde watcher (kill-log + RCON)
- `docs/arena-setup.md` — Layer 2 arena Custom Zone guide
- `docs/boss-cheat-sheet.md` — Layer 3 boss roster + commands
- `docs/live-verification-handoff.md` — how to reconcile values with your live server
- `docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md` — the design spec
