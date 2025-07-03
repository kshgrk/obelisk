"""
Model capability detection and management for tool calling support
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
import aiohttp
import json

from src.config.settings import settings
from src.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class ModelCapability:
    """Data class for model capabilities"""
    model_id: str
    name: str
    supports_tool_calls: bool
    context_length: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class ModelCapabilityManager:
    """Manages model capabilities and tool calling support detection"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager or DatabaseManager()
        self._capability_cache: Dict[str, ModelCapability] = {}
        self._cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        self._last_cache_update: Optional[datetime] = None
        
    async def initialize(self):
        """Initialize the capability manager and load cached capabilities"""
        await self.db_manager.initialize()
        await self._load_capabilities_cache()
        logger.info("Model capability manager initialized")
    
    async def _load_capabilities_cache(self):
        """Load model capabilities into cache from database"""
        try:
            models = await self.db_manager.get_models()
            self._capability_cache.clear()
            
            for model in models:
                capability = ModelCapability(
                    model_id=model['id'],
                    name=model['name'],
                    supports_tool_calls=bool(model['is_tool_call']),
                    context_length=model.get('context_length', 0),
                    created_at=datetime.fromisoformat(model['created_at']) if model.get('created_at') else None,
                    updated_at=datetime.fromisoformat(model['updated_at']) if model.get('updated_at') else None
                )
                self._capability_cache[model['id']] = capability
            
            self._last_cache_update = datetime.utcnow()
            logger.info(f"Loaded {len(self._capability_cache)} model capabilities into cache")
            
        except Exception as e:
            logger.error(f"Failed to load capabilities cache: {e}")
            raise
    
    async def _refresh_cache_if_needed(self):
        """Refresh cache if it's stale"""
        if (self._last_cache_update is None or 
            datetime.utcnow() - self._last_cache_update > self._cache_ttl):
            await self._load_capabilities_cache()
    
    async def supports_tool_calls(self, model_id: str) -> bool:
        """Check if a specific model supports tool calling"""
        try:
            await self._refresh_cache_if_needed()
            
            capability = self._capability_cache.get(model_id)
            if capability:
                return capability.supports_tool_calls
            
            # If not in cache, check database directly
            async with self.db_manager.get_connection() as db:
                cursor = await db.execute(
                    "SELECT is_tool_call FROM models WHERE id = ?",
                    (model_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    supports = bool(row['is_tool_call'])
                    logger.info(f"Model {model_id} tool calling support: {supports}")
                    return supports
                else:
                    logger.warning(f"Model {model_id} not found in database")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to check tool calling support for {model_id}: {e}")
            return False
    
    async def get_tool_capable_models(self) -> List[ModelCapability]:
        """Get all models that support tool calling"""
        try:
            await self._refresh_cache_if_needed()
            
            tool_models = [
                capability for capability in self._capability_cache.values()
                if capability.supports_tool_calls
            ]
            
            # Sort by name for consistent ordering
            tool_models.sort(key=lambda x: x.name)
            
            logger.info(f"Found {len(tool_models)} tool-capable models")
            return tool_models
            
        except Exception as e:
            logger.error(f"Failed to get tool-capable models: {e}")
            return []
    
    async def get_all_models(self) -> List[ModelCapability]:
        """Get all models with their capabilities"""
        try:
            await self._refresh_cache_if_needed()
            
            all_models = list(self._capability_cache.values())
            all_models.sort(key=lambda x: x.name)
            
            return all_models
            
        except Exception as e:
            logger.error(f"Failed to get all models: {e}")
            return []
    
    async def get_model_capability(self, model_id: str) -> Optional[ModelCapability]:
        """Get detailed capability information for a specific model"""
        try:
            await self._refresh_cache_if_needed()
            
            capability = self._capability_cache.get(model_id)
            if capability:
                return capability
            
            # Check database if not in cache
            async with self.db_manager.get_connection() as db:
                cursor = await db.execute(
                    "SELECT * FROM models WHERE id = ?",
                    (model_id,)
                )
                row = await cursor.fetchone()
                
                if row:
                    return ModelCapability(
                        model_id=row['id'],
                        name=row['name'],
                        supports_tool_calls=bool(row['is_tool_call']),
                        context_length=row.get('context_length', 0),
                        created_at=datetime.fromisoformat(row['created_at']) if row.get('created_at') else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row.get('updated_at') else None
                    )
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get model capability for {model_id}: {e}")
            return None
    
    async def refresh_capabilities_from_openrouter(self, api_key: Optional[str] = None) -> Dict[str, Any]:
        """Fetch and update model capabilities from OpenRouter API"""
        if not api_key:
            api_key = settings.openrouter.api_key
            
        if not api_key:
            raise ValueError("OpenRouter API key not provided")
        
        stats = {
            "total_models_fetched": 0,
            "models_updated": 0,
            "new_models_added": 0,
            "tool_capable_models": 0,
            "errors": []
        }
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise aiohttp.ClientError(f"OpenRouter API error: {response.status} - {error_text}")
                    
                    data = await response.json()
                    models_data = data.get('data', [])
                    stats['total_models_fetched'] = len(models_data)
                    
                    logger.info(f"Fetched {len(models_data)} models from OpenRouter API")
                    
                    # Process each model
                    models_to_save = []
                    for model_info in models_data:
                        try:
                            model_id = model_info.get('id')
                            if not model_id:
                                continue
                            
                            # Determine tool calling support based on OpenRouter data
                            # Check if model supports function calling or tools
                            supports_tools = False
                            
                            # Check various indicators of tool calling support
                            architecture = model_info.get('architecture', {})
                            if isinstance(architecture, dict):
                                # Some models explicitly indicate function calling support
                                if architecture.get('function_calling') or architecture.get('tool_use'):
                                    supports_tools = True
                            
                            # Check model description or capabilities
                            description = model_info.get('description', '').lower()
                            name = model_info.get('name', '').lower()
                            
                            # Known patterns that indicate tool calling support
                            tool_indicators = [
                                'function calling', 'tool use', 'tool calling', 'function call',
                                'tools', 'api calls', 'external functions'
                            ]
                            
                            for indicator in tool_indicators:
                                if indicator in description or indicator in name:
                                    supports_tools = True
                                    break
                            
                            # Known model families that support tools
                            tool_capable_families = [
                                'gpt-4', 'gpt-3.5', 'claude-3', 'claude-2', 'gemini',
                                'mistral', 'cohere', 'anthropic', 'openai'
                            ]
                            
                            for family in tool_capable_families:
                                if family in model_id.lower() or family in name:
                                    supports_tools = True
                                    break
                            
                            # Extract context length
                            context_length = model_info.get('context_length', 0)
                            if not context_length:
                                # Try to extract from model info
                                top_provider = model_info.get('top_provider', {})
                                if isinstance(top_provider, dict):
                                    context_length = top_provider.get('max_completion_tokens', 0)
                            
                            models_to_save.append({
                                'id': model_id,
                                'name': model_info.get('name', model_id),
                                'is_tool_call': 1 if supports_tools else 0,
                                'context_length': context_length,
                                'created_at': datetime.utcnow().isoformat(),
                                'updated_at': datetime.utcnow().isoformat()
                            })
                            
                            if supports_tools:
                                stats['tool_capable_models'] += 1
                                
                        except Exception as e:
                            stats['errors'].append(f"Error processing model {model_id}: {str(e)}")
                            logger.error(f"Error processing model {model_id}: {e}")
                    
                    # Save models to database
                    if models_to_save:
                        await self.db_manager.save_models(models_to_save)
                        stats['models_updated'] = len(models_to_save)
                        
                        # Refresh cache
                        await self._load_capabilities_cache()
                        
                        logger.info(f"Updated {len(models_to_save)} models in database")
                    
        except Exception as e:
            error_msg = f"Failed to refresh capabilities from OpenRouter: {e}"
            stats['errors'].append(error_msg)
            logger.error(error_msg)
            raise
        
        return stats
    
    async def get_capability_statistics(self) -> Dict[str, Any]:
        """Get statistics about model capabilities"""
        try:
            await self._refresh_cache_if_needed()
            
            total_models = len(self._capability_cache)
            tool_capable = sum(1 for cap in self._capability_cache.values() if cap.supports_tool_calls)
            
            # Get context length statistics
            context_lengths = [cap.context_length for cap in self._capability_cache.values() if cap.context_length > 0]
            avg_context = sum(context_lengths) / len(context_lengths) if context_lengths else 0
            max_context = max(context_lengths) if context_lengths else 0
            
            # Group by provider (extract from model ID)
            providers = {}
            for cap in self._capability_cache.values():
                provider = cap.model_id.split('/')[0] if '/' in cap.model_id else 'unknown'
                if provider not in providers:
                    providers[provider] = {'total': 0, 'tool_capable': 0}
                providers[provider]['total'] += 1
                if cap.supports_tool_calls:
                    providers[provider]['tool_capable'] += 1
            
            return {
                'total_models': total_models,
                'tool_capable_models': tool_capable,
                'non_tool_models': total_models - tool_capable,
                'tool_capability_percentage': (tool_capable / total_models * 100) if total_models > 0 else 0,
                'average_context_length': avg_context,
                'max_context_length': max_context,
                'providers': providers,
                'cache_last_updated': self._last_cache_update.isoformat() if self._last_cache_update else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get capability statistics: {e}")
            return {}
    
    async def validate_model_for_session(self, model_id: str, enable_tools: bool = True) -> Dict[str, Any]:
        """Validate if a model is suitable for a session with tool requirements"""
        try:
            capability = await self.get_model_capability(model_id)
            
            if not capability:
                return {
                    'valid': False,
                    'reason': f'Model {model_id} not found',
                    'supports_tools': False,
                    'recommendation': 'Choose a different model'
                }
            
            # Check tool calling requirements
            if enable_tools and not capability.supports_tool_calls:
                tool_alternatives = await self.get_tool_capable_models()
                alternatives = [m.model_id for m in tool_alternatives[:3]]  # Top 3 alternatives
                
                return {
                    'valid': False,
                    'reason': f'Model {model_id} does not support tool calling',
                    'supports_tools': False,
                    'recommendation': 'Either disable tools or choose a tool-capable model',
                    'alternatives': alternatives
                }
            
            return {
                'valid': True,
                'reason': 'Model is compatible with session requirements',
                'supports_tools': capability.supports_tool_calls,
                'context_length': capability.context_length,
                'model_name': capability.name
            }
            
        except Exception as e:
            logger.error(f"Failed to validate model {model_id}: {e}")
            return {
                'valid': False,
                'reason': f'Error validating model: {str(e)}',
                'supports_tools': False
            }


# Global instance for easy access
_capability_manager: Optional[ModelCapabilityManager] = None


async def get_capability_manager() -> ModelCapabilityManager:
    """Get or create the global capability manager instance"""
    global _capability_manager
    if _capability_manager is None:
        _capability_manager = ModelCapabilityManager()
        await _capability_manager.initialize()
    return _capability_manager


# Convenience functions for common operations
async def supports_tool_calls(model_id: str) -> bool:
    """Quick check if a model supports tool calling"""
    manager = await get_capability_manager()
    return await manager.supports_tool_calls(model_id)


async def get_tool_capable_models() -> List[ModelCapability]:
    """Get all tool-capable models"""
    manager = await get_capability_manager()
    return await manager.get_tool_capable_models()


async def refresh_model_capabilities() -> Dict[str, Any]:
    """Refresh model capabilities from OpenRouter API"""
    manager = await get_capability_manager()
    return await manager.refresh_capabilities_from_openrouter()


async def validate_model_for_tools(model_id: str) -> bool:
    """Validate if a model can be used for tool calling"""
    manager = await get_capability_manager()
    validation = await manager.validate_model_for_session(model_id, enable_tools=True)
    return validation['valid'] 