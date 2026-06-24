# NEXT CLAUDE — START HERE

**You are picking up after the first live test failed. Read this before touching
anything.** The full evidence is in `docs/live-test-2026-06-23-findings.md`; the
detailed in-game capture runbook is `docs/live-verification-handoff.md` (Steps
A–D). This file is the short version: the state of play and exactly what to do.

## State of play (what we know)

- `tools/arena_horde_loop.py` is **code-complete and reviewed**. No code bug has
  been found. The live failure was **operational**, not a logic error:
  - **Nothing spawned** because the CONFIG block on disk is blank (`LOG_DIR`,
    `RCON_PASSWORD`, and both puppet-ID lists are empty), so in watch mode the tool
    exits with code 2 at `_check_config` *before* it connects — and/or it never
    ran at all.
  - **The console "printed nothing"** — which is the real blocker. Every normal
    run prints a banner or an error. Silence means **the output was hidden or the
    process never launched.** Fix observability FIRST (Step 1) or you'll be blind.
  - **Players crashing is NOT the tool.** Those were client-side SCUM crashes in
    the native event (the tool spawned nothing). Don't try to "fix" the tool for
    that. See the findings doc.

**Do not re-run against a full live lobby** until Step 1–4 below pass on a quiet
test. Private server only; never an official server; never bypass anti-cheat.

## Step 1 — Make the run OBSERVABLE (do this first)

Run **on the server box**, in an **open console window you can read**, unbuffered:

```
python -u tools\arena_horde_loop.py --dry-run
```

`-u` forces unbuffered stdout so the banner can't get stuck in a buffer.

You MUST see one of these immediately:
- `Watching <LOG_DIR> for native-event kills.` — good, it started.
- `CONFIG NOT READY:` + bullet list — config isn't filled (go to Step 2).
- `connect attempt …/could not connect to RCON` — RCON host/port/password wrong.
  (This path only runs in normal mode, **not** `--dry-run`; you'll first see it when
  you drop `--dry-run` in Step 4.)

**If you see NOTHING, the process is not actually running its output to your
console.** Likely causes (these match Chris's earlier silent run):
- Launched via `Start-Process -RedirectStandardOutput` — buffers stdout until
  exit. **Don't.** Run it directly in the console.
- Double-clicked the `.py` — the window flashes the exit-2 message and closes.
  **Don't.** Launch from a console.
- `pythonw`, a pipe, or `> file` redirect swallowing output. **Don't.**
- `python` not on PATH / wrong working directory — you'd get a Python error, so
  confirm `python --version` works and you're in the repo root.

Don't proceed until you can see the tool's output.

## Step 2 — Fill the CONFIG block

Edit the top of `tools/arena_horde_loop.py` (lines ~76–122):

- `LOG_DIR` — the server's `…\SCUM\Saved\SaveFiles\Logs` folder (where
  `kill_<ts>.log` lives — NOT `…\Saved\Logs`, that's the engine console log).
- `RCON_HOST` + `RCON_PORT` + `RCON_PASSWORD` — from the SCUM-RCON mod config. The
  default host `127.0.0.1` works when you run this ON the server box; change it if
  RCON lives on another machine. Password is REQUIRED; blank = exit 2.
- `MILITARY_PUPPET_IDS` / `OTHER_PUPPET_IDS` — run `#ListZombies` in admin chat and
  sort the puppet TYPE IDs (military/soldier in the first bucket, rest in the
  second). Each wave is a random, military-leaning mix; tune `MILITARY_BIAS`.
- `ARENA_LOCATION` — **always required** (a placeholder brace is already filled in so
  validation passes, but replace it with YOUR arena). It's the center for
  `--once`/`--reset`, the `USE_EVENT_LOCATION=False` arena (recommended first run —
  see Step 5), *and* the fallback when an event kill has no parseable location. Stand
  in your arena, run `#Location`, paste the whole brace. Missing `X=` = exit 2.

Full capture details for each: `docs/live-verification-handoff.md`, Steps A–C.

## Step 3 — Prove event DETECTION with `--dry-run` (no RCON needed)

```
python -u tools\arena_horde_loop.py --dry-run
```

Start a real Tab > Events match with a second account and get one kill. Confirm:
- `[event] in-game-event kill (…) -> starting horde at …` appears, and
- the periodic `[watch] last 60s: parsed N kill line(s), M event-flagged, K located
  (state=…)` heartbeat shows **event-flagged > 0** and **located > 0** during the event.

Failure modes the heartbeat tells you about:
- parsed climbs but **flagged stays 0** → the `IsInGameEvent` field name is wrong
  for this build; fix `_event_from_obj` / `_truthy` usage.
- flagged climbs but **located stays 0** → the `ServerLocation` field name is
  wrong; fix `_loc_from`.

## Step 4 — Smoke-test the RCON spawn path

With config filled and RCON reachable:

```
python -u tools\arena_horde_loop.py --once     # fires one wave at ARENA_LOCATION
python -u tools\arena_horde_loop.py --reset     # clears it
```

Confirm puppets actually appear at the arena and clear. If `#SpawnZombie` argument
order differs on the live build, fix `SPAWN_TEMPLATE` (line 121).

## Step 5 — First live run: prefer the FIXED arena, keep it small

**The client crashes happened inside SCUM's native event arena** (teleport +
level-streaming load). Spawning a horde there could make that worse. For the first
live run:

- Set `USE_EVENT_LOCATION=False` and run the event at your own fixed
  `ARENA_LOCATION` (a custom zone you control) — fewer streaming transitions.
- Keep `COUNT_PER_WAVE` low and `INTERVAL_SECONDS` longer to start; ramp up only
  after clients prove stable.
- Watch the server log for `failed to respond to heartbeats` (client crashes) and
  the game-thread frame time. Stop if clients start dropping.

Only switch back to `USE_EVENT_LOCATION=True` (spawn at the native event) once
you've confirmed clients survive the native event itself.

## Ground rules (do not violate)

- Chris's **own private server** only. Never official servers; never advise
  anti-cheat bypass. (Disabling BattlEye on his own server is fine, not a bypass.)
- **Back up `ServerSettings.ini`** (copy to `*.bak`) before editing it.
- **No pak, no Blueprint.** Config + admin commands + this Python loop only.
- **Don't crank the Encounter multipliers** in `config/serversettings-horde-block.ini`
  to "make it bigger" — that re-globalizes the horde and
  `tools/validate_horde_block.py` will fail. Raise `COUNT_PER_WAVE` / lower
  `INTERVAL_SECONDS` instead.
- Confirm Chris's account is in the server admin list before expecting `#` commands
  to work.

## When done

Update `docs/live-verification-results.md` (create it) with each confirmed value →
source → confidence, and report to Chris what you changed and anything that
behaved differently. Commit/push only when Chris asks.
