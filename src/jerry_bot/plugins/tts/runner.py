"""Service runner for the Text-to-Speech Plugin."""

import asyncio
from pathlib import Path
from typing import ClassVar

from .models.config import TTSPluginConfig
from .models.exceptions import TTSRunnerError, TTSRunnerTimeoutError


class TTSServiceRunner:
    """Runner for the Text-to-Speech service."""

    READY_TIMEOUT_SECONDS: ClassVar[float] = 30.0
    
    def __init__(self, config: TTSPluginConfig, default_cwd: Path):
        """Initialize the TTS service runner.

        Args:
            config (TTSPluginConfig): The configuration for the TTS service.
        """
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self.path = config.service.cwd or default_cwd

    async def start(self) -> None:
        """Start the TTS service."""

        if self.process is not None:
            raise TTSRunnerError("TTS service is already running.")

        try:
            self.process = await asyncio.create_subprocess_exec(
                self.config.service.command,
                *self.config.service.args,
                cwd=self.path,
            )
        except FileNotFoundError as e:
            raise TTSRunnerError(
                f"Failed to start TTS service. Command not found: {self.config.service.command} ({self.path})"
            ) from e

    async def stop(self) -> None:
        """Stop the TTS service."""
        if self.process is None:
            return

        self.process.terminate()
        await self.process.wait()
        self.process = None

    async def wait_for_ready(self) -> None:
        """Wait for the TTS service to be ready."""
        if self.process is None:
            raise TTSRunnerError("TTS service is not running.")

        timeout = self.READY_TIMEOUT_SECONDS
        socket_path = self.path / self.config.socket_path

        try:
            async with asyncio.timeout(timeout):
                while True:
                    # The service must still be alive while we wait.
                    if self.process.returncode is not None:
                        raise TTSRunnerError(
                            f"TTS service exited before becoming ready (return code: {self.process.returncode})."
                        )

                    try:
                        _, writer = await asyncio.open_unix_connection(socket_path)
                        writer.close()
                        await writer.wait_closed()
                        return
                    except OSError:
                        await asyncio.sleep(0.1)
        except TimeoutError as exc:
            raise TTSRunnerTimeoutError(
                f"Timed out after {timeout:.1f}s waiting for TTS socket at '{socket_path}'."
            ) from exc

    @property
    def command(self) -> tuple[str, ...]:
        """Get the command and arguments to start the TTS service."""
        return (self.config.service.command, *self.config.service.args)

    @property
    def is_running(self) -> bool:
        """Check if the TTS service is currently running."""
        return self.process is not None and self.process.returncode is None
