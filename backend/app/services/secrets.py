import os
from pathlib import Path
from typing import Any


class SecretsManager:
    """Simple secret store with optional age/sops integration."""

    def __init__(self) -> None:
        self.settings = None

    def _get_settings(self):
        from app.settings import get_settings

        if self.settings is None:
            self.settings = get_settings()
        return self.settings

    async def for_agent(self, agent: str) -> dict[str, str]:
        settings = self._get_settings()
        secrets: dict[str, str] = {}

        # For now, load from plain env vars or an age-encrypted file stub.
        env_prefix = f"{agent.upper()}_"
        for k, v in os.environ.items():
            if k.startswith(env_prefix) or k in (
                "DEVIN_API_KEY",
                "WINDSURF_API_KEY",
                "AGY_API_KEY",
                "ACP_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
                "GEMINI_API_KEY",
            ):
                secrets[k] = v

        # If age/sops decryption is implemented, this is the place.
        if settings.secrets_vault in ("age", "sops") and settings.secrets_file.exists():
            secrets.update(await self._decrypt(settings.secrets_file))

        return secrets

    async def _decrypt(self, path: Path) -> dict[str, str]:
        # TODO: implement age/sops decryption.
        return {}

    async def get_secret(self, key: str) -> Any:
        secrets = await self.for_agent("global")
        return secrets.get(key)
