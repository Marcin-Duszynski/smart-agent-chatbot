#!/bin/bash

STACK_NAME="mcp-bedrock-kb-retrieval-server"
REGION="us-west-2"

# Configuration parameters (can be overridden via environment variables)
ALLOWED_KB_IDS="${ALLOWED_KB_IDS:-}"
KB_INCLUSION_TAG_KEY="${KB_INCLUSION_TAG_KEY:-mcp-multirag-kb}"
BEDROCK_REGION_OVERRIDE="${BEDROCK_REGION_OVERRIDE:-}"

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

echo "Deploying CloudFormation stack with configuration:"
echo "  Allowed KB IDs: ${ALLOWED_KB_IDS:-'(using tag-based discovery)'}"
echo "  KB Inclusion Tag Key: ${KB_INCLUSION_TAG_KEY}"
echo "  Reranking: Always enabled (amazon.rerank-v1:0)"
echo "  Bedrock Region Override: ${BEDROCK_REGION_OVERRIDE:-'(using current region)'}"

# Prepare parameter overrides
PARAM_OVERRIDES="DeploymentStage=prod AllowedKBIds=\"$ALLOWED_KB_IDS\" KBInclusionTagKey=\"$KB_INCLUSION_TAG_KEY\" AWSRegionOverride=\"$BEDROCK_REGION_OVERRIDE\""
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

CONFIG_SUMMARY=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ConfigurationSummary`].OutputValue' \
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
echo -e "\nConfiguration Summary:"
echo "$CONFIG_SUMMARY"

if [ -n "$API_URL" ] && [ "$API_URL" != "None" ]; then
    echo -e "\n=== Testing Bedrock Knowledge Base Retrieval MCP server ==="

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

    echo -e "\n3. Testing list knowledge bases:"
    curl -X POST $API_URL/mcp \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
          "name": "list_knowledge_bases",
          "arguments": {}
        }
      }'

    # Only test query if we have allowed KB IDs configured
    if [ -n "$ALLOWED_KB_IDS" ]; then
        # Extract first KB ID for testing
        FIRST_KB_ID=$(echo "$ALLOWED_KB_IDS" | cut -d',' -f1 | xargs)
        
        echo -e "\n4. Testing knowledge base query with KB ID: $FIRST_KB_ID"
        curl -X POST $API_URL/mcp \
          -H "Content-Type: application/json" \
          -d "{
            \"jsonrpc\": \"2.0\",
            \"id\": 3,
            \"method\": \"tools/call\",
            \"params\": {
              \"name\": \"query_knowledge_bases\",
              \"arguments\": {
                \"query\": \"What is AWS Lambda?\",
                \"knowledge_base_id\": \"$FIRST_KB_ID\",
                \"number_of_results\": 3
              }
            }
          }"
    else
        echo -e "\n4. Skipping knowledge base query test (no specific KB IDs configured)"
        echo "   To test queries, first run list_knowledge_bases to get available KB IDs"
    fi

else
    echo "Warning: API Gateway URL not found. Skipping tests."
    echo "Please check the CloudFormation stack outputs manually."
fi

echo -e "\n=== MCP Connection Information ==="
echo "To connect this MCP server to your application, use:"
echo "URL: $API_URL/mcp"
echo "Method: HTTP POST"
echo "Content-Type: application/json"

echo -e "\n=== Environment Variables Used ==="
echo "ALLOWED_KB_IDS: ${ALLOWED_KB_IDS:-'(not set - using tag-based discovery)'}"
echo "KB_INCLUSION_TAG_KEY: ${KB_INCLUSION_TAG_KEY}"
echo "BEDROCK_REGION_OVERRIDE: ${BEDROCK_REGION_OVERRIDE:-'(not set - using current region)'}"

echo -e "\n=== Usage Examples ==="
echo "To redeploy with specific KB IDs:"
echo "ALLOWED_KB_IDS='kb-12345,kb-67890' ./deploy.sh"
echo ""
echo "To use a different region:"
echo "BEDROCK_REGION_OVERRIDE='us-east-1' ./deploy.sh"
echo ""
echo "Note: Reranking is now always enabled using amazon.rerank-v1:0 model"

rm lambda-deployment.zip
