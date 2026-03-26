#!/bin/bash
# Start agentic-brain connected to Joseph's REAL Neo4j (60k+ nodes)

echo "🧠 Starting Joseph's Brain..."

# Use Joseph's existing Neo4j (already running with his data)
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="Brain2026"

# Redis (local brew)
if ! pgrep -x redis-server > /dev/null; then
    echo "Starting Redis..."
    brew services start redis 2>/dev/null || redis-server --daemonize yes
fi

# Start the app
cd ~/brain/agentic-brain
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -e . --quiet

echo "🚀 Starting API server at http://localhost:8000"
python -m uvicorn src.agentic_brain.api.main:app --host 0.0.0.0 --port 8000 --reload
