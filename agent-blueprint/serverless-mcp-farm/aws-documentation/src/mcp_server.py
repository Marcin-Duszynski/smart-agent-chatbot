#!/usr/bin/env python3
"""
AWS Documentation MCP Server for Lambda deployment using awslabs-mcp-lambda-handler
"""

import logging
import os
import sys
import httpx
import json
import re
import uuid
from typing import List
from awslabs.mcp_lambda_handler import MCPLambdaHandler
from pydantic import Field
from loguru import logger

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger_std = logging.getLogger(__name__)

# Set up loguru logging
logger.remove()
logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'WARNING'))

# Import models and utilities
from models import RecommendationResult, SearchResult
from server_utils import DEFAULT_USER_AGENT, read_documentation_impl
from util import parse_recommendation_results

# API URLs
SEARCH_API_URL = 'https://proxy.search.docs.aws.amazon.com/search'
RECOMMENDATIONS_API_URL = 'https://contentrecs-api.docs.aws.amazon.com/v1/recommendations'
SESSION_UUID = str(uuid.uuid4())

# Create MCP Lambda handler
mcp = MCPLambdaHandler(name="aws-documentation", version="1.1.2")

@mcp.tool()
def read_documentation(
    url: str = Field(description='URL of the AWS documentation page to read'),
    max_length: int = Field(
        default=5000,
        description='Maximum number of characters to return.',
        gt=0,
        lt=1000000,
    ),
    start_index: int = Field(
        default=0,
        description='On return output starting at this character index, useful if a previous fetch was truncated and more content is required.',
        ge=0,
    ),
) -> str:
    """Fetch and convert an AWS documentation page to markdown format.

    ## Usage

    This tool retrieves the content of an AWS documentation page and converts it to markdown format.
    For long documents, you can make multiple calls with different start_index values to retrieve
    the entire content in chunks.

    ## URL Requirements

    - Must be from the docs.aws.amazon.com domain
    - Must end with .html

    ## Example URLs

    - https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
    - https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html

    ## Output Format

    The output is formatted as markdown text with:
    - Preserved headings and structure
    - Code blocks for examples
    - Lists and tables converted to markdown format

    ## Handling Long Documents

    If the response indicates the document was truncated, you have several options:

    1. **Continue Reading**: Make another call with start_index set to the end of the previous response
    2. **Stop Early**: For very long documents (>30,000 characters), if you've already found the specific information needed, you can stop reading

    Args:
        url: URL of the AWS documentation page to read
        max_length: Maximum number of characters to return
        start_index: On return output starting at this character index

    Returns:
        Markdown content of the AWS documentation
    """
    logger_std.info(f"Reading AWS documentation from: {url}")
    
    try:
        # Validate that URL is from docs.aws.amazon.com and ends with .html
        url_str = str(url)
        if not re.match(r'^https?://docs\.aws\.amazon\.com/', url_str):
            error_msg = f'Invalid URL: {url_str}. URL must be from the docs.aws.amazon.com domain'
            logger_std.error(error_msg)
            return f"Error: {error_msg}"
        if not url_str.endswith('.html'):
            error_msg = f'Invalid URL: {url_str}. URL must end with .html'
            logger_std.error(error_msg)
            return f"Error: {error_msg}"

        # Use a mock context for the implementation
        class MockContext:
            async def error(self, msg):
                logger_std.error(msg)

        mock_ctx = MockContext()
        
        # Since we can't use async in Lambda tools, we'll implement synchronously
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                read_documentation_impl(mock_ctx, url_str, max_length, start_index, SESSION_UUID)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        error_msg = f"Error reading documentation: {str(e)}"
        logger_std.error(error_msg)
        return error_msg

