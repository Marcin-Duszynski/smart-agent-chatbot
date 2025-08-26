# Bedrock Knowledge Base Retrieval MCP Server

This is a Lambda-deployed MCP (Model Context Protocol) server that provides access to Amazon Bedrock Knowledge Bases for retrieving relevant information through natural language queries.

## Features

- **List Knowledge Bases**: Discover available knowledge bases and their data sources
- **Query Knowledge Bases**: Search knowledge bases using natural language queries
- **Configurable Access**: Control which knowledge bases are accessible via environment variables
- **Reranking Support**: Optional result reranking for improved relevance
- **Tag-based Discovery**: Automatically discover knowledge bases based on tags

## Environment Variables Configuration

The server behavior can be controlled through the following environment variables:

### Required Configuration
- `BEDROCK_REGION`: AWS region for Bedrock services (default: us-west-2)

### Knowledge Base Access Control
- `ALLOWED_KB_IDS`: Comma-separated list of specific Knowledge Base IDs to allow access to
  - Example: `kb-12345,kb-67890,kb-abcdef`
  - If not set, uses tag-based discovery
- `KB_INCLUSION_TAG_KEY`: Tag key to filter knowledge bases by when using tag-based discovery (default: `mcp-multirag-kb`)

### Query Configuration
- `BEDROCK_KB_RERANKING_ENABLED`: Enable/disable reranking by default (`true`/`false`, default: `false`)

### Logging
- `FASTMCP_LOG_LEVEL`: Log level for the server (`DEBUG`, `INFO`, `WARNING`, `ERROR`, default: `INFO`)

## Deployment

### Prerequisites
- AWS CLI configured with appropriate permissions
- Python 3.13
- pip

### Required AWS Permissions
The Lambda function needs the following permissions:
- `bedrock-agent:ListKnowledgeBases`
- `bedrock-agent:GetKnowledgeBase`
- `bedrock-agent:ListDataSources`
- `bedrock-agent:GetDataSource`
- `bedrock-agent:ListTagsForResource`
- `bedrock-agent-runtime:Retrieve`
- `bedrock:InvokeModel` (for reranking models)

### Deploy with Default Settings
```bash
cd infrastructure
./deploy.sh
```

### Deploy with Specific Knowledge Base IDs
```bash
cd infrastructure
ALLOWED_KB_IDS='kb-12345,kb-67890' ./deploy.sh
```

### Deploy with Reranking Enabled
```bash
cd infrastructure
BEDROCK_KB_RERANKING_ENABLED='true' ./deploy.sh
```

### Deploy with Custom Region
```bash
cd infrastructure
BEDROCK_REGION_OVERRIDE='us-east-1' ./deploy.sh
```

### Deploy with Multiple Configurations
```bash
cd infrastructure
ALLOWED_KB_IDS='kb-12345,kb-67890' \
BEDROCK_KB_RERANKING_ENABLED='true' \
BEDROCK_REGION_OVERRIDE='us-east-1' \
./deploy.sh
```

## Usage

### Available Tools

#### 1. list_knowledge_bases
Lists all available Amazon Bedrock Knowledge Bases and their data sources.

**Parameters**: None

**Example Response**:
```json
{
  "kb-12345": {
    "name": "Customer Support KB",
    "data_sources": [
      {"id": "ds-abc123", "name": "Technical Documentation"},
      {"id": "ds-def456", "name": "FAQs"}
    ]
  }
}
```

#### 2. query_knowledge_bases
Query an Amazon Bedrock Knowledge Base using natural language.

**Parameters**:
- `query` (required): Natural language query string
- `knowledge_base_id` (required): Knowledge base ID from list_knowledge_bases
- `number_of_results` (optional): Number of results to return (default: 10)
- `reranking` (optional): Whether to rerank results (default: from environment variable)
- `reranking_model_name` (optional): Reranking model ('COHERE' or 'AMAZON', default: 'AMAZON')
- `data_source_ids` (optional): List of data source IDs to filter by

**Example Usage**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "query_knowledge_bases",
    "arguments": {
      "query": "How do I configure AWS Lambda functions?",
      "knowledge_base_id": "kb-12345",
      "number_of_results": 5,
      "reranking": true
    }
  }
}
```

## MCP Connection

After deployment, connect to the MCP server using:
- **URL**: `https://your-api-gateway-url/mcp`
- **Method**: HTTP POST
- **Content-Type**: application/json

The deployment script will output the exact URL after successful deployment.

## Knowledge Base Setup

### Option 1: Using Specific Knowledge Base IDs
Set the `ALLOWED_KB_IDS` environment variable with comma-separated KB IDs:
```bash
ALLOWED_KB_IDS='kb-12345,kb-67890,kb-abcdef'
```

### Option 2: Using Tag-based Discovery
Tag your knowledge bases with the inclusion tag (default: `mcp-multirag-kb=true`):
```bash
aws bedrock-agent tag-resource \
  --resource-arn arn:aws:bedrock:us-west-2:123456789012:knowledge-base/kb-12345 \
  --tags mcp-multirag-kb=true
```

## Reranking Support

Reranking is supported in the following regions:
- us-west-2
- us-east-1
- ap-northeast-1
- ca-central-1

Available reranking models:
- `AMAZON`: amazon.rerank-v1:0
- `COHERE`: cohere.rerank-v3-5:0

## Troubleshooting

### Common Issues

1. **Knowledge bases not appearing**: 
   - Check that KB IDs are correct in `ALLOWED_KB_IDS`
   - Verify tags are set correctly for tag-based discovery
   - Ensure Lambda has proper permissions

2. **Query failures**:
   - Verify the knowledge base ID exists and is accessible
   - Check that the Lambda has `bedrock-agent-runtime:Retrieve` permissions
   - Ensure the knowledge base is in the same region as the Lambda

3. **Reranking errors**:
   - Verify the region supports reranking
   - Check that Lambda has `bedrock:InvokeModel` permissions for reranking models

### Logs
Check CloudWatch logs for the Lambda function for detailed error information.

## Architecture

```
Client → API Gateway → Lambda Function → Bedrock Knowledge Bases
                                    ↓
                              Bedrock Reranking Models (optional)
```

## Security Considerations

- The Lambda function uses IAM roles for AWS service access
- API Gateway endpoints are public but can be secured with additional authentication
- Knowledge base access is controlled via environment variables
- All AWS API calls use the Lambda's execution role permissions

## Cost Considerations

- Lambda execution costs based on invocation time and memory
- API Gateway request costs
- Bedrock Knowledge Base query costs
- Optional reranking model invocation costs

## License

This project is licensed under the Apache License 2.0 - see the original bedrock-kb-retrieval-mcp-server for details.
