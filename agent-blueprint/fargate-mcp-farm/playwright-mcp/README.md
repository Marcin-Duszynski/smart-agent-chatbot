# Playwright MCP Server on AWS Fargate

This directory contains the AWS CDK infrastructure and deployment scripts for running the Playwright MCP Server on AWS Fargate.

## Architecture

The deployment creates the following AWS resources:

- **ECS Fargate Cluster**: Runs the Playwright MCP server containers
- **Application Load Balancer**: Provides HTTP endpoint for MCP clients
- **ECR Repository**: Stores Docker images
- **VPC with Public/Private Subnets**: Network isolation and security
- **CloudWatch Log Groups**: Container logging and monitoring
- **Auto Scaling**: Automatic scaling based on CPU/memory utilization
- **Security Groups**: Network access control

## Prerequisites

Before deploying, ensure you have:

1. **AWS CLI** installed and configured with appropriate credentials
2. **AWS CDK** installed globally: `npm install -g aws-cdk`
3. **Docker** installed and running
4. **Python 3.8+** installed
5. **Git** (for cloning the source code during Docker build)

**Note**: This deployment automatically downloads the Playwright MCP server source code from GitHub during the Docker build process, so you don't need to have the source code locally.

## Quick Start

### 1. Deploy the Infrastructure

```bash
# Make the deploy script executable
chmod +x deploy.sh

# Deploy to default region (us-west-2) and stage (prod)
./deploy.sh

# Or specify custom region and stage
./deploy.sh --region us-east-1 --stage dev
```

### 2. Test the Deployment

The deployment script automatically tests the MCP endpoint. You can also test manually:

```bash
# Get the MCP endpoint from the deployment output
MCP_ENDPOINT="http://your-alb-url.amazonaws.com/mcp"

# Test MCP initialize
curl -X POST "$MCP_ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
  }'
```

### 3. Use with MCP Clients

Add the MCP endpoint to your client configuration:

```json
{
  "mcpServers": {
    "playwright": {
      "url": "http://your-alb-url.amazonaws.com/mcp"
    }
  }
}
```

## Deployment Options

### Command Line Options

```bash
./deploy.sh [OPTIONS]

Options:
  --skip-image     Skip Docker image build and push
  --region REGION  AWS region (default: us-west-2)
  --stage STAGE    Deployment stage (default: prod)
  -h, --help       Show help message
```

### Environment Variables

You can also set configuration via environment variables:

```bash
export AWS_REGION=us-east-1
export STAGE=dev
./deploy.sh
```

## Architecture Details

### Container Configuration

- **CPU**: 1 vCPU (1024 CPU units)
- **Memory**: 2 GB RAM
- **Port**: 8931 (internal container port)
- **Health Check**: `/health` endpoint with 30s interval

### Auto Scaling

- **Min Capacity**: 1 instance
- **Max Capacity**: 5 instances
- **CPU Scaling**: Triggers at 70% utilization
- **Memory Scaling**: Triggers at 80% utilization

### Security

- **Private Subnets**: Containers run in private subnets
- **Security Groups**: Only allow traffic from ALB on port 8931
- **IAM Roles**: Minimal permissions for ECS tasks
- **VPC**: Isolated network environment

## Monitoring and Logging

### CloudWatch Logs

Container logs are automatically sent to CloudWatch:

```bash
# View logs
aws logs tail /ecs/playwright-mcp-fargate-prod-playwright-mcp --follow
```

### CloudWatch Metrics

Monitor the deployment through CloudWatch:

- ECS Service metrics (CPU, Memory, Task count)
- ALB metrics (Request count, Response time, Error rate)
- Container Insights (if enabled)

## Cost Optimization

### Estimated Monthly Costs

- **Fargate**: ~$30-50 (24/7 operation)
- **ALB**: ~$20
- **ECR**: ~$1
- **Data Transfer**: Variable
- **Total**: ~$50-70/month

### Cost Reduction Tips

1. **Use Spot Instances**: Consider Fargate Spot for non-production
2. **Right-size Resources**: Monitor and adjust CPU/memory allocation
3. **Auto Scaling**: Ensure proper scaling policies to avoid over-provisioning
4. **Scheduled Scaling**: Scale down during off-hours if applicable

## Troubleshooting

### Common Issues

#### 1. Docker Build Fails

```bash
# Check Docker is running
docker info

# Check if playwright-mcp source exists
ls -la ../../../../playwright-mcp/
```

#### 2. CDK Bootstrap Required

```bash
# Bootstrap CDK in your region
cdk bootstrap --region us-west-2
```

#### 3. ECR Login Issues

```bash
# Manual ECR login
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-west-2.amazonaws.com
```

#### 4. Service Won't Start

Check ECS service logs:

```bash
# Get cluster and service names from stack outputs
aws ecs describe-services --cluster <cluster-name> --services <service-name>

# Check task logs in CloudWatch
aws logs tail /ecs/playwright-mcp-fargate-prod-playwright-mcp --follow
```

### Health Check Failures

The container includes a health check on `/health`. If failing:

1. Check if the Playwright MCP server supports health checks
2. Verify the server is binding to `0.0.0.0:8931`
3. Check container logs for startup errors

## Updating the Deployment

### Update Application Code

```bash
# Rebuild and redeploy with new code
./deploy.sh
```

### Update Infrastructure Only

```bash
# Skip image build if only infrastructure changed
./deploy.sh --skip-image
```

### Update Configuration

Modify the configuration in:
- `docker/config.json` - Playwright server configuration
- `cdk/stacks/playwright_fargate_stack.py` - Infrastructure configuration

## Cleanup

### Destroy the Deployment

```bash
# Make destroy script executable
chmod +x destroy.sh

# Destroy with confirmation
./destroy.sh

# Force destroy without confirmation
./destroy.sh --force
```

### Manual Cleanup

If the destroy script fails, manually delete:

1. CloudFormation stack: `playwright-mcp-fargate-prod`
2. ECR repository images
3. CloudWatch log groups

## Development

### Local Testing

Test the Docker image locally before deployment:

```bash
cd ../../../../playwright-mcp
cp ../strands-agent-demo-template/agent-blueprint/fargate-mcp-farm/playwright-mcp/docker/Dockerfile .
cp ../strands-agent-demo-template/agent-blueprint/fargate-mcp-farm/playwright-mcp/docker/config.json .

docker build -t playwright-mcp-local .
docker run -p 8931:8931 playwright-mcp-local
```

### CDK Development

```bash
cd cdk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Synthesize CloudFormation template
cdk synth

# Show differences
cdk diff
```

## Support

For issues related to:
- **Playwright MCP Server**: Check the main playwright-mcp repository
- **AWS Infrastructure**: Review CloudFormation events and ECS service logs
- **Deployment Scripts**: Check script output and AWS CLI configuration

## License

This deployment configuration follows the same license as the main project.
