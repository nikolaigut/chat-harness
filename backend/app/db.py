import datetime
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, Float, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.settings import Settings, get_settings


class Base(DeclarativeBase):
    type_annotation_map: dict[type, Any] = {dict: JSON}


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="New chat")
    selected_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="creating")
    container_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    container_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_active_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(32), index=True)
    turn: Mapped[int] = mapped_column(default=0)
    role: Mapped[str] = mapped_column(String(32))  # user, assistant, system, tool, browser
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    browser_action: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # pgvector vector column is added via migration when using PostgreSQL.
    # SQLite stores the embedding as JSON for portability.


def _ensure_data_dir(db_url: str) -> None:
    if "sqlite" in db_url:
        path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        Path(path).parent.mkdir(parents=True, exist_ok=True)


class Database:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        _ensure_data_dir(self.settings.database_url)
        self.engine = create_async_engine(
            self.settings.database_url,
            echo=self.settings.database_echo,
            future=True,
        )
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def get_chat(self, chat_id: str) -> Chat | None:
        async with self.session_factory() as session:
            return await session.get(Chat, chat_id)

    async def create_chat(self, chat: Chat) -> None:
        async with self.session_factory() as session:
            session.add(chat)
            await session.commit()

    async def update_chat(self, chat: Chat) -> None:
        async with self.session_factory() as session:
            await session.merge(chat)
            await session.commit()

    async def list_chats(self) -> list[Chat]:
        async with self.session_factory() as session:
            result = await session.execute(select(Chat).order_by(Chat.created_at.desc()))
            return list(result.scalars().all())

    async def add_event(self, event: Event) -> None:
        async with self.session_factory() as session:
            session.add(event)
            await session.commit()

    async def update_event(self, event: Event) -> None:
        async with self.session_factory() as session:
            await session.merge(event)
            await session.commit()

    async def get_events(self, chat_id: str) -> list[Event]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(Event).where(Event.chat_id == chat_id).order_by(Event.id.asc())
            )
            return list(result.scalars().all())


_db: Database | None = None


def get_database() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db


async def get_db_session() -> AsyncIterator[AsyncSession]:
    db = get_database()
    async with db.session_factory() as session:
        yield session
