"""Simple plugin maker script."""

import os
import sys

# Config
possible_paths = [
    "./src/jerry_bot/plugins",
    "./plugins",
]

base_plugin="""\"\"\"Main Module for {class_name}\"\"\"

# squid_core imports
from squid_core.plugin_base import Plugin, PluginCog
from squid_core.framework import Framework

class {class_name}(Plugin):
    \"\"\"{class_name} Plugin.\"\"\"

    def __init__(self, framework: Framework):
        super().__init__(framework)
        
    async def load(self):
        \"\"\"Load the {class_name} Plugin.\"\"\"
        pass
        
    async def unload(self):
        \"\"\"Unload the {class_name} Plugin.\"\"\"
        pass
"""
base_init="""\"\"\"{class_name} plugin\"\"\"
from .plugin import {class_name}
"""
base_config="""[plugin]
name = "{dir_name}"
description = "Description for {dir_name} plugin"
class = "{class_name}"
"""

def get_plugins_directory():
    """Get the absolute path to the plugins directory."""
    for path in possible_paths:
        abs_path = os.path.abspath(path)
        if os.path.isdir(abs_path):
            print(f"Using plugins directory: {abs_path}")
            return abs_path
        
    # Try parent dir
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), ".."))
    for path in possible_paths:
        abs_path = os.path.join(parent_dir, path)
        if os.path.isdir(abs_path):
            print(f"Using plugins directory: {abs_path}")
            return abs_path

    print("Could not find plugins directory!", file=sys.stderr)
    sys.exit(1)
    
def make_dir_name(name):
    """Convert a plugin name to a valid directory name."""
    return name.lower().replace(" ", "_")
def make_class_name(name):
    """Convert a plugin name to a valid class name."""
    return "".join(word.capitalize() for word in name.split(" "))
    
def make_plugin(plugin_name):
    """Create a new plugin file with the given name."""
    plugins_dir = get_plugins_directory()
    dir_name = make_dir_name(plugin_name)
    class_name = make_class_name(plugin_name)
    
    plugin_path = os.path.join(plugins_dir, dir_name)
    if os.path.exists(plugin_path):
        print(f"Plugin directory '{plugin_path}' already exists!", file=sys.stderr)
        sys.exit(1)


    os.makedirs(plugin_path)
    
    # Create plugin.py
    with open(os.path.join(plugin_path, "plugin.py"), "w") as f:
        f.write(base_plugin.format(dir_name=dir_name, class_name=class_name))
    # Create __init__.py
    with open(os.path.join(plugin_path, "__init__.py"), "w") as f:
        f.write(base_init.format(dir_name=dir_name, class_name=class_name))
    # Create config.toml
    with open(os.path.join(plugin_path, "plugin.toml"), "w") as f:
        f.write(base_config.format(dir_name=dir_name, class_name=class_name))
    print(f"Created plugin '{plugin_name}' at '{plugin_path}'")

def main():
    """Main function."""
    if len(sys.argv) != 2:
        print("Usage: python make_plugin.py <Plugin Name>", file=sys.stderr)
        sys.exit(1)
        
    plugin_name = sys.argv[1]
    make_plugin(plugin_name)
    
if __name__ == "__main__":
    main()