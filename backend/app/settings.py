from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Chat Harness"
    environment: str = "local"  # local, production

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/chat_harness.db"
    database_echo: bool = False

    # Postgres-specific (used when database_url starts with postgresql)
    pgvector_dim: int = 768

    # Podman
    podman_binary: str = "podman"
    mock_podman: bool = True  # run without podman for local dev
    chat_container_image: str = "localhost/chat-harness-agent:latest"
    chat_container_prefix: str = "chat-"
    chat_base_dir: Path = Path("./data/chats")
    inactivity_timeout_seconds: int = 30 * 60
    snapshot_interval_seconds: int = 60

    # Agents
    devin_default_model: str = "glm-5.2-high"
    agy_acp_command: str = "npx -y agy-acp"
    generic_acp_command: str = ""

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    # Secrets
    secrets_vault: str = "age"  # age, sops, none
    age_key_path: Path = Path("./data/secrets/age.key")
    secrets_file: Path = Path("./data/secrets/secrets.enc.yaml")

    # Web
    cors_origins: list[str] = ["http://localhost:5173"]
    websocket_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
