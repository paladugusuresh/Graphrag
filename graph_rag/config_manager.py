# graph_rag/config_manager.py
"""
Centralized configuration manager with lazy loading and reload support.
Eliminates import-time config reads and allows runtime configuration changes.
"""

import os
import yaml
from typing import Dict, Any, Optional, Callable
from pathlib import Path


class ConfigManager:
    """
    Singleton configuration manager that loads config.yaml on-demand.
    Supports reload notifications and development mode with fallback defaults.
    """
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[Dict[str, Any]] = None
    _reload_callbacks: list[Callable] = []
    _config_path: str = "config.yaml"
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """Get or create singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset singleton (for testing)"""
        cls._instance = None
        cls._config = None
        cls._reload_callbacks = []
    
    def set_config_path(self, path: str):
        """Set custom config file path"""
        self._config_path = path
        self._config = None  # Force reload
    
    def _load_config(self) -> Dict[str, Any]:
        """Load config from file or return defaults in DEV_MODE"""
        dev_mode = os.getenv("DEV_MODE", "").lower() in ("true", "1", "yes")
        
        # Try to load from file
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                if not dev_mode:
                    raise RuntimeError(f"Failed to load config from {self._config_path}: {e}")
        
        # In DEV_MODE or if file missing, return safe defaults
        if dev_mode:
            return self._get_dev_defaults()
        else:
            raise FileNotFoundError(f"Config file not found: {self._config_path}")
    
    def _get_dev_defaults(self) -> Dict[str, Any]:
        """Return safe default configuration for development/testing"""
        return {
            "logging": {
                "level": "INFO",
                "format": "%(message)s"
            },
            "schema": {
                "allow_list_path": "allow_list.json"
            },
            "retriever": {
                "max_chunks": 5
            },
            "guardrails": {
                "neo4j_timeout": 10,
                "max_cypher_results": 25,
                "max_traversal_depth": 2
            },
            "observability": {
                "metrics_enabled": False,  # Disabled in dev mode
                "metrics_port": 8000
            },
            "llm": {
                "provider": "openai",
                "model": "gpt-4o",
                "max_tokens": 512,
                "rate_limit_per_minute": 60,
                "redis_url": "redis://localhost:6379/0"
            },
            "schema_embeddings": {
                "index_name": "schema_embeddings",
                "node_label": "SchemaTerm",
                "embedding_model": "text-embedding-3-small",
                "top_k": 5
            }
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration, loading it if necessary"""
        if self._config is None:
            self._config = self._load_config()
        return self._config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get config value by dot-separated path.
        Examples:
            get("llm.model") -> "gpt-4o"
            get("guardrails.neo4j_timeout") -> 10
        """
        config = self.get_config()
        keys = key_path.split('.')
        
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def reload(self):
        """Reload configuration from file and notify subscribers"""
        self._config = self._load_config()
        
        # Notify all registered callbacks
        for callback in self._reload_callbacks:
            try:
                callback(self._config)
            except Exception as e:
                # Log but don't fail on callback errors
                print(f"Error in config reload callback: {e}")
    
    def subscribe_to_reload(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback to be notified when config is reloaded"""
        if callback not in self._reload_callbacks:
            self._reload_callbacks.append(callback)
    
    def unsubscribe_from_reload(self, callback: Callable):
        """Unregister a reload callback"""
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)


# Global singleton instance accessor
_config_manager: Optional[ConfigManager] = None


def get_config() -> Dict[str, Any]:
    """
    Get the current configuration.
    This is the primary API for accessing configuration.
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    return _config_manager.get_config()


def get_config_value(key_path: str, default: Any = None) -> Any:
    """
    Get a specific config value by dot-separated path.
    Examples:
        get_config_value("llm.model") -> "gpt-4o"
        get_config_value("missing.key", "default") -> "default"
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    return _config_manager.get(key_path, default)


def reload_config():
    """Reload configuration from file"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    _config_manager.reload()


def subscribe_to_config_reload(callback: Callable[[Dict[str, Any]], None]):
    """Subscribe to config reload notifications"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    _config_manager.subscribe_to_reload(callback)

