import json
import importlib
import asyncio
import contextlib
import logging
import requests
from typing import List, Dict, Any, Tuple, Optional
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from strands.tools.tools import PythonAgentTool
from mcp_session_manager import MCPSessionManager

logger = logging.getLogger(__name__)

class UnifiedToolManager:
    """Unified Tool Manager - Manages all tools in a single unified structure"""
    
    def __init__(self, config_path: str = "unified_tools_config.json"):
        self.config_path = config_path
        self.config = {}
        self.strands_tool_functions = {}
        self.custom_tool_functions = {}  # Custom tools storage
        
        # Initialize MCP session manager
        self.mcp_session_manager = MCPSessionManager()
        
        self.load_config()
        self.load_strands_tool_functions()
        self.load_custom_tool_functions()
    
    def load_config(self):
        """Load unified configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            self.config = {"tools": []}
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = {"tools": []}
    
    def _parse_mcp_response(self, response):
        """Parse MCP response - handles both JSON and SSE formats"""
        try:
            # First try regular JSON parsing
            return response.json()
        except:
            # If that fails, try SSE parsing
            try:
                lines = response.text.strip().split('\n')
                
                # Handle SSE format with event: message followed by data: {...}
                for i, line in enumerate(lines):
                    if line.startswith('event: message') and i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if next_line.startswith('data: '):
                            data_line = next_line[6:]  # Remove 'data: ' prefix
                            import json
                            return json.loads(data_line)
                
                # Fallback: look for any data: line (original logic)
                for line in lines:
                    if line.startswith('data: '):
                        data_line = line[6:]  # Remove 'data: ' prefix
                        import json
                        return json.loads(data_line)
                        
                return None
            except Exception as e:
                logger.warning(f"Failed to parse SSE response: {e}")
                return None
    
    def save_config(self):
        """Save configuration file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get_tools_by_type(self, tool_type: str) -> List[Dict[str, Any]]:
        """Get tools filtered by type"""
        return [tool for tool in self.config.get("tools", []) if tool.get("type") == tool_type]
    
    def get_tool_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific tool by ID"""
        for tool in self.config.get("tools", []):
            if tool["id"] == tool_id:
                return tool
        return None
    
    def load_strands_tool_functions(self):
        """Load Strands built-in tool functions"""
        tool_imports = [
            ("calculator", "strands_tools.calculator", "calculator"),
            ("http_request", "strands_tools.http_request", "http_request"),
            ("generate_image", "strands_tools.generate_image", "generate_image"),
            ("image_reader", "strands_tools.image_reader", "image_reader")
        ]
        
        for tool_id, module_name, function_name in tool_imports:
            try:
                module = importlib.import_module(module_name)
                self.strands_tool_functions[tool_id] = getattr(module, function_name)
                logger.info(f"✓ Loaded Strands tool: {tool_id}")
            except ImportError as e:
                logger.warning(f"✗ Could not import {tool_id} from {module_name}: {e}")
                self._disable_unavailable_tool(tool_id)
            except AttributeError as e:
                logger.warning(f"✗ Could not find function {function_name} in {module_name}: {e}")
                self._disable_unavailable_tool(tool_id)
    
    def _disable_unavailable_tool(self, tool_id: str):
        """Disable unavailable tool"""
        tool = self.get_tool_by_id(tool_id)
        if tool and tool.get("enabled", False):
            tool["enabled"] = False
            logger.info(f"  → Automatically disabled {tool_id} due to import failure")
    
    def load_custom_tool_functions(self):
        """Load custom tools with explicit module paths"""
        custom_tools = self.get_tools_by_type("custom_tools") + self.get_tools_by_type("agent") + self.get_tools_by_type("strands_tools_wrapper")
        
        for tool_config in custom_tools:
            if not tool_config.get("enabled", False):
                continue
                
            try:
                module_path = tool_config["module_path"]
                function_name = tool_config["function_name"]
                tool_id = tool_config["id"]
                
                module = importlib.import_module(module_path)
                tool_function = getattr(module, function_name)
                
                if hasattr(tool_function, 'tool_spec'):
                    self.custom_tool_functions[tool_id] = tool_function
                    logger.info(f"✓ Loaded custom tool: {tool_id} from {module_path}.{function_name}")
                else:
                    logger.warning(f"✗ Function {function_name} is not decorated with @tool")
                    self._disable_unavailable_tool(tool_id)
                    
            except ImportError as e:
                logger.warning(f"✗ Could not import {tool_config['module_path']}: {e}")
                self._disable_unavailable_tool(tool_config['id'])
            except AttributeError as e:
                logger.warning(f"✗ Could not find function {tool_config['function_name']} in {tool_config['module_path']}: {e}")
                self._disable_unavailable_tool(tool_config['id'])
            except Exception as e:
                logger.error(f"Failed to load custom tool {tool_config['id']}: {e}")
                self._disable_unavailable_tool(tool_config['id'])
    
    def get_enabled_custom_tools(self) -> List[Any]:
        """Return enabled custom tools"""
        enabled_tools = []
        custom_tools = self.get_tools_by_type("custom_tools") + self.get_tools_by_type("agent") + self.get_tools_by_type("strands_tools_wrapper")
        
        for tool_config in custom_tools:
            if not tool_config.get("enabled", False):
                continue
                
            tool_id = tool_config["id"]
            if tool_id not in self.custom_tool_functions:
                continue
            
            tool_func = self.custom_tool_functions[tool_id]
            
            # Custom tools should already be decorated with @tool
            if hasattr(tool_func, 'tool_spec'):
                enabled_tools.append(tool_func)
            else:
                logger.warning(f"Custom tool {tool_id} is not properly decorated with @tool")
        
        return enabled_tools
    
    def get_enabled_strands_tools(self) -> List[Any]:
        """Return enabled Strands built-in tools"""
        enabled_tools = []
        strands_tools = self.get_tools_by_type("strands_tools")
        
        for tool_config in strands_tools:
            if not tool_config.get("enabled", False):
                continue
                
            tool_id = tool_config["id"]
            if tool_id not in self.strands_tool_functions:
                continue
            
            tool_func = self.strands_tool_functions[tool_id]
            
            # Check if it's already a DecoratedFunctionTool
            if hasattr(tool_func, 'tool_spec'):
                enabled_tools.append(tool_func)
            else:
                # Wrap with PythonAgentTool
                try:
                    module_name = tool_config.get("import_path")
                    if module_name:
                        module = importlib.import_module(module_name)
                        if hasattr(module, 'TOOL_SPEC'):
                            tool_spec = module.TOOL_SPEC
                            wrapped_tool = PythonAgentTool(tool_id, tool_spec, tool_func)
                            enabled_tools.append(wrapped_tool)
                except Exception as e:
                    logger.error(f"Error wrapping tool {tool_id}: {e}")
        
        return enabled_tools
    
    def get_enabled_mcp_servers(self) -> List[Dict[str, Any]]:
        """Return enabled MCP server configurations"""
        return [tool for tool in self.get_tools_by_type("mcp") 
                if tool.get("enabled", False)]
    
    def _create_mcp_client(self, server_config: Dict[str, Any]) -> MCPClient:
        """Create MCPClient using the unified factory"""
        from mcp_client_factory import MCPClientFactory
        return MCPClientFactory.create_client(server_config)
    
    # Configuration management methods
    def update_tool_status(self, tool_id: str, enabled: bool) -> bool:
        """Update tool enabled status (unified method)"""
        tool = self.get_tool_by_id(tool_id)
        if tool:
            # All MCP servers are handled uniformly - no session_aware distinction needed
            
            tool["enabled"] = enabled
            self.save_config()
            
            # Reload custom tools if enabling a custom tool or agent
            if enabled and tool.get("type") in ["custom_tools", "agent", "strands_tools_wrapper"]:
                self.load_custom_tool_functions()
            return True
        return False
    
    
    def add_tool(self, tool_config: Dict[str, Any]) -> bool:
        """Add new tool"""
        # Check for duplicate ID
        if self.get_tool_by_id(tool_config["id"]):
            return False
        
        self.config.setdefault("tools", []).append(tool_config)
        self.save_config()
        
        # Try to load the new tool if it's enabled and is a custom tool
        if tool_config.get("enabled", False) and tool_config.get("type") in ["custom_tools", "agent"]:
            self.load_custom_tool_functions()
        
        return True
    
    def remove_tool(self, tool_id: str) -> bool:
        """Remove tool"""
        tools = self.config.get("tools", [])
        for i, tool in enumerate(tools):
            if tool["id"] == tool_id:
                tools.pop(i)
                # Remove from loaded functions if it's a custom tool
                if tool_id in self.custom_tool_functions:
                    del self.custom_tool_functions[tool_id]
                self.save_config()
                return True
        return False
    
    def get_tools_summary(self) -> Dict[str, Any]:
        """Return tools status summary"""
        all_tools = self.config.get("tools", [])
        
        # Group by type
        strands_tools = self.get_tools_by_type("strands_tools")
        custom_tools = self.get_tools_by_type("custom_tools")
        agent_tools = self.get_tools_by_type("agent")
        mcp_servers = self.get_tools_by_type("mcp")
        
        enabled_strands = [t for t in strands_tools if t.get("enabled", False)]
        enabled_custom = [t for t in custom_tools if t.get("enabled", False)]
        enabled_agents = [t for t in agent_tools if t.get("enabled", False)]
        enabled_mcp = [s for s in mcp_servers if s.get("enabled", False)]
        
        return {
            "strands_tools": {
                "total": len(strands_tools),
                "enabled": len(enabled_strands),
                "tools": strands_tools
            },
            "custom_tools": {
                "total": len(custom_tools),
                "enabled": len(enabled_custom),
                "tools": custom_tools
            },
            "agent_tools": {
                "total": len(agent_tools),
                "enabled": len(enabled_agents),
                "tools": agent_tools
            },
            "mcp_servers": {
                "total": len(mcp_servers),
                "enabled": len(enabled_mcp),
                "servers": mcp_servers
            },
            "total_enabled": len(enabled_strands) + len(enabled_custom) + len(enabled_agents) + len(enabled_mcp)
        }
    
    def get_mcp_connection_status(self) -> Dict[str, Dict[str, Any]]:
        """Get connection status for all MCP servers"""
        status = {}
        mcp_servers = self.get_tools_by_type("mcp")
        
        for server in mcp_servers:
            server_id = server["id"]
            is_enabled = server.get("enabled", False)
            
            # For enabled servers, assume connected
            # For disabled servers, show as disconnected
            connected = is_enabled
            
            status[server_id] = {
                "enabled": is_enabled,
                "connected": connected,
                "name": server.get("name", server_id),
                "type": server.get("type", "unknown")
            }
        
        return status
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Return all tools (regardless of enabled status)"""
        return self.config.get("tools", [])
    
    def get_all_strands_tools(self) -> List[Dict[str, Any]]:
        """Return all Strands tools (regardless of enabled status)"""
        return self.get_tools_by_type("strands_tools")
    
    def get_all_mcp_servers(self) -> List[Dict[str, Any]]:
        """Return all MCP servers (regardless of enabled status)"""
        return self.get_tools_by_type("mcp")
    
    def get_all_custom_tools(self) -> List[Dict[str, Any]]:
        """Return all custom tools (regardless of enabled status)"""
        return self.get_tools_by_type("custom_tools") + self.get_tools_by_type("agent")
    
    def _create_http_tool_wrapper(self, server_id: str, tool_info: Dict[str, Any], server_config: Dict[str, Any]) -> PythonAgentTool:
        """Create a PythonAgentTool wrapper for HTTP-based MCP server tools"""
        tool_name = tool_info.get("name", "unknown_tool")
        tool_description = tool_info.get("description", "MCP tool")
        input_schema = tool_info.get("inputSchema", {})
        
        # Create tool specification
        tool_spec = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": input_schema
        }
        
        # Create the actual function that will be called
        def http_tool_function(**kwargs):
            """HTTP tool function that calls the MCP server"""
            try:
                # Get server configuration
                url = server_config["config"]["url"]
                headers = server_config.get("headers", {})
                
                # Prepare headers
                request_headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
                
                # Add Authorization header if provided
                if headers:
                    for key, value in headers.items():
                        if key.lower() in ['x-tavily-api-key', 'tavily-api-key', 'api-key', 'apikey']:
                            request_headers['Authorization'] = f'Bearer {value}'
                            break
                        elif key.lower() == 'authorization':
                            request_headers['Authorization'] = value
                            break
                
                # Create MCP request payload
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": kwargs
                    }
                }
                
                # Make HTTP request
                response = requests.post(
                    url,
                    json=payload,
                    headers=request_headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Use the same MCP response parser for consistency
                    result = self._parse_mcp_response(response)
                    if result and "result" in result:
                        # Extract the actual result content
                        tool_result = result["result"]
                        if isinstance(tool_result, dict) and "content" in tool_result:
                            # Handle MCP tool result format
                            content = tool_result["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # Get the first content item
                                first_content = content[0]
                                if isinstance(first_content, dict) and "text" in first_content:
                                    return first_content["text"]
                                else:
                                    return str(first_content)
                            else:
                                return str(content)
                        else:
                            return str(tool_result)
                    elif "error" in result:
                        return f"Error: {result['error'].get('message', 'Unknown error')}"
                    else:
                        return f"Unexpected response format: {result}"
                else:
                    return f"HTTP Error {response.status_code}: {response.text}"
                    
            except requests.exceptions.Timeout:
                return "Error: Request timeout (30 seconds)"
            except requests.exceptions.ConnectionError:
                return "Error: Failed to connect to MCP server"
            except Exception as e:
                return f"Error calling {tool_name}: {str(e)}"
        
        # Create and return the PythonAgentTool
        return PythonAgentTool(
            tool_id=f"{server_id}_{tool_name}",
            tool_spec=tool_spec,
            tool_function=http_tool_function
        )
    
    # Session-aware MCP methods
    def get_tools_for_session(self, backend_session_id: str, session_config: Dict = None) -> Tuple[List[Any], List[Any]]:
        """Get tools for a specific backend session (includes session-aware MCP tools)"""
        # 1. Get regular tools (Strands + Custom)
        strands_tools = self.get_enabled_strands_tools()
        custom_tools = self.get_enabled_custom_tools()
        
        # 2. Get ALL MCP tools through unified MCPSessionManager approach
        if session_config:
            # Use session-specific config if provided
            session_tools = session_config.get("tools", [])
            enabled_servers = [tool for tool in session_tools 
                             if tool.get("type") == "mcp" and tool.get("enabled", False)]
            logger.info(f"Using session config: {len(enabled_servers)} enabled MCP servers")
        else:
            # Fall back to global config
            enabled_servers = self.get_enabled_mcp_servers()
            logger.info(f"Using global config: {len(enabled_servers)} enabled MCP servers")
        
        # All MCP servers (both stateful and stateless) handled by MCPSessionManager
        # Stateless servers will simply ignore session IDs - no problem!
        all_mcp_tools = self.mcp_session_manager.get_tools_for_session(backend_session_id, enabled_servers)
        logger.info(f"MCPSessionManager returned {len(all_mcp_tools)} MCP tools (unified approach)")
        
        all_tools = strands_tools + custom_tools + all_mcp_tools
        logger.info(f"Session {backend_session_id}: {len(all_tools)} tools available")
        
        return all_tools, []  # No separate client management needed
    
    def cleanup_session(self, backend_session_id: str):
        """Clean up session resources"""
        self.mcp_session_manager.cleanup_session(backend_session_id)
        logger.info(f"Cleaned up session: {backend_session_id}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        return self.mcp_session_manager.get_session_stats()
    
    async def start_session_cleanup_task(self):
        """Start background session cleanup task"""
        await self.mcp_session_manager.start_cleanup_task()
    
    def stop_session_cleanup_task(self):
        """Stop background session cleanup task"""
        self.mcp_session_manager.stop_cleanup_task()

    def test_server_connection(self, server_config: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection to an MCP server"""
        try:
            server_type = server_config["type"]
            config = server_config["config"]
            headers = server_config.get("headers", {})
            
            if server_type in ["streamable_http", "mcp"]:
                # Test HTTP connection by calling tools/list
                url = config["url"]
                
                # Prepare headers
                request_headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
                
                # Add Authorization header if provided
                if headers:
                    for key, value in headers.items():
                        if key.lower() in ['x-tavily-api-key', 'tavily-api-key', 'api-key', 'apikey']:
                            request_headers['Authorization'] = f'Bearer {value}'
                            break
                        elif key.lower() == 'authorization':
                            request_headers['Authorization'] = value
                            break
                
                try:
                    logger.info(f"Testing MCP server connection to: {url}")
                    logger.info(f"Request headers: {request_headers}")
                    
                    # Use the improved MCP response parser
                    def parse_mcp_response(response):
                        """Parse MCP response - handles both JSON and SSE formats"""
                        return self._parse_mcp_response(response)
                    
                    # Check if this is an AWS MCP server that requires SigV4 authentication
                    from mcp_client_factory import MCPClientFactory
                    if MCPClientFactory.is_aws_server(url):
                        logger.info(f"AWS MCP server detected, using SigV4 authentication for testing")
                        try:
                            # Use SigV4 authenticated requests for AWS MCP servers
                            from mcp_sigv4_client import make_sigv4_request
                            
                            # Extract region from URL
                            region = MCPClientFactory.extract_region_from_url(url)
                            service = "execute-api" if "execute-api" in url else "lambda"
                            
                            # Initialize server with proper roots capability support
                            init_payload = {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "initialize",
                                "params": {
                                    "protocolVersion": "2024-11-05",
                                    "capabilities": {
                                        "roots": {
                                            "listChanged": False
                                        }
                                    },
                                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                                }
                            }
                            
                            logger.info(f"Testing AWS MCP server with SigV4: service={service}, region={region}")
                            
                            # Make SigV4 authenticated request
                            init_response = make_sigv4_request(
                                method="POST",
                                url=url,
                                headers=request_headers,
                                json_data=init_payload,
                                service=service,
                                region=region,
                                timeout=3
                            )
                            
                        except ImportError as e:
                            logger.warning(f"SigV4 client not available for testing AWS MCP server: {e}")
                            return {
                                "success": False,
                                "message": f"AWS MCP server requires SigV4 authentication, but SigV4 client is not available: {e}"
                            }
                    else:
                        # For non-AWS servers, use regular HTTP requests
                        logger.info(f"Testing with initialization (skipping direct tools/list for compatibility)...")
                        
                        # Initialize server with proper roots capability support
                        init_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {
                                    "roots": {
                                        "listChanged": False
                                    }
                                },
                                "clientInfo": {"name": "test-client", "version": "1.0.0"}
                            }
                        }
                        
                        logger.info(f"Initialize payload: {init_payload}")
                        
                        # Initialize server first
                        init_response = requests.post(
                            url,
                            json=init_payload,
                            headers=request_headers,
                            timeout=3  # Shorter timeout for init
                        )
                    
                    logger.info(f"Initialize response status: {init_response.status_code}")
                    logger.info(f"Initialize response headers: {dict(init_response.headers)}")
                    logger.info(f"Initialize response text: {init_response.text[:500]}...")
                    
                    if init_response.status_code != 200:
                        return {
                            "success": False,
                            "message": f"Server initialization failed: HTTP {init_response.status_code}: {init_response.text}"
                        }
                    
                    # Parse initialization response to get server info
                    init_result = parse_mcp_response(init_response)
                    server_info = "Unknown MCP Server"
                    if init_result and "result" in init_result:
                        server_info_data = init_result["result"].get("serverInfo", {})
                        server_name = server_info_data.get("name", "Unknown")
                        server_version = server_info_data.get("version", "")
                        server_info = f"{server_name} v{server_version}" if server_version else server_name
                    
                    # For testing purposes, successful initialization is sufficient
                    # This avoids the roots/list timeout issue with Playwright MCP server
                    logger.info(f"✅ MCP server initialization successful: {server_info}")
                    
                    return {
                        "success": True,
                        "message": f"Connection successful! Server: {server_info} (initialization test only)",
                        "tools_count": 0,  # Not queried to avoid timeout
                        "tools": [],
                        "note": "Tools list not queried to avoid roots/list timeout. Server connection verified via initialization."
                    }
                        
                except requests.exceptions.Timeout:
                    return {
                        "success": False,
                        "message": "Connection timeout (reduced to 3 seconds for testing)"
                    }
                except requests.exceptions.ConnectionError:
                    return {
                        "success": False,
                        "message": "Failed to connect to server"
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "message": f"Request failed: {str(e)}"
                    }
            
            else:
                return {
                    "success": True,
                    "message": f"{server_type} server configuration looks valid"
                }
                
        except Exception as e:
            logger.error(f"Error testing server connection: {e}")
            return {
                "success": False,
                "message": f"Test failed with error: {str(e)}"
            }
