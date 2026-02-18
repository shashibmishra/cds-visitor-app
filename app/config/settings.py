"""
Application configuration management.
Loads settings from environment variables with sensible defaults.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional


log = logging.getLogger(__name__)


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str
    port: int
    db: int = 0
    password: Optional[str] = None
    socket_connect_timeout: int = 5
    socket_keepalive: bool = True
    
    @classmethod
    def from_env(cls):
        """Load Redis config from environment variables."""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            password=os.getenv("REDIS_PASSWORD"),
            socket_connect_timeout=int(os.getenv("REDIS_TIMEOUT", 5)),
        )


@dataclass
class FlaskConfig:
    """Flask application configuration."""
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls):
        """Load Flask config from environment variables."""
        return cls(
            debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            host=os.getenv("FLASK_HOST", "0.0.0.0"),
            port=int(os.getenv("FLASK_PORT", 5000)),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass
class AppConfig:
    """Application-wide configuration."""
    environment: str
    redis: RedisConfig
    flask: FlaskConfig
    counter_key: str = "visitor_count"
    max_retries: int = 3
    
    @classmethod
    def from_env(cls):
        """Load all config from environment."""
        environment = os.getenv("ENVIRONMENT", "development")
        return cls(
            environment=environment,
            redis=RedisConfig.from_env(),
            flask=FlaskConfig.from_env(),
            counter_key=os.getenv("COUNTER_KEY", "visitor_count"),
            max_retries=int(os.getenv("MAX_RETRIES", 3)),
        )


def get_config() -> AppConfig:
    """Get application configuration (singleton pattern)."""
    if not hasattr(get_config, "_instance"):
        get_config._instance = AppConfig.from_env()
        log.info(f"Loaded config for environment: {get_config._instance.environment}")
    return get_config._instance
