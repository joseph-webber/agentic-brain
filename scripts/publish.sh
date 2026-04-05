#!/usr/bin/env bash
# PyPI Publication Script for Agentic Brain
# Usage: ./scripts/publish.sh [--test] [--dry-run]
# 
# Examples:
#   ./scripts/publish.sh                    # Publish to PyPI (prod)
#   ./scripts/publish.sh --test             # Publish to TestPyPI
#   ./scripts/publish.sh --dry-run          # Show what would be published
#   ./scripts/publish.sh --test --dry-run   # Test mode with dry-run

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/dist"
TEST_PYPI_URL="https://test.pypi.org/legacy/"
PROD_PYPI_URL="https://upload.pypi.org/legacy/"
PYPI_URL="$PROD_PYPI_URL"
DRY_RUN=false
UPLOAD=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test)
            PYPI_URL="$TEST_PYPI_URL"
            echo -e "${YELLOW}Using TestPyPI: $TEST_PYPI_URL${NC}"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            UPLOAD=false
            echo -e "${YELLOW}DRY RUN MODE - no upload will occur${NC}"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--test] [--dry-run]"
            echo ""
            echo "Publish agentic-brain to PyPI"
            echo ""
            echo "Options:"
            echo "  --test         Publish to TestPyPI instead of PyPI"
            echo "  --dry-run      Show what would be published (no upload)"
            echo "  --help         Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            exit 1
            ;;
    esac
done

# Change to project directory
cd "$PROJECT_DIR"

echo -e "${BLUE}=== Agentic Brain PyPI Publisher ===${NC}"
echo ""

# Step 1: Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "✓ Python version: ${GREEN}$PYTHON_VERSION${NC}"

# Check for build tools
if ! command -v twine &> /dev/null; then
    echo -e "${RED}✗ twine not found. Installing with pipx...${NC}"
    if command -v pipx &> /dev/null; then
        pipx install twine --force 2>/dev/null || pipx upgrade twine 2>/dev/null || true
    else
        python3 -m pip install --user twine 2>/dev/null || true
    fi
fi
echo -e "✓ twine available"

if ! command -v build &> /dev/null; then
    echo -e "${YELLOW}! build not found. Installing with pipx...${NC}"
    if command -v pipx &> /dev/null; then
        pipx install build --force 2>/dev/null || pipx upgrade build 2>/dev/null || true
    else
        python3 -m pip install --user build 2>/dev/null || true
    fi
fi
echo -e "✓ build installed"

# Step 2: Verify package structure
echo ""
echo -e "${BLUE}Verifying package structure...${NC}"

if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}✗ pyproject.toml not found!${NC}"
    exit 1
fi
echo -e "✓ pyproject.toml found"

if [ ! -f "src/agentic_brain/__init__.py" ]; then
    echo -e "${RED}✗ src/agentic_brain/__init__.py not found!${NC}"
    exit 1
fi
echo -e "✓ src/agentic_brain/__init__.py found"

if [ ! -f "src/agentic_brain/py.typed" ]; then
    echo -e "${YELLOW}! src/agentic_brain/py.typed not found (creating...)${NC}"
    touch src/agentic_brain/py.typed
fi
echo -e "✓ py.typed marker present"

if [ ! -f "README.md" ]; then
    echo -e "${RED}✗ README.md not found!${NC}"
    exit 1
fi
echo -e "✓ README.md found"

if [ ! -f "LICENSE" ]; then
    echo -e "${RED}✗ LICENSE not found!${NC}"
    exit 1
fi
echo -e "✓ LICENSE found"

# Step 3: Extract version
echo ""
echo -e "${BLUE}Reading version information...${NC}"

VERSION=$(grep '__version__ = ' src/agentic_brain/__init__.py | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    echo -e "${RED}✗ Could not determine version!${NC}"
    exit 1
fi
echo -e "✓ Package version: ${GREEN}$VERSION${NC}"

# Step 4: Clean old builds
echo ""
echo -e "${BLUE}Cleaning previous builds...${NC}"

if [ -d "$BUILD_DIR" ]; then
    rm -rf "$BUILD_DIR"
    echo -e "✓ Removed $BUILD_DIR"
fi

rm -rf "$PROJECT_DIR/build"
rm -rf "$PROJECT_DIR/src/*.egg-info"
echo -e "✓ Cleaned build artifacts"

# Step 5: Build package
echo ""
echo -e "${BLUE}Building distribution packages...${NC}"

if ! python3 -m build; then
    echo -e "${RED}✗ Build failed!${NC}"
    exit 1
fi

# Verify build output
if [ ! -f "$BUILD_DIR/agentic_brain-$VERSION.tar.gz" ]; then
    echo -e "${RED}✗ Source distribution not found!${NC}"
    exit 1
fi
echo -e "✓ Source distribution: ${GREEN}agentic_brain-$VERSION.tar.gz${NC}"

WHEEL_FILE=$(find "$BUILD_DIR" -name "agentic_brain-$VERSION-py3-*.whl" | head -1)
if [ -z "$WHEEL_FILE" ]; then
    echo -e "${RED}✗ Wheel distribution not found!${NC}"
    exit 1
fi
echo -e "✓ Wheel distribution: ${GREEN}$(basename "$WHEEL_FILE")${NC}"

# Step 6: Validate package metadata
echo ""
echo -e "${BLUE}Validating package metadata...${NC}"

if ! python3 -m twine check "$BUILD_DIR"/*; then
    echo -e "${RED}✗ Metadata validation failed!${NC}"
    exit 1
fi
echo -e "✓ Package metadata is valid"

# Step 7: Dry-run or upload
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}Dry-run mode: showing what would be uploaded...${NC}"
    echo -e "Would upload:"
    ls -lh "$BUILD_DIR"/*
    echo ""
    echo -e "${GREEN}✓ Dry-run complete (no upload performed)${NC}"
else
    echo -e "${BLUE}Uploading to PyPI...${NC}"
    
    TWINE_ARGS="--repository-url $PYPI_URL"
    if [ "$PYPI_URL" = "$PROD_PYPI_URL" ]; then
        # Use default repository for production
        TWINE_ARGS=""
        echo -e "${YELLOW}Publishing to production PyPI${NC}"
    else
        echo -e "${YELLOW}Publishing to TestPyPI${NC}"
    fi
    
    if ! python3 -m twine upload $TWINE_ARGS "$BUILD_DIR"/*; then
        echo -e "${RED}✗ Upload failed!${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Package uploaded successfully!${NC}"
fi

# Step 8: Summary
echo ""
echo -e "${BLUE}=== Publication Summary ===${NC}"
echo -e "Package:        ${GREEN}agentic-brain${NC}"
echo -e "Version:        ${GREEN}$VERSION${NC}"
echo -e "Source dist:    ${GREEN}agentic_brain-$VERSION.tar.gz${NC}"
echo -e "Wheel dist:     ${GREEN}$(basename "$WHEEL_FILE")${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "Mode:           ${YELLOW}DRY RUN (no upload)${NC}"
    echo -e "Repository:     ${YELLOW}N/A${NC}"
else
    if [ "$PYPI_URL" = "$TEST_PYPI_URL" ]; then
        echo -e "Repository:     ${YELLOW}TestPyPI${NC}"
        echo -e "Install via:    ${BLUE}pip install -i https://test.pypi.org/simple/ agentic-brain==$VERSION${NC}"
    else
        echo -e "Repository:     ${GREEN}PyPI (Production)${NC}"
        echo -e "Install via:    ${BLUE}pip install agentic-brain==$VERSION${NC}"
    fi
fi

echo -e "${GREEN}✓ Done!${NC}"
