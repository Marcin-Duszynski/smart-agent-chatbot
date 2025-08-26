"""Global session registry for managing multiple user sessions."""

import logging
import os
import shutil
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .in_memory_session_manager import InMemorySessionManager

logger = logging.getLogger(__name__)


class GlobalSessionRegistry:
    """Global registry for managing multiple user sessions with complete isolation.
    
    Provides session lifecycle management, cleanup, and statistics.
    Each session gets its own InMemorySessionManager and ChatbotAgent instance.
    """
    
    def __init__(self):
        """Initialize the global session registry."""
        # Session isolation - each session_id gets its own manager and agent
        self.sessions: Dict[str, InMemorySessionManager] = {}
        self.agents: Dict[str, 'ChatbotAgent'] = {}  # Forward reference to avoid circular import
        
        # Session metadata
        self.session_creation_times: Dict[str, datetime] = {}
        
        logger.info("GlobalSessionRegistry initialized")
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Tuple[str, InMemorySessionManager, 'ChatbotAgent']:
        """Get existing session or create new one with complete isolation.
        
        Args:
            session_id: Optional session ID. If None, generates a new one.
            
        Returns:
            Tuple of (session_id, session_manager, agent)
        """
        # Generate session ID if not provided
        if not session_id:
            session_id = self._generate_session_id()
        
        # Return existing session if found
        if session_id in self.sessions:
            logger.debug(f"Returning existing session: {session_id}")
            return session_id, self.sessions[session_id], self.agents[session_id]
        
        # Create new session with complete isolation
        return self._create_new_session(session_id)
    
    def _create_new_session(self, session_id: str) -> Tuple[str, InMemorySessionManager, 'ChatbotAgent']:
        """Create a new session with isolated manager and agent.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Tuple of (session_id, session_manager, agent)
        """
        try:
            # Import here to avoid circular dependency
            from agent import ChatbotAgent
            
            # 1. Create session manager
            session_manager = InMemorySessionManager(session_id)
            
            # 2. Create isolated ChatbotAgent with session manager
            agent = ChatbotAgent(session_manager=session_manager)
            
            # 3. Register in global registry
            self.sessions[session_id] = session_manager
            self.agents[session_id] = agent
            self.session_creation_times[session_id] = datetime.now()
            
            logger.info(f"Created new session: {session_id} (total sessions: {len(self.sessions)})")
            
            return session_id, session_manager, agent
            
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            raise
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID.
        
        Returns:
            Unique session identifier
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = uuid.uuid4().hex[:8]
        session_id = f"session_{timestamp}_{random_suffix}"
        print(f"🔍 Backend - Generated new session ID: {session_id}")
        logger.info(f"🔍 Backend - Generated new session ID: {session_id}")
        return session_id
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a specific session's data and files.
        
        Args:
            session_id: Session to clear
            
        Returns:
            True if session was cleared, False if not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found for clearing: {session_id}")
            return False
        
        try:
            # 1. Clear session manager data
            self.sessions[session_id].clear_session()
            
            # 2. Clear session output directory
            self._clear_session_files(session_id)
            
            logger.info(f"Session cleared: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Completely delete a session and all associated data.
        
        Args:
            session_id: Session to delete
            
        Returns:
            True if session was deleted, False if not found
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found for deletion: {session_id}")
            return False
        
        try:
            # 1. Clear session data first
            self.clear_session(session_id)
            
            # 2. Remove from registry
            del self.sessions[session_id]
            del self.agents[session_id]
            if session_id in self.session_creation_times:
                del self.session_creation_times[session_id]
            
            logger.info(f"Session deleted: {session_id} (remaining sessions: {len(self.sessions)})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def _clear_session_files(self, session_id: str) -> None:
        """Clear session-specific output files.
        
        Args:
            session_id: Session whose files to clear
        """
        try:
            from config import Config
            
            session_output_dir = Config.get_session_output_dir(session_id)
            if session_output_dir and os.path.exists(session_output_dir):
                shutil.rmtree(session_output_dir)
                logger.debug(f"Session files cleared: {session_output_dir}")
                
        except Exception as e:
            logger.error(f"Failed to clear session files for {session_id}: {e}")
    
    
    def cleanup_expired_sessions(self, timeout_minutes: int = 30) -> int:
        """Clean up sessions that have been inactive for too long.
        
        Args:
            timeout_minutes: Minutes of inactivity before session expires
            
        Returns:
            Number of sessions cleaned up
        """
        if timeout_minutes <= 0:
            return 0
        
        cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
        expired_sessions = []
        
        # Find expired sessions
        for session_id, session_manager in self.sessions.items():
            if session_manager.last_activity < cutoff_time:
                expired_sessions.append(session_id)
        
        # Delete expired sessions
        cleaned_count = 0
        for session_id in expired_sessions:
            if self.delete_session(session_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired sessions (timeout: {timeout_minutes}min)")
        
        return cleaned_count
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get information about a specific session.
        
        Args:
            session_id: Session to get info for
            
        Returns:
            Session info dictionary or None if not found
        """
        if session_id not in self.sessions:
            return None
        
        session_manager = self.sessions[session_id]
        creation_time = self.session_creation_times.get(session_id)
        
        info = session_manager.get_session_info()
        if creation_time:
            info["created_at"] = creation_time.isoformat()
        
        return info
    
    def list_sessions(self) -> List[Dict]:
        """List all active sessions with their information.
        
        Returns:
            List of session info dictionaries
        """
        sessions_info = []
        
        for session_id in self.sessions:
            info = self.get_session_info(session_id)
            if info:
                sessions_info.append(info)
        
        # Sort by creation time (newest first)
        sessions_info.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return sessions_info
    
    def get_registry_stats(self) -> Dict:
        """Get overall registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        total_messages = sum(len(sm.messages) for sm in self.sessions.values())
        
        # Calculate memory usage estimate (rough)
        memory_estimate = 0
        for session_manager in self.sessions.values():
            memory_estimate += len(str(session_manager.messages)) * 2  # Rough estimate
            memory_estimate += len(str(session_manager.agent_state)) * 2
            memory_estimate += len(str(session_manager.conversation_manager_state)) * 2
        
        return {
            "total_sessions": len(self.sessions),
            "total_messages": total_messages,
            "memory_estimate_bytes": memory_estimate,
            "oldest_session": min(
                (sm.created_at for sm in self.sessions.values()),
                default=None
            ),
            "most_recent_activity": max(
                (sm.last_activity for sm in self.sessions.values()),
                default=None
            )
        }


# Global singleton instance
global_session_registry = GlobalSessionRegistry()
