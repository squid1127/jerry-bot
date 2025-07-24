"""Configuration management for JerryGemini."""

# Packages
import logging
from enum import Enum
import traceback

# squid core
import core

# Internal Imports
from .constants import ConfigFileDefaults, ConfigDefaults
from .prompts import SystemPromptGenerator
from .methods import AIMethodRegistry

# Logging
logger = logging.getLogger("jerry.JerryGemini.config")

# Debug: Print formatted config
import yaml

class ConfigStatus(Enum):
    """
    ConfigStatus is an enumeration that represents the status of the configuration.
    It can be used to indicate whether the configuration is loaded, not loaded, or has errors.
    """

    LOADED = "loaded"
    NOT_LOADED = "not_loaded"
    FAILED = "failed"


class JerryGeminiConfig:
    """
    JerryGeminiConfig is a class that manages the configuration for the JerryGemini AI integration.
    It handles loading and saving configuration data.
    """

    def __init__(self, bot: core.Bot):
        """
        Initializes the JerryGeminiConfig instance with the provided bot instance.

        Args:
            core.Bot: The bot instance to be used for interactions.
        """
        self.bot = bot
        self.config = None
        self.error = None
        self.status = ConfigStatus.NOT_LOADED
        self.logger = logging.getLogger("jerry.JerryGemini.config")

        # Configure logging
        self.files = self.bot.filebroker.configure_cog(
            "JerryGemini",
            config_file=True,
            config_default=ConfigFileDefaults.DEFAULT_CONFIG_CONTENTS,
            config_do_cache=300,
            cache=True,
            cache_clear_on_init=True,
        )
        self.files.init()

        # Try to load the configuration
        try:
            self.load_config()
            self.status = ConfigStatus.LOADED
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}\n{traceback.format_exc()}")
            self.error = str(e)
            self.status = ConfigStatus.FAILED
            self.config = None

    def process_instances(self):
        """
        Iterates through the instances in the configuration and ensures that each instance has a valid AI configuration.
        """
        if not self.config or "global" not in self.config or not "instances" in self.config:
            return None
        
        global_ai = self.config["global"]["ai"]

        
        logger.info("Processing agents")
        if ConfigDefaults.AGENT_METHOD not in self.config["methods"]:
            self.config["methods"][ConfigDefaults.AGENT_METHOD.value] = {
                "agents": {}
            }
        if "agents" not in self.config["methods"][ConfigDefaults.AGENT_METHOD.value]:
            self.config["methods"][ConfigDefaults.AGENT_METHOD.value]["agents"] = {}
        
        for agent_name, agent_config in self.config.get("agents", {}).items():
            if "ai" not in agent_config or not agent_config["ai"]:
                agent_config["ai"] = global_ai.copy()
                logger.info(f"Assigned global AI configuration to agent {agent_name}")
            else:
                logger.info(f"Agent {agent_name} has custom AI configuration")
                
            if "prompt" not in agent_config:
                agent_config["prompt"] = ConfigDefaults.AGENT_PROMPT.value
                logger.info(f"Assigned default prompt to agent {agent_name}")
                
            # Save to method config
            self.config["methods"][ConfigDefaults.AGENT_METHOD.value]["agents"][agent_name] = agent_config
            self.logger.info(f"Saved agent {agent_name} configuration to methods")

        methods_config: dict = self.config.get("methods", {})

        logger.info("Processing instances")
        for instance_id, instance_config in self.config["instances"].items():
            if "ai" not in instance_config or instance_config["ai"] == {}:
                instance_config["ai"] = global_ai.copy()
                logger.info(f"Assigned global AI configuration to instance {instance_id}")
            else:
                logger.info(f"Instance {instance_id} has custom AI configuration")
            
            # Methods generation
            methods = ConfigDefaults.BUILTIN_METHODS.value.copy()
            methods.extend(self.config["global"].get("capabilities", []))
            methods.extend(instance_config.get("capabilities", []))
            methods_set = set(methods)
            methods_map = {}
            methods_map_config = {}
            for method in methods_set:
                method_class = AIMethodRegistry.get_method(method)
                if method_class:
                    methods_map[method] = method_class
                    methods_map_config[method] = methods_config.get(method, {})
                    logger.info(f"Registered method {method} for instance {instance_id}")
                else:
                    logger.warning(f"Method {method} not found")
                    

            instance_config["ai"]["methods"] = methods_map
            instance_config["methods_config"] = methods_map_config

            # Agents
            agents = bool(methods_map.get(ConfigDefaults.AGENT_METHOD.value, False))
            if agents:
                logger.info(f"Agents enabled for instance {instance_id}")

            # Generate system prompt for the instance
            instance_config["ai"]["prompt"] = SystemPromptGenerator.generate_system_prompt(self.config, instance_id, agents=agents)

    def load_config(self):
        """
        Loads the configuration for the JerryGemini AI integration.
        """
        self.logger.info("Loading config")
        raw_config = self.files.get_config(cache=False)

        self.config: dict = ConfigFileDefaults.CONFIG_SCHEMA(raw_config)
        self.process_instances()
        self.logger.info("Config loaded successfully")
        self._debug_write_config()
        
        # Debug
    def _debug_write_config(self):
        """
        Writes the current configuration to a debug file for inspection.
        """
        debug_file = self.files.get_cache_dir() + "/debug_config.yaml"
        with open(debug_file, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)


    def get_channel_list(self) -> list[int]:
        """
        Returns the list of channels configured for JerryGemini.

        Returns:
            list: A list of channel IDs configured for JerryGemini.
        """
        if not self.config or "instances" not in self.config:
            return []

        return list(self.config["instances"].keys())
    
    
    def get_system_prompt(self, instance_id: int) -> str:
        """
        Returns the system prompt for a specific instance.

        Args:
            instance_id (int): The ID of the instance to retrieve the prompt for.

        Returns:
            str: The system prompt for the specified instance.
        """
        if not self.config or "instances" not in self.config:
            return ""

        return SystemPromptGenerator.generate_system_prompt(self.config, instance_id)