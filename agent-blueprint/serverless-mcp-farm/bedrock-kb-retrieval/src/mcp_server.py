#!/usr/bin/env python3
"""
Bedrock Knowledge Base Retrieval MCP Server for Lambda deployment using awslabs-mcp-lambda-handler
"""

import json
import logging
import os
import sys
from typing import List, Optional

import boto3
from awslabs.mcp_lambda_handler import MCPLambdaHandler
from loguru import logger
from pydantic import Field

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger_std = logging.getLogger(__name__)

# Set up loguru logging
logger.remove()
logger.add(sys.stderr, level=os.getenv('FASTMCP_LOG_LEVEL', 'WARNING'))

# Import models and utilities
from models import DataSource, KnowledgeBase, KnowledgeBaseMapping

# Environment variables for configuration
DEFAULT_KNOWLEDGE_BASE_TAG_INCLUSION_KEY = 'mcp-multirag-kb'
KB_INCLUSION_TAG_KEY = os.getenv('KB_INCLUSION_TAG_KEY', DEFAULT_KNOWLEDGE_BASE_TAG_INCLUSION_KEY)


# Environment variable for specific Knowledge Base IDs (comma-separated)
ALLOWED_KB_IDS = os.getenv('ALLOWED_KB_IDS', '').strip()
if ALLOWED_KB_IDS:
    ALLOWED_KB_IDS_LIST = [kb_id.strip() for kb_id in ALLOWED_KB_IDS.split(',') if kb_id.strip()]
else:
    ALLOWED_KB_IDS_LIST = []

logger.info(f'Allowed KB IDs: {ALLOWED_KB_IDS_LIST} (from ALLOWED_KB_IDS)')

# Create MCP Lambda handler
mcp = MCPLambdaHandler(name="bedrock-kb-retrieval", version="1.0.4")

def get_bedrock_agent_runtime_client():
    """Get a Bedrock agent runtime client."""
    region_name = os.getenv('BEDROCK_REGION') or os.getenv('AWS_REGION', 'us-west-2')
    profile_name = os.getenv('AWS_PROFILE')
    
    if profile_name:
        client = boto3.Session(profile_name=profile_name).client(
            'bedrock-agent-runtime', region_name=region_name
        )
        return client
    client = boto3.client('bedrock-agent-runtime', region_name=region_name)
    return client

def get_bedrock_agent_client():
    """Get a Bedrock agent management client."""
    region_name = os.getenv('BEDROCK_REGION') or os.getenv('AWS_REGION', 'us-west-2')
    profile_name = os.getenv('AWS_PROFILE')
    
    if profile_name:
        client = boto3.Session(profile_name=profile_name).client(
            'bedrock-agent', region_name=region_name
        )
        return client
    client = boto3.client('bedrock-agent', region_name=region_name)
    return client

