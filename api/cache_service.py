"""
Cache Service for Fantasy Football Neuron
Multi-layer caching for voice audio and API responses
"""

import asyncio
import hashlib
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import aioredis
import aiohttp
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Represents a cached item"""
    key: str
    value: Any
    timestamp: float
    ttl: int
    hit_count: int = 0
    size_bytes: int = 0

class CacheService:
    """Multi-layer cache service with L1 (Redis) and L2 (Storage)"""
    
    def __init__(
        self,
        redis_url: str,
        redis_token: str,
        storage_bucket: Optional[str] = None
    ):
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.storage_bucket = storage_bucket
        self.redis: Optional[aioredis.Redis] = None
        self.memory_cache: Dict[str, CacheEntry] = {}  # In-memory L0 cache
        self.stats = {
            "hits": 0,
            "misses": 0,
            "l0_hits": 0,
            "l1_hits": 0,
            "l2_hits": 0
        }
        
        # Initialize connection
        asyncio.create_task(self._init_redis())
    
    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis = aioredis.from_url(
                self.redis_url,
                password=self.redis_token,
                decode_responses=True
            )
            await self.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
    
    def _generate_key(self, prefix: str, content: str, params: Optional[Dict] = None) -> str:
        """Generate cache key"""
        key_parts = [prefix, content]
        if params:
            key_parts.append(json.dumps(params, sort_keys=True))
        
        key_string = ":".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    async def get(
        self,
        key: str,
        check_l2: bool = True
    ) -> Optional[Any]:
        """Get item from cache"""
        # L0: Memory cache
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if time.time() - entry.timestamp < entry.ttl:
                entry.hit_count += 1
                self.stats["hits"] += 1
                self.stats["l0_hits"] += 1
                logger.debug(f"L0 cache hit: {key}")
                return entry.value
            else:
                # Expired
                del self.memory_cache[key]
        
        # L1: Redis cache
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value:
                    self.stats["hits"] += 1
                    self.stats["l1_hits"] += 1
                    logger.debug(f"L1 cache hit: {key}")
                    
                    # Promote to L0
                    self._add_to_memory_cache(key, value, ttl=300)
                    
                    return json.loads(value) if isinstance(value, str) else value
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        # L2: Storage bucket (for audio files)
        if check_l2 and self.storage_bucket:
            value = await self._get_from_storage(key)
            if value:
                self.stats["hits"] += 1
                self.stats["l2_hits"] += 1
                logger.debug(f"L2 cache hit: {key}")
                
                # Promote to L1 and L0
                await self.set(key, value, ttl=3600)
                
                return value
        
        self.stats["misses"] += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 3600,
        store_l2: bool = False
    ) -> bool:
        """Set item in cache"""
        try:
            # L0: Always store in memory for fast access
            self._add_to_memory_cache(key, value, ttl)
            
            # L1: Redis
            if self.redis:
                if isinstance(value, (dict, list)):
                    value_str = json.dumps(value)
                else:
                    value_str = str(value)
                
                await self.redis.setex(key, ttl, value_str)
                logger.debug(f"Cached to L1: {key}")
            
            # L2: Storage for permanent items (e.g., audio files)
            if store_l2 and self.storage_bucket:
                await self._store_to_storage(key, value)
                logger.debug(f"Cached to L2: {key}")
            
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def _add_to_memory_cache(self, key: str, value: Any, ttl: int):
        """Add item to memory cache with LRU eviction"""
        # Simple size limit (1000 items)
        if len(self.memory_cache) >= 1000:
            # Remove least recently hit item
            lru_key = min(
                self.memory_cache.keys(),
                key=lambda k: self.memory_cache[k].hit_count
            )
            del self.memory_cache[lru_key]
        
        self.memory_cache[key] = CacheEntry(
            key=key,
            value=value,
            timestamp=time.time(),
            ttl=ttl,
            size_bytes=len(str(value))
        )
    
    async def get_audio(
        self,
        agent: str,
        text: str,
        voice_settings: Optional[Dict] = None
    ) -> Optional[bytes]:
        """Get cached audio for agent/text combination"""
        key = self._generate_key(f"audio:{agent}", text, voice_settings)
        
        # Check cache
        cached = await self.get(key, check_l2=True)
        if cached and isinstance(cached, dict) and "audio_data" in cached:
            # Decode base64 audio data
            import base64
            return base64.b64decode(cached["audio_data"])
        
        return None
    
    async def set_audio(
        self,
        agent: str,
        text: str,
        audio_data: bytes,
        voice_settings: Optional[Dict] = None,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Cache audio data"""
        key = self._generate_key(f"audio:{agent}", text, voice_settings)
        
        # Encode audio as base64 for JSON storage
        import base64
        cache_data = {
            "audio_data": base64.b64encode(audio_data).decode('utf-8'),
            "agent": agent,
            "text": text,
            "duration_ms": duration_ms,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        # Store in L1 for 1 hour, L2 permanently
        return await self.set(key, cache_data, ttl=3600, store_l2=True)
    
    async def cache_common_phrases(self):
        """Pre-cache common fantasy football phrases"""
        common_phrases = {
            "marcus": [
                "The regression model shows",
                "Statistical edge",
                "Objectively speaking",
                "The numbers never lie"
            ],
            "big_mike": [
                "Trust your gut",
                "Let it ride",
                "He's got that dog in him",
                "The eye test"
            ],
            "zareena": [
                "Fade the chalk",
                "When everyone zigs",
                "Contrarian play",
                "Ownership leverage"
            ],
            "sam": [
                "I've seen this before",
                "Been burned by that",
                "Experience tells me",
                "Long game"
            ],
            "leo": [
                "The projections say",
                "Ceiling play",
                "Why not go for it",
                "Analytics suggest"
            ],
            "architect": [
                "Game theory dictates",
                "Second-order thinking",
                "The meta suggests",
                "Consider the implications"
            ]
        }
        
        # In production, these would be pre-generated audio files
        for agent, phrases in common_phrases.items():
            for phrase in phrases:
                key = self._generate_key(f"audio:{agent}", phrase)
                # Store placeholder data
                await self.set(key, {"text": phrase, "cached": True}, ttl=86400)
        
        logger.info(f"Pre-cached {sum(len(p) for p in common_phrases.values())} common phrases")
    
    async def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.stats["hits"] + self.stats["misses"]
        if total == 0:
            return 0.0
        return self.stats["hits"] / total
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics"""
        hit_rate = await self.get_hit_rate()
        
        return {
            "hit_rate": hit_rate,
            "total_hits": self.stats["hits"],
            "total_misses": self.stats["misses"],
            "l0_hits": self.stats["l0_hits"],
            "l1_hits": self.stats["l1_hits"],
            "l2_hits": self.stats["l2_hits"],
            "memory_cache_size": len(self.memory_cache),
            "memory_cache_bytes": sum(e.size_bytes for e in self.memory_cache.values())
        }
    
    async def clear_expired(self):
        """Clear expired entries from memory cache"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.memory_cache.items()
            if current_time - entry.timestamp > entry.ttl
        ]
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired entries from memory cache")
    
    async def _get_from_storage(self, key: str) -> Optional[Any]:
        """Get from L2 storage (Cloud Storage/S3)"""
        # Placeholder for cloud storage integration
        # In production, this would fetch from GCS/S3
        return None
    
    async def _store_to_storage(self, key: str, value: Any) -> bool:
        """Store to L2 storage (Cloud Storage/S3)"""
        # Placeholder for cloud storage integration
        # In production, this would upload to GCS/S3
        return True
    
    async def close(self):
        """Close connections"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
