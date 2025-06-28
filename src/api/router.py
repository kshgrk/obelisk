"""
Main API router for Obelisk chat application
Aggregates all API routes and provides a single import point
"""

from fastapi import APIRouter
from .sessions import router as sessions_router
from .chat import router as chat_router

# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(sessions_router)
api_router.include_router(chat_router)

# Health check endpoint for the API
@api_router.get("/health")
async def api_health():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "api_version": "1.0.0",
        "available_endpoints": [
            "/sessions - Session management",
            "/chat - Chat completions and messaging",
            "/health - API health check"
        ]
    } 