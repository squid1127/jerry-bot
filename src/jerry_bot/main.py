"""Main runner for Jerry Bot."""

from pathlib import Path

from squid_core.framework import Framework


def main() -> None:
    """Main function to run the bot."""
    framework = Framework.create(
        manifest=Path("framework.toml"),
        env_file=Path(".env"),
    )
    framework.run()