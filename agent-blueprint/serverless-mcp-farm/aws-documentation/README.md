# AWS Documentation MCP Server - Lambda Deployment

This is a Lambda deployment blueprint for the AWS Documentation MCP Server, converted from the original Docker-based implementation to run on AWS Lambda with API Gateway.

## Overview

The AWS Documentation MCP Server provides tools to:
- Search AWS documentation using the official AWS Documentation Search API
- Read and convert AWS documentation pages to markdown format
- Get content recommendations for AWS documentation pages

## Features

- **search_documentation**: Search across all AWS documentation for pages matching your search phrase
- **read_documentation**: Fetch and convert an AWS documentation page to markdown format with pagination support
- **recommend**: Get content recommendations for related AWS documentation pages

## Architecture

- **AWS Lambda**: Hosts the MCP server logic
- **API Gateway**: Provides HTTP endpoints for MCP communication
- **CloudFormation**: Infrastructure as Code for deployment

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.13 or compatible version
- Bash shell for running deployment scripts

## Deployment

1. Navigate to the infrastructure directory:
   ```bash
   cd agent-blueprint/direct-lambda-mcp/aws-documentation/infrastructure
   ```

2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

The deployment script will:
- Build a Lambda deployment package with all dependencies
- Deploy the CloudFormation stack
- Update the Lambda function with the packaged code
- Run basic tests to verify functionality

## Configuration

The deployment uses the following default settings:
- **Stack Name**: `mcp-aws-documentation-server`
- **Region**: `us-west-2`
- **Stage**: `prod`

You can modify these settings in the `deploy.sh` script if needed.

## Testing

After deployment, the script automatically tests the following endpoints:

1. **Health Check**: `GET /` - Returns server status
2. **Tools List**: `POST /mcp` - Lists available MCP tools
3. **Documentation Search**: Search for AWS documentation
4. **Documentation Read**: Read a specific AWS documentation page
5. **Recommendations**: Get related content recommendations

## Usage Examples

### Search Documentation
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_documentation",
      "arguments": {
        "search_phrase": "AWS Lambda function",
        "limit": 5
      }
    }
  }'
```

### Read Documentation
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "read_documentation",
      "arguments": {
        "url": "https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html",
        "max_length": 1000
      }
    }
  }'
```

### Get Recommendations
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "recommend",
      "arguments": {
        "url": "https://docs.aws.amazon.com/lambda/latest/dg/lambda-invocation.html"
      }
    }
  }'
```

## File Structure

```
aws-documentation/
├── src/
│   ├── lambda_function.py      # Lambda entry point
│   ├── mcp_server.py          # Main MCP server implementation
│   ├── models.py              # Data models
│   ├── server_utils.py        # Server utilities
│   ├── util.py                # Utility functions
│   └── requirements.txt       # Python dependencies
├── infrastructure/
│   ├── cloudformation.yaml    # CloudFormation template
│   └── deploy.sh             # Deployment script
└── README.md                 # This file
```

## Dependencies

The server uses the following key dependencies:
- `awslabs-mcp-lambda-handler`: MCP Lambda handler framework
- `markdownify`: HTML to Markdown conversion
- `pydantic`: Data validation and serialization
- `httpx`: HTTP client for API calls
- `loguru`: Logging framework
- `beautifulsoup4`: HTML parsing

## Troubleshooting

### Common Issues

1. **Package size exceeds 50MB**: The deployment script checks package size and will fail if it exceeds Lambda limits. Consider optimizing dependencies if this occurs.

2. **Stack deployment fails**: Check CloudFormation events in the AWS Console for detailed error messages.

3. **Lambda function not updating**: Ensure the CloudFormation stack deployed successfully and the Lambda function name is correctly retrieved.

### Logs

Check CloudWatch Logs for the Lambda function to debug runtime issues:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/mcp-aws-documentation-server"
```

## Cleanup

To remove the deployed resources:
```bash
aws cloudformation delete-stack --stack-name mcp-aws-documentation-server --region us-west-2
```

## Original Implementation

This Lambda deployment is based on the original Docker-based AWS Documentation MCP Server from:
`mcp/src/aws-documentation-mcp-server/`

The main changes for Lambda deployment:
- Converted from FastMCP to awslabs-mcp-lambda-handler
- Adapted async functions to work in Lambda environment
- Simplified import structure for Lambda packaging
- Added CloudFormation infrastructure template
- Created deployment automation script

## License

This project maintains the same Apache 2.0 license as the original AWS Documentation MCP Server implementation.
