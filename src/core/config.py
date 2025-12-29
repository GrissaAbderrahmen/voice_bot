"""
Configuration management for Voice Assistant.
Loads settings from config.yaml with environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv


class Config:
    """Central configuration manager."""
    
    _instance: Optional['Config'] = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls) -> 'Config':
        """Singleton pattern - only one config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance
    
    def _load(self) -> None:
        """Load configuration from file and environment."""
        # Load .env file
        load_dotenv()
        
        # Find config file
        config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._defaults()
            
        # Apply environment overrides
        self._apply_env_overrides()
    
    def _defaults(self) -> Dict[str, Any]:
        """Default configuration values."""
        return {
            "assistant": {
                "name": "Nova",
                "wake_word": "hey nova",
                "languages": ["en", "fr"]
            },
            "whisper": {
                "model": "base",
                "device": "cpu"
            },
            "tts": {
                "engine": "edge",
                "voice_en": "en-US-AriaNeural",
                "voice_fr": "fr-FR-DeniseNeural",
                "rate": "+0%"
            },
            "openai": {
                "model": "gpt-4o-mini",
                "max_tokens": 500,
                "temperature": 0.7
            },
            "audio": {
                "sample_rate": 16000,
                "channels": 1,
                "silence_duration": 1.5,
                "energy_threshold": 300
            },
            "conversation": {
                "max_history": 20,
                "persist": True,
                "persist_path": "./conversations/"
            },
            "system_prompt": "You are Nova, a helpful voice assistant. Be concise and conversational.",
            "web": {
                "host": "127.0.0.1",
                "port": 5000,
                "debug": False
            },
            "logging": {
                "level": "INFO",
                "file": "./logs/assistant.log"
            }
        }
    
    def _apply_env_overrides(self) -> None:
        """Override config with environment variables."""
        # OpenAI API key
        if api_key := os.getenv("OPENAI_API_KEY"):
            self._config.setdefault("openai", {})["api_key"] = api_key
            
        # Porcupine access key
        if porcupine_key := os.getenv("PORCUPINE_ACCESS_KEY"):
            self._config.setdefault("porcupine", {})["access_key"] = porcupine_key
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a config value by key path.
        
        Example:
            config.get("openai", "model")  # Returns "gpt-4o-mini"
            config.get("audio", "sample_rate")  # Returns 16000
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        """Dict-like access: config["openai"]"""
        return self._config.get(key)
    
    @property
    def assistant_name(self) -> str:
        return self.get("assistant", "name", default="Nova")
    
    @property
    def wake_word(self) -> str:
        return self.get("assistant", "wake_word", default="hey nova")
    
    @property
    def languages(self) -> List[str]:
        return self.get("assistant", "languages", default=["en", "fr"])
    
    @property
    def whisper_model(self) -> str:
        return self.get("whisper", "model", default="base")
    
    @property
    def whisper_device(self) -> str:
        return self.get("whisper", "device", default="cpu")
    
    @property
    def tts_voice_en(self) -> str:
        return self.get("tts", "voice_en", default="en-US-AriaNeural")
    
    @property
    def tts_voice_fr(self) -> str:
        return self.get("tts", "voice_fr", default="fr-FR-DeniseNeural")
    
    @property
    def tts_rate(self) -> str:
        return self.get("tts", "rate", default="+0%")
    
    @property
    def openai_api_key(self) -> Optional[str]:
        return self.get("openai", "api_key")
    
    @property
    def openai_model(self) -> str:
        return self.get("openai", "model", default="gpt-4o-mini")
    
    @property
    def system_prompt(self) -> str:
        return self.get("system_prompt", default="You are a helpful assistant.")
    
    @property
    def sample_rate(self) -> int:
        return self.get("audio", "sample_rate", default=16000)
    
    @property
    def silence_duration(self) -> float:
        return self.get("audio", "silence_duration", default=1.5)
    
    @property
    def max_history(self) -> int:
        return self.get("conversation", "max_history", default=20)
    
    @property
    def persist_conversations(self) -> bool:
        return self.get("conversation", "persist", default=True)
    
    @property
    def conversations_path(self) -> Path:
        path = self.get("conversation", "persist_path", default="./conversations/")
        return Path(path)
    
    @property
    def log_level(self) -> str:
        return self.get("logging", "level", default="INFO")
    
    @property
    def log_file(self) -> Optional[str]:
        return self.get("logging", "file")
    
    @property
    def web_host(self) -> str:
        return self.get("web", "host", default="127.0.0.1")
    
    @property
    def web_port(self) -> int:
        return self.get("web", "port", default=5000)
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load()
    
    def to_dict(self) -> Dict[str, Any]:
        """Return full config as dictionary (excluding secrets)."""
        config = self._config.copy()
        # Remove sensitive values
        if "openai" in config:
            config["openai"] = {k: v for k, v in config["openai"].items() if k != "api_key"}
        if "porcupine" in config:
            config["porcupine"] = {k: v for k, v in config["porcupine"].items() if k != "access_key"}
        return config
