# AWS Pricing MCP Server - Lambda Deployment

This is a Lambda deployment blueprint for the AWS Pricing MCP Server, converted from the original Docker-based implementation to run on AWS Lambda with API Gateway.

## Overview

The AWS Pricing MCP Server provides tools to:
- Access real-time AWS pricing information from the AWS Pricing API
- Query pricing data with advanced filtering capabilities
- Generate comprehensive cost analysis reports
- Get architecture patterns and cost considerations for AWS services

## Features

- **get_pricing**: Get detailed pricing information with optional filters and multi-region comparison
- **get_pricing_service_codes**: Discover all AWS services with available pricing information
- **get_pricing_service_attributes**: Get filterable attributes for any AWS service
- **get_pricing_attribute_values**: Get possible values for specific attributes
- **get_price_list_urls**: Download complete pricing datasets in CSV/JSON formats
- **generate_cost_report**: Create comprehensive cost analysis reports
- **get_bedrock_patterns**: Get detailed architecture patterns for Amazon Bedrock services

## Architecture

- **AWS Lambda**: Hosts the MCP server logic with AWS Pricing API integration
- **API Gateway**: Provides HTTP endpoints for MCP communication
- **CloudFormation**: Infrastructure as Code for deployment
- **IAM Roles**: Proper permissions for AWS Pricing API access

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.13 or compatible version
- Bash shell for running deployment scripts
- AWS account with `pricing:*` permissions

## Deployment

1. Navigate to the infrastructure directory:
   ```bash
   cd agent-blueprint/direct-lambda-mcp/aws-pricing/infrastructure
   ```

2. Run the deployment script:
   ```bash
   ./deploy.sh
   ```

The deployment script will:
- Build a Lambda deployment package with all dependencies
- Deploy the CloudFormation stack with proper IAM permissions
- Update the Lambda function with the packaged code
- Run comprehensive tests to verify all pricing tools

## Configuration

The deployment uses the following default settings:
- **Stack Name**: `mcp-aws-pricing-server`
- **Region**: `us-west-2`
- **Stage**: `prod`
- **Memory**: `1024MB`
- **Timeout**: `60 seconds`

You can modify these settings in the `deploy.sh` script if needed.

## Testing

After deployment, the script automatically tests the following endpoints:

1. **Health Check**: `GET /` - Returns server status
2. **Tools List**: `POST /mcp` - Lists available MCP tools
3. **Service Codes**: Get all AWS service codes
4. **Service Attributes**: Get attributes for a specific service
5. **Pricing Query**: Get actual pricing data with filters
6. **Cost Report**: Generate a cost analysis report
7. **Bedrock Patterns**: Get architecture patterns

## Usage Examples

### Get AWS Service Codes
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_pricing_service_codes",
      "arguments": {}
    }
  }'
```

### Get Pricing Information
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_pricing",
      "arguments": {
        "service_code": "AmazonEC2",
        "region": "us-east-1",
        "filters": [
          {
            "Field": "instanceType",
            "Value": "t3.medium",
            "Type": "TERM_MATCH"
          }
        ],
        "max_results": 10
      }
    }
  }'
```

### Generate Cost Report
```bash
curl -X POST $API_URL/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "generate_cost_report",
      "arguments": {
        "pricing_data": {
          "status": "success",
          "service_name": "AmazonEC2",
          "data": []
        },
        "service_name": "Amazon EC2",
        "pricing_model": "ON DEMAND"
      }
    }
  }'
```

## File Structure

```
aws-pricing/
├── src/
│   ├── lambda_function.py      # Lambda entry point
│   ├── mcp_server.py          # Main MCP server implementation
│   ├── models.py              # Data models and validation
│   ├── pricing_client.py      # AWS Pricing API client
│   ├── pricing_transformer.py # Data transformation utilities
│   ├── report_generator.py    # Cost report generation
│   ├── helpers.py             # Helper utilities
│   ├── consts.py              # Constants and configuration
│   ├── static_data.py         # Static data (Bedrock patterns, templates)
│   └── requirements.txt       # Python dependencies
├── infrastructure/
│   ├── cloudformation.yaml    # CloudFormation template
│   └── deploy.sh             # Deployment script
└── README.md                 # This file
```

## Dependencies

The server uses the following key dependencies:
- `awslabs-mcp-lambda-handler`: MCP Lambda handler framework
- `boto3`: AWS SDK for Python
- `pydantic`: Data validation and serialization
- `loguru`: Logging framework

## AWS Permissions

The Lambda function requires the following IAM permissions:
- `pricing:GetProducts`: Get pricing data
- `pricing:DescribeServices`: List available services
- `pricing:GetAttributeValues`: Get attribute values
- `pricing:ListPriceLists`: List price list files
- `pricing:GetPriceListFileUrl`: Get download URLs
- `logs:CreateLogGroup`: CloudWatch logging
- `logs:CreateLogStream`: CloudWatch logging
- `logs:PutLogEvents`: CloudWatch logging

## Troubleshooting

### Common Issues

1. **Package size exceeds 50MB**: The deployment script checks package size and will fail if it exceeds Lambda limits. Consider optimizing dependencies if this occurs.

2. **AWS Pricing API access denied**: Ensure your AWS credentials have the required `pricing:*` permissions.

3. **Stack deployment fails**: Check CloudFormation events in the AWS Console for detailed error messages.

4. **Lambda timeout**: Increase the timeout value in CloudFormation if pricing queries take longer than 60 seconds.

### Logs

Check CloudWatch Logs for the Lambda function to debug runtime issues:
```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/mcp-aws-pricing-server"
```

## Cleanup

To remove the deployed resources:
```bash
aws cloudformation delete-stack --stack-name mcp-aws-pricing-server --region us-west-2
```

## Original Implementation

This Lambda deployment is based on the original Docker-based AWS Pricing MCP Server from:
`mcp/src/aws-pricing-mcp-server/`

The main changes for Lambda deployment:
- Converted from FastMCP to awslabs-mcp-lambda-handler
- Adapted async functions to work in Lambda environment
- Simplified import structure for Lambda packaging
- Added CloudFormation infrastructure template
- Created deployment automation script
- Removed file system dependent features (CDK/Terraform analysis)
- Converted static files to Python constants

## License

This project maintains the same Apache 2.0 license as the original AWS Pricing MCP Server implementation.
