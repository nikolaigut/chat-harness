from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator


@dataclass
class AgentUsage:
    remaining: int | None = None
    total: int | None = None
    model: str | None = None


class AgentAdapter(ABC):
    name: str = "unknown"

    @abstractmethod
    async def check_usage(self) -> AgentUsage:
        """Return current usage/quota information."""

    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        message: str,
        context: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield events from the agent (text, tool calls, reasoning, browser)."""
