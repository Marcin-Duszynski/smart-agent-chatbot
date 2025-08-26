"""
Memory-based storage for analysis results and charts
Simple in-memory storage without TTL or complex management
"""

from typing import Dict, Any, Optional
from datetime import datetime
import threading

class MemoryStore:
    """Simple memory store for session-based analysis data"""
    
    def __init__(self):
        self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._lock = threading.RLock()
    
    def store_analysis(self, session_id: str, tool_use_id: str, content: str, charts: Dict[str, Any] = None, metadata: Dict[str, Any] = None):
        """Store analysis result with content and charts"""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
            
            # Preserve existing charts data if it exists
            existing_charts = {}
            if tool_use_id in self._store[session_id]:
                existing_charts = self._store[session_id][tool_use_id].get("charts", {})
            
            # Merge existing charts with new charts metadata
            final_charts = existing_charts.copy()
            if charts:
                final_charts.update(charts)
            
            self._store[session_id][tool_use_id] = {
                "content": content,
                "charts": final_charts,
                "metadata": metadata or {},
                "created_at": datetime.now().isoformat()
            }
    
    def get_analysis(self, session_id: str, tool_use_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis result by session and tool use ID"""
        with self._lock:
            return self._store.get(session_id, {}).get(tool_use_id)
    
    def store_chart(self, session_id: str, tool_use_id: str, chart_id: str, chart_data: Dict[str, Any]):
        """Store chart data for a specific analysis"""
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = {}
            if tool_use_id not in self._store[session_id]:
                self._store[session_id][tool_use_id] = {
                    "content": "",
                    "charts": {},
                    "metadata": {},
                    "created_at": datetime.now().isoformat()
                }
            
            self._store[session_id][tool_use_id]["charts"][chart_id] = chart_data
    
    def get_chart(self, session_id: str, tool_use_id: str, chart_name: str) -> Optional[Dict[str, Any]]:
        """Get chart data by session, tool use ID, and chart name"""
        with self._lock:
            return self._store.get(session_id, {}).get(tool_use_id, {}).get("charts", {}).get(chart_name)
    
    
    def get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Get all data for a session"""
        with self._lock:
            return self._store.get(session_id, {})
    
    def clear_session(self, session_id: str):
        """Clear all data for a session"""
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics"""
        with self._lock:
            total_sessions = len(self._store)
            total_analyses = sum(len(session_data) for session_data in self._store.values())
            total_charts = sum(
                len(analysis_data.get("charts", {}))
                for session_data in self._store.values()
                for analysis_data in session_data.values()
            )
            
            return {
                "total_sessions": total_sessions,
                "total_analyses": total_analyses,
                "total_charts": total_charts
            }

# Global memory store instance
memory_store = MemoryStore()

def get_memory_store() -> MemoryStore:
    """Get the global memory store instance"""
    return memory_store
