from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.agents.acp_client import ACPClient
from app.agents.base import AgentAdapter, AgentUsage

logger = structlog.get_logger()


class GenericACPAdapter(AgentAdapter):
    name = "acp"

    def __init__(self, container_name: str, command: list[str]) -> None:
        self.container_name = container_name
        self.command = ["podman", "exec", "-i", container_name, *command]

    async def check_usage(self) -> AgentUsage:
        return AgentUsage(remaining=None, total=None)

    async def send_message(
        self,
        chat_id: str,
        message: str,
        context: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        client = ACPClient(self.command)
        await client.start()
        try:
            await client.call("initialize", {"protocolVersion": "2024-11-05"})
            await client.notify("session/new", {"chatId": chat_id})

            ctx_text = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in context
            )
            full_prompt = f"{ctx_text}\nuser: {message}" if ctx_text else message

            await client.notify("session/prompt", {"prompt": full_prompt})

            async for notif in client.notifications():
                yield notif
        finally:
            await client.stop()
