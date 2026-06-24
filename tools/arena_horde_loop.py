#!/usr/bin/env python3
"""Layer 1b — the arena horde loop, driven by SCUM's native in-game events.

WHAT THIS DOES
  SCUM has a native Deathmatch / TDM / CTF / Brawl / MMA event system (Tab >
  Events). There is NO way to force-start one and NO signal the instant it
  starts — RCON is request/response with no push, and no log line is written at
  event start (researched + adversarially verified, 2026-06-23). The ONE native
  signal that an event is live is the server's KILL log: every kill is logged as
  JSON, and an event kill carries `"IsInGameEvent": true` on the killer/victim.

  So this script TAILS the kill log. The moment the FIRST in-game-event kill of a
  match appears, it starts pouring a puppet horde in at that kill's location over
  RCON (`#SpawnZombie <id> <count> Location <coords>`), and the spawn point MOVES
  to follow the fight — each later event kill relocates the horde to that kill's
  spot. It does not track event identity, so it also FOLLOWS NEW EVENTS: when a
  fresh match starts somewhere else, its first event kill pulls the swarm over,
  and the watcher loops event after event for the whole session. Because only
  event kills carry the flag, every spot is inside SCUM's own deathmatch arena, so
  the swarm tracks the action without leaking onto the open map. Each wave is a
  RANDOM, military-leaning mix of puppet types (not the same roster every time),
  and it keeps waves coming while the event stays hot, then clears every spot it
  fired at once the event goes quiet. The rest of the map's Encounter Manager
  stays vanilla (config/serversettings-horde-block.ini).

KNOWN CAVEATS (live-test these — see docs/live-verification-handoff.md)
  - REACTIVE, not on-start: the horde begins after the FIRST event kill (an event
    needs >=2 players joined, then a death), not at the join/teleport moment.
  - The IsInGameEvent flag does not say WHICH event (DM vs Brawl vs MMA).
  - The native event teleports players into SCUM's OWN predetermined arena.
    Whether RCON-spawned puppets can reach / engage players inside that area is
    unverified. If they can't, set USE_EVENT_LOCATION=False and they'll spawn at
    your fixed ARENA_LOCATION instead.

  - No third-party deps. Pure stdlib (socket + struct + json + argparse).
  - Private server only. Never point this at an official server.

USAGE
  python tools/arena_horde_loop.py            # watch the kill log; horde on event
  python tools/arena_horde_loop.py --dry-run  # watch + print, but DON'T touch RCON
  python tools/arena_horde_loop.py --once      # fire one wave at ARENA_LOCATION, exit
  python tools/arena_horde_loop.py --reset     # clear ARENA_LOCATION and exit
  --dry-run works with --once/--reset too: it prints the command(s) and exits
  without connecting. Ctrl+C during the watch clears the arena if a horde is active.

BEFORE YOU RUN (fill in the CONFIG block below):
  1. Set LOG_DIR to the server's log folder (…\\SCUM\\Saved\\SaveFiles\\Logs).
  2. Enable RCON (SCUM-RCON mod) and set RCON_PORT + RCON_PASSWORD.
  3. Run `#ListZombies` in-game and SORT the puppet TYPE IDs you want into
     MILITARY_PUPPET_IDS (preferred) and OTHER_PUPPET_IDS. Each wave is a random,
     military-leaning mix (tune the lean with MILITARY_BIAS). Difficulty is
     arena-only (the global HP/speed multipliers are vanilla), so pick TOUGHER
     puppet types for tanky/fast enemies.
  4. (Only if USE_EVENT_LOCATION=False) stand in your arena, run `#Location`, and
     paste the whole brace into ARENA_LOCATION.
  Validate the watcher against real logs first with `--dry-run` (no RCON needed).
  While watching, a periodic [watch] heartbeat reports how many kill lines it
  parsed vs. how many were event-flagged — if kills are happening but NONE are
  flagged, the IsInGameEvent field-name assumption is wrong; fix it before live.
"""
import argparse
import glob
import json
import os
import random
import socket
import struct
import sys
import time

# =====================================================================
#  CONFIG — edit these for your server, then run.
# =====================================================================
# The server's gameplay-log folder. The kill log lives here as kill_<ts>.log.
# Windows dedicated server, typical path (raw string — note the trailing Logs):
LOG_DIR = r""                # e.g. r"C:\SCUMServer\SCUM\Saved\SaveFiles\Logs"

