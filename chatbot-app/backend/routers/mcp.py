from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)

# Import session registry
from session.global_session_registry import global_session_registry

class MCPServerConfig(BaseModel):
    id: str
    name: str
    description: str
    type: str  # stdio, sse, streamable_http
    config: Dict[str, Any]
    category: str = "general"
    icon: str = "server"
    enabled: bool = False

class MCPServerTestConfig(BaseModel):
    type: str  # stdio, sse, streamable_http
    config: Dict[str, Any]
    headers: Dict[str, str] = {}

@router.get("/servers")
async def get_mcp_servers(x_session_id: Optional[str] = Header(None)):
    """Get list of all MCP servers with connection status"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Get MCP servers from session tool config
        tool_config = session_manager.get_tool_config()
        mcp_servers = [tool for tool in tool_config.get("tools", []) if tool.get("type") == "mcp"]
        
        print(f"🔧 MCP API - Found {len(mcp_servers)} MCP servers for session {session_id}")
        for server in mcp_servers:
            print(f"  - {server.get('id')}: {server.get('name')} (enabled: {server.get('enabled', False)})")
        
        return {
            "servers": mcp_servers,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get MCP servers: {str(e)}")

@router.get("/servers/enabled")
async def get_enabled_mcp_servers(x_session_id: Optional[str] = Header(None)):
    """Get list of enabled MCP servers"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Get enabled MCP servers from session
        tool_config = session_manager.get_tool_config()
        enabled_mcp_servers = [
            tool for tool in tool_config.get("tools", []) 
            if tool.get("type") == "mcp" and tool.get("enabled", False)
        ]
        
        return {
            "enabled_servers": enabled_mcp_servers,
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get enabled MCP servers: {str(e)}")

@router.post("/servers/{server_id}/update")
async def update_mcp_server(server_id: str, server_config: MCPServerConfig, x_session_id: Optional[str] = Header(None)):
    """Update MCP server configuration in session memory"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Update server configuration in session memory
        success = session_manager.update_tool_config(server_id, server_config.dict())
        
        if not success:
            raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
        
        # Clear cache for this server since configuration changed
        try:
            from mcp_client_pool import mcp_pool
            mcp_pool.invalidate_cache(server_id)
        except Exception as e:
            logger.warning(f"Failed to clear cache for {server_id}: {e}")
        
        # Recreate agent with updated configuration
        await agent.create_agent_with_all_tools()
        
        return {
            "success": True,
            "server_id": server_id,
            "server_name": server_config.name,
            "message": f"Successfully updated server {server_config.name}",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update MCP server: {str(e)}")

@router.post("/servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, x_session_id: Optional[str] = Header(None)):
    """Toggle MCP server enabled/disabled status"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Find and toggle the server in session config
        tool_config = session_manager.get_tool_config()
        server_found = None
        
        for tool in tool_config.get("tools", []):
            if tool.get("type") == "mcp" and tool.get("id") == server_id:
                server_found = tool
                break
        
        if not server_found:
            raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
        
        # Toggle enabled status
        new_status = not server_found.get("enabled", False)
        success = session_manager.update_tool_enabled(server_id, new_status)
        
        if success:
            # Recreate agent with new MCP server configuration
            await agent.create_agent_with_all_tools()
            
            return {
                "success": True,
                "server_id": server_id,
                "enabled": new_status,
                "message": f"MCP server {server_found['name']} {'enabled' if new_status else 'disabled'}",
                "session_id": session_id
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to update MCP server {server_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle MCP server: {str(e)}")


@router.post("/servers/test")
async def test_mcp_server(test_config: MCPServerTestConfig, x_session_id: Optional[str] = Header(None)):
    """Test MCP server connection with Parameter Store URL resolution"""
    
    logger.info("🧪 Testing MCP connection with Parameter Store URL resolution...")
    
    try:
        logger.info("🔧 Step 1: Importing MCP client pool for URL resolution...")
        from mcp_client_pool import mcp_pool
        logger.info("✅ Import successful")
        
        logger.info("🔧 Step 2: Preparing server config...")
        server_config = {
            "type": test_config.type,
            "config": test_config.config,
            "headers": test_config.headers
        }
        logger.info(f"✅ Original server config: {server_config}")
        
        logger.info("🔧 Step 3: Resolving Parameter Store URLs...")
        original_url = server_config["config"].get("url", "")
        
        if original_url.startswith("ssm://"):
            logger.info(f"🔍 Resolving Parameter Store URL: {original_url}")
            resolved_url = mcp_pool.resolve_url(original_url)
            server_config["config"]["url"] = resolved_url
            logger.info(f"✅ Resolved to: {resolved_url}")
        else:
            logger.info(f"📍 URL does not use Parameter Store, using as-is: {original_url}")
            resolved_url = original_url
            
        logger.info("🔧 Step 4: Importing UnifiedToolManager for connection test...")
        from unified_tool_manager import UnifiedToolManager
        tool_manager = UnifiedToolManager()
        
        logger.info("🔧 Step 5: Testing connection with resolved URL...")
        result = tool_manager.test_server_connection(server_config)
        logger.info(f"✅ Test result: {result}")
        
        # Enhance the response with Parameter Store information
        response = {
            "success": result.get("success", False),
            "message": result.get("message", "Unknown result"),
            "tools_count": result.get("tools_count", 0),
            "tools": result.get("tools", []),
            "original_url": original_url,
            "resolved_url": resolved_url,
            "used_parameter_store": original_url.startswith("ssm://")
        }
        
        if original_url.startswith("ssm://"):
            response["message"] = f"Parameter Store URL '{original_url}' resolved to '{resolved_url}'. " + response["message"]
            
        return response
            
    except Exception as e:
        logger.error(f"❌ Test failed with error: {str(e)}")
        return {
            "success": False,
            "message": f"Test failed with error: {str(e)}",
            "session_id": x_session_id
        }

@router.get("/servers/{server_id}/tools")
async def get_mcp_server_tools(server_id: str, x_session_id: Optional[str] = Header(None)):
    """Get tools available from a specific MCP server"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Get tool manager
        tool_manager = agent.get_tool_manager()
        
        # Find the MCP server
        tool_config = session_manager.get_tool_config()
        server_found = None
        
        for tool in tool_config.get("tools", []):
            if tool.get("type") == "mcp" and tool.get("id") == server_id:
                server_found = tool
                break
        
        if not server_found:
            raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
        
        # If server is enabled, get its tools by testing connection
        tools = []
        if server_found.get("enabled", False):
            connection_test = tool_manager.test_server_connection(server_found)
            if connection_test["success"]:
                tools = connection_test.get("tools", [])
        
        # Return server tools info
        return {
            "server_id": server_id,
            "server_name": server_found.get("name", "Unknown"),
            "enabled": server_found.get("enabled", False),
            "tools": tools,
            "tools_count": len(tools),
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get MCP server tools: {str(e)}")

@router.post("/servers/add")
async def add_mcp_server(server_config: MCPServerConfig, x_session_id: Optional[str] = Header(None)):
    """Add a new MCP server"""
    try:
        # Get or create session-specific agent
        session_id, session_manager, agent = global_session_registry.get_or_create_session(x_session_id)
        
        # Check if server ID already exists
        tool_config = session_manager.get_tool_config()
        existing_server = None
        for tool in tool_config.get("tools", []):
            if tool.get("type") == "mcp" and tool.get("id") == server_config.id:
                existing_server = tool
                break
        
        if existing_server:
            raise HTTPException(status_code=400, detail=f"MCP server with ID '{server_config.id}' already exists")
        
        # Add server to session configuration
        success = session_manager.add_tool_config(server_config.dict())
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to add MCP server to configuration")
        
        # Recreate agent with new server configuration
        await agent.create_agent_with_all_tools()
        
        return {
            "success": True,
            "server_id": server_config.id,
            "server_name": server_config.name,
            "message": f"Successfully added MCP server '{server_config.name}'",
            "session_id": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add MCP server: {str(e)}")

