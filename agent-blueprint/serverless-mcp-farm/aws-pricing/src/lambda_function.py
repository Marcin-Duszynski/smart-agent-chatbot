"""
AWS Lambda entry point for AWS Pricing MCP Server
"""

from mcp_server import lambda_handler

# Export the lambda_handler for AWS Lambda
__all__ = ['lambda_handler']
