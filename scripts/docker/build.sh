#!/usr/bin/env bash
# ============================================================================
# Docker Build Script - Build production image
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="${IMAGE_NAME:-agentic-brain}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Agentic Brain - Docker Build      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo

cd "$PROJECT_ROOT"

# Parse arguments
BUILD_ARGS=()
PUSH=false
NO_CACHE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --push)
      PUSH=true
      shift
      ;;
    --no-cache)
      NO_CACHE=true
      BUILD_ARGS+=(--no-cache)
      shift
      ;;
    --tag)
      IMAGE_TAG="$2"
      FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"
      shift 2
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

echo -e "${GREEN}Building:${NC} ${FULL_IMAGE}"
echo

# Build the image
echo -e "${BLUE}→ Building Docker image...${NC}"
docker build \
  "${BUILD_ARGS[@]}" \
  -t "${FULL_IMAGE}" \
  -t "${IMAGE_NAME}:latest" \
  -f Dockerfile \
  . || {
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
  }

echo -e "${GREEN}✓ Build complete${NC}"
echo

# Show image info
echo -e "${BLUE}→ Image details:${NC}"
docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo

# Push if requested
if [ "$PUSH" = true ]; then
  echo -e "${BLUE}→ Pushing to registry...${NC}"
  docker push "${FULL_IMAGE}"
  echo -e "${GREEN}✓ Push complete${NC}"
fi

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Build Complete!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo
echo -e "${YELLOW}Run with:${NC} docker run -p 8000:8000 ${FULL_IMAGE}"
echo -e "${YELLOW}Or use:${NC} docker-compose up"
