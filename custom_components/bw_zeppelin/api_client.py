from __future__ import annotations

import ssl
import uuid

import aiohttp

from .const import DEFAULT_PORT, PROPERTY_LIGHT_STATE, STATED_CHANNEL


class BwZeppelinApiError(Exception):
    pass


class BwZeppelinApiClient:

    def __init__(self, session: aiohttp.ClientSession, host: str, node_id: str | None = None) -> None:
        self._session = session
        self._host = host
        self._node_id = node_id
        self._base_url = f"https://{host}:{DEFAULT_PORT}"
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    @property
    def node_id(self) -> str | None:
        return self._node_id

    @node_id.setter
    def node_id(self, value: str) -> None:
        self._node_id = value

    async def _get(self, path: str) -> dict:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, ssl=self._ssl_context) as resp:
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise BwZeppelinApiError(f"Request to {path} failed: {err}") from err

    async def _post_stated(self, method: str, parameters: dict) -> dict:
        if self._node_id is None:
            raise BwZeppelinApiError("Node ID not set")
        url = (
            f"{self._base_url}/mesh/node/{self._node_id}"
            f"/channel/{STATED_CHANNEL}/message"
        )
        payload = {
            "type": "query",
            "method": {
                "name": method,
                "parameters": parameters,
            },
        }
        headers = {"X-Request-Id": str(uuid.uuid4())}
        try:
            async with self._session.post(
                url, json=payload, headers=headers, ssl=self._ssl_context
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                if not text:
                    return {}
                data = await resp.json(content_type=None)
                if "error" in data:
                    raise BwZeppelinApiError(data["error"].get("message", "Unknown error"))
                return data
        except aiohttp.ClientError as err:
            raise BwZeppelinApiError(f"StateD request '{method}' failed: {err}") from err

    async def get_version(self) -> str:
        data = await self._get("/software/version")
        return data.get("version", "unknown")

    async def get_nodes(self) -> list[dict]:
        data = await self._get("/1/mesh/nodes")
        return data.get("nodes", [])

    async def get_light_state(self) -> dict:
        data = await self._post_stated("get_property", {"property": PROPERTY_LIGHT_STATE})
        return data.get("value", {})

    async def check_software_update(self) -> dict:
        return await self._post_stated("check_software_update", {})

    async def set_light_state(
        self,
        enabled: bool,
        brightness: float,
        rgb: tuple[int, int, int],
    ) -> None:
        await self._post_stated(
            "set_property",
            {
                "property": PROPERTY_LIGHT_STATE,
                "value": {
                    "enabled": enabled,
                    "brightness": brightness,
                    "rgb": {"red": rgb[0], "green": rgb[1], "blue": rgb[2]},
                    "supported": True,
                },
            },
        )
