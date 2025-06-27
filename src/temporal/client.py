"""
Temporal client setup for Obelisk integration
"""
import logging
from typing import Optional
from temporalio.client import Client

from src.config.settings import settings

logger = logging.getLogger(__name__)


class TemporalClientError(Exception):
    """Base exception for Temporal client operations"""
    pass


class TemporalClientManager:
    """Manages Temporal client connection and operations"""
    
    def __init__(self):
        self._client: Optional[Client] = None
    
    async def connect(self) -> Client:
        """Connect to Temporal server and return client instance"""
        if self._client is not None:
            return self._client
        
        try:
            # For development, we'll use insecure connection
            # In production, you would configure TLS
            self._client = await Client.connect(
                target_host=settings.temporal.server_url,
                namespace=settings.temporal.namespace,
                # tls=TLSConfig() if production else None
            )
            
            logger.info(f"Connected to Temporal server at {settings.temporal.server_url}")
            return self._client
            
        except Exception as e:
            logger.error(f"Failed to connect to Temporal server: {e}")
            raise TemporalClientError(f"Temporal connection failed: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from Temporal server"""
        if self._client is not None:
            try:
                # Temporal client doesn't have explicit disconnect method
                # Connection is automatically managed
                self._client = None
                logger.info("Disconnected from Temporal server")
            except Exception as e:
                logger.error(f"Error during Temporal disconnect: {e}")
    
    async def health_check(self) -> bool:
        """Check if Temporal server is accessible"""
        try:
            client = await self.connect()
            # Simple health check - if we can connect, consider it healthy
            return client is not None
        except Exception as e:
            logger.error(f"Temporal health check failed: {e}")
            return False
    
    @property
    def client(self) -> Optional[Client]:
        """Get the current client instance (may be None if not connected)"""
        return self._client
    
    async def get_client(self) -> Client:
        """Get connected client instance, connecting if necessary"""
        if self._client is None:
            self._client = await self.connect()
        return self._client


# Global Temporal client manager instance
temporal_client = TemporalClientManager() 