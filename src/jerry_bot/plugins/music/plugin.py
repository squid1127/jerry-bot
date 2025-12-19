"""Main Plugin Module for Music Player."""

from squid_core.plugin_base import Plugin, PluginCog
from squid_core.framework import Framework

import discord
from discord import app_commands
import asyncio

class MusicPlayerPlugin(Plugin):
    """Music Player Plugin for Jerry Bot."""

    def __init__(self, framework: Framework):
        super().__init__(framework)