# Chatbot Deployment

AWS CDK-based containerized deployment for Strands Agent Chatbot

## Overview

This deployment creates the following AWS resources:
- **Backend**: ECS Fargate container service
- **Frontend**: ECS Fargate container service (Nginx + Next.js)
- **Load Balancer**: ALB with path-based routing
- **Storage**: S3 bucket (shared file storage)

## Supported Regions

- `us-west-2` (default)
- `us-east-1`
- `ap-northeast-2` (Seoul)
- `eu-west-1` (Ireland)

## Prerequisites

- AWS CLI installed and configured
- Node.js 18+ installed
- Docker installed (for image building)

## Quick Start

### 1. Install Dependencies
```bash
cd agent-blueprint/chatbot-deployment/infrastructure
npm install

```

### 2. Configure AWS Credentials
```bash
aws configure
```

### 3. Set Deployment Region (Optional)
```bash
# Default: us-west-2
export AWS_REGION=us-west-2

# Or deploy to a different region
export AWS_REGION=us-east-1          # Virginia
export AWS_REGION=ap-northeast-2     # Seoul
export AWS_REGION=eu-west-1          # Ireland
```

### 4. Deploy
```bash
# Deploy to default region (us-west-2)
./scripts/deploy.sh

# Or deploy to specific region
AWS_REGION=ap-northeast-2 ./scripts/deploy.sh
```

### 5. Access URLs
After deployment, you'll get:
- **Application**: `http://chatbot-alb-xxxxx.{region}.elb.amazonaws.com` (Frontend + Backend)
- **API Docs**: `http://chatbot-alb-xxxxx.{region}.elb.amazonaws.com/docs`
- **Backend API**: `http://chatbot-alb-xxxxx.{region}.elb.amazonaws.com/api`

## Resources Created

- **ECS Cluster**: Fargate cluster for both containers
- **Backend Service**: FastAPI container with SSE streaming
- **Frontend Service**: Nginx + Next.js container
- **Application Load Balancer**: Path-based routing with sticky sessions
- **S3 Bucket**: Shared storage (uploads, output, generated_images)
- **ECR Repositories**: Docker image storage (backend + frontend)

## Architecture

### **Path-Based Routing**
```
ALB Routes:
├── /api/*     → Backend Container (Port 8000)
├── /docs      → Backend Container (Swagger UI)
├── /health    → Backend Container (Health Check)
└── /*         → Frontend Container (Port 3000)
```

### **Container Communication**
- **Frontend → Backend**: Direct internal communication
- **SSE Streaming**: Optimized with sticky sessions
- **File Storage**: Shared S3 bucket access

## SSE Streaming Optimization

### **ALB Configuration**
- **Sticky Sessions**: 1-hour duration for consistent connections
- **Health Checks**: 60-second intervals
- **Timeouts**: Extended for long-running streams

### **Frontend Container**
- **Nginx Proxy**: Built-in API proxy for development
- **Environment Variables**: Runtime injection support
- **Health Endpoint**: `/health` for ALB checks

### **Backend Container**
- **SSE Endpoints**: `/chat/stream`, `/tool-events/stream`
- **CORS**: Configured for cross-origin requests
- **S3 Integration**: Direct file upload/download

## Monitoring & Debugging

### **View Logs**
```bash
# Backend logs
aws logs tail /aws/ecs/chatbot-backend --follow --region us-west-2

# Frontend logs
aws logs tail /aws/ecs/chatbot-frontend --follow --region us-west-2
```

### **Scale Services**
```bash
# Scale backend
aws ecs update-service --cluster chatbot-cluster --service ChatbotBackendService --desired-count 2 --region us-west-2

# Scale frontend
aws ecs update-service --cluster chatbot-cluster --service ChatbotFrontendService --desired-count 2 --region us-west-2
```

## Cleanup

```bash
cdk destroy
```

## Estimated Cost

- **Backend ECS**: ~$15/month
- **Frontend ECS**: ~$15/month
- **Application Load Balancer**: ~$16/month
- **S3 Storage**: ~$1/month
- **ECR Storage**: ~$1/month
- **Total**: ~$48/month

## Benefits of Container Approach

✅ **SSE Optimized**: Direct container communication, no CloudFront complexity  
✅ **Consistent Environment**: Same containers in dev/prod  
✅ **Easy Debugging**: Direct log access and container inspection  
✅ **Scalable**: Independent scaling of frontend/backend  
✅ **Cost Predictable**: Fixed container costs, no CDN variables
