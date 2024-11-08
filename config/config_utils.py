import os
import yaml
from typing import Dict, Any

class ConfigManager:
    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self.load_config()

    def load_config(self):
        """Load the configuration file."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config',
            'app_config.yaml'
        )
        try:
            with open(config_path, 'r') as file:
                self._config = yaml.safe_load(file)
        except Exception as e:
            print(f"Error loading config file: {e}")
            self._config = {}

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.
        Example: config.get('server', 'port', default=4567)
        """
        value = self._config
        for key in keys:
            if not isinstance(value, dict):
                return default
            value = value.get(key, default)
            if value is None:
                return default
        return value

# Global configuration instance
config = ConfigManager()
