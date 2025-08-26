# Fargate MCP Farm

This directory contains infrastructure and deployment scripts for running MCP (Model Context Protocol) servers on AWS Fargate. Unlike the serverless MCP farm that uses Lambda functions, this deployment uses containerized services running on ECS Fargate for better performance and longer execution times.

## Architecture Overview

The Fargate MCP Farm provides:

- **ECS Fargate Clusters**: Run MCP servers as containerized services
- **Application Load Balancers**: HTTP endpoints for MCP clients
- **Auto Scaling**: Automatic scaling based on CPU/memory utilization
- **VPC Isolation**: Secure networking with public/private subnets
- **Container Insights**: CloudWatch monitoring and logging
- **ECR Repositories**: Docker image storage and management

## Why Fargate vs Serverless?

| Feature | Serverless (Lambda) | Fargate |
|---------|-------------------|---------|
| **Execution Time** | 15 minutes max | Unlimited |
| **Memory** | 10 GB max | Up to 30 GB |
| **Persistent Connections** | Limited | Full support |
| **Cold Starts** | Yes | Minimal |
| **Cost Model** | Pay per request | Pay for running time |
| **Best For** | Short-lived tasks | Long-running services |

**Fargate is ideal for:**
- Browser automation (Playwright)
- Long-running MCP sessions
- Services requiring persistent state
- High-memory applications

## Available Servers

### Playwright MCP Server

Located in `playwright-mcp/`, this server provides browser automation capabilities:

- **Browser Control**: Navigate, click, type, screenshot
- **PDF Generation**: Convert web pages to PDF
- **Web Scraping**: Extract data from websites
- **Visual Testing**: Screenshot comparison and analysis

## Quick Start

### Prerequisites

1. **AWS CLI** installed and configured
2. **AWS CDK** installed globally: `npm install -g aws-cdk`
3. **Docker** installed and running
4. **Python 3.8+** and **Node.js 18+**
5. **jq** for JSON processing

### Deploy All Servers

```bash
# Make scripts executable
chmod +x deploy-all.sh

# Deploy all enabled servers
./deploy-all.sh

# Deploy to specific region/stage
./deploy-all.sh --region us-east-1 --stage dev

# Deploy only specific server
./deploy-all.sh -s playwright-mcp
```

### Deploy Individual Server

```bash
cd playwright-mcp
chmod +x deploy.sh
./deploy.sh
```

## Configuration

### Global Configuration

Edit `deploy-config.json` to configure deployment settings:

```json
{
  "deployment": {
    "region": "us-west-2",
    "stage": "prod",
    "servers": {
      "playwright-mcp": {
        "enabled": true,
        "stack_name": "playwright-mcp-fargate",
        "description": "Playwright MCP Server on AWS Fargate"
      }
    }
  },
  "environment_variables": {
    "playwright-mcp": {
      "NODE_ENV": "production",
      "PORT": "8931",
      "LOG_LEVEL": "info"
    }
  }
}
```

### Server-Specific Configuration

Each server has its own configuration in its directory:
- `docker/config.json` - Application configuration
- `cdk/stacks/` - Infrastructure configuration

## Usage Examples

### Test Deployment

```bash
# Test all deployed servers
./deploy-all.sh -t

# Test specific server
curl -X POST "http://your-alb-url.amazonaws.com/mcp" \
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

### MCP Client Configuration

Add deployed servers to your MCP client:

```json
{
  "mcpServers": {
    "playwright": {
      "url": "http://your-playwright-alb.amazonaws.com/mcp"
    }
  }
}
```

## Monitoring and Logging

### CloudWatch Logs

View container logs:

```bash
# View logs for specific server
aws logs tail /ecs/playwright-mcp-fargate-prod-playwright-mcp --follow

# View logs with filter
aws logs filter-log-events \
  --log-group-name /ecs/playwright-mcp-fargate-prod-playwright-mcp \
  --filter-pattern "ERROR"
