import json
from abc import ABC, abstractmethod
from pathlib import Path


class ConfigError(Exception):
    """An error encountered while loading configuration or running a command."""

class Config(ABC):
    """The abstract class to support the configuration"""
    @abstractmethod
    def load(self, path: Path) -> list[str]:
        pass

class JSONConfig(Config):
    @classmethod
    def load(self, path: Path) -> list[str]:
        """Read and validate the cluster list."""
        try:
            with path.open(encoding="utf-8") as config_file:
                data = json.load(config_file)
        except FileNotFoundError as exc:
            raise ConfigError(f"Configuration file not found: {path}") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Cannot read configuration {path}: {exc}") from exc

        if not isinstance(data, dict) or not isinstance(data.get("clusters"), list):
            raise ConfigError("Configuration must contain a 'clusters' array.")
        clusters = data["clusters"]

        if not all(isinstance(cluster, str) and cluster.strip() for cluster in clusters):
            raise ConfigError("Every cluster must be a non-empty string.")
        return clusters
