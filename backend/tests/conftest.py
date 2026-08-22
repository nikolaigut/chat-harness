import httpx
import pytest
from httpx import ASGITransport


@pytest.fixture
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("MOCK_PODMAN", "true")
    monkeypatch.setenv("CHAT_BASE_DIR", str(tmp_path / "chats"))

    from app.db import Database
    from app.main import app
    from app.settings import get_settings

    get_settings.cache_clear()
    import app.db as db_module

    db_module._db = None

    db = Database()
    await db.init()
    db_module._db = db

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await db.close()
    db_module._db = None
