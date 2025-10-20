"""Main runner for Jerry Bot."""

from squid_core.framework import Framework
from pathlib import Path

def main() -> None:
    """Main function to run the bot."""
    framework = Framework.create(
        manifest=Path("framework.toml"),
        env_file=Path(".env"),
    )
    framework.run()