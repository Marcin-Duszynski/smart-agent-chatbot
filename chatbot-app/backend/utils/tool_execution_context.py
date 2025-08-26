"""
Tool Execution Context Manager

Manages tool execution contexts to handle concurrent tool calls safely.
Each tool execution gets its own isolated context with tool_use_id, tool_name, and metadata.
"""

import asyncio
import os
import threading
from datetime import datetime
from typing import Dict, Optional, Any
from contextvars import ContextVar


class ToolExecutionContext:
    """Represents a single tool execution context"""
    
    def __init__(self, tool_use_id: str, tool_name: str, session_id: str = None):
        self.tool_use_id = tool_use_id
        self.tool_name = tool_name
        self.session_id = session_id
        self.created_at = datetime.now()
        self.metadata: Dict[str, Any] = {}
    
    def __repr__(self):
        return f"ToolExecutionContext(tool_use_id='{self.tool_use_id}', tool_name='{self.tool_name}')"


class ToolContextManager:
    """Manages tool execution contexts with thread-safe operations"""
    
    def __init__(self):
        self._contexts: Dict[str, ToolExecutionContext] = {}
        self._lock = asyncio.Lock()
        self._current_context: ContextVar[Optional[ToolExecutionContext]] = ContextVar('current_tool_context', default=None)
    
    async def create_context(self, tool_use_id: str, tool_name: str, session_id: str = None) -> ToolExecutionContext:
        """Create a new tool execution context"""
        async with self._lock:
            context = ToolExecutionContext(tool_use_id, tool_name, session_id)
            self._contexts[tool_use_id] = context
            return context
    
    def get_context(self, tool_use_id: str) -> Optional[ToolExecutionContext]:
        """Get context by tool_use_id"""
        return self._contexts.get(tool_use_id)
    
    def get_current_context(self) -> Optional[ToolExecutionContext]:
        """Get the current context for the executing tool"""
        return self._current_context.get()
    
    def set_current_context(self, context: ToolExecutionContext):
        """Set the current context for the executing tool"""
        self._current_context.set(context)
    
    def clear_current_context(self):
        """Clear the current context"""
        self._current_context.set(None)
    
    async def cleanup_context(self, tool_use_id: str):
        """Clean up context after tool execution"""
        async with self._lock:
            self._contexts.pop(tool_use_id, None)
    
    def get_all_contexts(self) -> Dict[str, ToolExecutionContext]:
        """Get all active contexts (for debugging)"""
        return self._contexts.copy()
    
    async def cleanup_old_contexts(self, max_age_seconds: int = 3600):
        """Clean up contexts older than max_age_seconds"""
        now = datetime.now()
        to_remove = []
        
        async with self._lock:
            for tool_use_id, context in self._contexts.items():
                age = (now - context.created_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(tool_use_id)
            
            for tool_use_id in to_remove:
                self._contexts.pop(tool_use_id, None)


# Global instance
tool_context_manager = ToolContextManager()


def get_current_tool_use_id() -> Optional[str]:
    """Convenience function to get current tool_use_id"""
    context = tool_context_manager.get_current_context()
    return context.tool_use_id if context else None


def get_current_tool_name() -> Optional[str]:
    """Convenience function to get current tool_name"""
    context = tool_context_manager.get_current_context()
    return context.tool_name if context else None


def get_current_session_id() -> Optional[str]:
    """Convenience function to get current session_id"""
    context = tool_context_manager.get_current_context()
    return context.session_id if context else None


def get_session_output_dir(session_id: Optional[str] = None) -> str:
    """Get session-specific output directory"""
    from config import Config
    
    # Use provided session_id or get from current context
    if not session_id:
        session_id = get_current_session_id()
    
    # Fallback to default if no session_id available
    if not session_id:
        return Config.OUTPUT_DIR
    
    return Config.get_session_output_dir(session_id)


def get_session_analysis_dir(session_id: Optional[str] = None) -> str:
    """Get session-specific analysis directory"""
    from config import Config
    
    # Use provided session_id or get from current context
    if not session_id:
        session_id = get_current_session_id()
    
    # Fallback to default if no session_id available
    if not session_id:
        return os.path.join(Config.OUTPUT_DIR, "analysis")
    
    return Config.get_session_analysis_dir(session_id)


def get_session_repl_dir(session_id: Optional[str] = None) -> str:
    """Get session-specific REPL directory"""
    from config import Config
    
    # Use provided session_id or get from current context
    if not session_id:
        session_id = get_current_session_id()
    
    # Fallback to default if no session_id available
    if not session_id:
        return os.path.join(Config.OUTPUT_DIR, "repl")
    
    return Config.get_session_repl_dir(session_id)


def get_session_diagrams_dir(session_id: Optional[str] = None) -> str:
    """Get session-specific diagrams directory"""
    from config import Config
    
    # Use provided session_id or get from current context
    if not session_id:
        session_id = get_current_session_id()
    
    # Fallback to default if no session_id available
    if not session_id:
        return Config.DIAGRAMS_DIR
    
    return Config.get_session_diagrams_dir(session_id)


def get_session_charts_dir(session_id: Optional[str] = None) -> str:
    """Get session-specific charts directory"""
    from config import Config
    
    # Use provided session_id or get from current context
    if not session_id:
        session_id = get_current_session_id()
    
    # Fallback to default if no session_id available
    if not session_id:
        return Config.CHARTS_DIR
    
    return Config.get_session_charts_dir(session_id)


async def execute_with_context(tool_use_id: str, tool_name: str, session_id: str, coro):
    """Execute a coroutine with a tool execution context"""
    context = await tool_context_manager.create_context(tool_use_id, tool_name, session_id)
    
    # Set as current context
    tool_context_manager.set_current_context(context)
    
    try:
        result = await coro
        return result
    finally:
        # Clean up
        tool_context_manager.clear_current_context()
        await tool_context_manager.cleanup_context(tool_use_id)


def create_context_aware_agent(agent, session_id: str, tool_use_id: str, tool_name: str):
    """
    Create a context-aware wrapper for a Strands Agent that propagates tool context
    to all nested tool calls within the agent execution.
    """
    import asyncio
    from contextvars import copy_context
    
    class ContextAwareAgent:
        def __init__(self, original_agent, session_id, tool_use_id, tool_name):
            self.original_agent = original_agent
            self.session_id = session_id
            self.tool_use_id = tool_use_id
            self.tool_name = tool_name
        
        async def stream_async(self, *args, **kwargs):
            """Stream with context propagation"""
            # Check if context already exists (from parent tool)
            existing_context = tool_context_manager.get_context(self.tool_use_id)
            context_created = False
            
            if not existing_context:
                # Create context if it doesn't exist
                context = await tool_context_manager.create_context(
                    self.tool_use_id, self.tool_name, self.session_id
                )
                context_created = True
            else:
                context = existing_context
            
            # Set as current context
            tool_context_manager.set_current_context(context)
            
            try:
                # Execute the original agent with context maintained
                async for chunk in self.original_agent.stream_async(*args, **kwargs):
                    yield chunk
            finally:
                # Only clean up if we created the context
                if context_created:
                    tool_context_manager.clear_current_context()
                    await tool_context_manager.cleanup_context(self.tool_use_id)
        
        def __getattr__(self, name):
            # Delegate all other attributes to the original agent
            return getattr(self.original_agent, name)
    
    return ContextAwareAgent(agent, session_id, tool_use_id, tool_name)


def with_tool_context(func):
    """Decorator to automatically find and set tool context during execution"""
    import asyncio
    import functools
    import inspect
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        tool_name = func.__name__
        
        # First, check if we already have a current context (nested call scenario)
        current_context = tool_context_manager.get_current_context()
        if current_context:
            # We're in a nested tool call - inherit the parent context
            # This means an agent-type tool is calling other tools
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Tool {tool_name} inheriting context from parent tool {current_context.tool_name} (session: {current_context.session_id})")
            
            # Execute with inherited context
            return await func(*args, **kwargs)
        
        # Look for any active context with matching tool name
        all_contexts = tool_context_manager.get_all_contexts()
        matching_context = None
        
        for context in all_contexts.values():
            if context.tool_name == tool_name:
                matching_context = context
                break
        
        if matching_context:
            # Set context during execution
            tool_context_manager.set_current_context(matching_context)
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                tool_context_manager.clear_current_context()
        else:
            # No context found - log warning but continue execution
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"No tool context found for {tool_name} - this may cause session ID issues")
            return await func(*args, **kwargs)
    
    return wrapper
