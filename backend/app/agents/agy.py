from typing import Any, AsyncIterator

import structlog

from app.agents.base import AgentAdapter, AgentUsage
from app.agents.acp_client import ACPClient
from app.settings import get_settings

logger = structlog.get_logger()


class AGYAdapter(AgentAdapter):
    name = "agy"

    def __init__(self, container_name: str) -> None:
        self.container_name = container_name
        self.settings = get_settings()

    async def check_usage(self) -> AgentUsage:
        # AGY quota can be queried from the agent's own status if available.
        return AgentUsage(remaining=None, total=None)

    async def send_message(
        self,
        chat_id: str,
        message: str,
        context: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        command = [
            "podman",
            "exec",
            "-i",
            self.container_name,
            "npx",
            "-y",
            "agy-acp",
        ]
        client = ACPClient(command)
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
