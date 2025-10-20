#!/bin/bash

STACK_NAME="mcp-tavily-web-search-server"
REGION="us-west-2"

echo "Building Lambda deployment package..."

mkdir -p temp
cd temp

cp ../../src/*.py .

pip install -r ../../src/requirements.txt -t . --platform linux --python-version 3.13 --only-binary=:all:

find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete

zip -r ../lambda-deployment.zip . -x "*.pyc" "*/__pycache__/*"

cd ..
rm -rf temp

PACKAGE_SIZE=$(wc -c < lambda-deployment.zip)
PACKAGE_SIZE_MB=$((PACKAGE_SIZE / 1024 / 1024))

echo "Package size: ${PACKAGE_SIZE_MB}MB"

if [ $PACKAGE_SIZE_MB -gt 50 ]; then
    echo "Error: Package size exceeds 50MB. Please reduce package size."
    rm lambda-deployment.zip
    exit 1
fi

echo "Checking existing stack status..."
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo "STACK_NOT_EXISTS")

if [[ "$STACK_STATUS" == "ROLLBACK_IN_PROGRESS" || "$STACK_STATUS" == "ROLLBACK_COMPLETE" || "$STACK_STATUS" == "CREATE_FAILED" ]]; then
    echo "Stack is in $STACK_STATUS state. Deleting existing stack..."
    aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
    echo "Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $REGION
fi

echo "Deploying CloudFormation stack..."

# Prepare parameter overrides
PARAM_OVERRIDES="DeploymentStage=prod"
if [ -n "$CF_PARAMETERS" ]; then
    echo "Adding CloudFormation parameters: $CF_PARAMETERS"
    PARAM_OVERRIDES="$PARAM_OVERRIDES $CF_PARAMETERS"
fi

aws cloudformation deploy \
  --template-file cloudformation.yaml \
  --stack-name $STACK_NAME \
  --parameter-overrides $PARAM_OVERRIDES \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $REGION

echo "Getting deployment outputs..."
LAMBDA_FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text \
  --region $REGION 2>/dev/null)

API_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text \
  --region $REGION 2>/dev/null)

if [ -n "$LAMBDA_FUNCTION_NAME" ] && [ "$LAMBDA_FUNCTION_NAME" != "None" ]; then
    echo "Updating Lambda function code..."
    aws lambda update-function-code \
      --function-name $LAMBDA_FUNCTION_NAME \
      --zip-file fileb://lambda-deployment.zip \
      --region $REGION
else
    echo "Warning: Lambda function name not found in stack outputs"
fi

echo "Deployment completed!"
echo "API Gateway URL: $API_URL"

if [ -n "$API_URL" ] && [ "$API_URL" != "None" ]; then
    echo -e "\n=== Testing MCP server ==="

    echo -e "\n1. Testing health check (GET) - Root path:"
    curl -X GET $API_URL

    echo -e "\n2. Testing tools/list - MCP endpoint:"
    curl -X POST $API_URL/mcp \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
      }'

    echo -e "\n3. Testing Tavily web search (requires API key in Authorization Bearer header - MCP standard):"
    curl -X POST $API_URL/mcp \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer YOUR_TAVILY_API_KEY" \
      -d '{
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
          "name": "tavilyWebSearch",
          "arguments": {
            "query": "AWS Lambda MCP",
            "max_results": 3,
            "search_depth": "basic"
          }
        }
      }'

    echo -e "\n4. Testing Tavily content extraction (requires API key in Authorization Bearer header - MCP standard):"
    curl -X POST $API_URL/mcp \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer YOUR_TAVILY_API_KEY" \
      -d '{
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
          "name": "tavilyExtract",
          "arguments": {
            "urls": "https://docs.aws.amazon.com/lambda/",
            "extract_depth": "basic"
          }
        }
      }'
else
    echo "Warning: API Gateway URL not found. Skipping tests."
    echo "Please check the CloudFormation stack outputs manually."
fi

rm lambda-deployment.zip
