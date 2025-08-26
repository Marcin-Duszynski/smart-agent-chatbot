# Dockerfile for MCP Run Python Server
# Uses local code for customization capabilities
# Addresses known issues: lockfile version, file paths, top-level await

ARG PYODIDE_CACHE_PATH=/pyodide-cache

# ------------------------------
# Base
# ------------------------------
FROM --platform=linux/arm64 denoland/deno:2.1.4 AS base

ARG PYODIDE_CACHE_PATH
ENV PYODIDE_CACHE_PATH=${PYODIDE_CACHE_PATH}

# Set the working directory
WORKDIR /app

# Switch to root to install system dependencies
USER root

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy local source code and configuration
COPY src ./src
COPY deno.json ./deno.json

# Remove lockfile to prevent version conflicts (if exists)
RUN rm -f deno.lock

# Create cache directory for Pyodide and ensure permissions
RUN mkdir -p ${PYODIDE_CACHE_PATH} && \
    mkdir -p /app/node_modules && \
    chown -R deno:deno /app && \
    chown -R deno:deno ${PYODIDE_CACHE_PATH}

# Set environment variables for production
ENV NODE_ENV=production
ENV PORT=3001

# ------------------------------
# Runtime
# ------------------------------
FROM base

ARG PYODIDE_CACHE_PATH
ARG USERNAME=deno

# Ensure proper permissions for the deno user
RUN chown -R deno:deno /app

# Switch to deno user for security
USER ${USERNAME}

# Expose port
EXPOSE 3001

# Health check - simplified to avoid potential issues
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
  CMD curl -f http://localhost:3001/mcp || exit 1

# Run the MCP server in streamable HTTP mode
# Increased permissions to handle file operations safely
ENTRYPOINT ["deno", "run", \
    "--allow-all", \
    "--node-modules-dir=auto", \
    "src/main.ts", "streamable_http", "--port", "3001"]