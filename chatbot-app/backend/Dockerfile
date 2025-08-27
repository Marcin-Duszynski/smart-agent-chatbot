FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads output generated_images

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set default environment variables for OTEL (can be overridden by container environment)
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=http/protobuf
ENV OTEL_LOGS_EXPORTER=otlp
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=agents/strands-agent-logs,x-aws-metric-namespace=agentsd
ENV OTEL_RESOURCE_ATTRIBUTES=service.name=strands-chatbot
ENV AGENT_OBSERVABILITY_ENABLED=true
ENV AWS_REGION=us-west-2

# OTEL batch processing settings for real-time traces
ENV OTEL_BSP_SCHEDULE_DELAY=100
ENV OTEL_BSP_MAX_EXPORT_BATCH_SIZE=1
ENV OTEL_BSP_EXPORT_TIMEOUT=5000

# Run the application with OpenTelemetry instrumentation
CMD ["sh", "-c", "echo 'Starting with OTEL instrumentation...' && opentelemetry-instrument --version && opentelemetry-instrument python app.py"]
