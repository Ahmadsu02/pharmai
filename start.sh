#!/bin/bash

# Start MCP server in background
echo "Starting MCP server..."
cd israel-drugs-mcp-server && node dist/server.js --http &
cd ..

# Wait for MCP to be ready
sleep 3
echo "MCP server started"

# Start FastAPI
exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
