from __future__ import annotations

import asyncio
import json
import logging
import ssl
from collections.abc import Callable

import aiohttp

from homeassistant.core import HomeAssistant

from .const import DEFAULT_PORT, PROPERTY_AUDIOTILE

_LOGGER = logging.getLogger(__name__)

RECONNECT_INTERVAL = 5
MAX_RECONNECT_INTERVAL = 60


class BwZeppelinWebSocket:

    def __init__(self, host: str) -> None:
        self._host = host
        self._url = f"wss://{host}:{DEFAULT_PORT}/messages"
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._audiotile_callbacks: list[Callable[[dict], None]] = []

    def register_audiotile_callback(self, callback: Callable[[dict], None]) -> Callable[[], None]:
        self._audiotile_callbacks.append(callback)
        return lambda: self._audiotile_callbacks.remove(callback)

    def start(self, hass: HomeAssistant) -> None:
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
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                _LOGGER.debug("WebSocket connection error: %s", err)
            except asyncio.CancelledError:
                return
            except Exception:
                _LOGGER.exception("Unexpected WebSocket error")

            if self._stop_event.is_set():
                return
            _LOGGER.debug("Reconnecting in %s seconds", backoff)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
                return
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, MAX_RECONNECT_INTERVAL)

    async def _listen(self) -> None:
        session = aiohttp.ClientSession()
        try:
            async with session.ws_connect(self._url, ssl=self._ssl_context) as ws:
                _LOGGER.debug("WebSocket connected to %s", self._host)
                async for msg in ws:
                    if self._stop_event.is_set():
                        return
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        self._handle_message(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
        finally:
            await session.close()

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

        if name == "property_changed" and params.get("property") == PROPERTY_AUDIOTILE:
            value = params.get("value", {})
            tile = next(iter(value.values()), None) if isinstance(value, dict) else None
            if tile:
                for callback in self._audiotile_callbacks:
                    try:
                        callback(tile)
                    except Exception:
                        _LOGGER.exception("Error in audiotile callback")
