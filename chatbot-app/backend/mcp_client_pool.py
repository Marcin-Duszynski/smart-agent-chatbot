"""Global MCP Client Pool for efficient connection management."""

import logging
import os
import boto3
from typing import Dict, Optional, List, Any
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from config import Config
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class MCPClientPool:
    """Singleton MCP client pool for managing persistent connections."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.clients: Dict[str, MCPClient] = {}
        self.client_tools: Dict[str, List[Any]] = {}
        self._ssm_client = None
        self._initialized = True
        logger.info("MCP Client Pool initialized")
    
    @property
    def ssm_client(self):
        """Lazy initialization of SSM client for Parameter Store access"""
        if self._ssm_client is None:
            try:
                self._ssm_client = boto3.client('ssm')
            except (NoCredentialsError, ClientError) as e:
                logger.warning(f"Failed to initialize SSM client: {e}")
                self._ssm_client = None
        return self._ssm_client
    
    def resolve_url(self, url: str) -> str:
        """Resolve URL using the unified factory."""
        from mcp_client_factory import MCPClientFactory
        return MCPClientFactory.resolve_url(url)

    def get_or_create_client(self, server_id: str, server_config: Dict[str, Any]) -> Optional[MCPClient]:
        """Get existing client or create new one for server."""
        # Check if configuration has changed (URL changed)
        current_url = server_config.get("config", {}).get("url", "")
        
        if server_id in self.clients:
            client = self.clients[server_id]
            
            # Check if URL has changed - if so, invalidate cache
            cached_url = getattr(client, '_cached_url', None)
            if cached_url and cached_url != current_url:
                logger.info(f"URL changed for {server_id}: {cached_url} -> {current_url}")
                logger.info(f"Invalidating cache for {server_id}")
                self.cleanup_client(server_id)
            elif server_id in self.clients:
                # Check if client is still alive
                try:
                    if hasattr(client, 'is_connected') and client.is_connected():
                        return client
                    elif server_id in self.client_tools:
                        # Client exists and we have cached tools
                        return client
                except Exception as e:
                    logger.warning(f"MCP client {server_id} health check failed: {e}")
        
        # Create new client
        try:
            client = self._create_client(server_config)
            if client:
                # Store URL for future comparison
                client._cached_url = current_url
                self.clients[server_id] = client
                # Cache tools on first connection
                self._cache_tools(server_id, client)
                logger.info(f"MCP client created for server: {server_id} (URL: {current_url})")
                return client
        except Exception as e:
            logger.error(f"Failed to create MCP client for {server_id}: {e}")
            return None
    
    def get_cached_tools(self, server_id: str) -> List[Any]:
        """Get cached tools for a server."""
        return self.client_tools.get(server_id, [])
    
    def _create_client(self, server_config: Dict[str, Any]) -> Optional[MCPClient]:
        """Create MCP client using the unified factory."""
        try:
            from mcp_client_factory import MCPClientFactory
            return MCPClientFactory.create_client(server_config)
        except Exception as e:
            logger.error(f"Error creating MCP client: {e}")
            return None
    
    def _cache_tools(self, server_id: str, client: MCPClient):
        """Cache tools from MCP server."""
        try:
            with client:
                tools = client.list_tools_sync()
                self.client_tools[server_id] = tools
                logger.info(f"Cached {len(tools)} tools for MCP server: {server_id}")
        except Exception as e:
            logger.error(f"Failed to cache tools for {server_id}: {e}")
            self.client_tools[server_id] = []
    
    
    def cleanup_client(self, server_id: str):
        """Clean up specific client."""
        if server_id in self.clients:
            try:
                client = self.clients[server_id]
                if hasattr(client, 'close'):
                    client.close()
            except Exception as e:
                logger.error(f"Error closing MCP client {server_id}: {e}")
            finally:
                del self.clients[server_id]
                if server_id in self.client_tools:
                    del self.client_tools[server_id]
    
    def cleanup_all(self):
        """Clean up all clients."""
        for server_id in list(self.clients.keys()):
            self.cleanup_client(server_id)
        logger.info("All MCP clients cleaned up")
    
    def invalidate_cache(self, server_id: str = None):
        """Invalidate cache for specific server or all servers."""
        if server_id:
            if server_id in self.clients:
                logger.info(f"Invalidating cache for MCP server: {server_id}")
                self.cleanup_client(server_id)
        else:
            logger.info("Invalidating all MCP client caches")
            self.cleanup_all()
    
    # TODO: Replace with S3 URL parsing
    def parse_resource_uris_from_result(self, tool_result: str, server_id: str = None) -> tuple[List[str], str]:
        """
        DEPRECATED: Parse MCP resource URIs from tool result text
        
        NEW APPROACH:
        Instead of parsing MCP resource URIs, we should parse S3 URLs from tool results.
        MCP servers will upload files to S3 and return S3 URLs in the tool result.
        
        Example new format:
        "Files uploaded to S3: https://bucket.s3.region.amazonaws.com/sessions/session_id/tool_use_id/file.py"
        
        Args:
            tool_result: Raw tool result containing S3 URLs
            server_id: Optional server ID (unused in S3 approach)
            
        Returns:
            Tuple of (S3 URLs list, session_id from S3 path)
        """
        # TODO: Implement S3 URL parsing logic
        print(f"📝 TODO: Parse S3 URLs from tool result instead of MCP resource URIs")
        print(f"📝 Tool result preview: {tool_result[:200]}...")
        return [], None
    
    # TODO: Replace with S3 bucket detection if needed
    def detect_mcp_server_from_resource_uri(self, resource_uri: str) -> str:
        """
        DEPRECATED: Detect which MCP server a resource URI belongs to
        
        NEW APPROACH:
        With S3-based approach, we don't need server detection since all files
        will be in the same S3 bucket with organized paths like:
        chatbot-static-contents-account-region/sessions/session_id/tool_use_id/file.py
        
        Args:
            resource_uri: S3 URL to analyze
            
        Returns:
            Server ID (not needed for S3 approach)
        """
        # TODO: Remove this method when S3 approach is implemented
        print(f"📝 TODO: Replace with S3 bucket detection if needed")
        return 'unknown'
    
    # TODO: Replace with S3 file copying if needed
    def download_resources_to_session(
        self,
        server_id: str,
        server_config: Dict[str, Any],
        session_id: str,
        tool_use_id: str,
        resource_uris: List[str],
        mcp_session_id: str = None
    ) -> bool:
        """
        DEPRECATED: Download MCP resources to backend session directory
        
        NEW APPROACH:
        With S3-based approach, files are already in S3. Options:
        1. Keep files in S3 and provide URLs to frontend
        2. Copy S3 files to local session directory if needed for compatibility
        3. Generate presigned URLs for temporary access
        
        The simplest approach is option 1 - just provide S3 URLs to frontend.
        
        Args:
            server_id: MCP server ID (unused)
            server_config: MCP server configuration (unused)
            session_id: Backend session ID
            tool_use_id: Tool use ID
            resource_uris: List of S3 URLs
            mcp_session_id: Unused in S3 approach
            
        Returns:
            bool: True if S3 URLs are valid
        """
        # TODO: Implement S3 URL validation or file copying if needed
        print(f"📝 TODO: Replace MCP resource download with S3 file handling")
        print(f"📝 Session: {session_id}, Tool: {tool_use_id}")
        print(f"📝 S3 URLs: {resource_uris}")
        return True  # Placeholder - assume S3 URLs are valid
    
    # TODO: Replace with S3-based resource processing
    def process_tool_result_resources(
        self,
        tool_result: str,
        session_id: str,
        tool_use_id: str,
        tool_info: dict = None
    ) -> bool:
        """
        DEPRECATED: Unified MCP resources processing for any tool result
        
        NEW APPROACH:
        1. Parse S3 URLs from tool result instead of MCP resource URIs
        2. Validate S3 URLs or copy files if needed
        3. Store S3 URLs in session metadata for frontend access
        4. Generate presigned URLs if temporary access is needed
        
        Much simpler than the old MCP resource download approach!
        
        Args:
            tool_result: Raw tool result text containing S3 URLs
            session_id: Backend session ID
            tool_use_id: Tool use ID
            tool_info: Optional tool metadata
            
        Returns:
            bool: True if S3 URLs were processed successfully
        """
        # TODO: Implement S3 URL processing
        print(f"📝 TODO: Replace MCP resource processing with S3 URL handling")
        print(f"📝 Session: {session_id}, Tool: {tool_use_id}")
        print(f"📝 Tool result preview: {tool_result[:200]}...")
        
        # Placeholder: Look for S3 URLs in tool result
        import re
        s3_urls = re.findall(r'https://[^\s]+\.s3\.[^\s]+\.amazonaws\.com/[^\s]+', tool_result)
        if s3_urls:
            print(f"📝 Found {len(s3_urls)} S3 URLs: {s3_urls}")
            # TODO: Store S3 URLs in session metadata or database
            return True
        else:
            print(f"📝 No S3 URLs found in tool result")
            return True  # Not an error if no files were generated
    
    # TODO: Remove when S3 approach is implemented
    def _get_server_config_from_session(self, session_id: str, server_id: str) -> dict:
        """
        DEPRECATED: Get MCP server configuration from session tool manager
        
        With S3 approach, we won't need server configurations for file downloads.
        All files will be in the same S3 bucket with predictable paths.
        
        Args:
            session_id: Session ID (unused)
            server_id: MCP server ID (unused)
            
        Returns:
            Server configuration dict (not needed for S3)
        """
        # TODO: Remove this method when S3 approach is implemented
        print(f"📝 TODO: Remove server config lookup when using S3")
        return None

    # TODO: Remove when S3 approach is implemented
    # def _parse_mcp_response(self, response):
    #     """DEPRECATED: Parse MCP response - handles both JSON and SSE formats"""
    #     # This method will be removed when switching to S3-based file handling
    #     pass
    
    # def _download_resource_via_http(self, ...):
    #     """DEPRECATED: Download resource via direct HTTP call to MCP server"""
    #     # This complex HTTP download logic will be replaced with simple S3 operations
    #     # MCP servers will upload files to S3 and return S3 URLs
    #     # Much simpler than HTTP-based resource downloading!
    #     pass


# Global instance
mcp_pool = MCPClientPool()