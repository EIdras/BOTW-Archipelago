"""PopTracker, told on this computer where Link is, which the room does not know: the region he
stands in and his position in the MainField, for the map's view of a region and Link's mark
(tools/build_poptracker.py, tools/poptracker/scripts/uat.lua). Nothing goes through the room.

UAT, Universal Auto-Tracking (github.com/black-sliver/UAT, PROTOCOL.md): a websocket server on
this computer, at PORTS[0] or else PORTS[1], that PopTracker connects to by itself, again and
again while there is none. A message is a JSON array of commands: Info as a tracker connects,
a Var for each variable when it asks with Sync, then a Var for each one that changes.
"""
from __future__ import annotations

import json
from typing import Callable

PORTS = (65399, 44444)          # the protocol's port, and its fallback
HOSTS = ("localhost", "127.0.0.1")
PROTOCOL = 0
NAME = "Breath of the Wild Archipelago"
FEED_SECONDS = 0.5              # Link's position read so often (runtime._feed_loop)
_MISSING = object()


class UatServer:
    """set(**values) sends the variables that changed to every tracker connected."""

    def __init__(self, version: str = "", log: Callable[[str], None] = print, ports=PORTS, hosts=HOSTS):
        self.version, self.log, self.ports, self.hosts = version, log, tuple(ports), tuple(hosts)
        self.values: dict = {}
        self.peers: set = set()
        self.runner = None
        self.port = None

    async def start(self) -> int | None:
        """The port listened at; None when neither is free (logged: the session goes on)."""
        from aiohttp import web
        app = web.Application()
        app.router.add_get("/", self._connection)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        failure = None
        for port in self.ports:
            for host in self.hosts:
                try:
                    await web.TCPSite(runner, host, port).start()
                except OSError as exc:
                    failure = exc
                    continue
                self.runner, self.port = runner, port
                return port
        await runner.cleanup()
        self.log(f"PopTracker (UAT): no port to listen at ({', '.join(map(str, self.ports))}): {failure}")
        return None

    def info(self) -> dict:
        return {"cmd": "Info", "name": NAME, "version": self.version, "protocol": PROTOCOL,
                "features": [], "slots": []}

    def replies(self, commands) -> list[dict]:
        """What a tracker's commands are answered with."""
        out = []
        for command in commands if isinstance(commands, list) else [commands]:
            name = command.get("cmd") if isinstance(command, dict) else None
            if name == "Sync":
                out += self.vars(self.values)
            else:
                out.append({"cmd": "ErrorReply", "name": str(name), "reason": "unknown cmd"})
        return out

    @staticmethod
    def vars(values: dict) -> list[dict]:
        return [{"cmd": "Var", "name": name, "value": value} for name, value in values.items()]

    async def _connection(self, request):
        from aiohttp import WSMsgType, web
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        self.peers.add(socket)
        try:
            await socket.send_str(json.dumps([self.info()]))
            async for message in socket:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    commands = json.loads(message.data)
                except ValueError:
                    break                       # the protocol: not JSON, the connection closed
                replies = self.replies(commands)
                if replies:
                    await socket.send_str(json.dumps(replies))
        finally:
            self.peers.discard(socket)
        return socket

    async def set(self, **values) -> None:
        changed = {name: value for name, value in values.items() if self.values.get(name, _MISSING) != value}
        if not changed:
            return
        self.values.update(changed)
        packet = json.dumps(self.vars(changed))
        for socket in list(self.peers):
            try:
                await socket.send_str(packet)
            except Exception:  # noqa: BLE001 - a tracker gone: it connects again by itself
                self.peers.discard(socket)

    async def close(self) -> None:
        for socket in list(self.peers):
            try:
                await socket.close()
            except Exception:  # noqa: BLE001 - closing anyway
                pass
        self.peers.clear()
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = self.port = None


class RoomThrottle:
    """Link's whereabouts for Universal Tracker's map, which reads them from the room's data
    storage (botw_world/tracker.py, ROOM_KEY): sent again only once he moved ROOM_METRES or
    changed region, and never sooner than ROOM_SECONDS after the last."""

    def __init__(self, clock=None):
        import time
        self.clock = clock or time.monotonic
        self.last, self.at = None, None

    def due(self, values: dict) -> bool:
        if self.last is None:
            return True
        if self.clock() - self.at < ROOM_SECONDS:
            return False
        moved = ((values["x"] - self.last["x"]) ** 2 + (values["z"] - self.last["z"]) ** 2) ** 0.5
        turned = (abs((values["heading"] - self.last["heading"] + 180) % 360 - 180)
                  if "heading" in values and "heading" in self.last else 0)
        return moved >= ROOM_METRES or turned >= ROOM_DEGREES or values["region"] != self.last["region"]

    def sent(self, values: dict) -> None:
        self.last, self.at = dict(values), self.clock()


ROOM_KEY = "botw_link_{team}_{player}"      # botw_world/tracker.py: Universal Tracker's map
ROOM_METRES, ROOM_SECONDS = 50.0, 2.0
ROOM_DEGREES = 22.5     # a turn of his mark's (botw_world/tracker.py ARROWS)


def room_set(team: int, slot: int, values: dict) -> dict:
    return {"cmd": "Set", "key": ROOM_KEY.format(team=team, player=slot), "default": {}, "want_reply": False,
            "operations": [{"operation": "replace", "value": dict(values)}]}


def whereabouts(field: bool, position, areas, heading: float | None = None) -> dict | None:
    """The variables of Link in the MainField (in_field()): his region (areas: region_border.Areas,
    "" between two), his position, whole metres on the map's plane, and where he faces, whole
    degrees (FieldReader.heading); None out of it, the last ones kept (a shrine, a Divine Beast:
    where he went in)."""
    if not field or position is None:
        return None
    x, z = position[0], position[2]
    values = {"region": areas.region_at(x, z) or "", "x": round(x), "z": round(z)}
    if heading is not None:
        values["heading"] = round(heading) % 360
    return values
