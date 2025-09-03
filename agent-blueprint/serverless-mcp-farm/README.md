# Serverless MCP Farm

A unified deployment system for multiple Model Context Protocol (MCP) servers on AWS Lambda with API Gateway.

## Overview

This deployment system allows you to deploy and manage multiple MCP servers with a single command. Each server is deployed as a serverless AWS Lambda function with API Gateway endpoints, making them accessible via HTTP/HTTPS for integration with Cline and other MCP clients.

## Available MCP Servers

- **aws-documentation**: Search and retrieve AWS documentation
- **aws-pricing**: Get AWS service pricing information
- **bedrock-kb-retrieval**: Query Amazon Bedrock Knowledge Bases
- **tavily-web-search**: Perform web searches using Tavily API
- **financial-market**: Get stock quotes, market data, and financial analysis

## Prerequisites

1. **AWS CLI** - Configured with appropriate permissions
2. **jq** - JSON processor for parsing configuration
3. **curl** - For testing deployed endpoints

### Installation

```bash
# macOS
brew install awscli jq

# Ubuntu/Debian
sudo apt-get install awscli jq curl

# Amazon Linux
sudo yum install awscli jq curl
```

### AWS Configuration

```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, Region, and Output format
```

Required AWS permissions:
- CloudFormation (create, update, delete stacks)
- Lambda (create, update functions)
- API Gateway (create, manage APIs)
- IAM (create roles and policies)

## Quick Start

1. **Configure deployment settings**:
   ```bash
   # Edit deploy-config.json to customize settings
   vim deploy-config.json
   ```

2. **Deploy all enabled servers**:
   ```bash
   ./deploy-server.sh
   ```

3. **Deploy specific server**:
   ```bash
   ./deploy-server.sh -s aws-documentation
   ./deploy-server.sh -s financial-market
   ```

## Configuration

The `deploy-config.json` file controls all deployment settings:

### Basic Configuration

```json
{
  "deployment": {
    "region": "us-west-2",
    "stage": "prod",
    "servers": {
      "aws-documentation": {
        "enabled": true,
        "stack_name": "mcp-aws-documentation-server",
        "description": "AWS Documentation Search MCP Server"
      }
    }
  }
}
```

### Environment Variables

Set environment variables for each server:

```json
{
  "environment_variables": {
    "tavily-web-search": {
      "TAVILY_API_KEY": "your-api-key-here",
      "LOG_LEVEL": "INFO"
    }
  }
}
```

### Testing Configuration

Configure automated testing:

```json
{
  "testing": {
    "enabled": true,
    "timeout": 30,
    "test_cases": {
      "aws-documentation": [
        {
          "name": "Search AWS Lambda documentation",
          "method": "searchDocumentation",
          "arguments": {
            "search_phrase": "AWS Lambda function",
            "limit": 5
          }
        }
      ]
    }
  }
}
```

## Usage

### Command Line Options

```bash
./deploy-server.sh [OPTIONS]

Options:
  -c, --config FILE    Use custom configuration file (default: deploy-config.json)
  -s, --server NAME    Deploy only specific server
  -t, --test-only      Run tests only (skip deployment)
  -h, --help           Show help message

Examples:
  ./deploy-server.sh                           # Deploy all enabled servers
  ./deploy-server.sh -s aws-documentation      # Deploy only aws-documentation server
  ./deploy-server.sh -c custom-config.json     # Use custom configuration file
  ./deploy-server.sh -t                        # Run tests only
```

### Deployment Process

1. **Validation**: Checks dependencies and configuration
2. **Build**: Creates Lambda deployment packages
3. **Deploy**: Deploys CloudFormation stacks
4. **Test**: Runs automated tests (if enabled)
5. **Summary**: Displays deployment results and MCP endpoints

### Example Output

```
[INFO] Starting MCP Farm deployment...
[INFO] Loading configuration from deploy-config.json
[INFO] Servers to deploy: aws-documentation aws-pricing

----------------------------------------
[INFO] Deploying MCP server: aws-documentation
[INFO]   Stack Name: mcp-aws-documentation-server
[INFO]   Description: AWS Documentation Search MCP Server
[INFO]   Region: us-west-2
[INFO]   Stage: prod
[SUCCESS] Successfully deployed aws-documentation
----------------------------------------

==========================================
  MCP Farm Deployment Summary
==========================================

Deployed Servers:

  • aws-documentation
    Description: AWS Documentation Search MCP Server
    API URL: https://abc123.execute-api.us-west-2.amazonaws.com/prod
    MCP Endpoint: https://abc123.execute-api.us-west-2.amazonaws.com/prod/mcp

==========================================

## Server-Specific Configuration

### AWS Documentation Server

No additional configuration required. Searches AWS documentation directly.

### AWS Pricing Server

No additional configuration required. Uses AWS Pricing API.

### Bedrock KB Retrieval Server

Requires access to Amazon Bedrock Knowledge Bases in your AWS account.

### Tavily Web Search Server

Requires Tavily API key:

```json
{
  "environment_variables": {
    "tavily-web-search": {
      "TAVILY_API_KEY": "your-tavily-api-key-here"
    }
  }
}
```

Get your API key from [Tavily](https://tavily.com/).

### Financial Market Server

No additional configuration required. Provides real-time stock quotes and market analysis using Yahoo Finance data.

Available tools:
- `stock_quote`: Get current stock information
- `historical_data`: Get historical price data
- `market_indices`: Get major market index data
- `financial_news`: Get latest financial news
- `fundamental_analysis`: Get company fundamentals
- `market_data`: Get comprehensive market overview

### Manual Testing

Test deployed endpoints manually:

```bash
# Health check
curl https://your-api-gateway-url.amazonaws.com/prod

# MCP tools list
curl -X POST https://your-api-gateway-url.amazonaws.com/prod/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

## Cleanup

To remove deployed servers:

```bash
# Delete specific stack
aws cloudformation delete-stack --stack-name mcp-aws-documentation-server --region us-west-2

# Delete all MCP stacks (be careful!)
aws cloudformation list-stacks --query 'StackSummaries[?contains(StackName, `mcp-`) && StackStatus != `DELETE_COMPLETE`].StackName' --output text | xargs -n1 aws cloudformation delete-stack --stack-name
```

## Cost Considerations

- **Lambda**: Pay per request and execution time
- **API Gateway**: Pay per API call

Typical costs are very low for development/testing usage.

## Security

- All servers run with minimal IAM permissions
- API Gateway endpoints are public but can be restricted
- Consider adding API keys or authentication for production use