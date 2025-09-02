# Nova Act MCP Server on AWS Fargate

This directory contains the AWS CDK infrastructure and deployment scripts for running the Nova Act MCP Server on AWS Fargate.

## Architecture

The deployment creates the following AWS resources:

- **ECS Fargate Cluster**: Runs the Nova Act MCP server containers
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
4. **Python 3.13+** installed
5. **Nova Act API Key** from https://nova-act.com/dashboard

## Configuration

### 1. Environment Variables Setup

Configure your sensitive credentials:

```bash
# Copy the template and add your API key
cp src/.env.local.example src/.env.local
```

Edit `src/.env.local` with your sensitive values:

```env
# Nova Act API Key (Required)
NOVA_ACT_API_KEY=your_actual_api_key_here
```

Public configuration is already set in `src/.env` (safe to commit to GitHub):

```env
# Browser Configuration
NOVA_BROWSER_HEADLESS=true
NOVA_BROWSER_MAX_STEPS=3
NOVA_BROWSER_TIMEOUT=30

# MCP Server Settings  
NOVA_MCP_LOG_LEVEL=INFO
PORT=8000
```

### 2. Configuration Priority

The system uses the following priority for configuration:

1. **AWS Parameter Store** (highest priority) - for production overrides
2. **ECS Environment Variables** - populated from your `.env` and `.env.local` files during deployment  
3. **Application Defaults** - fallback values in the code

This allows you to:
- Keep public settings in `.env` (safe to commit to GitHub)
- Store sensitive values in `.env.local` (ignored by git)
- Override any setting in AWS Parameter Store for production
- Modify settings in ECS without redeployment if needed

## Nova Act MCP Features

This deployment includes:

- **High-level Natural Language Actions**: Navigate, act, extract data
- **Low-level Browser Control**: JavaScript execution, element targeting, condition waiting
- **Intelligent Page Structure Analysis**: With keyword-based filtering for large pages
- **Optimized Screenshot Handling**: FastMCP Image objects for efficient transmission
- **Session Management**: Multi-session support with automatic cleanup
- **Chrome Headless**: Full browser automation in containerized environment

## Configuration

### Source Code Location

The deployment script expects Nova Act MCP source code at:
```
/Users/kevmyung/Downloads/agent-app-testing/nova-act-mcp-server-client
```

This path can be modified in the `deploy.sh` script if needed.

### Resource Configuration

Default resources (can be modified in `../deploy-config.json`):
- CPU: 2048 (2 vCPU)
- Memory: 4096 MB (4 GB)
- Port: 8000
- Desired Count: 1
- Auto Scaling: 1-5 instances

## Quick Start

### 1. Deploy Infrastructure and Application

```bash
./deploy.sh
```

This will:
1. Set up CDK environment
2. Bootstrap CDK (if needed)
3. Prepare Nova Act build context
4. Build and push Docker image
5. Deploy CDK infrastructure
6. Force service deployment

### 2. Check Deployment Status

```bash
./deploy.sh --status
```

### 3. Test the Deployment

The deployment provides an MCP endpoint that can be used with Strands agents:

```
http://your-load-balancer-url/mcp
```

## Available Tools

The Nova Act MCP server provides these tools:

### Native Tools (High-level)
- **navigate**: Navigate to URLs with auto-initialization
- **act**: Natural language browser actions
- **extract**: Data extraction with schema support

### Low-level Browser Control Tools
- **get_page_structure**: Detailed page analysis with keyword filtering
- **wait_for_condition**: Wait for specific page conditions
- **execute_js**: Direct JavaScript execution
- **quick_action**: Direct element interactions

## Docker Configuration

The Docker image includes:
- Python 3.13 runtime
- Node.js (for Nova Act SDK)
- Google Chrome (headless)
- Xvfb (virtual display)
- Nova Act SDK and MCP server

## Environment Variables

Key environment variables configured:
- `PYTHONUNBUFFERED=1`: Python output buffering
- `DISPLAY=:99`: Virtual display for Chrome
- `NODE_ENV=development`: Node.js environment
- `PORT=8000`: Server port

## Monitoring

The deployment includes:
- CloudWatch logging with 7-day retention
- Container Insights for metrics
- Health checks on `/health` endpoint
- Auto scaling based on CPU/memory thresholds

## Troubleshooting

### Common Issues

1. **Build fails**: Check Nova Act source code path
2. **Chrome crashes**: Increase memory allocation
3. **Timeout errors**: Increase health check timeout
4. **Network issues**: Check security groups and VPC configuration

### Logs

View container logs:
```bash
aws logs tail /ecs/nova-act-mcp-fargate --follow
```

### Scaling

Manual scaling:
```bash
aws ecs update-service \
  --cluster nova-act-mcp-cluster \
  --service nova-act-mcp-service \
  --desired-count 3
```

## Cleanup

To destroy all resources:
```bash
./destroy.sh
```

## Cost Optimization

The deployment includes several cost optimization features:
- Single NAT Gateway
- ECR lifecycle policies
- 7-day log retention
- Auto scaling to minimize idle resources

## Security

Security features include:
- VPC with private subnets
- Security groups with minimal required access
- Non-root container execution
- Chrome sandbox disabled (required for containers)

## Integration with Strands Agents

To use this MCP server with Strands agents, add to your `unified_tools_config.json`:

```json
{
  "id": "nova-act-browser",
  "name": "Nova Act Browser Automation",
  "type": "mcp",
  "enabled": true,
  "config": {
    "url": "http://your-load-balancer-url/mcp"
  }
}
```