from fastapi import APIRouter, HTTPException
from memory_store import get_memory_store
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/debug/memory/stats")
async def get_memory_stats():
    """Get memory store statistics"""
    try:
        memory_store = get_memory_store()
        stats = memory_store.get_stats()
        return {
            "success": True,
            "stats": stats,
            "total_sessions": len(memory_store._store)
        }
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/memory/all")
async def get_all_memory_data():
    """Get all memory store data (development only)"""
    try:
        memory_store = get_memory_store()
        return {
            "success": True,
            "sessions": dict(memory_store._store)
        }
    except Exception as e:
        logger.error(f"Error getting all memory data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/memory/{session_id}")
async def get_session_memory(session_id: str):
    """Get all data for a specific session"""
    try:
        memory_store = get_memory_store()
        session_data = memory_store.get_session_data(session_id)
        
        if not session_data:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "data": session_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/memory/{session_id}/{tool_use_id}")
async def get_tool_memory(session_id: str, tool_use_id: str):
    """Get data for a specific tool use ID"""
    try:
        memory_store = get_memory_store()
        analysis_data = memory_store.get_analysis(session_id, tool_use_id)
        
        if not analysis_data:
            raise HTTPException(status_code=404, detail=f"Tool use data not found: {session_id}/{tool_use_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "tool_use_id": tool_use_id,
            "data": analysis_data
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/memory/{session_id}/{tool_use_id}/charts")
async def get_tool_charts(session_id: str, tool_use_id: str):
    """Get charts for a specific tool use ID"""
    try:
        memory_store = get_memory_store()
        analysis_data = memory_store.get_analysis(session_id, tool_use_id)
        
        if not analysis_data:
            raise HTTPException(status_code=404, detail=f"Tool use data not found: {session_id}/{tool_use_id}")
        
        charts = analysis_data.get("charts", {})
        
        return {
            "success": True,
            "session_id": session_id,
            "tool_use_id": tool_use_id,
            "charts": list(charts.keys()),
            "chart_data": charts
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tool charts: {e}")
        raise HTTPException(status_code=500, detail=str(e))