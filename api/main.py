"""
Fantasy Football Neuron API
Main FastAPI application
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import os
from typing import List, Optional, Dict
import uuid
import logging

from .routes import debates, agents, voice
from .services.cache_service import CacheService
from .services.cost_tracker import CostTracker
from agents.debate_engine import DebateOrchestrator
from agents.agent_responses import ResponseGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
cache_service = None
cost_tracker = None
debate_orchestrator = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    global cache_service, cost_tracker, debate_orchestrator
    
    # Initialize services
    cache_service = CacheService(
        redis_url=os.getenv("UPSTASH_REDIS_URL"),
        redis_token=os.getenv("UPSTASH_REDIS_TOKEN")
    )
    
    cost_tracker = CostTracker(
        daily_budget=float(os.getenv("DAILY_BUDGET", "50.0")),
        cache_service=cache_service
    )
    
    response_generator = ResponseGenerator(
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    debate_orchestrator = DebateOrchestrator(
        response_generator=response_generator
    )
    
    logger.info("Services initialized successfully")
    
    yield
    
    # Cleanup
    await cache_service.close()
    logger.info("Services cleaned up")

# Create FastAPI app
app = FastAPI(
    title="Fantasy Football Neuron API",
    description="AI-powered fantasy football debate platform",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://fantasyfootballneuron.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(debates.router, prefix="/api/debates", tags=["debates"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(voice.router, prefix="/api/voice", tags=["voice"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Fantasy Football Neuron API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    checks = {
        "api": "healthy",
        "cache": "unknown",
        "cost_tracker": "unknown"
    }
    
    # Check cache
    try:
        if cache_service:
            await cache_service.redis.ping()
            checks["cache"] = "healthy"
    except Exception as e:
        checks["cache"] = f"unhealthy: {str(e)}"
    
    # Check cost tracker
    try:
        if cost_tracker:
            budget = await cost_tracker.get_remaining_budget()
            checks["cost_tracker"] = f"healthy (${budget:.2f} remaining)"
    except Exception as e:
        checks["cost_tracker"] = f"unhealthy: {str(e)}"
    
    # Overall status
    all_healthy = all(
        v == "healthy" or v.startswith("healthy") 
        for v in checks.values()
    )
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks
    }

@app.get("/api/stats")
async def get_stats():
    """Get platform statistics"""
    stats = {
        "total_debates": 0,
        "active_debates": 0,
        "cache_hit_rate": 0.0,
        "daily_cost": 0.0,
        "remaining_budget": 0.0
    }
    
    if debate_orchestrator:
        stats["active_debates"] = len(debate_orchestrator.active_debates)
    
    if cache_service:
        stats["cache_hit_rate"] = await cache_service.get_hit_rate()
    
    if cost_tracker:
        stats["daily_cost"] = await cost_tracker.get_daily_cost()
        stats["remaining_budget"] = await cost_tracker.get_remaining_budget()
    
    return stats

# WebSocket endpoint for real-time debates
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/debate/{debate_id}")
async def websocket_debate(websocket: WebSocket, debate_id: str):
    """WebSocket for real-time debate updates"""
    await websocket.accept()
    
    try:
        # Get or create debate
        debate = debate_orchestrator.active_debates.get(debate_id)
        if not debate:
            await websocket.send_json({
                "type": "error",
                "message": "Debate not found"
            })
            return
        
        # Send initial state
        await websocket.send_json({
            "type": "debate_state",
            "debate": {
                "topic": debate.topic,
                "agents": [a.name for a in debate.agents],
                "turns": len(debate.turns)
            }
        })
        
        # Listen for commands
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "continue":
                # Generate next turns
                new_turns = await debate_orchestrator.continue_debate(
                    debate,
                    num_turns=data.get("num_turns", 1)
                )
                
                # Send each turn as it's generated
                for turn in new_turns:
                    await websocket.send_json({
                        "type": "new_turn",
                        "turn": {
                            "agent": turn.agent.name,
                            "text": turn.text,
                            "emotion": turn.emotion,
                            "responding_to": turn.responding_to
                        }
                    })
                    
                    # Simulate voice generation delay
                    await asyncio.sleep(0.5)
            
            elif data["type"] == "conclude":
                # Generate conclusion
                conclusion = await debate_orchestrator.conclude_debate(debate)
                await websocket.send_json({
                    "type": "conclusion",
                    "turn": {
                        "agent": conclusion.agent.name,
                        "text": conclusion.text
                    }
                })
            
            elif data["type"] == "end":
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for debate {debate_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle value errors"""
    return {
        "error": str(exc),
        "status_code": 400
    }

# Middleware for request tracking
from fastapi import Request
import time

@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Track request metrics"""
    start_time = time.time()
    
    # Log request
    logger.info(f"{request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Track metrics
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
    # Track costs for voice endpoints
    if "/voice/generate" in request.url.path and cost_tracker:
        # This would be done properly in the route handler
        pass
    
    return response

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
