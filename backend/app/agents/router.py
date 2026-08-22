import structlog

from app.agents.base import AgentAdapter, AgentUsage
from app.agents.devin import DevinAdapter
from app.settings import get_settings

logger = structlog.get_logger()


class AgentRouter:
    def __init__(self, container_name: str) -> None:
        self.container_name = container_name
        self.settings = get_settings()

    def get_adapter(self, name: str) -> AgentAdapter:
        if name == "devin":
            return DevinAdapter(self.container_name)
        if name == "agy":
            from app.agents.agy import AGYAdapter
            return AGYAdapter(self.container_name)
        if name == "acp":
            from app.agents.generic_acp import GenericACPAdapter
            return GenericACPAdapter(
                self.container_name,
                self.settings.generic_acp_command.split(),
            )
        raise ValueError(f"Unknown agent: {name}")

    async def check_quota(self, name: str) -> AgentUsage:
        return await self.get_adapter(name).check_usage()

    async def select_agent(self, message: str, requested: str | None = None) -> str:
        """Return the best agent for the message or fallback to devin."""
        candidates = ["devin"]
        if self.settings.agy_acp_command:
            candidates.append("agy")
        if self.settings.generic_acp_command:
            candidates.append("acp")

        if requested and requested in candidates:
            return requested

        # Pre-flight quota check: prefer requested agent, else try in order.
        for candidate in [requested] if requested else candidates:
            if not candidate:
                continue
            try:
                usage = await self.check_quota(candidate)
                if usage.remaining is None or usage.remaining > 0:
                    return candidate
            except Exception as exc:  # noqa: BLE001
                logger.warning("agent.quota_check_failed", agent=candidate, error=str(exc))
                continue

        return "devin"
