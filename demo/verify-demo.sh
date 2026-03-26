#!/bin/bash
# Demo Environment Verification Script

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          Agentic Brain Demo - Verification Check              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

ERRORS=0
WARNINGS=0

# Check Docker
echo "▶ Checking Docker..."
if docker info > /dev/null 2>&1; then
    echo "  ✓ Docker is running"
else
    echo "  ✗ Docker is not running"
    ((ERRORS++))
fi

# Check Docker Compose
echo "▶ Checking Docker Compose..."
if docker-compose version > /dev/null 2>&1; then
    echo "  ✓ Docker Compose is installed"
else
    echo "  ✗ Docker Compose is not installed"
    ((ERRORS++))
fi

# Check required files
echo "▶ Checking required files..."
FILES=(
    "docker-compose.demo.yml"
    "setup-demo.sh"
    "cleanup-demo.sh"
    "README.md"
    "QUICKSTART.md"
    "sample-data/products.json"
    "sample-data/customers.json"
    "sample-data/orders.json"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file missing"
        ((ERRORS++))
    fi
done

# Check plugin directory
echo "▶ Checking plugin directory..."
if [ -d "../plugins/wordpress/agentic-brain" ]; then
    echo "  ✓ WordPress plugin directory exists"
    if [ -f "../plugins/wordpress/agentic-brain/agentic-brain.php" ]; then
        echo "  ✓ Plugin main file exists"
    else
        echo "  ✗ Plugin main file missing"
        ((ERRORS++))
    fi
else
    echo "  ✗ Plugin directory not found"
    ((ERRORS++))
fi

# Check executable permissions
echo "▶ Checking permissions..."
if [ -x "setup-demo.sh" ]; then
    echo "  ✓ setup-demo.sh is executable"
else
    echo "  ⚠ setup-demo.sh not executable (will fix)"
    chmod +x setup-demo.sh
    ((WARNINGS++))
fi

if [ -x "cleanup-demo.sh" ]; then
    echo "  ✓ cleanup-demo.sh is executable"
else
    echo "  ⚠ cleanup-demo.sh not executable (will fix)"
    chmod +x cleanup-demo.sh
    ((WARNINGS++))
fi

# Check ports availability
echo "▶ Checking port availability..."
PORTS=(8080 8000 7475 7688 6380)
for port in "${PORTS[@]}"; do
    if lsof -i :$port > /dev/null 2>&1; then
        echo "  ⚠ Port $port is in use"
        ((WARNINGS++))
    else
        echo "  ✓ Port $port is available"
    fi
done

# Summary
echo ""
echo "════════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ All checks passed! Ready to run ./setup-demo.sh"
elif [ $ERRORS -eq 0 ]; then
    echo "⚠️  $WARNINGS warning(s) found, but should work"
    echo "   Consider changing ports in .env if in use"
else
    echo "❌ $ERRORS error(s) found. Please fix before running demo."
fi
echo "════════════════════════════════════════════════════════════════"
echo ""
