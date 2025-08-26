ARG PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ------------------------------
# Base
# ------------------------------
# Base stage: Contains only the minimal dependencies required for runtime
FROM --platform=linux/arm64 node:22-bookworm-slim AS base

ARG PLAYWRIGHT_BROWSERS_PATH
ENV PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH}

# Set the working directory
WORKDIR /app

# Install curl for health checks and git for cloning
RUN apt-get update && apt-get install -y curl git && rm -rf /var/lib/apt/lists/*

# Clone the playwright-mcp repository
ARG REPO_URL=https://github.com/microsoft/playwright-mcp.git
ARG REPO_TAG=v0.0.33

RUN git clone --depth 1 --branch ${REPO_TAG} ${REPO_URL} /tmp/repo && \
    cp -r /tmp/repo/* /app/ && \
    rm -rf /tmp/repo

# Install dependencies
RUN npm ci --omit=dev && \
    # Install system dependencies for playwright
    npx -y playwright-core install-deps chromium

# ------------------------------
# Builder
# ------------------------------
FROM base AS builder

# Install all dependencies (including dev dependencies)
RUN npm ci

# Build the app
RUN npm run build

# ------------------------------
# Browser
# ------------------------------
# Cache optimization:
# - Browser is downloaded only when node_modules or Playwright system dependencies change
# - Cache is reused when only source code changes
FROM base AS browser

RUN npx -y playwright-core install --no-shell chromium

# ------------------------------
# Runtime
# ------------------------------
FROM base

ARG PLAYWRIGHT_BROWSERS_PATH
ARG USERNAME=node
ENV NODE_ENV=production
ENV PORT=8931

# Set the correct ownership for the runtime user on production `node_modules`
RUN chown -R ${USERNAME}:${USERNAME} node_modules

USER ${USERNAME}

COPY --from=browser --chown=${USERNAME}:${USERNAME} ${PLAYWRIGHT_BROWSERS_PATH} ${PLAYWRIGHT_BROWSERS_PATH}
COPY --from=builder --chown=${USERNAME}:${USERNAME} /app/lib /app/lib

# Copy config file (this will be provided by the deployment)
COPY --chown=${USERNAME}:${USERNAME} config.json ./

# Expose port
EXPOSE 8931

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8931/health || exit 1

# Run in headless and only with chromium (other browsers need more dependencies not included in this image)
ENTRYPOINT ["node", "cli.js", "--headless", "--browser", "chromium", "--no-sandbox", "--host", "0.0.0.0", "--port", "8931"]
