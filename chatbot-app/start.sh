#!/bin/bash

echo "Starting Agent Chatbot Template..."

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ] || [ ! -f "frontend/node_modules/lucide-react/package.json" ]; then
    echo "WARNING: Frontend dependencies not found. Please run setup first:"
    echo "  ./setup.sh"
    exit 1
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        sleep 1
        # Force kill if still running
        kill -9 $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
        sleep 1
        kill -9 $FRONTEND_PID 2>/dev/null || true
    fi
    # Also clean up any remaining processes on ports
    lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
    # Clean up log file
    if [ -f "backend.log" ]; then
        rm backend.log
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "Starting backend server..."

# Clean up any existing backend and frontend processes
echo "Checking for existing processes on ports 8000 and 3000..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Killing process on port 8000..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Killing process on port 3000..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi
# Wait for OS to release ports
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 || lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Waiting for ports to be released..."
    sleep 2
fi
echo "Ports cleared successfully"

# Get absolute path to project root and master .env file
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MASTER_ENV_FILE="$PROJECT_ROOT/agent-blueprint/.env"

cd backend
source venv/bin/activate

# Load environment variables from master .env file
if [ -f "$MASTER_ENV_FILE" ]; then
    echo "Loading environment variables from: $MASTER_ENV_FILE"
    set -a
    source "$MASTER_ENV_FILE"
    set +a
    echo "Environment variables loaded"
    echo "CORS Origins: $CORS_ORIGINS"
    echo "Backend Port: ${PORT:-8000}"
else
    echo "WARNING: Master .env file not found at $MASTER_ENV_FILE, using defaults"
    echo "Setting up local development defaults..."
    export CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
    # Note: PORT is not set here as it should be backend-specific
    # Backend will use its default port (8000) from code
    echo "Local development configuration set"
fi

# Start backend and capture the actual port it's using with environment
# Note: Disable opentelemetry-instrument for local development to avoid connection errors
env $(grep -v '^#' "$MASTER_ENV_FILE" 2>/dev/null | xargs) python app.py > ../backend.log 2>&1 &
#env $(grep -v '^#' "$MASTER_ENV_FILE" 2>/dev/null | xargs) opentelemetry-instrument python app.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start and determine the actual port
sleep 3

# Extract the actual port from the backend log
ACTUAL_PORT=$(grep -o "http://0.0.0.0:[0-9]*" backend.log | grep -o "[0-9]*" | tail -1)
if [ -z "$ACTUAL_PORT" ]; then
    ACTUAL_PORT=8000
fi

echo "Backend is running on port: $ACTUAL_PORT"

# Update environment variable for frontend
export NEXT_PUBLIC_API_URL="http://localhost:$ACTUAL_PORT"

echo "Starting frontend server..."
cd frontend
# Unset PORT to let Next.js use default port 3000
unset PORT
NODE_NO_WARNINGS=1 npx next dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Services started successfully!"
echo ""
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:$ACTUAL_PORT"
echo "API Docs: http://localhost:$ACTUAL_PORT/docs"
echo ""
echo "Embedding Test Pages:"
echo "  - Interactive Examples: http://localhost:3000/embed-example.html"
echo "  - Local Test Page: file://$(pwd)/test-embedding-local.html"
echo "  - Auth Testing: http://localhost:3000/iframe-test.html"
echo ""
echo "Embed URL: http://localhost:3000/embed"
echo "CORS Origins: $CORS_ORIGINS"
echo ""
echo "Frontend is configured to use backend at: http://localhost:$ACTUAL_PORT"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for background processes
wait
