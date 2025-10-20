# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive AI agent testing platform built with the Strands Agents framework. It's designed for rapid prototyping and testing of business-specific AI tools with plug-and-play integration of built-in tools, custom tools, MCP servers, and agents.

**Tech Stack:**
- Backend: FastAPI (Python 3.8+) with Strands Agents (v1.5.0) and AWS Bedrock
- Frontend: Next.js 15 (React 18) with TypeScript and Tailwind CSS
- AI Engine: AWS Bedrock (Claude Sonnet 4) via Strands Agents framework
- MCP Servers: Serverless (AWS Lambda) and Stateful (AWS ECS Fargate)
- Real-time: Server-Sent Events (SSE) for streaming responses

## Development Commands

### Local Development

**Initial Setup:**
```bash
cd agent-blueprint
cp .env.example .env
# Edit .env with your AWS credentials and API keys
```

**Start Full Stack (Frontend + Backend):**
```bash
cd chatbot-app
./start.sh
```
- Frontend runs at http://localhost:3000
- Backend API at http://localhost:8000
- API Docs at http://localhost:8000/docs

**Frontend Only:**
```bash
cd chatbot-app/frontend
npm install
npm run dev      # Development server with hot reload
npm run build    # Production build
npm run start    # Production server
npm run lint     # Lint code
```

**Backend Only:**
```bash
cd chatbot-app/backend
source venv/bin/activate
python app.py    # Start FastAPI server
```

### Cloud Deployment

**Full System Deployment:**
```bash
cd agent-blueprint
./deploy-all.sh       # Deploy everything
./destroy-all.sh      # Remove all components
```

**Individual Components:**
```bash
# Web application (creates VPC)
cd agent-blueprint/chatbot-deployment/infrastructure
./scripts/deploy.sh

# Serverless MCP servers (Lambda)
cd ../../serverless-mcp-farm
./deploy-server.sh

# Shared infrastructure for stateful MCP
cd ../fargate-mcp-farm/shared-infrastructure
./deploy.sh

# Stateful MCP servers (ECS)
cd ../
./deploy-all.sh -s nova-act-mcp
```

**MCP Server Development:**
```bash
# Deploy individual serverless MCP server
cd agent-blueprint/serverless-mcp-farm/<server-name>
./deploy.sh

# Deploy individual stateful MCP server
cd agent-blueprint/fargate-mcp-farm/<server-name>
./deploy.sh
```

### Observability Setup

```bash
# Set up CloudWatch observability
./setup-observability.sh
```
Then enable Transaction Search in CloudWatch Console → Application Signals → Transaction search.

## Architecture

### Project Structure

```
sample-strands-agent-chatbot/
├── chatbot-app/                    # Main application
│   ├── backend/                    # FastAPI backend
│   │   ├── app.py                 # Main FastAPI application
│   │   ├── agent.py               # Strands agent implementation
│   │   ├── config.py              # Configuration management
│   │   ├── unified_tool_manager.py # Tool lifecycle management
│   │   ├── unified_tools_config.json # Tool definitions
│   │   ├── routers/               # API route handlers
│   │   │   ├── chat.py           # SSE streaming chat endpoint
│   │   │   ├── tools.py          # Tool management endpoints
│   │   │   ├── mcp.py            # MCP server management
│   │   │   └── model.py          # Model configuration
│   │   ├── custom_tools/          # Custom tool implementations
│   │   ├── middleware/            # Security and validation
│   │   ├── mcp_session_manager.py # MCP connection pooling
│   │   └── services/              # Business logic services
│   └── frontend/                   # Next.js frontend
│       └── src/
│           ├── app/               # Next.js 15 app router
│           ├── components/        # React components
│           │   ├── chat/         # Chat interface components
│           │   └── ui/           # shadcn/ui components
│           ├── hooks/            # Custom React hooks
│           └── types/            # TypeScript type definitions
└── agent-blueprint/               # Infrastructure & MCP servers
    ├── chatbot-deployment/        # AWS CDK for main app
    ├── serverless-mcp-farm/       # Lambda-based MCP servers
    │   ├── aws-documentation/
    │   ├── aws-pricing/
    │   ├── bedrock-kb-retrieval/
    │   ├── tavily-web-search/
    │   ├── financial-market/
    │   └── recruiter-insights/
    └── fargate-mcp-farm/          # ECS-based stateful MCP servers
        ├── nova-act-mcp/          # Browser automation
        └── python-mcp/            # Python sandbox
```

### Core Architecture Concepts

**Session Management:**
- Each chat conversation has a unique session ID
- Sessions are isolated with separate agent instances
- MCP connections are pooled and reused across sessions
- Sessions reset on page refresh

**Tool System:**
The platform uses a unified tool configuration system (`unified_tools_config.json`) with four tool types:

1. **Built-in Tools (strands_tools)**: Core framework tools (calculator, HTTP request, image generator/reader)
2. **Custom Tools (custom_tools)**: Business-specific Python functions (diagram creator, weather, visualisation, code interpreter)
3. **MCP Servers (mcp)**: External services via Model Context Protocol (AWS docs, pricing, web search, browser automation, etc.)
4. **Agents (agent)**: Sub-agents for complex workflows (spending analysis, financial narrative)

Tools are dynamically loaded based on the `enabled` flag and their `tool_type`.

**MCP Connection Management:**
- MCP servers use either serverless (Lambda via Streamable HTTP) or stateful (ECS containers) transport
- Connection pooling prevents reconnection overhead
- URLs support AWS Parameter Store references (`ssm:///parameter/name`)
- SigV4 authentication for AWS-hosted MCP servers
- Health checks monitor MCP server connectivity in real-time

