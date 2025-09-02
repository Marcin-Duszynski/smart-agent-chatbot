# Nova Act MCP Server Dockerfile for AWS Fargate
FROM --platform=linux/arm64 python:3.13-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV NODE_ENV=development
ENV PORT=8000

# Set working directory
WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Node.js not needed - Nova Act uses Playwright Python

# Playwright will install its own browser - no need for system Chromium

# Copy Nova Act MCP server code (will be provided by build context)
COPY . /app/build-context/

# Upgrade pip
RUN pip install --upgrade pip

# Copy Nova Act MCP server files from build context
RUN mkdir -p /app/server && cp /app/build-context/*.py /app/server/ && cp /app/build-context/requirements.txt /app/server/ && cp /app/build-context/.env /app/server/

# Install Nova Act MCP server dependencies (including nova-act SDK from PyPI)
WORKDIR /app/server
RUN pip install -r requirements.txt

# Install additional required packages
RUN pip install fastmcp uvicorn[standard]

# Let Nova Act use Playwright's browser
ENV NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL=false


# Create non-root user and set permissions efficiently
RUN useradd --create-home --shell /bin/bash nova-act

# Change ownership only of necessary directories
RUN chown -R nova-act:nova-act /app/server

USER nova-act

# Set the working directory to the simplified server location
WORKDIR /app/server

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start script with Xvfb for headless browser support
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & python nova_act_server.py --transport streamable-http --host 0.0.0.0 --port 8000"]