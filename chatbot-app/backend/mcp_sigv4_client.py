"""
StreamableHTTP Client Transport with AWS SigV4 Signing

This module extends the MCP StreamableHTTPTransport to add AWS SigV4 request signing
for authentication with MCP servers that authenticate using AWS IAM.

Based on: run-model-context-protocol-servers-with-aws-lambda/src/python/src/mcp_lambda/client/streamable_http_sigv4.py
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Generator, Dict, Any

import httpx
import boto3
import requests
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from mcp.client.streamable_http import (
    GetSessionIdCallback,
    StreamableHTTPTransport,
    streamablehttp_client,
)
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage


class SigV4HTTPXAuth(httpx.Auth):
    """HTTPX Auth class that signs requests with AWS SigV4."""

    def __init__(
        self,
        credentials: Credentials,
        service: str,
        region: str,
    ):
        self.credentials = credentials
        self.service = service
        self.region = region
        self.signer = SigV4Auth(credentials, service, region)

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Signs the request with SigV4 and adds the signature to the request headers."""

        # Create an AWS request
        headers = dict(request.headers)
        # Header 'connection' = 'keep-alive' is not used in calculating the request
        # signature on the server-side, and results in a signature mismatch if included
        headers.pop("connection", None)  # Remove if present, ignore if not

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )

        # Sign the request with SigV4
        self.signer.add_auth(aws_request)

        # Add the signature header to the original request
        request.headers.update(dict(aws_request.headers))

        yield request


class StreamableHTTPTransportWithSigV4(StreamableHTTPTransport):
    """
    Streamable HTTP client transport with AWS SigV4 signing support.

    This transport enables communication with MCP servers that authenticate using AWS IAM,
    such as servers behind a Lambda function URL or API Gateway.
    """

    def __init__(
        self,
        url: str,
        credentials: Credentials,
        service: str,
        region: str,
        headers: dict[str, str] | None = None,
        timeout: float | timedelta = 30,
        sse_read_timeout: float | timedelta = 60 * 5,
    ) -> None:
        """Initialize the StreamableHTTP transport with SigV4 signing.

        Args:
            url: The endpoint URL.
            credentials: AWS credentials for signing.
            service: AWS service name (e.g., 'lambda').
            region: AWS region (e.g., 'us-east-1').
            headers: Optional headers to include in requests.
            timeout: HTTP timeout for regular operations.
            sse_read_timeout: Timeout for SSE read operations.
        """
        # Initialize parent class with SigV4 auth handler
        super().__init__(
            url=url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            auth=SigV4HTTPXAuth(credentials, service, region),
        )

        self.credentials = credentials
        self.service = service
        self.region = region


@asynccontextmanager
async def streamablehttp_client_with_sigv4(
    url: str,
    credentials: Credentials = None,
    service: str = "execute-api",
    region: str = "us-west-2",
    headers: dict[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 60 * 5,
    terminate_on_close: bool = True,
    httpx_client_factory: McpHttpClientFactory = create_mcp_http_client,
) -> AsyncGenerator[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
        GetSessionIdCallback,
    ],
    None,
]:
    """
    Client transport for Streamable HTTP with SigV4 auth.

    This transport enables communication with MCP servers that authenticate using AWS IAM,
    such as servers behind a Lambda function URL or API Gateway.

    Args:
        url: The endpoint URL.
        credentials: AWS credentials for signing. If None, will use default credentials.
        service: AWS service name (e.g., 'execute-api', 'lambda').
        region: AWS region (e.g., 'us-west-2').
        headers: Optional headers to include in requests.
        timeout: HTTP timeout for regular operations.
        sse_read_timeout: Timeout for SSE read operations.
        terminate_on_close: Whether to terminate on close.
        httpx_client_factory: Factory for creating HTTP clients.

    Yields:
        Tuple containing:
            - read_stream: Stream for reading messages from the server
            - write_stream: Stream for sending messages to the server
            - get_session_id_callback: Function to retrieve the current session ID
    """
    
    # Get credentials if not provided
    if credentials is None:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if not credentials:
            raise ValueError(
                "AWS credentials not found. Please configure your AWS credentials."
            )

    async with streamablehttp_client(
        url=url,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
        terminate_on_close=terminate_on_close,
        httpx_client_factory=httpx_client_factory,
        auth=SigV4HTTPXAuth(credentials, service, region),
    ) as result:
        yield result


def make_sigv4_request(
    method: str,
    url: str, 
    headers: Dict[str, str] = None,
    json_data: Dict[str, Any] = None,
    service: str = "execute-api",
    region: str = "us-west-2",
    credentials: Credentials = None,
    timeout: int = 30
) -> requests.Response:
    """
    Make a single HTTP request with AWS SigV4 authentication.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dictionary
        json_data: Optional JSON data for POST requests
        service: AWS service name (e.g., 'execute-api', 'lambda')
        region: AWS region
        credentials: AWS credentials (if None, uses default)
        timeout: Request timeout in seconds
        
    Returns:
        requests.Response object
    """
    # Get credentials if not provided
    if credentials is None:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if not credentials:
            raise ValueError(
                "AWS credentials not found. Please configure your AWS credentials."
            )
    
    # Prepare headers
    if headers is None:
        headers = {}
    
    # Prepare request body
    body = None
    if json_data:
        import json
        body = json.dumps(json_data)
        headers['Content-Type'] = 'application/json'
    
    # Create AWS request
    request_headers = dict(headers)
    # Remove connection header if present (causes signature mismatch)
    request_headers.pop("connection", None)
    
    aws_request = AWSRequest(
        method=method,
        url=url,
        data=body,
        headers=request_headers,
    )
    
    # Sign the request with SigV4
    signer = SigV4Auth(credentials, service, region)
    signer.add_auth(aws_request)
    
    # Make the actual HTTP request using requests library
    response = requests.request(
        method=method,
        url=url,
        headers=dict(aws_request.headers),
        data=body,
        timeout=timeout
    )
    
    return response
