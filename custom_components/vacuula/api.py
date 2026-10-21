"""Minimal async client for the Vacuula server HTTP API."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# The server waits up to 30 s for the robot to answer a command.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=40, sock_connect=10)
_STREAM_TIMEOUT = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=60)


class VacuulaError(Exception):
    """Base error."""


class VacuulaConnectionError(VacuulaError):
    """The Vacuula server could not be reached."""


class VacuulaCommandError(VacuulaError):
    """The server or the robot refused a request."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


class VacuulaClient:
    """Talks to /api on a Vacuula server."""

    def __init__(
        self, session: aiohttp.ClientSession, host: str, port: int
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self._base = f"http://{host}:{port}/api"

    async def _request(
        self, method: str, path: str, body: Any | None = None
    ) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._base}{path}",
                data=None if body is None else json.dumps(body),
                timeout=_REQUEST_TIMEOUT,
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    message = text
                    try:
                        message = json.loads(text).get("error", text)
                    except (ValueError, AttributeError):
                        pass
                    raise VacuulaCommandError(resp.status, message)
                try:
                    return json.loads(text)
                except ValueError:
                    return text
        except (aiohttp.ClientError, TimeoutError) as err:
            raise VacuulaConnectionError(str(err) or type(err).__name__) from err

    async def get_server_info(self) -> dict[str, Any]:
        """GET /api/server."""
        info = await self._request("GET", "/server")
        if not isinstance(info, dict) or "version" not in info:
            raise VacuulaConnectionError("Not a Vacuula server")
        return info

    async def get_robots(self) -> dict[str, dict[str, Any]]:
        """GET /api/robots -> {serial: {type, name, connected, ...}}."""
        robots = await self._request("GET", "/robots")
        return robots if isinstance(robots, dict) else {}

    async def get_maps(self, serial: str) -> list[dict[str, Any]]:
        """GET /api/robot/<serial>/maps (floorplans shown in the app)."""
        return await self._request("GET", f"/robot/{serial}/maps")

    async def get_map(self, serial: str, map_id: str) -> dict[str, Any]:
        """GET /api/robot/<serial>/maps/<id> (floor grid as run-length data)."""
        return await self._request("GET", f"/robot/{serial}/maps/{map_id}")

    async def get_runs(self, serial: str) -> list[dict[str, Any]]:
        """GET /api/robot/<serial>/runs (one row per finished cleaning)."""
        return await self._request("GET", f"/robot/{serial}/runs")

    async def get_run(self, serial: str, run_id: str) -> dict[str, Any]:
        """GET /api/robot/<serial>/run/<id> (the driven path of one run)."""
        return await self._request("GET", f"/robot/{serial}/run/{run_id}")

    async def get_boundaries(
        self, serial: str, map_id: str
    ) -> list[dict[str, Any]]:
        """GET /api/robot/<serial>/maps/<id>/boundaries (zones, no-go lines)."""
        return await self._request(
            "GET", f"/robot/{serial}/maps/{map_id}/boundaries"
        )

    async def command(self, serial: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST a robot command; returns the robot's response envelope."""
        result = await self._request("POST", f"/robot/{serial}/command", payload)
        return result if isinstance(result, dict) else {}

    async def stream(self, path: str) -> AsyncIterator[tuple[str, Any]]:
        """Yield (event, data) tuples from a server-sent-event endpoint."""
        try:
            async with self._session.get(
                f"{self._base}{path}",
                timeout=_STREAM_TIMEOUT,
                headers={"Accept": "text/event-stream"},
            ) as resp:
                if resp.status != 200:
                    raise VacuulaCommandError(resp.status, "stream refused")
                event = "message"
                data_lines: list[str] = []
                async for raw in resp.content:
                    line = raw.decode("utf-8", "replace").rstrip("\r\n")
                    if line == "":
                        if data_lines:
                            payload = "\n".join(data_lines)
                            try:
                                yield event, json.loads(payload)
                            except ValueError:
                                _LOGGER.debug("Bad SSE payload: %.200s", payload)
                        event, data_lines = "message", []
                    elif line.startswith(":"):
                        continue
                    elif line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
        except (aiohttp.ClientError, TimeoutError) as err:
            raise VacuulaConnectionError(str(err) or type(err).__name__) from err
