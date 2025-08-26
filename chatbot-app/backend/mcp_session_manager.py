import logging
import time
import asyncio
from typing import Dict, Optional, List, Any
from threading import Lock

from strands.tools.mcp import MCPClient

logger = logging.getLogger(__name__)

class MCPSessionManager:
    """Session-aware MCP client manager using Strands SDK"""
    
    def __init__(self):
        # Session-based client management
        self.session_clients = {}          # backend_session_id -> {server_id: MCPClient}
        self.session_contexts = {}         # backend_session_id -> [context_managers]
        self.session_metadata = {}         # backend_session_id -> metadata
        
        # Concurrency control
        self._lock = Lock()
        
        # Cleanup settings
        self.cleanup_interval = 300        # 5 minutes
        self.session_timeout = 3600        # 1 hour
        self.cleanup_task_running = False
    
    def get_tools_for_session(self, backend_session_id: str, enabled_servers: List[Dict[str, Any]]) -> List[Any]:
        """Get MCP tools for a specific backend session"""
        with self._lock:
            try:
                # Get or create session clients
                session_clients = self._get_or_create_session_clients(backend_session_id, enabled_servers)
                
                # Collect tools from all session clients
                session_tools = []
                for server_id, client in session_clients.items():
                    try:
                        tools = client.list_tools_sync()
                        session_tools.extend(tools)
                        logger.info(f"✓ Loaded {len(tools)} tools from {server_id} for session {backend_session_id}")
                    except Exception as e:
                        logger.warning(f"✗ Failed to get tools from {server_id}: {e}")
                
                # Update session metadata
                self._update_session_metadata(backend_session_id)
                
                logger.info(f"Session {backend_session_id}: {len(session_tools)} MCP tools available")
                return session_tools
                
            except Exception as e:
                logger.error(f"❌ Failed to get tools for session {backend_session_id}: {e}")
                return []
    
    def _get_or_create_session_clients(self, backend_session_id: str, enabled_servers: List[Dict[str, Any]]) -> Dict[str, MCPClient]:
        """Get or create MCP clients for a backend session"""
        if backend_session_id not in self.session_clients:
            logger.info(f"🔧 Creating new MCP clients for session: {backend_session_id}")
            
            self.session_clients[backend_session_id] = {}
            self.session_contexts[backend_session_id] = []
            
            # Create clients for ALL enabled servers
            # Session ID will be passed to all servers - they can use it or ignore it
            for server_config in enabled_servers:
                server_id = server_config["id"]
                
                try:
                    client = self._create_mcp_client(server_config)
                    
                    # Start the client context
                    client_context = client.__enter__()
                    
                    self.session_clients[backend_session_id][server_id] = client_context
                    self.session_contexts[backend_session_id].append(client)
                    
                    logger.info(f"✅ Created MCP client for {server_config['name']} (session: {backend_session_id})")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create MCP client for {server_id}: {e}")
            
            # Initialize session metadata
            self.session_metadata[backend_session_id] = {
                "created_at": time.time(),
                "last_used": time.time(),
                "client_count": len(self.session_clients[backend_session_id])
            }
        
        return self.session_clients[backend_session_id]
    
    def _create_mcp_client(self, server_config: Dict[str, Any]) -> MCPClient:
        """Create MCPClient using existing unified_tool_manager logic"""
        # Import here to avoid circular import
        from unified_tool_manager import UnifiedToolManager
        temp_manager = UnifiedToolManager()
        return temp_manager._create_mcp_client(server_config)
    
    def _update_session_metadata(self, backend_session_id: str):
        """Update session last used time"""
        if backend_session_id in self.session_metadata:
            self.session_metadata[backend_session_id]["last_used"] = time.time()
    
    def cleanup_session(self, backend_session_id: str):
        """Clean up session and all associated MCP clients"""
        with self._lock:
            try:
                if backend_session_id in self.session_contexts:
                    # Close all context managers (SDK handles cleanup)
                    for client in self.session_contexts[backend_session_id]:
                        try:
                            client.__exit__(None, None, None)
                        except Exception as e:
                            logger.warning(f"Error closing MCP client: {e}")
                    
                    # Clean up tracking data
                    del self.session_contexts[backend_session_id]
                
                if backend_session_id in self.session_clients:
                    del self.session_clients[backend_session_id]
                
                if backend_session_id in self.session_metadata:
                    del self.session_metadata[backend_session_id]
                
                logger.info(f"🧹 Cleaned up session: {backend_session_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to cleanup session {backend_session_id}: {e}")
    
    async def start_cleanup_task(self):
        """Start background cleanup task"""
        if self.cleanup_task_running:
            return
            
        self.cleanup_task_running = True
        logger.info("🚀 Starting MCP session cleanup task")
        
        try:
            while self.cleanup_task_running:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired_sessions()
        except Exception as e:
            logger.error(f"❌ Cleanup task error: {e}")
        finally:
            self.cleanup_task_running = False
    
    async def _cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        try:
            current_time = time.time()
            expired_sessions = []
            
            with self._lock:
                for backend_session_id, metadata in self.session_metadata.items():
                    if current_time - metadata["last_used"] > self.session_timeout:
                        expired_sessions.append(backend_session_id)
            
            for session_id in expired_sessions:
                logger.info(f"🕐 Cleaning up expired session: {session_id}")
                self.cleanup_session(session_id)
                
            if expired_sessions:
                logger.info(f"🧹 Cleaned up {len(expired_sessions)} expired sessions")
                
        except Exception as e:
            logger.error(f"❌ Failed to cleanup expired sessions: {e}")
    
    def stop_cleanup_task(self):
        """Stop cleanup task"""
        self.cleanup_task_running = False
        logger.info("🛑 Stopping MCP session cleanup task")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        with self._lock:
            return {
                "backend_sessions": len(self.session_metadata),
                "total_clients": sum(len(clients) for clients in self.session_clients.values()),
                "cleanup_running": self.cleanup_task_running
            }
    