```

### CloudWatch Metrics

Monitor through AWS Console or CLI:

```bash
# Get ECS service metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=playwright-mcp-fargate-prod-playwright-mcp-service \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-01T23:59:59Z \
  --period 300 \
  --statistics Average
```

## Cost Management

### Estimated Monthly Costs

Per server (24/7 operation):
- **Fargate**: $30-50
- **ALB**: $20
- **ECR**: $1
- **Data Transfer**: Variable
- **Total per server**: ~$50-70

### Cost Optimization

1. **Right-size Resources**: Monitor and adjust CPU/memory
2. **Auto Scaling**: Configure appropriate scaling policies
3. **Scheduled Scaling**: Scale down during off-hours
4. **Spot Instances**: Use Fargate Spot for non-production

```bash
# Example: Scale down service manually
aws ecs update-service \
  --cluster playwright-mcp-fargate-prod-cluster \
  --service playwright-mcp-fargate-prod-playwright-mcp-service \
  --desired-count 0
```

## Troubleshooting

### Common Issues

#### 1. CDK Bootstrap Required

```bash
cdk bootstrap --region us-west-2
```

#### 2. Docker Build Fails

```bash
# Check Docker daemon
docker info

# Check source directory
ls -la ../../../playwright-mcp/
```

#### 3. Service Won't Start

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster your-cluster-name \
  --services your-service-name

# Check task logs
aws logs tail /ecs/your-log-group --follow
```

#### 4. Health Check Failures

- Verify application binds to `0.0.0.0:PORT`
- Check if health endpoint exists
- Review container startup logs

### Debug Commands

```bash
# List all stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Get stack outputs
aws cloudformation describe-stacks --stack-name your-stack-name

# Check ECS tasks
aws ecs list-tasks --cluster your-cluster-name

# Describe task
aws ecs describe-tasks --cluster your-cluster-name --tasks your-task-arn
```

## Development

### Adding New Servers

1. Create new directory: `your-server-name/`
2. Add CDK stack in `your-server-name/cdk/`
3. Add Docker configuration in `your-server-name/docker/`
4. Create deployment scripts: `deploy.sh` and `destroy.sh`
5. Update `deploy-config.json`

### Local Testing

```bash
# Test Docker image locally
cd your-server-name
docker build -f docker/Dockerfile -t your-server-local ../../../your-source-dir
docker run -p 8931:8931 your-server-local
```

### CDK Development

```bash
cd your-server-name/cdk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Synthesize template
cdk synth

# Deploy with diff
cdk diff
cdk deploy
```

## Cleanup

### Destroy All Servers

```bash
# Destroy all servers
for server in */; do
  if [ -f "$server/destroy.sh" ]; then
    cd "$server"
    ./destroy.sh --force
    cd ..
  fi
done
```

### Destroy Specific Server

```bash
cd playwright-mcp
./destroy.sh
```

### Manual Cleanup

If scripts fail, manually delete:

1. CloudFormation stacks
2. ECR repositories and images
3. CloudWatch log groups
4. Load balancers (if not deleted by stack)

## Security Considerations

### Network Security

- Services run in private subnets
- Security groups restrict access to necessary ports
- ALB provides public endpoint with SSL termination

### IAM Permissions

- Minimal permissions for ECS tasks
- Separate execution and task roles
- No hardcoded credentials

### Container Security

- Non-root user in containers
- Read-only root filesystem where possible
- Security scanning enabled on ECR

## Support and Contributing

### Getting Help

1. Check server-specific README files
2. Review CloudWatch logs and metrics
3. Check AWS service health dashboard
4. Review CDK documentation

### Contributing

1. Follow existing patterns for new servers
2. Include comprehensive documentation
3. Add appropriate monitoring and logging
4. Test in multiple regions/stages

## License

This deployment configuration follows the same license as the main project.