async def discover_knowledge_bases(agent_client, tag_key: str = DEFAULT_KNOWLEDGE_BASE_TAG_INCLUSION_KEY) -> KnowledgeBaseMapping:
    """Discover knowledge bases."""
    result: KnowledgeBaseMapping = {}

    # If specific KB IDs are configured, use only those
    if ALLOWED_KB_IDS_LIST:
        for kb_id in ALLOWED_KB_IDS_LIST:
            try:
                kb_response = agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
                kb_info = kb_response.get('knowledgeBase', {})
                kb_name = kb_info.get('name', f'Knowledge Base {kb_id}')
                
                result[kb_id] = {'name': kb_name, 'data_sources': []}
                
                # Collect data sources for this knowledge base
                data_sources = []
                data_sources_paginator = agent_client.get_paginator('list_data_sources')
                
                for page in data_sources_paginator.paginate(knowledgeBaseId=kb_id):
                    for ds in page.get('dataSourceSummaries', []):
                        ds_id = ds.get('dataSourceId')
                        ds_name = ds.get('name')
                        data_sources.append({'id': ds_id, 'name': ds_name})
                
                result[kb_id]['data_sources'] = data_sources
                
            except Exception as e:
                logger.error(f'Error getting knowledge base {kb_id}: {e}')
                continue
        
        return result

    # Original discovery logic using tags
    kb_data = []
    kb_paginator = agent_client.get_paginator('list_knowledge_bases')

    # First, collect all knowledge bases that match our tag criteria
    for page in kb_paginator.paginate():
        for kb in page.get('knowledgeBaseSummaries', []):
            kb_id = kb.get('knowledgeBaseId')
            kb_name = kb.get('name')

            kb_arn = (
                agent_client.get_knowledge_base(knowledgeBaseId=kb_id)
                .get('knowledgeBase', {})
                .get('knowledgeBaseArn')
            )

            tags = agent_client.list_tags_for_resource(resourceArn=kb_arn).get('tags', {})
            if tag_key in tags and tags[tag_key] == 'true':
                kb_data.append((kb_id, kb_name))

    # Then, for each matching knowledge base, collect its data sources
    for kb_id, kb_name in kb_data:
        result[kb_id] = {'name': kb_name, 'data_sources': []}

        # Collect data sources for this knowledge base
        data_sources = []
        data_sources_paginator = agent_client.get_paginator('list_data_sources')

        for page in data_sources_paginator.paginate(knowledgeBaseId=kb_id):
            for ds in page.get('dataSourceSummaries', []):
                ds_id = ds.get('dataSourceId')
                ds_name = ds.get('name')
                data_sources.append({'id': ds_id, 'name': ds_name})

        result[kb_id]['data_sources'] = data_sources

    return result

async def query_knowledge_base(
    query: str,
    knowledge_base_id: str,
    kb_agent_client,
    number_of_results: int = 20,
) -> str:
    """Query an Amazon Bedrock Knowledge Base with reranking always enabled."""
    
    # Check if KB ID is allowed (if restriction is configured)
    if ALLOWED_KB_IDS_LIST and knowledge_base_id not in ALLOWED_KB_IDS_LIST:
        raise ValueError(f'Knowledge Base ID {knowledge_base_id} is not allowed. Allowed IDs: {ALLOWED_KB_IDS_LIST}')

    retrieve_request = {
        'vectorSearchConfiguration': {
            'numberOfResults': number_of_results,
            'rerankingConfiguration': {
                'type': 'BEDROCK_RERANKING_MODEL',
                'bedrockRerankingConfiguration': {
                    'modelConfiguration': {
                        'modelArn': f'arn:aws:bedrock:{kb_agent_client.meta.region_name}::foundation-model/amazon.rerank-v1:0'
                    },
                },
            },
        }
    }

    response = kb_agent_client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={'text': query},
        retrievalConfiguration=retrieve_request,
    )
    results = response['retrievalResults']
    documents = []
    for result in results:
        if result['content'].get('type') == 'IMAGE':
            logger.warning('Images are not supported at this time. Skipping...')
            continue
        else:
            documents.append(
                {
                    'content': result['content'],
                    'location': result.get('location', ''),
                    'score': result.get('score', ''),
                }
            )

    return '\n\n'.join([json.dumps(document) for document in documents])