@mcp.tool()
def search_documentation(
    search_phrase: str = Field(description='Search phrase to use'),
    limit: int = Field(
        default=10,
        description='Maximum number of results to return',
        ge=1,
        le=50,
    ),
) -> str:
    """Search AWS documentation using the official AWS Documentation Search API.

    ## Usage

    This tool searches across all AWS documentation for pages matching your search phrase.
    Use it to find relevant documentation when you don't have a specific URL.

    ## Search Tips

    - Use specific technical terms rather than general phrases
    - Include service names to narrow results (e.g., "S3 bucket versioning" instead of just "versioning")
    - Use quotes for exact phrase matching (e.g., "AWS Lambda function URLs")
    - Include abbreviations and alternative terms to improve results

    ## Result Interpretation

    Each result includes:
    - rank_order: The relevance ranking (lower is more relevant)
    - url: The documentation page URL
    - title: The page title
    - context: A brief excerpt or summary (if available)

    Args:
        search_phrase: Search phrase to use
        limit: Maximum number of results to return

    Returns:
        Formatted search results with URLs, titles, and context snippets
    """
    logger_std.info(f'Searching AWS documentation for: {search_phrase}')

    try:
        request_body = {
            'textQuery': {
                'input': search_phrase,
            },
            'contextAttributes': [{'key': 'domain', 'value': 'docs.aws.amazon.com'}],
            'acceptSuggestionBody': 'RawText',
            'locales': ['en_us'],
        }

        search_url_with_session = f'{SEARCH_API_URL}?session={SESSION_UUID}'

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def perform_search():
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        search_url_with_session,
                        json=request_body,
                        headers={
                            'Content-Type': 'application/json',
                            'User-Agent': DEFAULT_USER_AGENT,
                            'X-MCP-Session-Id': SESSION_UUID,
                        },
                        timeout=30,
                    )
                except httpx.HTTPError as e:
                    error_msg = f'Error searching AWS docs: {str(e)}'
                    logger_std.error(error_msg)
                    return [SearchResult(rank_order=1, url='', title=error_msg, context=None)]

                if response.status_code >= 400:
                    error_msg = f'Error searching AWS docs - status code {response.status_code}'
                    logger_std.error(error_msg)
                    return [SearchResult(rank_order=1, url='', title=error_msg, context=None)]

                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    error_msg = f'Error parsing search results: {str(e)}'
                    logger_std.error(error_msg)
                    return [SearchResult(rank_order=1, url='', title=error_msg, context=None)]

                results = []
                if 'suggestions' in data:
                    for i, suggestion in enumerate(data['suggestions'][:limit]):
                        if 'textExcerptSuggestion' in suggestion:
                            text_suggestion = suggestion['textExcerptSuggestion']
                            context = None

                            # Add context if available
                            if 'summary' in text_suggestion:
                                context = text_suggestion['summary']
                            elif 'suggestionBody' in text_suggestion:
                                context = text_suggestion['suggestionBody']

                            results.append(
                                SearchResult(
                                    rank_order=i + 1,
                                    url=text_suggestion.get('link', ''),
                                    title=text_suggestion.get('title', ''),
                                    context=context,
                                )
                            )

                logger_std.info(f'Found {len(results)} search results for: {search_phrase}')
                return results

        try:
            results = loop.run_until_complete(perform_search())
        finally:
            loop.close()

        # Format results for return
        if not results or (len(results) == 1 and not results[0].url):
            return f"No results found for '{search_phrase}'"

        formatted_results = []
        for result in results:
            if result.url:  # Skip error results
                context_text = f"\n📝 Context: {result.context}" if result.context else ""
                formatted_results.append(f"""**[{result.rank_order}] {result.title}**
🔗 URL: {result.url}{context_text}
""")

        formatted_output = f"""# 🔍 AWS Documentation Search Results for "{search_phrase}"

Found {len([r for r in results if r.url])} results:

---

""" + "\n\n".join(formatted_results)

        return formatted_output

    except Exception as e:
        error_msg = f"AWS documentation search error: {str(e)}"
        logger_std.error(error_msg)
        return error_msg

@mcp.tool()
def recommend(
    url: str = Field(description='URL of the AWS documentation page to get recommendations for'),
) -> str:
    """Get content recommendations for an AWS documentation page.

    ## Usage

    This tool provides recommendations for related AWS documentation pages based on a given URL.
    Use it to discover additional relevant content that might not appear in search results.

    ## Recommendation Types

    The recommendations include four categories:

    1. **Highly Rated**: Popular pages within the same AWS service
    2. **New**: Recently added pages within the same AWS service - useful for finding newly released features
    3. **Similar**: Pages covering similar topics to the current page
    4. **Journey**: Pages commonly viewed next by other users

    ## When to Use

    - After reading a documentation page to find related content
    - When exploring a new AWS service to discover important pages
    - To find alternative explanations of complex concepts
    - To discover the most popular pages for a service
    - To find newly released information by using a service's welcome page URL and checking the **New** recommendations

    ## Finding New Features

    To find newly released information about a service:
    1. Find any page belong to that service, typically you can try the welcome page
    2. Call this tool with that URL
    3. Look specifically at the **New** recommendation type in the results

    ## Result Interpretation

    Each recommendation includes:
    - url: The documentation page URL
    - title: The page title
    - context: A brief description (if available)

    Args:
        url: URL of the AWS documentation page to get recommendations for

    Returns:
        Formatted list of recommended pages with URLs, titles, and context
    """
    url_str = str(url)
    logger_std.info(f'Getting recommendations for: {url_str}')

    try:
        recommendation_url = f'{RECOMMENDATIONS_API_URL}?path={url_str}&session={SESSION_UUID}'

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def get_recommendations():
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        recommendation_url,
                        headers={'User-Agent': DEFAULT_USER_AGENT},
                        timeout=30,
                    )
                except httpx.HTTPError as e:
                    error_msg = f'Error getting recommendations: {str(e)}'
                    logger_std.error(error_msg)
                    return [RecommendationResult(url='', title=error_msg, context=None)]

                if response.status_code >= 400:
                    error_msg = f'Error getting recommendations - status code {response.status_code}'
                    logger_std.error(error_msg)
                    return [RecommendationResult(url='', title=error_msg, context=None)]

                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    error_msg = f'Error parsing recommendations: {str(e)}'
                    logger_std.error(error_msg)
                    return [RecommendationResult(url='', title=error_msg, context=None)]

                results = parse_recommendation_results(data)
                logger_std.info(f'Found {len(results)} recommendations for: {url_str}')
                return results

        try:
            results = loop.run_until_complete(get_recommendations())
        finally:
            loop.close()

        # Format results for return
        if not results or (len(results) == 1 and not results[0].url):
            return f"No recommendations found for '{url_str}'"

        formatted_results = []
        for i, result in enumerate(results, 1):
            if result.url:  # Skip error results
                context_text = f"\n📝 Context: {result.context}" if result.context else ""
                formatted_results.append(f"""**[{i}] {result.title}**
🔗 URL: {result.url}{context_text}
""")

        formatted_output = f"""# 💡 AWS Documentation Recommendations for "{url_str}"

Found {len([r for r in results if r.url])} recommendations:

---

""" + "\n\n".join(formatted_results)

        return formatted_output

    except Exception as e:
        error_msg = f"AWS documentation recommendations error: {str(e)}"
        logger_std.error(error_msg)
        return error_msg

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    logger_std.info("Processing Lambda request for AWS Documentation MCP Server")
    
    # Handle GET requests for health check
    if event.get('httpMethod') == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '{"status": "healthy", "service": "AWS Documentation MCP Server"}'
        }
    
    return mcp.handle_request(event, context)