RCON_HOST = "127.0.0.1"      # run this on the server box (or its LAN/tailnet IP)
RCON_PORT = 27015            # SCUM-RCON port from the server config (verify!)
RCON_PASSWORD = ""           # SCUM-RCON password — REQUIRED, set this

# Spawn the horde AT the event's location (read from the kill log) and let it MOVE
# to follow the fight — each event kill relocates the horde to that kill's spot.
# Set False to always use the fixed ARENA_LOCATION below instead (use this if
# puppets can't reach the native arena).
USE_EVENT_LOCATION = True

# Fallback / --once arena center, as SCUM's `#Location` brace (X/Y/Z | P/Y/R).
# Used when USE_EVENT_LOCATION is False, for --once / --reset, and as the fallback
# when an event kill has no parseable ServerLocation. Keep it valid regardless.
ARENA_LOCATION = "{X=-152157.266 Y=287169.562 Z=69696.133|P=0.000000 Y=0.000000 R=0.000000}"

# Puppet TYPE IDs (from `#ListZombies`), split into two buckets so each wave is a
# RANDOM, military-leaning mix instead of the same fixed roster every time. Every
# puppet in a wave is drawn independently at random; a military type is
# MILITARY_BIAS times as likely to be picked as a non-military one. Put your
# military/soldier puppet IDs in MILITARY_PUPPET_IDS and everything else in
# OTHER_PUPPET_IDS.
#   - OTHER empty    => military only.
#   - MILITARY empty => no preference (everything in OTHER, equal odds).
# Pick tougher/faster types for arena-only difficulty (the global HP/speed
# multipliers stay vanilla).
MILITARY_PUPPET_IDS = [
    # "0",   # <- military / soldier puppet IDs from #ListZombies (show up most)
]
OTHER_PUPPET_IDS = [
    # "1",   # <- civilian / everything-else IDs (show up less often)
]
MILITARY_BIAS = 4            # a military type is this many times likelier than a non-military one

COUNT_PER_WAVE = 10          # TOTAL puppets per wave (randomly typed; mind MaxAllowedPuppets)
INTERVAL_SECONDS = 20        # seconds between waves while an event is live
EVENT_QUIET_TIMEOUT = 90     # no event kills for this long => event over, clear arena
POLL_SECONDS = 3             # how often to re-read the kill log
HEARTBEAT_SECONDS = 60       # how often to print the parsed-vs-flagged diagnostic
CLEANUP_RADIUS = 200         # metres for #DestroyZombiesWithinRadius on stop/reset

# Command templates. If live `#SpawnZombie` syntax differs on your build, fix it
# here once (verify via docs/live-verification-handoff.md). SCUM-RCON keeps the
# leading `#`. The brace is self-delimiting, so it is passed unquoted.
SPAWN_TEMPLATE = "#SpawnZombie {id} {count} Location {loc}"
CLEANUP_TEMPLATE = "#DestroyZombiesWithinRadius {radius} {loc}"

# Valve Source RCON packet types.
SERVERDATA_AUTH = 3
SERVERDATA_EXECCOMMAND = 2
SERVERDATA_AUTH_RESPONSE = 2
SERVERDATA_RESPONSE_VALUE = 0


class RconError(Exception):
    pass


class RconClient:
    """Minimal Valve Source RCON client (TCP). Auto-reconnects on demand."""

    def __init__(self, host, port, password, timeout=10):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.sock = None
        self._id = 0

    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)
        self._authenticate()

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _next_id(self):
        self._id += 1
        return self._id

    def _send_packet(self, pkt_id, pkt_type, body):
        payload = struct.pack("<ii", pkt_id, pkt_type) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(payload)) + payload)

    def _recv_exactly(self, n):
        chunks = []
        got = 0
        while got < n:
            chunk = self.sock.recv(n - got)
            if not chunk:
                raise RconError("connection closed by server")
            chunks.append(chunk)
            got += len(chunk)
        return b"".join(chunks)

    def _recv_packet(self):
        size = struct.unpack("<i", self._recv_exactly(4))[0]
        # A valid packet is at least 4 (id) + 4 (type) + 0 (body) + 2 (nulls) = 10.
        # Guard so a garbage/truncated frame raises RconError (caught + reconnected)
        # instead of a struct.error escaping and killing the watcher.
        if size < 10 or size > 4 * 1024 * 1024:
            raise RconError("bad RCON packet size: %d" % size)
        data = self._recv_exactly(size)
        try:
            pkt_id, pkt_type = struct.unpack("<ii", data[:8])
        except struct.error as e:
            raise RconError("malformed RCON packet: %s" % e)
        body = data[8:-2]  # strip the two trailing null bytes
        return pkt_id, pkt_type, body.decode("utf-8", errors="replace")

    def _authenticate(self):
        req_id = self._next_id()
        self._send_packet(req_id, SERVERDATA_AUTH, self.password)
        # Server may send an empty RESPONSE_VALUE first, then the AUTH_RESPONSE.
        while True:
            pkt_id, pkt_type, _ = self._recv_packet()
            if pkt_type == SERVERDATA_AUTH_RESPONSE:
                if pkt_id == -1:
                    raise RconError("RCON auth failed (bad password?)")
                return
            # otherwise keep reading until the auth response arrives

    def command(self, cmd):
        req_id = self._next_id()
        self._send_packet(req_id, SERVERDATA_EXECCOMMAND, cmd)
        pkt_id, _, body = self._recv_packet()
        if pkt_id != req_id:
            # Synchronous request/response, so this shouldn't happen — surface a
            # possible desync rather than silently trusting a stale reply.
            print("warning: RCON response id %s != request id %s (possible desync)"
                  % (pkt_id, req_id), file=sys.stderr)
        return body


