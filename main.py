"""
Obelisk FastAPI Server - Main Application Entry Point with Temporal Integration
"""

import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load environment variables from .env file
load_dotenv()

# Import database manager, temporal client and API router
from src.database.manager import db_manager
from src.temporal.client import temporal_client
from src.api.router import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database, event system, and test Temporal connection on startup"""
    logger.info("Starting Obelisk FastAPI server with Temporal integration...")

    # Initialize database
    await db_manager.initialize()
    logger.info("Database initialized")

    # Test Temporal connection (optional - don't fail startup if Temporal is down)
    try:
        _ = await temporal_client.connect()
        await temporal_client.disconnect()
        logger.info("Temporal connection verified")
    except Exception as e:
        logger.warning(f"Temporal connection failed (will retry on requests): {e}")

    logger.info("Server startup complete")

    yield

    logger.info("Shutting down Obelisk FastAPI server...")

    logger.info("Server shutdown complete")

app = FastAPI(title="Obelisk - OpenRouter FastAPI Server", version="0.1.0", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
