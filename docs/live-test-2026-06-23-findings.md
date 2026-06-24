# Live-Test Post-Incident Findings — 2026-06-23

**First real run against live players. Both symptoms root-caused; the tool itself
is exonerated.** This is the evidence record. For what to DO next, read
`docs/NEXT-CLAUDE-START-HERE.md` first.

## What happened

Chris ran `tools/arena_horde_loop.py` on the SCUM dedicated-server box during a
real, populated native **Deathmatch** (7 players). Two things went wrong:

- **A — Nothing spawned.** No horde ever appeared.
- **B — Players "fatal errored a ton."** Multiple clients crashed out.

And a third clue surfaced while diagnosing A:

- **C — The tool's console "didn't print anything."** Total silence, which is
  itself anomalous (see below).

## Evidence reviewed

- `scum_server_last30min.txt` — the dedicated server console for the test window
  (server install `C:/SCUMServer/…`, a DIFFERENT box from the game client). UTC
  timestamps; fresh server boot ~04:05:15, players active through ~04:23 (last
  heartbeat-timeout disconnect 04:23:27).
- `scum_event_kill_logs.json` — the server's event-DB export confirming a real
  Deathmatch: WhiteJesus (Chris, 14k/14d), Necro (10k/8d), Skadi (8k/18d), plus
  JOEJOE and three zero-kill players (BoNeSSeNoB, BOSS11645, Alpha).
- Chris's client crash dump — `…/SCUM/Saved/Crashes/UE4CC-…/CrashContext.runtime-xml`
  + `SCUM.log`.
- `tools/arena_horde_loop.py` — the tool under investigation.

A 5-agent adversarial verification pass (each agent trying to *break* one
conclusion) reviewed all of the above: **4 of 5 conclusions upheld at high
confidence; 1 refined** (see C3 below).

## Symptom A — nothing spawned

**Root cause: the tool never sent a single spawn command.** Two compounding
reasons:

1. **The CONFIG block was unconfigured.** On disk, `LOG_DIR = ""` (line 76),
   `RCON_PASSWORD = ""` (line 80), and both `MILITARY_PUPPET_IDS` /
   `OTHER_PUPPET_IDS` are empty (lines 103–108). In default watch mode
   `_check_config(need_rcon, need_puppets=True, need_log=True)` (line 636) fails
   on all three, prints `CONFIG NOT READY:` to **stderr**, and returns exit code 2
   — *before* it ever opens an RCON socket.
2. **The console printed nothing** (Symptom C), so we can't even confirm the tool
   reached that check. Every code path in watch mode emits *something* (the
   `Watching … for native-event kills.` startup banner printed from line 479 on a
   good start,
   `CONFIG NOT READY:` on blank config, or `connect attempt …/could not connect to
   RCON` on an unreachable server). **A truly silent console means the output was
   hidden or the process never launched** — e.g. stdout block-buffered behind
   `Start-Process -RedirectStandardOutput` (a known buffering trap — stdout isn't
   flushed until exit), a pipe/redirect, `pythonw`, or a double-click window that
   flashed the exit-2 message and closed.

**Server-side confirmation:** the server log has **zero** `#SpawnZombie`,
`#DestroyZombiesWithinRadius`, RCON, or RemoteAdmin lines for the entire window.
The `Z:` puppet count grew **smoothly** (e.g. 97→100→101→103 across 5-second
ticks) — normal vanilla Encounter-Manager population, **not** the +10 jumps a
`#SpawnZombie` wave produces. The watcher never fired.

## Symptom B — players fatal errored

**Root cause: client-side crashes during SCUM's native Deathmatch. The server was
healthy; the tool was not involved.**

- **Server health:** game-thread frame time held ~14.7–14.8 ms (~68 FPS) from boot
  to end of window. No `Fatal`, `Exception`, `OOM`, or crash anywhere in the 911 KB
  log. Server and client versions match exactly (`1.3.0.2.119181`, DB schema 50) —
  no version/pak mismatch.
- **The "400.0 ms (2.5 FPS)" column is a red herring.** That third Global-Stats
  column shows 400 ms even at idle boot with `C:0 P:0 Z:0`. It's a clamped periodic
  metric, not event overload.
- **The three disconnects are all heartbeat timeouts** — `LogSCUM: Error: <name>
  failed to respond to heartbeats. Closing connection.` That is the server giving
  up on a client that stopped answering (a client freeze/crash), **not** a server
  kick and **not** a server fault. They hit only the three most active fighters
  (WhiteJesus 04:19:04, Skadi 04:20:45, Necro 04:23:27); the three zero-kill
  players never dropped.
- **Chris's crash is confirmed by a dump:** `EXCEPTION_ACCESS_VIOLATION` on the
  GameThread; his client `SCUM.log` ends at **04:18:45**, exactly **19 seconds**
  before the server's heartbeat timeout at **04:19:04** — the textbook "client
  froze → server timed it out" sequence. The crash tail is navmesh / door-nav-link
  churn at `B_3_Mirkovci_02` under heavy level streaming (consistent with the
  event teleport + admin map-click teleports + `TeleportToMe` happening during the
  match).

### Correction logged (C3): don't over-claim

The first pass asserted "all three disconnects are proven client crashes." That
over-reached. **Only Chris's (WhiteJesus) crash has a dump on hand.** Skadi's and
Necro's disconnects show *only* as heartbeat timeouts — the same client-side
fingerprint, and consistent with Chris's report that "players fatal errored a
ton," but their crash dumps live on *their* machines, so they're not independently
proven here. Direction is unchanged (client-side, not server, not the tool); the
strength of evidence per player is not uniform.

## The tool is exonerated

Because the tool sent zero spawns (Symptom A), there is **no mechanism** by which
it could have caused the client crashes. The crashes happened in vanilla
native-event play. Do not "fix" the tool to address the crashes — they are a
client-side SCUM issue triggered by the native event's teleport/streaming load.

## The standing risk to weigh before the next run

The tool is *designed* to spawn the horde **into SCUM's native event arena**
(`USE_EVENT_LOCATION=True`) — which is exactly where the clients crashed. Piling a
puppet horde (more actors, more streaming) onto an already crash-prone native
event could make B worse. The fixed-arena fallback (`USE_EVENT_LOCATION=False` +
a custom `ARENA_LOCATION`) sidesteps the native-event teleport entirely and is the
safer first live target. See the next-steps doc.

## Verification summary

| Claim | Verdict | Confidence |
|---|---|---|
| Tool sent zero spawns; `Z:` count is vanilla population | upheld | high |
| Server stayed healthy; versions match; "400 ms" is a clamp | upheld | high |
| All three disconnects = *proven* client crashes | **refuted → refined** | high |
| Tool exonerated for the crashes | upheld | high |
| No code path runs the watcher silently (silence = hidden/never-launched) | upheld | high |
