# Nova Act MCP Server Dockerfile for AWS Fargate (Ubuntu 22.04 like local)
FROM --platform=linux/arm64 ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies and Python 3.13 (same as local working version)
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    ca-certificates \
    software-properties-common \
    git \
    xvfb \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix

# Install Python 3.13 from source (same as local)
RUN cd /tmp && \
    wget https://www.python.org/ftp/python/3.13.1/Python-3.13.1.tgz && \
    tar xzf Python-3.13.1.tgz && \
    cd Python-3.13.1 && \
    ./configure --enable-optimizations --enable-shared && \
    make -j$(nproc) && \
    make altinstall && \
    ldconfig && \
    cd / && rm -rf /tmp/Python-3.13.1*

# Create python symlinks (same as local)
RUN ln -sf /usr/local/bin/python3.13 /usr/local/bin/python3 && \
    ln -sf /usr/local/bin/python3.13 /usr/local/bin/python && \
    ln -sf /usr/local/bin/pip3.13 /usr/local/bin/pip3 && \
    ln -sf /usr/local/bin/pip3.13 /usr/local/bin/pip

# Upgrade pip first
RUN pip3 install --upgrade pip

# Copy requirements file first for better Docker layer caching
COPY requirements.txt /app/server/

# Install Chromium browser (Ubuntu package name - same as local)
RUN apt-get update && apt-get install -y \
    chromium-browser \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome environment variables (Ubuntu path - same as local)
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Install Nova Act MCP server dependencies (including nova-act SDK from PyPI)
WORKDIR /app/server
RUN pip3 install -r requirements.txt

# Install additional required packages
RUN pip3 install fastmcp uvicorn[standard]

# Install Playwright system dependencies as root first
RUN python -m playwright install-deps chromium

# Copy all Python files from current directory (src)
COPY *.py /app/server/

# Create non-root user and set permissions efficiently
RUN useradd --create-home --shell /bin/bash nova-act

# Change ownership only of necessary directories
RUN chown -R nova-act:nova-act /app/server

# Switch to nova-act user BEFORE installing Playwright browsers
USER nova-act

# Install Playwright browser binaries as nova-act user (no system deps needed)
RUN python -m playwright install chromium

# Tell Nova Act to skip browser installation since we already did it
ENV NOVA_ACT_SKIP_PLAYWRIGHT_INSTALL=true

# Set the working directory to the simplified server location
WORKDIR /app/server

# Expose port
EXPOSE 8000

# Health check using MCP endpoint (406 response means FastMCP server is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/nova-act/mcp || [ $? -eq 22 ]

# Start script with Xvfb for headless browser support (same as local)
CMD ["sh", "-c", "Xvfb :99 -screen 0 1920x1080x24 & python nova_act_server.py --transport streamable-http --host 0.0.0.0 --port 8000"]