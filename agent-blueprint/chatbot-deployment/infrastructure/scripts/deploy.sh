#!/bin/bash

set -e

echo "Starting Chatbot deployment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "Error: AWS CLI is not configured. Please run 'aws configure' first."
    exit 1
fi

# Set region - use environment variable or default
export AWS_REGION=${AWS_REGION:-us-west-2}
export AWS_DEFAULT_REGION=$AWS_REGION

echo "🌍 Deployment region: $AWS_REGION"

# Get account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Deploying to AWS Account: $ACCOUNT_ID in region: $AWS_REGION"

# Install dependencies
echo "Installing CDK dependencies..."
npm install

# Bootstrap CDK (if not already done)
echo "Bootstrapping CDK..."
cdk bootstrap aws://$ACCOUNT_ID/$AWS_REGION || echo "CDK already bootstrapped"

# Build and push Docker images
echo "Building and pushing Docker images..."

# Get ECR login token
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Create ECR repositories if they don't exist
aws ecr describe-repositories --repository-names chatbot-backend --region $AWS_REGION > /dev/null 2>&1 || \
aws ecr create-repository --repository-name chatbot-backend --region $AWS_REGION

aws ecr describe-repositories --repository-names chatbot-frontend --region $AWS_REGION > /dev/null 2>&1 || \
aws ecr create-repository --repository-name chatbot-frontend --region $AWS_REGION

# Build and push Backend
echo "Building backend container..."
cd ../../../chatbot-app/backend
docker build --platform linux/amd64 -t chatbot-backend .
docker tag chatbot-backend:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/chatbot-backend:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/chatbot-backend:latest

# Build and push Frontend
echo "Building frontend container..."
cd ../frontend
docker build --platform linux/amd64 -t chatbot-frontend .
docker tag chatbot-frontend:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/chatbot-frontend:latest
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/chatbot-frontend:latest

# Return to CDK directory
cd ../../agent-blueprint/chatbot-deployment/infrastructure

# Deploy CDK stack
echo "Deploying CDK stack..."
cdk deploy --require-approval never

echo "Deployment completed successfully!"
echo ""
echo "🎉 Your containerized chatbot application is now running!"
echo ""
echo "📋 Access URLs:"
aws cloudformation describe-stacks --stack-name ChatbotStack --query "Stacks[0].Outputs" --output table --region $AWS_REGION

echo ""
echo "🔧 Useful commands:"
echo "  View logs: aws logs tail /aws/ecs/chatbot-backend --follow --region $AWS_REGION"
echo "  View logs: aws logs tail /aws/ecs/chatbot-frontend --follow --region $AWS_REGION"
echo "  Scale up:  aws ecs update-service --cluster chatbot-cluster --service ChatbotBackendService --desired-count 2 --region $AWS_REGION"