@mcp.tool()
def list_knowledge_bases() -> str:
    """List all available Amazon Bedrock Knowledge Bases and their data sources.

    This tool returns a mapping of knowledge base IDs to their details, including:
    - name: The human-readable name of the knowledge base
    - data_sources: A list of data sources within the knowledge base, each with:
      - id: The unique identifier of the data source
      - name: The human-readable name of the data source

    ## Configuration

    The available knowledge bases can be controlled through environment variables:
    - ALLOWED_KB_IDS: Comma-separated list of specific KB IDs to allow (if not set, uses tag-based discovery)
    - KB_INCLUSION_TAG_KEY: Tag key to filter knowledge bases by (default: 'mcp-multirag-kb')

    ## Example response structure:
    ```json
    {
        "kb-12345": {
            "name": "Customer Support KB",
            "data_sources": [
                {"id": "ds-abc123", "name": "Technical Documentation"},
                {"id": "ds-def456", "name": "FAQs"}
            ]
        },
        "kb-67890": {
            "name": "Product Information KB",
            "data_sources": [
                {"id": "ds-ghi789", "name": "Product Specifications"}
            ]
        }
    }
    ```

    ## How to use this information:
    1. Extract the knowledge base IDs (like "kb-12345") for use with the QueryKnowledgeBases tool
    2. Use the names to determine which knowledge base is most relevant to the user's query
    3. Note: Data source filtering is not available - queries will search across all data sources in the selected knowledge base
    """
    logger_std.info("Listing available knowledge bases")
    
    try:
        kb_agent_mgmt_client = get_bedrock_agent_client()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            knowledge_bases = loop.run_until_complete(
                discover_knowledge_bases(kb_agent_mgmt_client, KB_INCLUSION_TAG_KEY)
            )
            return json.dumps(knowledge_bases)
        finally:
            loop.close()
            
    except Exception as e:
        error_msg = f"Error listing knowledge bases: {str(e)}"
        logger_std.error(error_msg)
        return error_msg

@mcp.tool()
def query_knowledge_bases(
    query: str = Field(
        ..., description='A natural language query to search the knowledge base with'
    ),
    knowledge_base_id: str = Field(
        ...,
        description='The knowledge base ID to query. It must be a valid ID from the ListKnowledgeBases tool',
    ),
    number_of_results: int = Field(
        10,
        description='The number of results to return. Use smaller values for focused results and larger values for broader coverage.',
    ),
) -> str:
    """Query an Amazon Bedrock Knowledge Base using natural language with automatic reranking.

    ## Usage Requirements
    - You MUST first use the ListKnowledgeBases tool to get valid knowledge base IDs
    - You can query different knowledge bases or make multiple queries to the same knowledge base

    ## Configuration
    
    The behavior can be controlled through environment variables:
    - ALLOWED_KB_IDS: Comma-separated list of specific KB IDs to allow (restricts which KBs can be queried)
    - AWS_REGION: AWS region for Bedrock services (default: us-west-2)

    ## Features
    - Automatic reranking using Amazon's rerank-v1:0 model for improved relevance
    - No complex filtering - searches across all data sources in the knowledge base
    - Simplified parameter set for ease of use

    ## Query Tips
    - Use clear, specific natural language queries for best results
    - You can use this tool MULTIPLE TIMES with different queries to gather comprehensive information
    - Break complex questions into multiple focused queries
    - Consider querying for factual information and explanations separately

    ## Tool output format
    The response contains multiple JSON objects (one per line), each representing a retrieved document with:
    - content: The text content of the document
    - location: The source location of the document
    - score: The relevance score of the document

    ## Interpretation Best Practices
    1. Extract and combine key information from multiple results
    2. Consider the source and relevance score when evaluating information
    3. Use follow-up queries to clarify ambiguous or incomplete information
    4. If the response is not relevant, try a different query or knowledge base
    5. After a few attempts, ask the user for clarification or a different query.
    """
    logger_std.info(f"Querying knowledge base {knowledge_base_id} with query: {query}")
    
    try:
        kb_runtime_client = get_bedrock_agent_runtime_client()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                query_knowledge_base(
                    query=query,
                    knowledge_base_id=knowledge_base_id,
                    kb_agent_client=kb_runtime_client,
                    number_of_results=number_of_results,
                )
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        error_msg = f"Error querying knowledge base: {str(e)}"
        logger_std.error(error_msg)
        return error_msg

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    logger_std.info("Processing Lambda request for Bedrock Knowledge Base Retrieval MCP Server")
    
    # Handle GET requests for health check
    if event.get('httpMethod') == 'GET':
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '{"status": "healthy", "service": "Bedrock Knowledge Base Retrieval MCP Server"}'
        }
    
    return mcp.handle_request(event, context)
