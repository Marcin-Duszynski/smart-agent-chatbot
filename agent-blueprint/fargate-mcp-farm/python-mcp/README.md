# Python MCP Server - ECS Fargate Deployment

This directory contains the AWS deployment configuration for the Python MCP Server (pydantic-ai/mcp-run-python) on ECS Fargate.

## Architecture

- **Runtime**: Deno + TypeScript with Pyodide for safe Python code execution
- **Infrastructure**: AWS ECS Fargate with shared ALB from MCP Farm
- **URL Path**: `/python/*` routes to this service
- **Port**: 3001 (internal container port)
- **Resources**: 2 vCPU, 4GB RAM (optimized for Pyodide)

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK installed (`npm install -g aws-cdk`)
- Docker installed and running
- Python 3.x installed
- Shared MCP Farm infrastructure deployed (VPC, ALB)

### Deploy

```bash
# Make scripts executable
chmod +x deploy.sh destroy.sh

# Deploy to development environment
./deploy.sh

# Deploy to production environment
./deploy.sh prod
```

### Access the Service

After deployment, the service will be available at:
```
http://<MCP-FARM-ALB-DNS>/python/mcp
```

The exact URL will be shown in the deployment outputs.

## Docker Image

The deployment uses a git-based approach similar to playwright-mcp:

- **Repository**: https://github.com/pydantic/pydantic-ai.git
- **Version**: v0.7.2 (fixed version for stability)
- **Path**: `mcp-run-python/` subdirectory
- **Base Image**: `denoland/deno:2.1.4`
- **Architecture**: ARM64 for cost efficiency

### Docker Build Optimizations

The Dockerfile addresses known issues from previous deployments:

1. **Lockfile Version Conflicts**: Removes `deno.lock` to prevent version conflicts
2. **File Path Issues**: Uses git clone to ensure all files are present
3. **Top-level Await**: Increased permissions to handle runtime file loading
4. **Cache Optimization**: Pre-caches dependencies without warmup to avoid startup issues

## CDK Stack

### Resources Created

- **ECR Repository**: For Docker image storage
- **ECS Cluster**: Fargate cluster for container orchestration  
- **ECS Service**: Manages container instances with auto-scaling
- **Target Group**: Health checks and load balancer integration
- **Security Groups**: Network access control
- **CloudWatch Logs**: Centralized logging
- **IAM Roles**: Task execution and runtime permissions

### Auto Scaling

- **Min Capacity**: 1 instance
- **Max Capacity**: 10 instances  
- **CPU Scaling**: Target 60% utilization
- **Memory Scaling**: Target 70% utilization
- **Scale-out**: 3 minute cooldown
- **Scale-in**: 10 minute cooldown (conservative for stability)

### Health Checks

- **Path**: `/mcp`
- **Timeout**: 10 seconds
- **Interval**: 30 seconds
- **Healthy Codes**: 200, 400 (MCP protocol returns 400 for GET requests)

## Integration with MCP Farm

This service integrates with the shared MCP Farm infrastructure:

- **VPC**: Uses shared VPC from ChatbotStack
- **ALB**: Attaches to shared Application Load Balancer
- **Listener Rule**: Priority 200, routes `/python/*` traffic
- **Security**: Private subnet deployment with ALB-only access

## Files Structure

```
python-mcp/
├── docker/
│   ├── Dockerfile          # Multi-stage Docker build
│   └── config.json         # Service configuration
├── cdk/
│   ├── app.py             # CDK application entry point
│   ├── cdk.json           # CDK configuration
│   ├── requirements.txt   # Python dependencies
│   └── stacks/
│       └── python_mcp_fargate_stack.py  # Main CDK stack
├── deploy.sh              # Deployment script
├── destroy.sh             # Cleanup script
└── README.md              # This file
```

## Monitoring

### CloudWatch Logs

Logs are stored in CloudWatch under:
```
/ecs/<stack-name>-python-mcp
```

### Metrics

Standard ECS and ALB metrics are available in CloudWatch:
- CPU and Memory utilization
- Request count and latency
- Target group health
- Container insights (optional)

## Troubleshooting

### Common Issues

1. **Docker Build Failures**
   - Check Deno version compatibility
   - Verify git repository access
   - Review lockfile conflicts

2. **Health Check Failures**
   - Container may take 60-90 seconds to start
   - Pyodide initialization requires additional time
   - Check CloudWatch logs for startup errors

3. **ALB Integration Issues**
   - Verify shared infrastructure is deployed
   - Check security group rules
   - Confirm VPC and subnet configuration

### Debugging

```bash
# Check service status
aws ecs describe-services --cluster <cluster-name> --services <service-name>

# View logs
aws logs tail /ecs/<stack-name>-python-mcp --follow

# Test local Docker build
cd docker && docker build --platform linux/arm64 -t python-mcp-test .
docker run -p 3001:3001 python-mcp-test
```

## Cost Optimization

- **ARM64 Architecture**: ~20% cost savings vs x86_64
- **Fargate Spot**: Consider for non-production workloads
- **Auto Scaling**: Scales down to 1 instance during low usage
- **Log Retention**: 1 week retention to control costs

## Security

- **Private Subnets**: Containers run in private subnets
- **IAM Roles**: Least privilege access
- **Security Groups**: Restricted network access
- **Image Scanning**: ECR vulnerability scanning enabled
- **Non-root User**: Container runs as `deno` user

## Updates

To update the service:

1. Update `REPO_TAG` in `docker/Dockerfile`
2. Run `./deploy.sh` to deploy the new version
3. ECS will perform rolling deployment automatically

## Cleanup

To remove all resources:

```bash
./destroy.sh [environment]
```

**Warning**: This will permanently delete all resources including logs and ECR images.