**Real-time Streaming:**
- Backend uses SSE (Server-Sent Events) to stream AI responses
- Frontend uses EventSource API to consume SSE streams
- Tool execution events are streamed as they occur
- Progress updates show tool status (pending → in_progress → completed)

**Environment Configuration:**
- Master `.env` file at `agent-blueprint/.env`
- Variables are loaded by `start.sh` and propagated to backend/frontend
- AWS Parameter Store integration for secrets in production
- CORS origins configured via `CORS_ORIGINS` environment variable

## Important Development Guidelines

### Adding New Tools

**Custom Tools:**
1. Create a new Python file in `chatbot-app/backend/custom_tools/`
2. Implement a function decorated with Strands' `@tool` decorator
3. Add configuration to `unified_tools_config.json`:
   ```json
   {
     "id": "my_tool",
     "type": "custom_tools",
     "name": "My Tool",
     "description": "What it does",
     "module_path": "custom_tools.my_tool",
     "function_name": "my_tool",
     "category": "utilities",
     "icon": "wrench",
     "enabled": true,
     "tool_type": "custom"
   }
   ```

**MCP Servers:**
- See `docs/guides/Add_New_Serverless_MCP.md` for detailed guide
- Serverless: Deploy to Lambda using provided deployment scripts
- Stateful: Deploy to ECS using CDK in `fargate-mcp-farm/`
- Add configuration to `unified_tools_config.json` with `type: "mcp"`

### Working with the Backend

**Key Files:**
- `app.py` - FastAPI application setup, CORS, middleware
- `agent.py` - Strands agent initialization and streaming logic
- `unified_tool_manager.py` - Loads and manages all tool types
- `routers/chat.py` - Main streaming chat endpoint (`/api/chat`)
- `mcp_session_manager.py` - MCP connection pooling and lifecycle

**Session Isolation:**
- Session IDs are generated client-side and passed in requests
- Each session has its own agent instance stored in `session_managers`
- MCP connections are reused but state is isolated per session

**Adding New API Endpoints:**
1. Create a new router in `backend/routers/`
2. Import and include in `app.py`
3. Use async functions for I/O operations
4. Return proper FastAPI response types

### Working with the Frontend

**Key Technologies:**
- Next.js 15 with App Router (not Pages Router)
- React Server Components and Client Components
- TypeScript for type safety
- shadcn/ui for UI components
- Tailwind CSS for styling

**Key Files:**
- `src/app/page.tsx` - Main chat page
- `src/components/chat/` - Chat interface components
- `src/hooks/` - Custom React hooks for SSE, tools, etc.
- `src/types/` - TypeScript interfaces

**Adding New Features:**
1. Create components in `src/components/`
2. Use `'use client'` directive for client-side interactivity
3. API calls go through `/api` routes to backend
4. Use TypeScript interfaces from `src/types/`

### Testing MCP Servers

MCP servers require cloud infrastructure for proper testing. Deploy them to AWS first:

```bash
# For serverless MCP
cd agent-blueprint/serverless-mcp-farm/<server-name>
./deploy.sh

# For stateful MCP
cd agent-blueprint/fargate-mcp-farm/<server-name>
./deploy.sh
```

Then enable in `unified_tools_config.json` and test via the web UI.

### Security Considerations

**Local Development:**
- CORS origins configured for localhost
- No authentication required
- AWS credentials from local profile

**Cloud Deployment:**
- Cognito authentication required (`ENABLE_COGNITO=true`)
- CloudFront CDN fronts all traffic
- ALB only accepts CloudFront traffic
- MCP servers in private subnets
- VPC isolation for ECS tasks

## Common Patterns

### Streaming Responses

Backend streaming with SSE:
```python
async def stream_response():
    async for chunk in agent.stream():
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"
```

Frontend consuming SSE:
```typescript
const eventSource = new EventSource(`/api/chat?session_id=${sessionId}`)
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // Handle chunk
}
```

### Tool Configuration Changes

After modifying `unified_tools_config.json`:
1. Restart the backend server
2. Tools are automatically reloaded
3. Frontend fetches updated tool list via `/api/tools`

### AWS Parameter Store URLs

In `unified_tools_config.json`, MCP URLs can reference Parameter Store:
```json
"url": "ssm:///mcp/endpoints/serverless/aws-documentation"
```

Backend resolves these at runtime using boto3.

## Environment Variables

**Key Variables in `agent-blueprint/.env`:**
- `AWS_REGION` - AWS region for services
- `CORS_ORIGINS` - Comma-separated allowed origins
- `ENABLE_COGNITO` - Enable authentication (true/false)
- `TAVILY_API_KEY` - For Tavily web search MCP
- `NOVA_ACT_API_KEY` - For Nova Act browser MCP

See `agent-blueprint/.env.example` for full list.

## Observability

The application includes full AgentCore observability with AWS CloudWatch:
- Session-based trace grouping using `session.id`
- All Bedrock calls, tool executions, and HTTP requests are traced
- CloudWatch GenAI Observability Dashboard available
- Enable Transaction Search in CloudWatch Console for trace viewing

## Additional Resources

- **Deployment Guide**: `DEPLOYMENT.md`
- **Adding MCP Servers**: `docs/guides/Add_New_Serverless_MCP.md`
- **Iframe Embedding**: `docs/guides/EMBEDDING_GUIDE.md`
- **Troubleshooting**: `docs/guides/TROUBLESHOOTING.md`
- **Strands Agents Docs**: https://github.com/aws-samples/strands-agents
