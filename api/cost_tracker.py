"""
Cost Tracking Service for Fantasy Football Neuron
Real-time cost monitoring and budget enforcement
"""

import asyncio
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import json

from .cache_service import CacheService

logger = logging.getLogger(__name__)

@dataclass
class CostEvent:
    """Represents a single cost event"""
    timestamp: datetime
    service: str  # 'openai', 'elevenlabs', 'vertex_ai'
    operation: str  # 'tts', 'llm', 'embedding'
    cost: float
    metadata: Dict
    user_id: Optional[str] = None
    debate_id: Optional[str] = None

class CostTracker:
    """Tracks and manages API costs in real-time"""
    
    # Cost rates per service
    COST_RATES = {
        "elevenlabs": {
            "tts_premium": 0.030,  # per 1000 chars
            "tts_standard": 0.018  # per 1000 chars
        },
        "openai": {
            "tts": 0.015,  # per 1000 chars
            "gpt-4": 0.03,  # per 1K tokens (input)
            "gpt-4-output": 0.06  # per 1K tokens (output)
        },
        "vertex_ai": {
            "inference": 0.0005  # per prediction
        }
    }
    
    def __init__(
        self,
        daily_budget: float,
        cache_service: CacheService,
        alert_threshold: float = 0.8
    ):
        self.daily_budget = daily_budget
        self.cache_service = cache_service
        self.alert_threshold = alert_threshold
        self.current_costs: Dict[str, float] = {}
        self.cost_events: List[CostEvent] = []
        
        # Start background tasks
        asyncio.create_task(self._periodic_budget_check())
    
    async def track_cost(
        self,
        service: str,
        operation: str,
        units: float,
        metadata: Optional[Dict] = None,
        user_id: Optional[str] = None,
        debate_id: Optional[str] = None
    ) -> float:
        """Track a cost event and return the cost amount"""
        # Calculate cost based on service and operation
        cost = self._calculate_cost(service, operation, units)
        
        # Create cost event
        event = CostEvent(
            timestamp=datetime.utcnow(),
            service=service,
            operation=operation,
            cost=cost,
            metadata=metadata or {},
            user_id=user_id,
            debate_id=debate_id
        )
        
        # Store event
        await self._store_cost_event(event)
        
        # Update running totals
        date_key = datetime.utcnow().strftime("%Y-%m-%d")
        if date_key not in self.current_costs:
            self.current_costs[date_key] = 0.0
        self.current_costs[date_key] += cost
        
        # Check budget
        if await self._check_budget_exceeded():
            logger.warning(f"Daily budget exceeded! Current: ${self.current_costs[date_key]:.2f}")
            # Could trigger alerts or throttling here
        
        return cost
    
    def _calculate_cost(self, service: str, operation: str, units: float) -> float:
        """Calculate cost based on service rates"""
        if service == "elevenlabs":
            rate_key = "tts_premium" if "premium" in operation else "tts_standard"
            rate = self.COST_RATES["elevenlabs"][rate_key]
            return (units / 1000) * rate
        
        elif service == "openai":
            if operation == "tts":
                return (units / 1000) * self.COST_RATES["openai"]["tts"]
            elif operation == "llm_input":
                return (units / 1000) * self.COST_RATES["openai"]["gpt-4"]
            elif operation == "llm_output":
                return (units / 1000) * self.COST_RATES["openai"]["gpt-4-output"]
        
        elif service == "vertex_ai":
            return units * self.COST_RATES["vertex_ai"]["inference"]
        
        return 0.0
    
    async def _store_cost_event(self, event: CostEvent):
        """Store cost event in cache and append to events list"""
        # Keep in memory for quick access
        self.cost_events.append(event)
        
        # Limit memory usage - keep only last 1000 events
        if len(self.cost_events) > 1000:
            self.cost_events = self.cost_events[-1000:]
        
        # Store in Redis for persistence
        if self.cache_service.redis:
            key = f"cost_event:{event.timestamp.isoformat()}"
            await self.cache_service.set(
                key,
                {
                    "timestamp": event.timestamp.isoformat(),
                    "service": event.service,
                    "operation": event.operation,
                    "cost": event.cost,
                    "metadata": event.metadata,
                    "user_id": event.user_id,
                    "debate_id": event.debate_id
                },
                ttl=86400 * 7  # Keep for 7 days
            )
    
    async def get_daily_cost(self, date: Optional[datetime] = None) -> float:
        """Get total cost for a specific day"""
        if date is None:
            date = datetime.utcnow()
        
        date_key = date.strftime("%Y-%m-%d")
        return self.current_costs.get(date_key, 0.0)
    
    async def get_remaining_budget(self) -> float:
        """Get remaining budget for today"""
        daily_cost = await self.get_daily_cost()
        return max(0, self.daily_budget - daily_cost)
    
    async def _check_budget_exceeded(self) -> bool:
        """Check if daily budget is exceeded"""
        daily_cost = await self.get_daily_cost()
        return daily_cost >= self.daily_budget
    
    async def get_cost_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """Get detailed cost breakdown by service and operation"""
        if start_date is None:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0)
        if end_date is None:
            end_date = datetime.utcnow()
        
        breakdown = {
            "total": 0.0,
            "by_service": {},
            "by_operation": {},
            "by_hour": {},
            "cache_savings": 0.0
        }
        
        # Analyze cost events
        for event in self.cost_events:
            if start_date <= event.timestamp <= end_date:
                breakdown["total"] += event.cost
                
                # By service
                if event.service not in breakdown["by_service"]:
                    breakdown["by_service"][event.service] = 0.0
                breakdown["by_service"][event.service] += event.cost
                
                # By operation
                op_key = f"{event.service}:{event.operation}"
                if op_key not in breakdown["by_operation"]:
                    breakdown["by_operation"][op_key] = 0.0
                breakdown["by_operation"][op_key] += event.cost
                
                # By hour
                hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
                if hour_key not in breakdown["by_hour"]:
                    breakdown["by_hour"][hour_key] = 0.0
                breakdown["by_hour"][hour_key] += event.cost
        
        # Calculate cache savings
        cache_stats = await self.cache_service.get_stats()
        if cache_stats["hit_rate"] > 0:
            # Estimate savings based on cache hits
            avg_cost_per_request = breakdown["total"] / max(1, len(self.cost_events))
            breakdown["cache_savings"] = cache_stats["total_hits"] * avg_cost_per_request * 0.7
        
        return breakdown
    
    async def get_user_costs(self, user_id: str, days: int = 7) -> Dict[str, float]:
        """Get costs for a specific user"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        user_costs = {
            "total": 0.0,
            "by_day": {},
            "debate_count": 0
        }
        
        for event in self.cost_events:
            if event.user_id == user_id and event.timestamp >= cutoff_date:
                user_costs["total"] += event.cost
                
                day_key = event.timestamp.strftime("%Y-%m-%d")
                if day_key not in user_costs["by_day"]:
                    user_costs["by_day"][day_key] = 0.0
                user_costs["by_day"][day_key] += event.cost
                
                if event.debate_id:
                    user_costs["debate_count"] += 1
        
        return user_costs
    
    async def estimate_debate_cost(
        self,
        agents: List[str],
        estimated_turns: int = 10,
        use_cache: bool = True
    ) -> Dict[str, float]:
        """Estimate cost for a debate before running it"""
        estimates = {
            "llm_cost": 0.0,
            "voice_cost": 0.0,
            "total": 0.0,
            "cache_discount": 0.0
        }
        
        # Estimate LLM tokens (rough approximation)
        avg_tokens_per_turn = 150
        total_tokens = estimated_turns * len(agents) * avg_tokens_per_turn
        estimates["llm_cost"] = (total_tokens / 1000) * self.COST_RATES["openai"]["gpt-4-output"]
        
        # Estimate voice costs
        avg_chars_per_turn = 200
        for agent in agents:
            # Check if agent uses premium or standard voice
            if agent in ["marcus", "big_mike", "sam", "leo"]:
                # ElevenLabs premium
                char_cost = self.COST_RATES["elevenlabs"]["tts_premium"]
            else:
                # OpenAI TTS
                char_cost = self.COST_RATES["openai"]["tts"]
            
            total_chars = estimated_turns * avg_chars_per_turn
            estimates["voice_cost"] += (total_chars / 1000) * char_cost
        
        # Apply cache discount
        if use_cache:
            cache_hit_rate = await self.cache_service.get_hit_rate()
            estimates["cache_discount"] = estimates["voice_cost"] * cache_hit_rate
            estimates["voice_cost"] *= (1 - cache_hit_rate)
        
        estimates["total"] = estimates["llm_cost"] + estimates["voice_cost"]
        
        return estimates
    
    async def _periodic_budget_check(self):
        """Periodically check budget and send alerts"""
        while True:
            try:
                daily_cost = await self.get_daily_cost()
                budget_used_pct = daily_cost / self.daily_budget
                
                if budget_used_pct >= self.alert_threshold:
                    logger.warning(
                        f"Budget alert: {budget_used_pct:.1%} of daily budget used "
                        f"(${daily_cost:.2f} of ${self.daily_budget:.2f})"
                    )
                    # In production, send alerts via email/Slack/etc
                
                # Reset daily costs at midnight
                current_hour = datetime.utcnow().hour
                if current_hour == 0 and len(self.current_costs) > 1:
                    # Archive yesterday's costs
                    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
                    if yesterday in self.current_costs:
                        await self._archive_daily_costs(yesterday, self.current_costs[yesterday])
                        del self.current_costs[yesterday]
                
                # Wait 5 minutes before next check
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in budget check: {e}")
                await asyncio.sleep(60)
    
    async def _archive_daily_costs(self, date: str, total: float):
        """Archive daily cost summary"""
        if self.cache_service.redis:
            await self.cache_service.set(
                f"daily_cost_archive:{date}",
                {
                    "date": date,
                    "total": total,
                    "breakdown": await self.get_cost_breakdown(
                        datetime.strptime(date, "%Y-%m-%d"),
                        datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
                    )
                },
                ttl=86400 * 30  # Keep for 30 days
            )
            logger.info(f"Archived costs for {date}: ${total:.2f}")
