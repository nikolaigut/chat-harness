import asyncio
import json
import random
import string
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from app.settings import get_settings

logger = structlog.get_logger()


def _random_id(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


@dataclass
class ContainerState:
    id: str
    name: str
    image: str | None = None
    status: str = "unknown"
    running: bool = False


class PodmanManager:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.mock = self.settings.mock_podman
        self._mock_containers: dict[str, dict[str, Any]] = {}

    async def _run(self, *cmd: str) -> str:
        full_cmd = [self.settings.podman_binary, *cmd]
        logger.info("podman.run", cmd=" ".join(full_cmd))
        if self.mock:
            return json.dumps({"mock": True, "cmd": cmd})
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"podman {' '.join(cmd)} failed: {stderr.decode()}")
        return stdout.decode()

    async def create(
        self,
        chat_id: str,
        workspace: Path,
        agent: str,
        secrets: dict[str, str],
        image: str | None = None,
    ) -> ContainerState:
        name = f"{self.settings.chat_container_prefix}{chat_id}"
        image = image or self.settings.chat_container_image

        # Build the run command with rootless Podman and secrets as env vars.
        # For real isolation we also add --userns=keep-id and --network slirp4netns.
        env_args = []
        for k, v in secrets.items():
            env_args.extend(["-e", f"{k}={v}"])

        cmd = [
            "run",
            "-d",
            "--name",
            name,
            "--replace",
            "--userns=keep-id",
            "--network",
            "slirp4netns:allow_host_loopback=false",
            "--security-opt",
            "seccomp=unconfined",
            "--security-opt",
            "apparmor=unconfined",
            "-v",
            f"{workspace}:/workspace:Z",
            "-p",
            "6080",  # novnc; port mapped dynamically
            *env_args,
            image,
        ]

        if self.mock:
            self._mock_containers[name] = {
                "chat_id": chat_id,
                "status": "running",
                "image": image,
                "created_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            }
            return ContainerState(id=name, name=name, image=image, status="running", running=True)

        output = await self._run(*cmd)
        container_id = output.strip().split("\n")[-1].strip()
        return ContainerState(
            id=container_id,
            name=name,
            image=image,
            status="running",
            running=True,
        )

    async def exec(self, container_id: str, *args: str) -> str:
        cmd = ["exec", container_id, *args]
        return await self._run(*cmd)

    async def exec_interactive(
        self,
        container_id: str,
        *args: str,
        input_data: str | None = None,
    ) -> tuple[str, str]:
        full_cmd = [self.settings.podman_binary, "exec", "-i", container_id, *args]
        logger.info("podman.exec_interactive", cmd=" ".join(full_cmd))
        if self.mock:
            return (
                "mock output",
                "",
            )
        proc = await asyncio.create_subprocess_exec(
            *full_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input_data.encode() if input_data else None)
        return stdout.decode(), stderr.decode()

    async def stop_and_commit(self, container_id: str, image_name: str) -> str:
        if self.mock:
            self._mock_containers[container_id]["status"] = "committed"
            return f"localhost/{image_name}:latest"

        await self._run("stop", container_id)
        await self._run("commit", container_id, f"localhost/{image_name}:latest")
        await self._run("rm", container_id)
        return f"localhost/{image_name}:latest"

    async def resume_from_image(self, chat_id: str, image_name: str, workspace: Path) -> ContainerState:
        name = f"{self.settings.chat_container_prefix}{chat_id}"
        cmd = [
            "run",
            "-d",
            "--name",
            name,
            "--replace",
            "--userns=keep-id",
            "--network",
            "slirp4netns:allow_host_loopback=false",
            "-v",
            f"{workspace}:/workspace:Z",
            f"localhost/{image_name}:latest",
        ]
        output = await self._run(*cmd)
        container_id = output.strip().split("\n")[-1].strip()
        return ContainerState(
            id=container_id,
            name=name,
            image=image_name,
            status="running",
            running=True,
        )

    async def is_running(self, container_id: str) -> bool:
        if self.mock:
            c = self._mock_containers.get(container_id)
            return c is not None and c["status"] == "running"
        try:
            out = await self._run("inspect", container_id, "--format", "{{.State.Status}}")
            return out.strip() == "running"
        except RuntimeError:
            return False

    async def get_browser_port(self, container_id: str) -> int | None:
        if self.mock:
            return 6080
        try:
            out = await self._run("port", container_id, "6080")
            for line in out.strip().split("\n"):
                if ":" in line:
                    return int(line.rsplit(":", 1)[-1])
        except RuntimeError:
            pass
        return None

    async def list_chat_containers(self) -> list[ContainerState]:
        if self.mock:
            return [
                ContainerState(
                    id=k,
                    name=k,
                    image=v.get("image"),
                    status=v.get("status", "unknown"),
                    running=v.get("status") == "running",
                )
                for k, v in self._mock_containers.items()
            ]
        try:
            out = await self._run(
                "ps",
                "-a",
                "--filter",
                f"name={self.settings.chat_container_prefix}",
                "--format",
                "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}",
            )
        except RuntimeError:
            return []

        states = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 3:
                states.append(
                    ContainerState(
                        id=parts[0],
                        name=parts[1],
                        image=parts[2],
                        status=parts[3] if len(parts) > 3 else "unknown",
                        running="Up" in (parts[3] if len(parts) > 3 else ""),
                    )
                )
        return states
