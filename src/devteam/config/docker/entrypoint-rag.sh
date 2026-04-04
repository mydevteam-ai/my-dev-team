#!/bin/sh
set -e

/qdrant/qdrant &
QDRANT_PID=$!

echo "Waiting for Qdrant..."
until curl -sf http://localhost:6333/readyz > /dev/null 2>&1; do
    sleep 1
done
echo "Qdrant is ready."

QDRANT_URL=http://localhost:6333 \
COLLECTION_NAME="${COLLECTION_NAME:-mydevteam}" \
uvx mcp-server-qdrant --transport streamable-http &
MCP_PID=$!

if [ -z "$COLLECTION_NAME" ]; then
    echo "WARNING: COLLECTION_NAME not set, using default 'mydevteam'. Pass -e COLLECTION_NAME=<name> to set it explicitly."
fi

echo "MCP server started (collection: ${COLLECTION_NAME:-mydevteam})."

wait -n $QDRANT_PID $MCP_PID
