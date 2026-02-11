#!/bin/bash

# Start Query Explorer Server
# Usage: ./start-server.sh

set -e

echo "🚀 Starting Query Explorer Server..."

# Kill any existing instances
pkill -9 query-explorer 2>/dev/null || true
sleep 2

# Set environment variables
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=diversiplant
export DB_PASSWORD=""  # Empty for trust auth (pg_hba.conf configured)
export DB_NAME=diversiplant
export DEV_MODE=true

# Check if binary exists
if [ ! -f "./query-explorer" ]; then
    echo "❌ Binary not found. Compiling..."
    go build -o query-explorer .
    echo "✅ Compiled successfully"
fi

# Start server in background
echo "Starting server on http://localhost:8080"
nohup ./query-explorer > server.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
echo "Waiting for server to initialize..."
for i in {1..10}; do
    sleep 1
    if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        echo "Health endpoint: http://localhost:8080/api/health"
        echo "UI: http://localhost:8080/"
        echo ""
        echo "To view logs: tail -f server.log"
        echo "To stop: kill $SERVER_PID"
        exit 0
    fi
    echo -n "."
done

echo ""
echo "⚠️  Server started but not responding yet."
echo "Check logs: tail -f server.log"
echo "Server PID: $SERVER_PID"
