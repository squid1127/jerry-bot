"""Configuration manager for the Joe plugin."""

import logging
from pathlib import Path

import aiofiles
from pydantic import ValidationError
from yaml import YAMLError, safe_load

from .config import JoePluginConfig


class ConfigManager:
    """Loads and validates the Joe plugin configuration."""

    def __init__(self, config_path: Path, logger: logging.Logger | None = None):
        self.config_path = config_path
        self.logger = logger or logging.getLogger(__name__)
        self._config: JoePluginConfig | None = None

    @property
    def template_path(self) -> Path:
        """Get the path to the example configuration."""
        return Path(__file__).parent / "config.example.yaml"

    @property
    def config(self) -> JoePluginConfig | None:
        """Get the currently loaded configuration."""
        return self._config

    async def load(self) -> JoePluginConfig:
        """Load and validate the plugin configuration from YAML."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            if self.template_path.exists():
                async with aiofiles.open(self.template_path, mode="r") as source:
                    content = await source.read()
                async with aiofiles.open(self.config_path, mode="w") as destination:
                    await destination.write(content)
                error_message = (
                    f"Config file not found. Created example config at "
                    f"{self.config_path}. Please edit it and restart."
                )
            else:
                error_message = f"Config file not found at {self.config_path}."
            self.logger.error(error_message)
            raise FileNotFoundError(error_message)

        try:
            async with aiofiles.open(self.config_path, mode="r") as config_file:
                config_data = safe_load(await config_file.read())
            if not isinstance(config_data, dict):
                raise TypeError("Config file must contain a YAML mapping.")
            self._config = JoePluginConfig.model_validate(config_data)
        except (OSError, TypeError, ValueError, ValidationError, YAMLError):
            self.logger.exception("Failed to load Joe plugin configuration.")
            raise

        self.logger.info("Successfully loaded config from %s", self.config_path)
        return self._config
