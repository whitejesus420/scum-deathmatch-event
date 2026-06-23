# Live-Server Verification Handoff (for another Claude)

**Read this if you are an AI agent (or a future session) asked to finalize the SCUM COD-Zombies
deathmatch horde event.** The design is fixed; your job is to replace the three "verify on live server"
unknowns with real values pulled from Chris's running SCUM 1.3.x dedicated server, then update the project
artifacts and report what you changed.

Do NOT redesign anything. The architecture (three layers: config horde + one Custom Zone arena + a
printable random-boss cheat-sheet, PvPvE, no script, no pak) is locked. See
`docs/superpowers/specs/2026-06-22-scum-cod-zombies-deathmatch-event-design.md`.

## Project location & artifacts you will edit

Project root: `C:\Users\chris\scum-deathmatch-event\`

| File | What you update |
|---|---|
| `config/serversettings-horde-block.ini` | Correct any key name that differs on the live server; confirm ranges; keep Chris's tuned values. |
| `docs/boss-cheat-sheet.md` | Replace the boss roster with the real `BP_` codes from `#ListCharacters`. |
| `docs/arena-setup.md` | Correct the Custom Zone steps / PvP-flag wording if the live behavior differs. |
| `docs/live-verification-results.md` | **Create this** — log every confirmed value, its source (file path / in-game output), and confidence. |

## Ground rules (do not violate)

- This is Chris's **own private server**. Never touch official servers; never advise anti-cheat bypass.
- **Back up `ServerSettings.ini`** (copy to `*.bak`) before changing it.
- **Custom Zone changes:** zones created in the in-game **Admin Panel / Custom Zone Manager apply in real
  time (no restart)** — only zones defined in a config file require a restart. See `docs/arena-setup.md`.
  Confirm this on the live server. Some `ServerSettings.ini` settings may still need a restart — never
  assume a setting hot-reloads; note which ones do.
- Confirm Chris's account is in the server's admin list before expecting in-game `#` commands to work.
- If you cannot reach the live server, STOP and tell Chris exactly which of Steps A/B/C you could not do —
  do not invent values.

---

## Step A — Pull the real `ServerSettings.ini` keys & values

1. **Find the file.** For a Windows dedicated server it is typically:
   `...\SCUM\Saved\Config\WindowsServer\ServerSettings.ini` (under the server install dir, NOT the game
   client). If hosted (g-portal/nitrado/etc.), it is in the host panel's config-file editor / FTP.
   Locate it with Glob, e.g. pattern `**/Saved/Config/**/ServerSettings.ini`. If you find more than one,
   prefer the one under `WindowsServer` (the dedicated server), and ask Chris which install is live if
   ambiguous. The admin list lives next to it as `AdminUsers.ini`.
2. **Read it** and locate each of these settings by substring search (`MaxAllowedPuppets`, and the
   substrings `Encounter`, `Horde`, `Puppet`). For EACH, record: the exact key string as written
   (including any section header or `scum.` prefix), its current value, and whether it is present at all:
   - `MaxAllowedPuppets`
   - `EncounterHordeActivationChanceMultiplier`
   - `EncounterHordePuppetHordeActivationScreamOverrideChance`
   - `EncounterHordeBaseCharacterAmountMultiplier`
   - `EncounterHordeSpawnDistanceMultiplier`
   - `EncounterCharacterRespawnTimeMultiplier`
   - `EncounterCharacterRespawnBatchSizeMultiplier`
   - `EncounterCharacterAggressiveSpawnChanceOverride`
   - `PuppetHealthMultiplier`
   - `PuppetRunningSpeedMultiplier`
   - `EnableEncounterManagerLowPlayerCountMode`
   - `EncounterCanRemoveLowPriorityCharacters`
3. **Reconcile** against `config/serversettings-horde-block.ini`:
   - If a key's real name **differs** (renamed/re-cased/sectioned), fix it in the block.
   - If a key is **absent** from the live file, note it — it may be settable anyway, or may be the wrong
     name; flag for Chris, don't silently drop it.
   - Keep Chris's **tuned values** from the block (those are the intent); only the key NAMES and any
     out-of-range clamps come from the live file. If the live file documents a different valid range,
     clamp the value and note it.
   - Record which settings hot-reload (e.g. via `#ReloadServerSettings` if that exists on 1.3.x) vs.
     require a restart.

## Step B — Capture the real boss NPC codes (in-game, as admin)

1. In-game admin chat, run `#ListCharacters` (and `#ListZombies` for reference). Capture the full output.
2. From it, pick the **boss-tier** entries for the cheat-sheet — mech/sentry, drone, bear, wolf, armed
   NPC/prisoner, and any named boss. Record the EXACT `BP_` code for each (codes drift between patches —
   the in-game list is authoritative, not any wiki).
3. Sanity-test one: stand somewhere safe and run `#SpawnCharacter <code> 1`. Confirm it spawns in front of
   you and that the command takes **no** location argument (this is expected — it's why the admin stands in
   the arena). Also confirm the cleanup command and its argument format:
   `#DestroyZombiesWithinRadius <radius> [location]`.
4. **Update `docs/boss-cheat-sheet.md`**: replace the roster numbers 1..N with the confirmed codes, each
   line `N. <flavor name> — #SpawnCharacter <code> <amount>`.

## Step C — Verify the Custom Zone behavior

1. As admin, open the in-game Admin Panel / Custom Zone Manager. Confirm: zones must be **named**, whether
   changes apply in **real time (no restart)** as `docs/arena-setup.md` documents for Admin-Panel zones,
   and the per-zone damage flags. Specifically confirm you can create a zone that keeps **player-vs-player
   damage ON** (PvPvE free-for-all) — note the exact flag names/options.
2. **Update `docs/arena-setup.md`** if any step or flag wording is wrong. Leave the chosen arena POI as
   whatever Chris specified (ask him if it's still unset).

---

## When done

1. Write `docs/live-verification-results.md` with a table: setting/code → confirmed value → source
   (file path or in-game command) → confidence (high/med/low). List anything you could NOT confirm.
2. Commit with a message like `chore: reconcile artifacts with live SCUM 1.3.x server values`.
3. Report back to Chris: a short diff summary (what key names/codes changed), and any setting that was
   absent or out of range so he can decide.
