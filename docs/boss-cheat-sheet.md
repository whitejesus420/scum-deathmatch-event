# Layer 3 — Random Boss Cheat-Sheet

Print this or keep it on a second monitor. To drop a boss: **roll 1–8** (any
die/RNG), then type the matching command in in-game chat **while standing in the
arena**. `#SpawnCharacter` has **no location argument** — the NPC spawns in front
of you, which is exactly why you stand in the arena to fire it.

> Two different spawn commands — don't mix them up:
> - **Bosses (this sheet):** `#SpawnCharacter <code>` — no location, spawns in
>   front of you. Stand in the arena.
> - **The horde:** `#SpawnZombie <id> <count> Location <brace>` — targets the
>   arena coordinates. You don't type this by hand; `tools/arena_horde_loop.py`
>   fires it on a loop. (Only `#SpawnZombie`/`#SpawnAnimal`/`#SpawnVehicle` take
>   a Location arg; `#SpawnCharacter` does not.)

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
