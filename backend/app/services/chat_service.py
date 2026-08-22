import random
import string
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import structlog

from app.agents.router import AgentRouter
from app.db import Chat, Event, get_database
from app.podman import PodmanManager
from app.services.embeddings import EmbeddingService
from app.services.retrieval import ContextRetriever
from app.services.secrets import SecretsManager
from app.settings import get_settings

logger = structlog.get_logger()


class ChatService:
    def __init__(self) -> None:
        self.db = get_database()
        self.podman = PodmanManager()
        self.embeddings = EmbeddingService()
        self.retrieval = ContextRetriever(self.embeddings)
        self.secrets = SecretsManager()
        self.settings = get_settings()

    def _random_id(self, n: int = 12) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    async def create_chat(self, name: str, agent: str | None = None) -> Chat:
        chat_id = self._random_id()
        workspace = self.settings.chat_base_dir / chat_id
        workspace.mkdir(parents=True, exist_ok=True)

        # Initial container creation.
        secrets = await self.secrets.for_agent(agent or "devin")
        container = await self.podman.create(
            chat_id=chat_id,
            workspace=workspace,
            agent=agent or "devin",
            secrets=secrets,
            image=self.settings.chat_container_image,
        )

        chat = Chat(
            id=chat_id,
            name=name,
            selected_agent=agent,
            status="running",
            container_id=container.id,
            container_image=container.image,
            workspace_dir=str(workspace),
        )
        await self.db.create_chat(chat)
        return chat

    async def list_chats(self) -> list[Chat]:
        return await self.db.list_chats()

    async def get_chat(self, chat_id: str) -> Chat | None:
        return await self.db.get_chat(chat_id)

    async def send_message(
        self,
        chat_id: str,
        message: str,
        requested_agent: str | None = None,
    ) -> AsyncIterator[Event]:
        chat = await self.get_chat(chat_id)
        if not chat:
            raise ValueError(f"Chat {chat_id} not found")
        assert chat.container_id is not None
        assert chat.workspace_dir is not None

        # Ensure container is running.
        if not await self.podman.is_running(chat.container_id) and chat.container_image:
            workspace = Path(chat.workspace_dir)
            container = await self.podman.resume_from_image(
                chat_id, chat.container_image, workspace
            )
            chat.container_id = container.id
            chat.status = "running"
            await self.db.update_chat(chat)

        # Persist user message.
        user_event = Event(
            chat_id=chat_id,
            role="user",
            content=message,
            turn=0,
        )
        await self.db.add_event(user_event)

        # Embed and re-fetch events.
        events = await self.db.get_events(chat_id)
        if events:
            texts = [self._event_text(e) for e in events]
            embeddings = self.embeddings.encode(texts)
            for e, emb in zip(events, embeddings, strict=True):
                e.embedding = emb
                await self.db.update_event(e)
            # reload events with embeddings
            events = await self.db.get_events(chat_id)

        context = self.retrieval.build_context(events, message)

        # Dynamic agent selection.
        router = AgentRouter(chat.container_id)
        agent_name = await router.select_agent(message, requested_agent)

        # Add system selection event.
        system_event = Event(
            chat_id=chat_id,
            role="system",
            content=f"Selected agent: {agent_name}",
            turn=0,
        )
        await self.db.add_event(system_event)

        if self.settings.mock_podman:
            mock_event = Event(
                chat_id=chat_id,
                role="assistant",
                content="This is a mock agent response. Podman is not available on this host, so no real agent container was started.",
                reasoning="mock mode",
                turn=0,
            )
            await self.db.add_event(mock_event)
            yield mock_event
            chat.last_active_at = datetime.now(UTC).replace(tzinfo=None)
            await self.db.update_chat(chat)
            return

        adapter = router.get_adapter(agent_name)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        async for notif in adapter.send_message(chat_id, message, context):
            # ACP notifications are rich; normalize here.
            content = notif.get("params", {}).get("content", "")
            reasoning = notif.get("params", {}).get("reasoning")
            tool_calls = notif.get("params", {}).get("tool_calls")
            browser_action = notif.get("params", {}).get("browser_action")

            if content:
                content_parts.append(content)
            if reasoning:
                reasoning_parts.append(reasoning)

            event = Event(
                chat_id=chat_id,
                role="assistant",
                content="".join(content_parts) if content_parts else None,
                reasoning="\n".join(reasoning_parts) if reasoning_parts else None,
                tool_calls=tool_calls,
                browser_action=browser_action,
                turn=0,
            )
            await self.db.add_event(event)
            yield event

        chat.last_active_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.update_chat(chat)

    def _event_text(self, event: Event) -> str:
        parts = [event.role or "", event.content or "", event.reasoning or ""]
        return "\n".join(parts)

    async def stop_inactive(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        chats = await self.db.list_chats()
        for chat in chats:
            if chat.status != "running" or not chat.container_id:
                continue
            last = chat.last_active_at or chat.created_at
            if (now - last).total_seconds() > self.settings.inactivity_timeout_seconds:
                image = await self.podman.stop_and_commit(
                    chat.container_id, f"chat-snapshot-{chat.id}"
                )
                chat.container_image = image
                chat.container_id = ""
                chat.status = "snapshot"
                await self.db.update_chat(chat)
