from fastapi import APIRouter, Header
from typing import Optional
import os

router = APIRouter(prefix="/conversation", tags=["conversation"])

# Import session registry
from session.global_session_registry import global_session_registry

@router.get("/stats")
async def get_conversation_stats(x_session_id: Optional[str] = Header(None)):
    """Get conversation statistics"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        stats = agent.get_conversation_stats()
        return {
            "success": True,
            "stats": stats,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Failed to get conversation stats: {str(e)}")
        return {"error": "Failed to get conversation stats"}

@router.post("/clear")
async def clear_conversation(x_session_id: Optional[str] = Header(None)):
    """Clear conversation memory with session support"""
    try:
        # Get or create session-specific agent (will create if doesn't exist)
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Clear the session
        success = global_session_registry.clear_session(session_id)
        if success:
            return {
                "success": True,
                "message": f"Session {session_id} cleared successfully",
                "session_id": session_id
            }
        else:
            return {
                "success": False,
                "message": f"Failed to clear session {session_id}"
            }
    except Exception as e:
        logger.error(f"Failed to clear conversation: {str(e)}")
        return {"error": "Failed to clear conversation"}

@router.post("/export")
async def export_conversation(request: dict, x_session_id: Optional[str] = Header(None)):
    """Export conversation to file"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        export_file = request.get("filename", "conversation_export.json")
        
        # Ensure the filename has .json extension
        if not export_file.endswith('.json'):
            export_file += '.json'
        
        # Export to output directory
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        export_path = os.path.join(output_dir, export_file)
        
        success = agent.export_conversation(export_path)
        if success:
            return {
                "success": True,
                "message": f"Conversation exported successfully to {export_file}",
                "filename": export_file,
                "path": export_path,
                "file_exists": os.path.exists(export_path),
                "session_id": session_id
            }
        else:
            return {
                "success": False,
                "message": "Failed to export conversation"
            }
    except Exception as e:
        logger.error(f"Failed to export conversation: {str(e)}")
        return {"error": "Failed to export conversation"}

@router.get("/memory")
async def get_conversation_memory(x_session_id: Optional[str] = Header(None)):
    """Get current conversation memory"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Get recent messages from session manager
        messages = session_manager.messages
        recent_messages = messages[-10:] if messages else []  # Get last 10 messages
        
        return {
            "success": True,
            "message_count": len(messages),
            "recent_messages": recent_messages,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Failed to get conversation memory: {str(e)}")
        return {"error": "Failed to get conversation memory"}

@router.post("/recreate_agent")
async def recreate_agent(x_session_id: Optional[str] = Header(None)):
    """Recreate the agent instance with clean memory"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        agent.recreate_agent()
        return {
            "success": True,
            "message": "Agent recreated successfully with clean memory",
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Failed to recreate agent: {str(e)}")
        return {"error": "Failed to recreate agent"}

@router.get("/health")
async def conversation_health(x_session_id: Optional[str] = Header(None)):
    """Check conversation system health"""
    try:
        # Get registry stats
        registry_stats = global_session_registry.get_registry_stats()
        
        # Try to get or create a session to test agent availability
        agent_available = False
        session_id = None
        try:
            session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
            agent_available = agent.is_available()
        except Exception:
            pass
        
        return {
            "success": True,
            "agent_available": agent_available,
            "total_sessions": registry_stats["total_sessions"],
            "total_messages": registry_stats["total_messages"],
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"error": "Health check failed"}

@router.post("/restore")
async def restore_conversation(messages: list, x_session_id: Optional[str] = Header(None)):
    """Restore conversation from provided messages"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Clear existing messages and restore new ones
        session_manager.messages.clear()
        session_manager.messages.extend(messages)
        
        # Recreate agent to apply restored messages
        agent.recreate_agent()
        
        return {
            "success": True,
            "message": f"Restored {len(messages)} messages to conversation",
            "message_count": len(messages),
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Failed to restore conversation: {str(e)}")
        return {"error": "Failed to restore conversation"}

@router.get("/is_agent_available")
async def is_agent_available(x_session_id: Optional[str] = Header(None)):
    """Check if the agent is available"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        available = agent.is_available()
        return {
            "success": True,
            "agent_available": available,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Failed to check agent availability: {str(e)}")
        return {"error": "Failed to check agent availability"}