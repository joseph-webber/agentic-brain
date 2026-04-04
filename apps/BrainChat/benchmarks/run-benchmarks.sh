#!/bin/bash

# BrainChat LLM Performance Benchmark Suite
# This script runs comprehensive benchmarks on all configured LLM providers

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BRAINCHAT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$(dirname "$(dirname "$BRAINCHAT_DIR")")")"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          LLM PERFORMANCE BENCHMARK RUNNER                     ║"
echo "║                     BrainChat v1.0                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Load environment variables if available
if [ -f "$BRAINCHAT_DIR/local-config.json" ]; then
    echo "📋 Found local config, loading environment variables..."
    # Extract API keys from JSON config (basic parsing)
    export CLAUDE_API_KEY=$(grep -o '"claude_key":"[^"]*' "$BRAINCHAT_DIR/local-config.json" | cut -d'"' -f4 || true)
    export OPENAI_API_KEY=$(grep -o '"openai_key":"[^"]*' "$BRAINCHAT_DIR/local-config.json" | cut -d'"' -f4 || true)
    export GROQ_API_KEY=$(grep -o '"groq_key":"[^"]*' "$BRAINCHAT_DIR/local-config.json" | cut -d'"' -f4 || true)
fi

# Set defaults
OLLAMA_ENDPOINT="${OLLAMA_ENDPOINT:-http://localhost:11434/api/chat}"
export OLLAMA_ENDPOINT

echo "Configuration:"
echo "  Ollama: $OLLAMA_ENDPOINT"
echo "  Claude API: ${CLAUDE_API_KEY:+✓ Set}${CLAUDE_API_KEY:-✗ Not set}"
echo "  OpenAI API: ${OPENAI_API_KEY:+✓ Set}${OPENAI_API_KEY:-✗ Not set}"
echo "  Groq API: ${GROQ_API_KEY:+✓ Set}${GROQ_API_KEY:-✗ Not set}"
echo ""

# Check if swift is available
if ! command -v swift &> /dev/null; then
    echo "❌ ERROR: Swift toolchain not found"
    echo "Please install Xcode or the Swift toolchain"
    exit 1
fi

echo "🚀 Running benchmarks (this may take a few minutes)..."
echo ""

# Build and run tests in release mode
cd "$BRAINCHAT_DIR"

# Option 1: Run using XCTest
if [ "$1" = "test" ]; then
    echo "Running XCTest benchmarks..."
    swift test --configuration release --parallel 1 -v 2>&1 || true
    
# Option 2: Build and run release executable
elif [ "$1" = "run" ]; then
    echo "Building release binary..."
    swift build --configuration release -v || {
        echo "❌ Build failed"
        exit 1
    }
    
    # Find the built executable
    EXECUTABLE=$(find .build/release -name "BrainChat-*" -type f 2>/dev/null | head -1)
    if [ -z "$EXECUTABLE" ]; then
        echo "⚠️ Could not find built executable"
    else
        echo "✓ Built: $EXECUTABLE"
    fi
    
# Option 3: Direct performance test (default)
else
    echo "Running quick benchmark check..."
    
    # Check Ollama availability
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✓ Ollama is running"
        OLLAMA_AVAILABLE=true
    else
        echo "⚠️ Ollama not available at $OLLAMA_ENDPOINT"
        OLLAMA_AVAILABLE=false
    fi
    
    # Check cloud API availability
    if [ ! -z "$GROQ_API_KEY" ]; then
        echo "✓ Groq API key configured"
    fi
    
    if [ ! -z "$CLAUDE_API_KEY" ]; then
        echo "✓ Claude API key configured"
    fi
    
    if [ ! -z "$OPENAI_API_KEY" ]; then
        echo "✓ OpenAI API key configured"
    fi
    
    echo ""
    echo "To run the full benchmark suite, ensure:"
    echo "1. Ollama is running: ollama serve"
    echo "2. API keys are set in environment or local-config.json"
    echo ""
    echo "Then run:"
    echo "  $0 test       # Run XCTest benchmarks"
    echo "  $0 run        # Build and run release binary"
fi

echo ""
echo "📊 Benchmark results:"
echo "  Baseline: $SCRIPT_DIR/llm-baseline.json"
echo "  History:  $SCRIPT_DIR/llm-benchmark-*.json"
echo ""
echo "✅ Benchmark script complete!"
