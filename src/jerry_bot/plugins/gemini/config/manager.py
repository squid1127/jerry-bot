"""Configuration manager for Gemini plugin."""

import logging
from pathlib import Path
from typing import Optional
import aiofiles
from aiofiles import os as aiofiles_os
from yaml import safe_load, safe_dump

from .global_config import GlobalConfig


class ConfigManager:
    """Manages configuration loading, validation, and reloading for the Gemini plugin."""

    def __init__(self, config_path: Path, logger: Optional[logging.Logger] = None):
        """
        Initialize the ConfigManager.

        Args:
            config_path: Path to the configuration YAML file.
            logger: Optional logger instance for logging events.
        """
        self.config_path = config_path
        self.logger = logger or logging.getLogger(__name__)
        self._config: Optional[GlobalConfig] = None

    @property
    def template_path(self) -> Path:
        """Get the path to the example config template."""
        return Path(__file__).parent / "config.example.yaml"

    @property
    def config(self) -> Optional[GlobalConfig]:
        """Get the currently loaded configuration."""
        return self._config

    async def load(self) -> GlobalConfig:
        """
        Load the plugin configuration from the YAML file.

        Returns:
            The loaded GlobalConfig instance.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            ValueError: If the config file is invalid.
        """
        if not self.config_path.exists():
            await self._create_config_directory()

            # Try to copy the example config if it exists
            if self.template_path.exists():
                await self._copy_template()
                error_msg = (
                    f"Config file not found. Created example config at {self.config_path}. "
                    "Please edit it with your settings and restart."
                )
            else:
                error_msg = (
                    f"Config file not found at {self.config_path}. "
                    f"Example template also missing at {self.template_path}. "
                    "Please create a config.yaml with the appropriate settings."
                )

            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            async with aiofiles.open(self.config_path, mode="r") as f:
                content = await f.read()
                config_dict = safe_load(content)

                if config_dict is None:
                    raise ValueError("Config file is empty or invalid YAML")

                self._config = GlobalConfig(**config_dict)
                self.logger.info(f"Successfully loaded config from {self.config_path}")
                return self._config

        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            raise

    async def reload(self) -> GlobalConfig:
        """
        Reload the configuration from disk.

        Returns:
            The reloaded GlobalConfig instance.
        """
        self.logger.info("Reloading configuration...")
        return await self.load()

    async def save(self, config: Optional[GlobalConfig] = None) -> None:
        """
        Save the configuration to disk.

        Args:
            config: Optional GlobalConfig to save. If None, saves the current config.

        Raises:
            ValueError: If no config is provided and no config is currently loaded.
        """
        config_to_save = config or self._config
        if config_to_save is None:
            raise ValueError("No configuration to save")

        await self._create_config_directory()

        try:
            config_dict = config_to_save.model_dump(mode="json", exclude_none=True)

            async with aiofiles.open(self.config_path, mode="w") as f:
                yaml_content = safe_dump(
                    config_dict,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                await f.write(yaml_content)

            self._config = config_to_save
            self.logger.info(f"Successfully saved config to {self.config_path}")

        except Exception as e:
            self.logger.error(f"Failed to save config: {e}")
            raise

    async def _create_config_directory(self) -> None:
        """Create the configuration directory if it doesn't exist."""
        if not self.config_path.parent.exists():
            self.logger.info(f"Creating config directory at {self.config_path.parent}")
            await aiofiles_os.makedirs(self.config_path.parent, exist_ok=True)

    async def _copy_template(self) -> None:
        """Copy the example config template to the config path."""
        try:
            async with aiofiles.open(self.template_path, mode="r") as src:
                content = await src.read()

            async with aiofiles.open(self.config_path, mode="w") as dst:
                await dst.write(content)

            self.logger.info(
                f"Copied example config from {self.template_path} to {self.config_path}"
            )
        except Exception as e:
            self.logger.warning(f"Failed to copy template config: {e}")

    async def create_example_config(self) -> None:
        """
        Create an example configuration file at the config path.

        This is a convenience method that can be called to generate
        a template config file with all options documented.

        Raises:
            FileExistsError: If config file already exists.
        """
        if self.config_path.exists():
            raise FileExistsError(
                f"Config file already exists at {self.config_path}. "
                "Delete it first if you want to regenerate."
            )

        await self._create_config_directory()
        await self._copy_template()
        self.logger.info(f"Created example config at {self.config_path}")

    def validate(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if the configuration is valid, False otherwise.
        """
        if self._config is None:
            self.logger.warning("No configuration loaded to validate")
            return False

        try:
            # Pydantic validation happens on model creation
            # Additional custom validation can be added here

            if not self._config.providers:
                self.logger.error("Configuration must have at least one provider")
                return False

            if (
                self._config.default_provider
                and self._config.default_provider not in self._config.providers
            ):
                self.logger.error(
                    f"Default provider '{self._config.default_provider}' not found in providers"
                )
                return False

            self.logger.info("Configuration validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False
