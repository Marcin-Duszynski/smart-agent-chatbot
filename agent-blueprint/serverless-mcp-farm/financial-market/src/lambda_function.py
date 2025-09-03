#!/usr/bin/env python3
"""
Lambda function entry point for Financial Market MCP Server
"""

from mcp_server import mcp

def lambda_handler(event, context):
    """AWS Lambda handler function"""
    return mcp.handle_request(event, context)