# =====================================================================
#  Kill-log watcher — the native-event signal source.
# =====================================================================
_DECODER = json.JSONDecoder()


def _read_text(path):
    """Read a SCUM log file (UTF-16-LE, optional BOM) into decoded text."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\xff\xfe":
        raw = raw[2:]
    return raw.decode("utf-16-le", errors="replace")


def _complete_lines(text):
    """Split into lines, holding back a trailing line the server hasn't finished
    writing. If `text` does not end in a newline, its last line is mid-flush — we
    drop it this read so it isn't counted as 'seen' and then skipped once it
    finishes on a later read."""
    lines = text.splitlines()
    if text and text[-1] not in "\r\n":
        lines = lines[:-1]
    return lines


def _parse_kill_json(line):
    """A modern kill line is 'YYYY.MM.DD-HH.MM.SS: {json}'. Return the dict or None.
    Uses raw_decode so trailing content after the JSON object is tolerated."""
    brace = line.find("{")
    if brace == -1:
        return None  # old plaintext format or a non-kill line
    try:
        obj, _end = _DECODER.raw_decode(line[brace:])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _truthy(v):
    """True whether the flag is a JSON bool, the number 1, or a string form."""
    return v is True or v == 1 or (isinstance(v, str) and v.strip().lower() in ("true", "1", "yes"))


def _loc_brace(x, y, z):
    return "{X=%0.3f Y=%0.3f Z=%0.3f|P=0.000000 Y=0.000000 R=0.000000}" % (x, y, z)


def _loc_from(entity):
    sl = entity.get("ServerLocation")
    if not isinstance(sl, dict):
        return None
    try:
        return _loc_brace(float(sl["X"]), float(sl["Y"]), float(sl["Z"]))
    except (KeyError, TypeError, ValueError):
        return None


def _event_from_obj(obj):
    """If a parsed kill dict is an in-game-event kill, return {killer, victim, loc}."""
    killer = obj.get("Killer") or {}
    victim = obj.get("Victim") or {}
    if not (_truthy(killer.get("IsInGameEvent")) or _truthy(victim.get("IsInGameEvent"))):
        return None
    return {
        "killer": killer.get("ProfileName") or "?",   # tolerate JSON null
        "victim": victim.get("ProfileName") or "?",
        "loc": _loc_from(victim) or _loc_from(killer),
    }


def _event_kill(line):
    """Convenience: parse a raw line and return its event-kill dict or None."""
    obj = _parse_kill_json(line)
    return _event_from_obj(obj) if obj else None


class KillLogWatcher:
    """Tails the newest kill_<ts>.log in LOG_DIR, yielding only event kills."""

    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.current = None
        self.lines_seen = 0

    def _newest_kill_log(self):
        files = glob.glob(os.path.join(self.log_dir, "kill_*.log"))
        if not files:
            return None
        return max(files, key=os.path.getmtime)  # the live file is the most-recently written

    def prime(self):
        """Skip existing history so we only react to kills from now on."""
        self.current = self._newest_kill_log()
        if self.current:
            self.lines_seen = len(_complete_lines(_read_text(self.current)))

    def poll(self):
        """Return {events, parsed, flagged, located} for new lines since last poll.
        `parsed` counts new lines that looked like kill JSON, `flagged` how many
        were in-event, `located` how many of those yielded a spawn location."""
        empty = {"events": [], "parsed": 0, "flagged": 0, "located": 0}
        newest = self._newest_kill_log()
        if newest is None:
            return empty
        if newest != self.current:
            # Server bounced / log rotated: a fresh file — process it from the top.
            self.current = newest
            self.lines_seen = 0
        lines = _complete_lines(_read_text(self.current))
        if len(lines) < self.lines_seen:
            self.lines_seen = 0  # file was truncated/replaced under us
        new = lines[self.lines_seen:]
        self.lines_seen = len(lines)

        events = []
        parsed = flagged = located = 0
        for ln in new:
            obj = _parse_kill_json(ln)
            if not obj or not (isinstance(obj.get("Killer"), dict) or isinstance(obj.get("Victim"), dict)):
                continue
            parsed += 1
            ev = _event_from_obj(obj)
            if ev is None:
                continue
            flagged += 1
            if ev["loc"] is not None:
                located += 1
            events.append(ev)
        return {"events": events, "parsed": parsed, "flagged": flagged, "located": located}


# =====================================================================
#  Spawning / cleanup.
# =====================================================================
def _weighted_pool():
    """Flat list of puppet IDs weighted by preference: each military ID appears
    MILITARY_BIAS times, each other ID once, so random.choice over it draws a
    military-leaning mix. Empty if nothing is configured."""
    bias = MILITARY_BIAS if MILITARY_BIAS > 0 else 1
    pool = list(OTHER_PUPPET_IDS)
    for pid in MILITARY_PUPPET_IDS:
        pool.extend([pid] * bias)
    return pool


def _roll_wave():
    """Roll one wave: draw COUNT_PER_WAVE puppets at random from the military-
    weighted pool and tally them into [(id, count), ...] in first-seen order, so a
    wave is a random mix that leans military. Empty if no IDs are configured."""
    pool = _weighted_pool()
    if not pool:
        return []
    order = []
    tally = {}
    for _ in range(COUNT_PER_WAVE):
        pid = random.choice(pool)
        if pid not in tally:
            order.append(pid)
        tally[pid] = tally.get(pid, 0) + 1
    return [(pid, tally[pid]) for pid in order]


def _pool_summary():
    """Short human label for the configured pool (for the startup banner)."""
    return "mil=%s x%d, other=%s" % (
        MILITARY_PUPPET_IDS or "[]", MILITARY_BIAS, OTHER_PUPPET_IDS or "[]")


def fire_wave(rcon, loc):
    """Spawn one wave: COUNT_PER_WAVE puppets total at `loc`, each a random type
    drawn from the military-weighted pool (random horde, leaning military)."""
    for pid, n in _roll_wave():
        cmd = SPAWN_TEMPLATE.format(id=pid, count=n, loc=loc)
        resp = rcon.command(cmd)
        print("  spawn id=%s x%d -> %s" % (pid, n, resp.strip() or "ok"))


def clear_arena(rcon, loc):
    cmd = CLEANUP_TEMPLATE.format(radius=CLEANUP_RADIUS, loc=loc)
    resp = rcon.command(cmd)
    print("cleanup r=%d -> %s" % (CLEANUP_RADIUS, resp.strip() or "ok"))


def _connect_with_retry(rcon, attempts=5):
    """SCUM servers bounce often during events — retry the connect a few times."""
    for i in range(1, attempts + 1):
        try:
            rcon.connect()
            return True
        except (OSError, RconError) as e:
            print("connect attempt %d/%d failed: %s" % (i, attempts, e), file=sys.stderr)
            if i < attempts:
                time.sleep(min(2 * i, 10))
    return False


def _safe_call(rcon, fn, loc, what):
    """Run fn(rcon, loc), surviving a dropped connection with ONE quick reconnect.
    Returns True on success, False if it still failed. Never raises on RCON errors
    (so a mid-event drop can't kill the watcher); a single reconnect keeps the loop
    responsive instead of blocking on the full startup retry sequence."""
    try:
        fn(rcon, loc)
        return True
    except (OSError, RconError) as e:
        print("%s failed (%s); reconnecting once..." % (what, e), file=sys.stderr)
        try:
            rcon.connect()
            fn(rcon, loc)
            return True
        except (OSError, RconError) as e2:
            print("%s still failing (%s); skipping." % (what, e2), file=sys.stderr)
            return False


def _do_wave(rcon, loc, dry):
    if dry:
        rolled = _roll_wave()
        if not rolled:
            print("  [dry] (no puppet IDs configured — nothing to spawn)")
        for pid, n in rolled:
            print("  [dry] " + SPAWN_TEMPLATE.format(id=pid, count=n, loc=loc))
        return True
    return _safe_call(rcon, fire_wave, loc, "wave")


def _do_clear(rcon, loc, dry):
    if dry:
        print("  [dry] " + CLEANUP_TEMPLATE.format(radius=CLEANUP_RADIUS, loc=loc))
        return True
    return _safe_call(rcon, clear_arena, loc, "cleanup")


def _do_clear_all(rcon, locs, dry):
    """Clear every location a wave actually fired at this event, not just the last
    one — the spawn point moves with the fight, so the horde leaves puppets across
    multiple spots."""
    ok = True
    for loc in locs:
        if not _do_clear(rcon, loc, dry):
            ok = False
    return ok


# =====================================================================
#  Modes.
# =====================================================================
def run_event_watcher(rcon, dry_run=False):
    watcher = KillLogWatcher(LOG_DIR)
    watcher.prime()
    state = "IDLE"
    last_event_at = 0.0
    spawn_loc = ARENA_LOCATION
    next_wave_at = 0.0
    active_locs = []        # every distinct loc a wave fired at this event (for cleanup)
    wave_fail = 0
    warned_no_loc = False
    acc_parsed = acc_flagged = acc_located = 0
    last_heartbeat = time.monotonic()

    where = "the event location" if USE_EVENT_LOCATION else ("ARENA_LOCATION " + ARENA_LOCATION)
    print("Watching %s for native-event kills." % LOG_DIR)
    print("On an in-game-event kill: %d puppets/wave (random, military-leaning: %s) "
          "every %ds at %s; stop after %ds quiet."
          % (COUNT_PER_WAVE, _pool_summary(), INTERVAL_SECONDS, where, EVENT_QUIET_TIMEOUT))
    if dry_run:
        print("DRY RUN — not connecting to RCON; printing the commands instead.")
    print("Ctrl+C to stop (clears the arena if a horde is active).")

    try:
        while True:
            now = time.monotonic()
            try:
                res = watcher.poll()
            except OSError as e:
                print("log read failed (%s); will retry." % e, file=sys.stderr)
                res = {"events": [], "parsed": 0, "flagged": 0, "located": 0}

            acc_parsed += res["parsed"]
            acc_flagged += res["flagged"]
            acc_located += res["located"]

            for k in res["events"]:
                # The horde starts on the FIRST event kill, and the spawn point
                # MOVES with the fight: each later event kill relocates it to that
                # kill's spot. Event identity isn't tracked, so a brand-new event's
                # first kill pulls the horde over too (follow-new-events). Every
                # flagged kill is inside SCUM's deathmatch arena, so the swarm
                # tracks the action without leaking onto the open map.
                if k["loc"] is None and USE_EVENT_LOCATION and not warned_no_loc:
                    print("warning: event kill had no parseable ServerLocation; using "
                          "ARENA_LOCATION. If this persists, verify the ServerLocation "
                          "field name (see live-verification-handoff.md).", file=sys.stderr)
                    warned_no_loc = True
                loc = k["loc"] if (USE_EVENT_LOCATION and k["loc"]) else ARENA_LOCATION
                last_event_at = now
                spawn_loc = loc
                if state == "IDLE":
                    print("[event] in-game-event kill (%s -> %s) -> starting horde at %s"
                          % (k["killer"], k["victim"], loc))
                    state = "ACTIVE"
                    active_locs = []
                    if _do_wave(rcon, spawn_loc, dry_run):
                        active_locs.append(spawn_loc)
                        wave_fail = 0
                    else:
                        wave_fail += 1
                        print("WARNING: first wave failed (RCON down?); horde stalled, "
                              "retrying next interval.", file=sys.stderr)
                    next_wave_at = now + INTERVAL_SECONDS

            if state == "ACTIVE":
                quiet = (now - last_event_at) > EVENT_QUIET_TIMEOUT
                if not quiet and now >= next_wave_at:
                    if _do_wave(rcon, spawn_loc, dry_run):
                        if spawn_loc not in active_locs:
                            active_locs.append(spawn_loc)
                        wave_fail = 0
                    else:
                        wave_fail += 1
                        print("WARNING: wave failed %dx (RCON down?); horde stalled, "
                              "retrying next interval." % wave_fail, file=sys.stderr)
                    next_wave_at = now + INTERVAL_SECONDS
                if quiet:
                    locs = active_locs or [spawn_loc]
                    print("[event] quiet for %ds -> horde over, clearing arena (%d spot(s))."
                          % (EVENT_QUIET_TIMEOUT, len(locs)))
                    if _do_clear_all(rcon, locs, dry_run):
                        state = "IDLE"
                        active_locs = []
                        warned_no_loc = False
                        wave_fail = 0
                    else:
                        print("cleanup incomplete (RCON down?); staying active to retry.",
                              file=sys.stderr)

            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                if acc_parsed > 0 or dry_run:
                    msg = ("[watch] last %ds: parsed %d kill line(s), %d event-flagged, "
                           "%d located (state=%s)"
                           % (HEARTBEAT_SECONDS, acc_parsed, acc_flagged, acc_located, state))
                    if acc_parsed > 0 and acc_flagged == 0:
                        msg += ("  <- kills seen but NONE flagged in-event; if an event IS "
                                "running, check the IsInGameEvent field name "
                                "(see live-verification-handoff.md).")
                    print(msg)
                acc_parsed = acc_flagged = acc_located = 0
                last_heartbeat = now

            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        print("\nstopping.")
        if state == "ACTIVE":
            _do_clear_all(rcon, active_locs or [spawn_loc], dry_run)
        return 0


def _check_config(need_rcon, need_puppets, need_log):
    problems = []
    if need_rcon and not RCON_PASSWORD:
        problems.append("RCON_PASSWORD is empty — set it to your SCUM-RCON password.")
    if need_puppets and not (MILITARY_PUPPET_IDS or OTHER_PUPPET_IDS):
        problems.append("No puppet IDs configured — add real IDs from `#ListZombies` "
                        "to MILITARY_PUPPET_IDS and/or OTHER_PUPPET_IDS.")
    if need_log:
        if not LOG_DIR:
            problems.append("LOG_DIR is empty — set it to …\\SCUM\\Saved\\SaveFiles\\Logs.")
        elif not os.path.isdir(LOG_DIR):
            problems.append("LOG_DIR not found: %s" % LOG_DIR)
    # ARENA_LOCATION is used by --once/--reset and as the watch-mode fallback, so
    # it must always be a valid brace regardless of USE_EVENT_LOCATION.
    if "X=" not in ARENA_LOCATION:
        problems.append("ARENA_LOCATION doesn't look like a `#Location` brace (needs X=..).")
    if problems:
        print("CONFIG NOT READY:", file=sys.stderr)
        for p in problems:
            print("  - %s" % p, file=sys.stderr)
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description="SCUM event-driven arena horde loop.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true",
                   help="fire one wave at ARENA_LOCATION and exit")
    g.add_argument("--reset", action="store_true",
                   help="clear ARENA_LOCATION and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command(s) instead of touching RCON (works in any mode)")
    args = ap.parse_args()
    dry = args.dry_run

    if args.reset or args.once:
        if not _check_config(need_rcon=not dry, need_puppets=args.once, need_log=False):
            return 2
        if dry:
            if args.reset:
                print("[dry] " + CLEANUP_TEMPLATE.format(radius=CLEANUP_RADIUS, loc=ARENA_LOCATION))
            else:
                for pid, n in _roll_wave():
                    print("[dry] " + SPAWN_TEMPLATE.format(id=pid, count=n, loc=ARENA_LOCATION))
            return 0
        rcon = RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
        if not _connect_with_retry(rcon):
            print("could not connect to RCON — check host/port/password and that "
                  "the SCUM-RCON mod is running.", file=sys.stderr)
            return 1
        try:
            if args.reset:
                clear_arena(rcon, ARENA_LOCATION)
            else:
                fire_wave(rcon, ARENA_LOCATION)
            return 0
        finally:
            rcon.close()

    # Default: event-driven watch mode.
    if not _check_config(need_rcon=not dry, need_puppets=True, need_log=True):
        return 2
    rcon = None
    if not dry:
        rcon = RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
        if not _connect_with_retry(rcon):
            print("could not connect to RCON — check host/port/password and that "
                  "the SCUM-RCON mod is running.", file=sys.stderr)
            return 1
    try:
        return run_event_watcher(rcon, dry_run=dry)
    finally:
        if rcon is not None:
            rcon.close()


if __name__ == "__main__":
    sys.exit(main())
