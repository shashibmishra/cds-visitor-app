"""
Redis cache service with retry logic and error handling.
Provides abstraction layer over redis-py client.
"""

import logging
import redis
from typing import Optional, Any
from functools import wraps
import time

log = logging.getLogger(__name__)


class CacheConnectionError(Exception):
    """Custom exception for cache connection failures."""
    pass


class CacheService:
    """Wraps Redis client with retry logic and graceful degradation."""
    
    def __init__(self, host: str, port: int, db: int = 0, password: Optional[str] = None,
                 socket_connect_timeout: int = 5, max_retries: int = 3):
        """
        Initialize Redis cache service.
        
        Args:
            host: Redis server hostname
            port: Redis server port
            db: Database number (default 0)
            password: Redis password (if required)
            socket_connect_timeout: Connection timeout in seconds
            max_retries: Max retry attempts on failure
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.socket_connect_timeout = socket_connect_timeout
        self.max_retries = max_retries
        self._client: Optional[redis.Redis] = None
        self._is_available = False
        
        self._connect()
    
    def _connect(self) -> None:
        """Establish Redis connection with retry logic."""
        for attempt in range(self.max_retries):
            try:
                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    password=self.password,
                    socket_connect_timeout=self.socket_connect_timeout,
                    decode_responses=True,
                    retry_on_timeout=True,
                )
                # Ping to verify connection
                self._client.ping()
                self._is_available = True
                log.info(f"Connected to Redis at {self.host}:{self.port}")
                return
            
            except (redis.ConnectionError, redis.TimeoutError) as e:
                log.warning(f"Redis connection attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    log.error(f"Failed to connect to Redis after {self.max_retries} attempts")
                    self._is_available = False
    
    def is_available(self) -> bool:
        """Check if Redis is available."""
        return self._is_available
    
    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a counter by amount.
        
        Args:
            key: Counter key
            amount: Amount to increment (default 1)
        
        Returns:
            New counter value, or None if unavailable
        """
        if not self._is_available or not self._client:
            log.warning(f"Attempted to increment '{key}' but Redis is unavailable")
            return None
        
        try:
            return self._client.incrby(key, amount)
        except redis.RedisError as e:
            log.exception(f"Error incrementing '{key}': {e}")
            self._is_available = False
            return None
    
    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        if not self._is_available or not self._client:
            return None
        
        try:
            return self._client.get(key)
        except redis.RedisError as e:
            log.exception(f"Error getting '{key}': {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value with optional TTL (in seconds)."""
        if not self._is_available or not self._client:
            return False
        
        try:
            self._client.set(key, value, ex=ttl)
            return True
        except redis.RedisError as e:
            log.exception(f"Error setting '{key}': {e}")
            return False
    
    def health_check(self) -> bool:
        """Perform health check on Redis connection."""
        try:
            if self._client:
                self._client.ping()
                self._is_available = True
                return True
        except redis.RedisError:
            self._is_available = False
        
        return False


# Global cache service instance
_cache_service: Optional[CacheService] = None


def init_cache_service(host: str, port: int, db: int = 0, password: Optional[str] = None,
                       socket_connect_timeout: int = 5, max_retries: int = 3) -> CacheService:
    """Initialize global cache service."""
    global _cache_service
    _cache_service = CacheService(
        host=host,
        port=port,
        db=db,
        password=password,
        socket_connect_timeout=socket_connect_timeout,
        max_retries=max_retries,
    )
    return _cache_service


def get_cache_service() -> Optional[CacheService]:
    """Get global cache service instance."""
    return _cache_service
