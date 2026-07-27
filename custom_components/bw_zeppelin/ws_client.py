from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Callable

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, PROPERTY_AUDIOTILE, PROPERTY_AUDIOTILE_ARTWORK

_LOGGER = logging.getLogger(__name__)

RECONNECT_INTERVAL = 10
MAX_RECONNECT_INTERVAL = 120


class BwZeppelinWebSocket:

    def __init__(self, host: str) -> None:
        self._host = host
        self._url = f"wss://{host}:{DEFAULT_PORT}/messages"
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        self._hass: HomeAssistant | None = None
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._audiotile_callbacks: list[Callable[[dict], None]] = []
        self._artwork_callbacks: list[Callable[[dict], None]] = []
        self._volume_callbacks: list[Callable[[dict], None]] = []

    def register_audiotile_callback(self, callback: Callable[[dict], None]) -> Callable[[], None]:
        self._audiotile_callbacks.append(callback)
        return lambda: self._audiotile_callbacks.remove(callback)

    def register_artwork_callback(self, callback: Callable[[dict], None]) -> Callable[[], None]:
        self._artwork_callbacks.append(callback)
        return lambda: self._artwork_callbacks.remove(callback)

    def register_volume_callback(self, callback: Callable[[dict], None]) -> Callable[[], None]:
        self._volume_callbacks.append(callback)
        return lambda: self._volume_callbacks.remove(callback)

    def start(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._stop_event.clear()
        self._task = hass.async_create_task(self._run())

    def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run(self) -> None:
        backoff = RECONNECT_INTERVAL
        while not self._stop_event.is_set():
            try:
                await self._listen()
                backoff = RECONNECT_INTERVAL
            except asyncio.CancelledError:
                return
            except Exception:
                _LOGGER.debug("WebSocket error, reconnecting in %ss", backoff, exc_info=True)

            if self._stop_event.is_set():
                return
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, MAX_RECONNECT_INTERVAL)

    async def _listen(self) -> None:
        session = async_get_clientsession(self._hass, verify_ssl=False)
        ws = await session.ws_connect(
            self._url, ssl=self._ssl_context, heartbeat=30, autoclose=True
        )
        try:
            _LOGGER.debug("WebSocket connected to %s", self._host)
            async for msg in ws:
                if self._stop_event.is_set():
                    return
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._handle_message(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        finally:
            if not ws.closed:
                await ws.close()

    def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        method = (
            data.get("payload", {})
            .get("args", {})
            .get("message", {})
            .get("method", {})
        )
        name = method.get("name")
        params = method.get("parameters", {})
        prop = params.get("property", "")

        if prop == PROPERTY_AUDIOTILE and name in ("property_changed", "success"):
            value = params.get("value", {})
            tile = next(iter(value.values()), None) if isinstance(value, dict) else None
            if tile:
                for cb in self._audiotile_callbacks:
                    try:
                        cb(tile)
                    except Exception:
                        _LOGGER.exception("Error in audiotile callback")

        elif prop == PROPERTY_AUDIOTILE_ARTWORK and name in ("property_changed", "success"):
            value = params.get("value", {})
            artwork = next(iter(value.values()), None) if isinstance(value, dict) else None
            if artwork:
                for cb in self._artwork_callbacks:
                    try:
                        cb(artwork)
                    except Exception:
                        _LOGGER.exception("Error in artwork callback")

        elif name in ("volume_changed", "success") and "value" in params and "muted" in params:
            for cb in self._volume_callbacks:
                try:
                    cb(params)
                except Exception:
                    _LOGGER.exception("Error in volume callback")
