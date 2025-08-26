#!/usr/bin/env python3
"""
Tavily Search MCP Server for Lambda deployment using awslabs-mcp-lambda-handler
"""

import logging
import os
import requests
from awslabs.mcp_lambda_handler import MCPLambdaHandler
import json

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP Lambda handler
mcp = MCPLambdaHandler(name="tavily-search", version="1.0.0")

@mcp.tool()
def tavily_web_search(
    query: str, 
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    include_images: bool = False,
    include_raw_content: bool = False,
    include_domains: str = None,
    exclude_domains: str = None
) -> str:
    """
    Performs web search using Tavily AI search engine.
    
    Args:
        query: Search query
        max_results: Maximum number of search results (5-20, default 5)
        search_depth: Search depth - 'basic' or 'advanced' (default 'basic')
        topic: Search topic - 'general' or 'news' (default 'general')
        include_images: Include images in results (default False)
        include_raw_content: Include raw HTML content (default False)
        include_domains: Comma-separated domains to include (optional)
        exclude_domains: Comma-separated domains to exclude (optional)
    
    Returns:
        Formatted search results with titles, descriptions, and URLs
    """
    logger.info(f"Performing Tavily web search for: {query}")
    
    try:
        # Get API key from environment variables
        api_key = os.environ.get('TAVILY_API_KEY')
        if not api_key:
            return "Error: Tavily API key not found. Please set TAVILY_API_KEY environment variable."
        
        # Validate inputs
        if not query or len(query.strip()) == 0:
            return "Error: Query cannot be empty"
        
        if not 5 <= max_results <= 20:
            max_results = min(max(max_results, 5), 20)
        
        # Prepare search parameters
        search_params = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "topic": topic,
            "max_results": max_results,
            "include_images": include_images,
            "include_raw_content": include_raw_content
        }
        
        # Add domain filters if provided
        if include_domains:
            search_params["include_domains"] = [d.strip() for d in include_domains.split(',') if d.strip()]
        
        if exclude_domains:
            search_params["exclude_domains"] = [d.strip() for d in exclude_domains.split(',') if d.strip()]
        
        # Make API request to Tavily
        try:
            response = requests.post(
                "https://api.tavily.com/search",
                json=search_params,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                timeout=30
            )
            
            if response.status_code == 401:
                return "Error: Invalid Tavily API key"
            elif response.status_code == 429:
                return "Error: Tavily API usage limit exceeded"
            elif response.status_code != 200:
                return f"Error: Tavily API returned status {response.status_code}: {response.text}"
            
            search_results = response.json()
            
        except requests.exceptions.Timeout:
            return "Error: Tavily API request timed out"
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to connect to Tavily API: {str(e)}"
        
        # Format results
        if not search_results.get('results'):
            return f"No results found for '{query}'"
        
        formatted_results = []
        results = search_results.get('results', [])
        
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            url = result.get('url', 'No URL')
            content = result.get('content', 'No description')
            score = result.get('score', 0)
            
            formatted_results.append(f"""**[{i}] {title}**
📊 Score: {score:.2f}
🔗 URL: {url}
📝 Content: {content}
""")
        
        # Add images if included
        images_section = ""
        if include_images and search_results.get('images'):
            images_section = "\n\n## 🖼️ Related Images:\n"
            for i, image in enumerate(search_results['images'][:5], 1):  # Limit to 5 images
                if isinstance(image, str):
                    images_section += f"[{i}] {image}\n"
                else:
                    images_section += f"[{i}] {image.get('url', 'No URL')}\n"
                    if image.get('description'):
                        images_section += f"    Description: {image['description']}\n"
        
        formatted_output = f"""# 🔍 Tavily Search Results for "{query}"

Found {len(results)} results (Search Depth: {search_depth}, Topic: {topic}):

---

""" + "\n\n".join(formatted_results) + images_section
        
        logger.info(f"Tavily search completed successfully, found {len(results)} results")
        return formatted_output
        
    except Exception as e:
        error_msg = f"Tavily search error: {str(e)}"
        logger.error(error_msg)
        return error_msg

@mcp.tool()
def tavily_extract(
    urls: str,
    extract_depth: str = "basic",
    include_images: bool = False
) -> str:
    """
    Extracts content from specified URLs using Tavily.
    
    Args:
        urls: Comma-separated list of URLs to extract content from
        extract_depth: Extraction depth - 'basic' or 'advanced' (default 'basic')
        include_images: Include images from the pages (default False)
    
    Returns:
        Formatted extracted content from the URLs
    """
    logger.info(f"Performing Tavily content extraction for URLs: {urls}")
    
    try:
        # Get API key from environment variables
        api_key = os.environ.get('TAVILY_API_KEY')
        if not api_key:
            return "Error: Tavily API key not found. Please set TAVILY_API_KEY environment variable."
        
        # Parse URLs
        if not urls or len(urls.strip()) == 0:
            return "Error: URLs cannot be empty"
        
        url_list = [url.strip() for url in urls.split(',') if url.strip()]
        if not url_list:
            return "Error: No valid URLs provided"
        
        # Prepare extraction parameters
        extract_params = {
            "api_key": api_key,
            "urls": url_list,
            "extract_depth": extract_depth,
            "include_images": include_images
        }
        
        # Make API request to Tavily
        try:
            response = requests.post(
                "https://api.tavily.com/extract",
                json=extract_params,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                },
                timeout=30
            )
            
            if response.status_code == 401:
                return "Error: Invalid Tavily API key"
            elif response.status_code == 429:
                return "Error: Tavily API usage limit exceeded"
            elif response.status_code != 200:
                return f"Error: Tavily API returned status {response.status_code}: {response.text}"
            
            extract_results = response.json()
            
        except requests.exceptions.Timeout:
            return "Error: Tavily API request timed out"
        except requests.exceptions.RequestException as e:
            return f"Error: Failed to connect to Tavily API: {str(e)}"
        
        # Format results
        if not extract_results.get('results'):
            return f"No content extracted from the provided URLs"
        
        formatted_results = []
        results = extract_results.get('results', [])
        
        for i, result in enumerate(results, 1):
            url = result.get('url', 'No URL')
            content = result.get('raw_content', result.get('content', 'No content'))
            
            # Truncate very long content
            if len(content) > 2000:
                content = content[:2000] + "... [Content truncated]"
            
            formatted_results.append(f"""**[{i}] {url}**
📄 Content:
{content}
""")
        
        # Add images if included
        images_section = ""
        if include_images and extract_results.get('images'):
            images_section = "\n\n## 🖼️ Extracted Images:\n"
            for i, image in enumerate(extract_results['images'][:10], 1):  # Limit to 10 images
                images_section += f"[{i}] {image}\n"
        
        formatted_output = f"""# 📄 Tavily Content Extraction Results

Extracted content from {len(results)} URLs (Depth: {extract_depth}):

---

""" + "\n\n".join(formatted_results) + images_section
        
        logger.info(f"Tavily extraction completed successfully for {len(results)} URLs")
        return formatted_output
        
    except Exception as e:
        error_msg = f"Tavily extraction error: {str(e)}"
        logger.error(error_msg)
        return error_msg

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    logger.info("Processing Lambda request")
    
    # Handle GET requests for health check
    if event.get('httpMethod') == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '{"status": "healthy", "service": "Tavily MCP Server"}'
        }
    
    # Check if API key is available in environment
    api_key = os.environ.get('TAVILY_API_KEY')
    if api_key:
        logger.info("Tavily API key found in environment variables")
    else:
        logger.warning("No Tavily API key found in environment variables")
    
    return mcp.handle_request(event, context)