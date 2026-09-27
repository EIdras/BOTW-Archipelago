"""Archipelago protocol support used by the BOTW memory bridge."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from . import GAME_NAME


@dataclass(frozen=True)
class NetworkItem:
    item: int
    location: int
    player: int
    flags: int


@dataclass(frozen=True)
class LocationInfo:
    item: int
    location: int
    player: int
    flags: int


@dataclass(frozen=True)
class APMessage:
    text: str
    kind: str
    nodes: tuple[dict, ...]
    # PrintJSON fields, when the server gives them: slot receiving the item
    # (ItemSend, Hint), slot whose world holds it (the item's player), author
    # of a chat line.
    receiving: int | None = None
    sender: int | None = None
    slot: int | None = None


@dataclass(frozen=True)
class DeathLinkEvent:
    timestamp: float
    source: str
    cause: str


def _slot(value) -> int | None:
    return value if type(value) is int else None


def decode_network_item(raw) -> NetworkItem:
    if isinstance(raw, dict):
        return NetworkItem(int(raw["item"]), int(raw["location"]),
                           int(raw["player"]), int(raw.get("flags", 0)))
    return NetworkItem(*(int(value) for value in raw[:4]))


def decode_location_info(raw) -> LocationInfo:
    item = decode_network_item(raw)
    return LocationInfo(item.item, item.location, item.player, item.flags)


def server_url(address: str) -> str:
    if "://" not in address:
        address = "ws://" + address
    parsed = urlparse(address)
    if parsed.scheme not in ("ws", "wss") or not parsed.netloc:
        raise ValueError(f"invalid Archipelago address: {address}")
    return address


def server_urls(address: str) -> list[str]:
    """The URLs to try: the address itself when it names its scheme, else the
    secure one first, then the plain one, as Archipelago's own client does
    (rooms on archipelago.gg answer wss://, a local server ws://)."""
    if "://" in address:
        return [server_url(address)]
    return [server_url("wss://" + address), server_url("ws://" + address)]


class ArchipelagoClient:
    def __init__(self, address: str, slot_name: str, password: str | None = None,
                 game: str = GAME_NAME, log=print):
        self.urls = server_urls(address)
        self.url = self.urls[0]
        self.slot_name = slot_name
        self.password = password
        self.game = game
        self.log = log
        self.session = self.websocket = self.reader_task = None
        self.connected = False
        self.connected_event = asyncio.Event()
        self.data_package_event = asyncio.Event()
        self.scout_event = asyncio.Event()
        self.seed_name = None
        self.slot = None
        self.team = None
        self.slot_data: dict = {}
        self.item_name_by_id: dict[int, str] = {}
        self.item_names_by_game: dict[str, dict[int, str]] = {}
        self.location_names_by_game: dict[str, dict[int, str]] = {}
        self.items_synchronized = False
        self._initial_received_items_seen = False
        self.location_id_by_name: dict[str, int] = {}
        self.location_name_by_id: dict[int, str] = {}
        self.checked_locations: set[int] = set()
        # Unchecked locations of this slot (Connected); with checked_locations,
        # the locations that exist in the seed (options may leave some out).
        self.missing_locations: set[int] | None = None     # None: not sent by the server
        self.received_items: dict[int, NetworkItem] = {}
        self.scouted_locations: dict[int, LocationInfo] = {}
        self.players = {}
        self.slot_info = {}
        self.refused_reason = None
        self.messages: asyncio.Queue[APMessage] = asyncio.Queue()
        self.deathlinks: asyncio.Queue[DeathLinkEvent] = asyncio.Queue()
        self.death_link_enabled = False
        self.last_death_link = 0.0
        self._scout_expected: set[int] = set()

    @property
    def data_package_checksum(self) -> str:
        payload = {
            "game": self.game,
            "items": self.item_name_by_id,
            "locations": self.location_id_by_name,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    async def connect(self, timeout: float = 15.0):
        import aiohttp
        await self.close()
        self.seed_name = self.slot = self.team = None
        self.slot_data.clear()
        self.received_items.clear()
        self.scouted_locations.clear()
        self.items_synchronized = False
        self._initial_received_items_seen = False
        self.checked_locations.clear()
        self.missing_locations = None
        self.connected_event.clear()
        self.data_package_event.clear()
        self.scout_event.clear()
        self._scout_expected.clear()
        self.refused_reason = None
        self.session = aiohttp.ClientSession()
        failure = None
        for url in self.urls:
            try:
                # aiohttp otherwise defaults to compress=0 and emits AP's deprecation
                # warning. 15 negotiates RFC 7692 permessage-deflate.
                self.websocket = await self.session.ws_connect(
                    url, heartbeat=30, compress=15, max_msg_size=64 * 1024 * 1024)
            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as exc:
                failure = exc
                continue
            # The scheme that answered is kept for the reconnections.
            self.url, self.urls = url, [url]
            break
        else:
            raise failure
        self.reader_task = asyncio.create_task(self._reader(), name="AP reader")
        await asyncio.wait_for(self.connected_event.wait(), timeout)
        if self.refused_reason:
            raise RuntimeError("connection refused: " + ", ".join(self.refused_reason))
        if not self.connected:
            raise ConnectionError("Archipelago connection closed before authentication")
        return self

    async def close(self):
        self.connected = False
        task, self.reader_task = self.reader_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if self.websocket:
            await self.websocket.close()
        if self.session:
            await self.session.close()
        self.websocket = self.session = None

    async def send(self, *commands: dict):
        if not self.websocket or self.websocket.closed:
            raise ConnectionError("Archipelago server disconnected")
        await self.websocket.send_str(json.dumps(list(commands), separators=(",", ":")))

    async def _reader(self):
        import aiohttp
        try:
            async for message in self.websocket:
                if message.type == aiohttp.WSMsgType.TEXT:
                    for packet in json.loads(message.data):
                        await self._packet(packet)
                elif message.type in (aiohttp.WSMsgType.CLOSED,
                                       aiohttp.WSMsgType.CLOSE,
                                       aiohttp.WSMsgType.ERROR):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.log(f"Archipelago read interrupted: {exc}")
        finally:
            self.connected = False
            self.connected_event.set()

    async def _packet(self, packet: dict):
        command = packet.get("cmd")
        if command == "RoomInfo":
            self.seed_name = packet.get("seed_name", "unknown-seed")
            await self.send({
                "cmd": "Connect",
                "password": self.password,
                "game": self.game,
                "name": self.slot_name,
                "uuid": str(uuid.getnode()),
                "version": {"major": 0, "minor": 6, "build": 7,
                            "class": "Version"},
                "items_handling": 7,
                "tags": ["AP"],
                "slot_data": True,
            })
        elif command == "ConnectionRefused":
            self.refused_reason = list(packet.get("errors", ["unknown reason"]))
            self.connected_event.set()
        elif command == "Connected":
            self.team = int(packet["team"])
            self.slot = int(packet["slot"])
            self.slot_data = dict(packet.get("slot_data") or {})
            self.checked_locations = {int(x) for x in packet.get("checked_locations", [])}
            self.missing_locations = ({int(x) for x in packet["missing_locations"]}
                                      if "missing_locations" in packet else None)
            self.players = {}
            for player in packet.get("players", []):
                if isinstance(player, dict):
                    slot = int(player["slot"])
                    label = player.get("alias") or player.get("name") or str(slot)
                else:
                    slot = int(player[1])
                    label = player[2] or player[3] or str(slot)
                self.players[slot] = label
            self.slot_info = {int(k): v for k, v in packet.get("slot_info", {}).items()}
            self.connected = True
            self.death_link_enabled = bool(self.slot_data.get("death_link", False))
            self.log(f"connected to {self.seed_name}, slot {self.slot_name} ({self.slot})")
            self.log("DeathLink: " + ("actif" if self.death_link_enabled else
                                      "off in this seed"))
            # A BOTW location can contain an item belonging to any game.
            games = {self.game}
            for info in self.slot_info.values():
                game = info.get("game") if isinstance(info, dict) else info[1]
                if game:
                    games.add(game)
            commands = [{"cmd": "GetDataPackage", "games": sorted(games)}]
            if self.death_link_enabled:
                commands.append({"cmd": "ConnectUpdate", "tags": ["AP", "DeathLink"]})
            await self.send(*commands)
            self.connected_event.set()
        elif command == "DataPackage":
            games = packet.get("data", {}).get("games", {})
            for game, package in games.items():
                self.item_names_by_game[game] = {
                    int(value): name for name, value in package.get("item_name_to_id", {}).items()}
                self.location_names_by_game[game] = {
                    int(value): name for name, value in package.get("location_name_to_id", {}).items()}
            data = games.get(self.game)
            if data:
                self.item_name_by_id = {int(value): name for name, value in
                                        data.get("item_name_to_id", {}).items()}
                self.location_id_by_name = {name: int(value) for name, value in
                                            data.get("location_name_to_id", {}).items()}
                self.location_name_by_id = {
                    value: name for name, value in self.location_id_by_name.items()}
                self.log(f"data package: {len(self.item_name_by_id)} items, "
                         f"{len(self.location_id_by_name)} locations")
                # AP 0.6.7 sends Connected + optional ReceivedItems in order,
                # then answers GetDataPackage. An empty slot gets no
                # ReceivedItems packet at all. At this barrier, no initial
                # packet means the empty inventory is complete.
                if self.connected and not self._initial_received_items_seen:
                    self.items_synchronized = True
                self.data_package_event.set()
        elif command == "ReceivedItems":
            self._initial_received_items_seen = True
            start = int(packet.get("index", 0))
            if start < 0:
                raise ValueError("negative ReceivedItems index")
            incoming = [decode_network_item(raw) for raw in packet.get("items", [])]
            if start == 0:
                self.received_items.clear()
                self.items_synchronized = True
            elif (not self.items_synchronized or start > len(self.received_items)
                  or any(self.received_items.get(start + offset, item) != item
                         for offset, item in enumerate(incoming))):
                self.items_synchronized = False
                await self.sync()
                return
            for offset, item in enumerate(incoming):
                self.received_items[start + offset] = item
        elif command == "LocationInfo":
            for raw in packet.get("locations", []):
                info = decode_location_info(raw)
                self.scouted_locations[info.location] = info
            if self._scout_expected.issubset(self.scouted_locations):
                self.scout_event.set()
        elif command == "RoomUpdate":
            self.checked_locations.update(int(x) for x in packet.get("checked_locations", []))
            for player in packet.get("players", []):
                if isinstance(player, dict):
                    self.players[int(player["slot"])] = player.get("alias") or player["name"]
                else:
                    self.players[int(player[1])] = player[2] or player[3]
        elif command == "PrintJSON":
            nodes = tuple(dict(part) for part in packet.get("data", []))
            text = "".join(self.render_node(part) for part in nodes)
            if text:
                item = packet.get("item")
                sender = (decode_network_item(item).player
                          if isinstance(item, (dict, list)) else None)
                message = APMessage(text, str(packet.get("type", "PrintJSON")), nodes,
                                    _slot(packet.get("receiving")), sender,
                                    _slot(packet.get("slot")))
                await self.messages.put(message)
                self.log(text)
        elif command == "Bounced" and "DeathLink" in packet.get("tags", []):
            data = packet.get("data") or {}
            timestamp = float(data.get("time", 0.0))
            if timestamp > self.last_death_link:
                self.last_death_link = timestamp
                event = DeathLinkEvent(
                    timestamp,
                    str(data.get("source") or "another player"),
                    str(data.get("cause") or "DeathLink"))
                await self.deathlinks.put(event)

    async def scout_locations(self, names: list[str], timeout: float = 15.0):
        unresolved = [name for name in names if name not in self.location_id_by_name]
        if unresolved:
            raise ValueError("locations to scout missing: " + ", ".join(unresolved))
        ids = [self.location_id_by_name[name] for name in names]
        self._scout_expected = set(ids)
        self.scout_event.clear()
        await self.send({"cmd": "LocationScouts", "locations": ids,
                         "create_as_hint": 0})
        if not self._scout_expected.issubset(self.scouted_locations):
            await asyncio.wait_for(self.scout_event.wait(), timeout)
        return {location_id: self.scouted_locations[location_id] for location_id in ids}

    @property
    def seed_locations(self) -> set[int]:
        """Locations of this seed; empty when the server did not say (no filtering)."""
        if self.missing_locations is None:
            return set()
        return self.checked_locations | self.missing_locations

    async def send_hints(self, location_ids: list[int]):
        """Hint these locations (LocationScouts create_as_hint=2: a hint only
        for what is not already known, announced once)."""
        if location_ids:
            await self.send({"cmd": "LocationScouts", "locations": sorted(location_ids),
                             "create_as_hint": 2})

    async def send_checks(self, names: list[str]) -> list[str]:
        unresolved = [name for name in names if name not in self.location_id_by_name]
        ids = [self.location_id_by_name[name] for name in names
               if name in self.location_id_by_name]
        if ids:
            # Do not add these to checked_locations here. Only Connected and
            # RoomUpdate are acknowledgements; reconnect can safely resend.
            await self.send({"cmd": "LocationChecks", "locations": ids})
        return unresolved

    async def send_goal(self):
        await self.send({"cmd": "StatusUpdate", "status": 30})

    async def say(self, text: str):
        await self.send({"cmd": "Say", "text": text})

    async def send_death(self, cause: str):
        if not self.death_link_enabled:
            return
        timestamp = time.time()
        self.last_death_link = max(self.last_death_link, timestamp)
        await self.send({
            "cmd": "Bounce", "tags": ["DeathLink"],
            "data": {"time": timestamp, "source": self.slot_name, "cause": cause},
        })
        self.log(f"DeathLink sent: {cause}")

    async def sync(self):
        await self.send({"cmd": "Sync"})

    def item_name(self, item: NetworkItem | LocationInfo) -> str | None:
        if isinstance(item, LocationInfo):
            game = self.player_game(item.player)
            return self.item_names_by_game.get(game, self.item_name_by_id if game == self.game else {}).get(item.item)
        return self.item_name_by_id.get(item.item)

    def player_game(self, player: int) -> str:
        if player == self.slot:
            return self.game
        info = self.slot_info.get(player, {})
        return (info.get("game", "unknown game") if isinstance(info, dict)
                else info[1] if len(info) > 1 else "unknown game")

    def render_node(self, node: dict) -> str:
        text = str(node.get("text", ""))
        kind = node.get("type")
        if kind not in {"player_id", "item_id", "location_id"}:
            return text
        try:
            value = int(text)
        except ValueError:
            return text
        if kind == "player_id":
            return self.players.get(value, f"slot {value}")
        game = self.player_game(int(node.get("player", self.slot or 0)))
        maps = self.item_names_by_game if kind == "item_id" else self.location_names_by_game
        return maps.get(game, {}).get(value, text)

    def location_name(self, location_id: int) -> str | None:
        return self.location_name_by_id.get(location_id)

    def sender(self, item: NetworkItem | LocationInfo) -> tuple[str, str]:
        name = self.players.get(item.player, f"slot {item.player}")
        info = self.slot_info.get(item.player, {})
        if isinstance(info, dict):
            game = info.get("game", "unknown game")
        else:
            game = info[1] if len(info) > 1 else "unknown game"
        return name, game
