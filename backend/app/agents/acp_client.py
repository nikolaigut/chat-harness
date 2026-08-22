import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import structlog

logger = structlog.get_logger()


class ACPClient:
    """Lightweight stdio JSON-RPC ACP client."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self.command = command
        self.env = env or {}
        self._proc: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._notif_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._read_task: asyncio.Task | None = None

    async def start(self) -> None:
        env = {**os.environ, **self.env}
        self._proc = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("acp.invalid_json", line=line.decode(errors="replace"))
                continue
            if "id" in msg and msg["id"] in self._pending:
                self._pending[msg["id"]].set_result(msg)
            elif "method" in msg:
                await self._notif_queue.put(msg)

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        req_id = str(uuid.uuid4())
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(req).encode() + b"\n")
        await self._proc.stdin.drain()
        return await asyncio.wait_for(fut, timeout=30.0)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        req = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(req).encode() + b"\n")
        await self._proc.stdin.drain()

    async def notifications(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            yield await self._notif_queue.get()

    async def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except TimeoutError:
                self._proc.kill()
        if self._read_task:
            self._read_task.cancel()
