#!/usr/bin/env python3
"""Layer 1b — the arena horde loop (SCUM COD-Zombies deathmatch event).

This is what actually makes the horde, and it is the ONLY part of the design
that puts puppets at a chosen location. SCUM has no config/zone knob to make a
horde appear at one spot, but the admin/console command `#SpawnZombie` takes an
optional Location argument. This script connects to the server over RCON
(SCUM-RCON Nexus mod, standard Valve Source RCON) and, on an interval, fires
`#SpawnZombie <id> <count> Location <arena>` so puppets keep pouring into the
arena and NOWHERE ELSE on the map. The rest of the map's Encounter Manager
stays vanilla (see config/serversettings-horde-block.ini).

  - No third-party deps. Pure stdlib (socket + struct + argparse).
  - Private server only. Never point this at an official server.

USAGE
  python tools/arena_horde_loop.py            # run the wave loop until Ctrl+C
  python tools/arena_horde_loop.py --once     # fire one wave and exit
  python tools/arena_horde_loop.py --reset    # clear the arena and exit
  Ctrl+C during the loop also clears the arena on the way out.

BEFORE YOU RUN (fill in the CONFIG block below):
  1. Enable RCON on the server (SCUM-RCON mod) and set RCON_PORT + RCON_PASSWORD.
  2. Stand in the middle of your arena in-game, run `#Location`, Ctrl+C the
     brace it prints, and paste it into ARENA_LOCATION. Capture the WHOLE brace
     (X/Y/Z + P/Y/R), not just X/Y.
  3. Run `#ListZombies` in-game and put the puppet TYPE IDs you want into
     PUPPET_IDS. Difficulty is arena-only now (the global HP/speed multipliers
     are back at 1.0), so pick TOUGHER puppet types here if you want tanky/fast
     enemies — that buffs only what spawns in the arena.
"""
import argparse
import socket
import struct
import sys
import time

# =====================================================================
#  CONFIG — edit these for your server, then run.
# =====================================================================
RCON_HOST = "127.0.0.1"      # run this on the server box (or its LAN/tailnet IP)
RCON_PORT = 27015            # SCUM-RCON port from the server config (verify!)
RCON_PASSWORD = ""           # SCUM-RCON password — REQUIRED, set this

# The arena center, as SCUM's `#Location` brace (X/Y/Z world | P/Y/R rotation).
# Capture it in-game with `#Location` while standing in the arena. Example shape:
ARENA_LOCATION = "{X=-152157.266 Y=287169.562 Z=69696.133|P=0.000000 Y=0.000000 R=0.000000}"

# Puppet TYPE IDs to spawn each wave (from `#ListZombies`). Mix types to taste;
# pick tougher/faster types here for arena-only difficulty. The loop fires one
# spawn command per ID per wave.
PUPPET_IDS = [
    # "0",   # <- replace with real IDs from #ListZombies, e.g. a runner + a heavy
    # "1",
]

COUNT_PER_WAVE = 10          # puppets spawned per ID, per wave (mind MaxAllowedPuppets)
INTERVAL_SECONDS = 20        # seconds between waves
CLEANUP_RADIUS = 200         # metres for #DestroyZombiesWithinRadius on reset/exit

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
        data = self._recv_exactly(size)
        pkt_id, pkt_type = struct.unpack("<ii", data[:8])
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
        _, _, body = self._recv_packet()
        return body


def _check_config():
    problems = []
    if not RCON_PASSWORD:
        problems.append("RCON_PASSWORD is empty — set it to your SCUM-RCON password.")
    if not PUPPET_IDS:
        problems.append("PUPPET_IDS is empty — add real IDs from `#ListZombies`.")
    if "X=" not in ARENA_LOCATION:
        problems.append("ARENA_LOCATION doesn't look like a `#Location` brace.")
    if problems:
        print("CONFIG NOT READY:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return False
    return True


def fire_wave(rcon):
    """Spawn one wave: COUNT_PER_WAVE of each puppet ID at the arena."""
    for pid in PUPPET_IDS:
        cmd = SPAWN_TEMPLATE.format(id=pid, count=COUNT_PER_WAVE, loc=ARENA_LOCATION)
        resp = rcon.command(cmd)
        print(f"  spawn id={pid} x{COUNT_PER_WAVE} -> {resp.strip() or 'ok'}")


def clear_arena(rcon):
    cmd = CLEANUP_TEMPLATE.format(radius=CLEANUP_RADIUS, loc=ARENA_LOCATION)
    resp = rcon.command(cmd)
    print(f"cleanup r={CLEANUP_RADIUS} -> {resp.strip() or 'ok'}")


def _connect_with_retry(rcon, attempts=5):
    """SCUM servers bounce often during events — retry the connect a few times."""
    for i in range(1, attempts + 1):
        try:
            rcon.connect()
            return True
        except (OSError, RconError) as e:
            print(f"connect attempt {i}/{attempts} failed: {e}", file=sys.stderr)
            if i < attempts:
                time.sleep(min(2 * i, 10))
    return False


def run_loop(rcon):
    print(f"Arena horde loop: every {INTERVAL_SECONDS}s, {COUNT_PER_WAVE} per id "
          f"{PUPPET_IDS} at {ARENA_LOCATION}")
    print("Ctrl+C to stop (clears the arena on the way out).")
    try:
        while True:
            try:
                fire_wave(rcon)
            except (OSError, RconError) as e:
                print(f"wave failed ({e}); reconnecting...", file=sys.stderr)
                if not _connect_with_retry(rcon):
                    print("could not reconnect — giving up.", file=sys.stderr)
                    return 1
                continue
            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nstopping — clearing the arena.")
        try:
            clear_arena(rcon)
        except (OSError, RconError) as e:
            print(f"cleanup failed: {e}", file=sys.stderr)
        return 0


def main():
    ap = argparse.ArgumentParser(description="SCUM arena horde RCON loop.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="fire one wave and exit")
    g.add_argument("--reset", action="store_true", help="clear the arena and exit")
    args = ap.parse_args()

    # --reset only needs the location; --once / loop need spawn config too.
    if not RCON_PASSWORD or "X=" not in ARENA_LOCATION or (not args.reset and not PUPPET_IDS):
        if not _check_config():
            return 2

    rcon = RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
    if not _connect_with_retry(rcon):
        print("could not connect to RCON — check host/port/password and that the "
              "SCUM-RCON mod is running.", file=sys.stderr)
        return 1

    try:
        if args.reset:
            clear_arena(rcon)
            return 0
        if args.once:
            fire_wave(rcon)
            return 0
        return run_loop(rcon)
    finally:
        rcon.close()


if __name__ == "__main__":
    sys.exit(main())
