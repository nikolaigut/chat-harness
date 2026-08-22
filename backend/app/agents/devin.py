from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.agents.acp_client import ACPClient
from app.agents.base import AgentAdapter, AgentUsage
from app.settings import get_settings

logger = structlog.get_logger()


class DevinAdapter(AgentAdapter):
    name = "devin"

    def __init__(self, container_name: str) -> None:
        self.container_name = container_name
        self.settings = get_settings()

    async def check_usage(self) -> AgentUsage:
        # Devin does not expose a direct usage endpoint via CLI.
        # A small `devin doctor` or `devin auth status` call can be a proxy.
        return AgentUsage(remaining=None, total=None, model=self.settings.devin_default_model)

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
            "devin",
            "acp",
            "--model",
            self.settings.devin_default_model,
        ]
        client = ACPClient(command)
        await client.start()
        try:
            init = await client.call("initialize", {"protocolVersion": "2024-11-05"})
            logger.info("devin.acp.init", result=init)
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
