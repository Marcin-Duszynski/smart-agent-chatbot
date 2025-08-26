"""Session management API endpoints."""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional, Dict, Any, List
import logging

from session.global_session_registry import global_session_registry
from memory_store import get_memory_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["session"])


@router.post("/new")
async def create_new_session() -> Dict[str, Any]:
    """Create a new session and return session ID."""
    try:
        session_id, session_manager, agent = global_session_registry.get_or_create_session()
        
        return {
            "success": True,
            "session_id": session_id,
            "message": f"New session created: {session_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create new session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/{session_id}/info")
async def get_session_info(session_id: str) -> Dict[str, Any]:
    """Get information about a specific session."""
    try:
        session_info = global_session_registry.get_session_info(session_id)
        
        if session_info is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return {
            "success": True,
            "session_info": session_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")


@router.delete("/{session_id}/clear")
async def clear_session(session_id: str) -> Dict[str, Any]:
    """Clear a session's data and files."""
    try:
        success = global_session_registry.clear_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return {
            "success": True,
            "message": f"Session {session_id} cleared successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.delete("/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """Completely delete a session and all associated data."""
    try:
        success = global_session_registry.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        return {
            "success": True,
            "message": f"Session {session_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("")
async def list_sessions() -> Dict[str, Any]:
    """List all active sessions with their information."""
    try:
        sessions_info = global_session_registry.list_sessions()
        
        return {
            "success": True,
            "sessions": sessions_info,
            "total_sessions": len(sessions_info)
        }
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/stats")
async def get_registry_stats() -> Dict[str, Any]:
    """Get overall session registry statistics."""
    try:
        stats = global_session_registry.get_registry_stats()
        
        return {
            "success": True,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get registry stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/cleanup")
async def cleanup_expired_sessions(timeout_minutes: int = 30) -> Dict[str, Any]:
    """Clean up sessions that have been inactive for too long."""
    try:
        if timeout_minutes <= 0:
            raise HTTPException(status_code=400, detail="Timeout must be greater than 0")
        
        cleaned_count = global_session_registry.cleanup_expired_sessions(timeout_minutes)
        
        return {
            "success": True,
            "cleaned_sessions": cleaned_count,
            "timeout_minutes": timeout_minutes,
            "message": f"Cleaned up {cleaned_count} expired sessions"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup expired sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup sessions: {str(e)}")


@router.get("/current")
async def get_current_session(x_session_id: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Get current session information from header."""
    try:
        if not x_session_id:
            return {
                "success": False,
                "message": "No session ID provided in X-Session-ID header"
            }
        
        session_info = global_session_registry.get_session_info(x_session_id)
        
        if session_info is None:
            return {
                "success": False,
                "message": f"Session {x_session_id} not found"
            }
        
        return {
            "success": True,
            "session_info": session_info
        }
        
    except Exception as e:
        logger.error(f"Failed to get current session info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get current session: {str(e)}")


@router.get("/{session_id}/analysis/{tool_use_id}")
async def get_session_analysis(session_id: str, tool_use_id: str) -> Dict[str, Any]:
    """Get analysis result from session memory."""
    try:
        memory_store = get_memory_store()
        analysis_data = memory_store.get_analysis(session_id, tool_use_id)
        
        if analysis_data is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Analysis not found for session {session_id}, tool_use_id {tool_use_id}"
            )
        
        return {
            "success": True,
            "session_id": session_id,
            "tool_use_id": tool_use_id,
            "analysis": analysis_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis for session {session_id}, tool_use_id {tool_use_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get analysis: {str(e)}")


@router.get("/{session_id}/data")
async def get_all_session_data(session_id: str) -> Dict[str, Any]:
    """Get all analysis data for a session."""
    try:
        memory_store = get_memory_store()
        session_data = memory_store.get_session_data(session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "data": session_data,
            "total_analyses": len(session_data)
        }
        
    except Exception as e:
        logger.error(f"Failed to get session data for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session data: {str(e)}")
