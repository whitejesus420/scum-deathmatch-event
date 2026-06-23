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
7. **Record the zone's center — as the full `#Location` brace.** Stand in the
   middle of the arena, run `#Location` in chat, and copy the WHOLE brace it
   prints (X/Y/Z **and** P/Y/R), not just X/Y. This single value drives the
   whole event:

       Arena name: ____________________
       #Location brace: ____________________________________________
       (e.g. {X=-152157.266 Y=287169.562 Z=69696.133|P=0.000000 Y=0.000000 R=0.000000})
       Radius: ____________________

   - Paste that brace into `ARENA_LOCATION` at the top of
     `tools/arena_horde_loop.py` — it is where the horde spawns.
   - It also feeds the `[location]` arg of `#DestroyZombiesWithinRadius` for cleanup.
   - The admin stands near this center to drop bosses (`#SpawnCharacter` has no
     location argument — it spawns in front of the admin).

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
