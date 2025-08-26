from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
import json
import logging
from config import Config
from memory_store import get_memory_store

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/charts/{chart_name}")
async def get_chart(chart_name: str, session_id: str = Query(..., description="Session ID for chart isolation"), tool_use_id: str = Query(..., description="Tool Use ID for chart context")):
    """
    Get chart data by chart name from memory store using tool context
    """
    try:
        # Remove .json extension if present
        clean_chart_name = chart_name.replace('.json', '')
        
        logger.info(f"Looking for chart in memory: {clean_chart_name} (session: {session_id}, tool_use_id: {tool_use_id})")
        
        # Get chart data from memory store using new method
        memory_store = get_memory_store()
        chart_data = memory_store.get_chart(session_id, tool_use_id, clean_chart_name)
        
        if chart_data is None:
            logger.warning(f"Chart not found in memory: {clean_chart_name} for session: {session_id}, tool_use_id: {tool_use_id}")
            raise HTTPException(status_code=404, detail=f"Chart not found: {clean_chart_name}")
        
        logger.info(f"Successfully loaded chart: {clean_chart_name}")
        
        return JSONResponse(
            content=chart_data,
            headers={
                'Cache-Control': 'public, max-age=60, stale-while-revalidate=300',
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error loading chart {chart_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
