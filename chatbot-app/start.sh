#!/bin/bash

echo "🚀 Starting Agent Chatbot Template..."

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ] || [ ! -f "frontend/node_modules/lucide-react/package.json" ]; then
    echo "⚠️  Frontend dependencies not found. Please run setup first:"
    echo "  ./setup.sh"
    exit 1
fi

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null
    fi
    # Clean up log file
    if [ -f "backend.log" ]; then
        rm backend.log
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "🔧 Starting backend server..."
cd backend
source venv/bin/activate

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "📋 Loading environment variables from .env"
    set -a
    source .env
    set +a
    echo "✅ Environment variables loaded: OTEL_PYTHON_DISTRO=$OTEL_PYTHON_DISTRO"
fi

# Start backend and capture the actual port it's using with environment
env $(grep -v '^#' .env 2>/dev/null | xargs) opentelemetry-instrument python app.py > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# Wait for backend to start and determine the actual port
sleep 3

# Extract the actual port from the backend log
ACTUAL_PORT=$(grep -o "http://0.0.0.0:[0-9]*" backend.log | grep -o "[0-9]*" | tail -1)
if [ -z "$ACTUAL_PORT" ]; then
    ACTUAL_PORT=8000
fi

echo "📋 Backend is running on port: $ACTUAL_PORT"

# Update environment variable for frontend
export NEXT_PUBLIC_API_URL="http://localhost:$ACTUAL_PORT"

echo "🎨 Starting frontend server..."
cd frontend
NODE_NO_WARNINGS=1 npx next dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Services started successfully!"
echo ""
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:$ACTUAL_PORT"
echo "📚 API Docs: http://localhost:$ACTUAL_PORT/docs"
echo ""
echo "ℹ️  Frontend is configured to use backend at: http://localhost:$ACTUAL_PORT"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for background processes
wait
