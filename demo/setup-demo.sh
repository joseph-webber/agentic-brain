#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Demo configuration
DEMO_ADMIN_USER="${DEMO_ADMIN_USER:-admin}"
DEMO_ADMIN_PASSWORD="${DEMO_ADMIN_PASSWORD:-Admin123!Demo}"
DEMO_ADMIN_EMAIL="${DEMO_ADMIN_EMAIL:-admin@agenticbrain.demo}"
DEMO_SITE_TITLE="${DEMO_SITE_TITLE:-Agentic Brain Demo Store}"
DEMO_SITE_URL="${DEMO_SITE_URL:-http://localhost:8080}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Agentic Brain WooCommerce Demo Setup                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Function to print warnings
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Function to wait for service to be ready
wait_for_service() {
    local service=$1
    local max_attempts=60
    local attempt=1
    
    print_header "Waiting for $service to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f docker-compose.demo.yml ps $service 2>/dev/null | grep -q "Up (healthy)"; then
            print_success "$service is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service failed to start within timeout"
    return 1
}

# Function to execute wp-cli command
wp_cli() {
    docker-compose -f docker-compose.demo.yml exec -T demo-wp-cli wp "$@" --allow-root
}

# Check if Docker is running
print_header "Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
print_success "Docker is running"

# Stop and remove existing containers if they exist
print_header "Cleaning up existing demo containers..."
docker-compose -f docker-compose.demo.yml down -v 2>/dev/null || true
print_success "Cleanup complete"

# Start all services
print_header "Starting demo services..."
docker-compose -f docker-compose.demo.yml up -d

# Wait for services to be ready
wait_for_service "demo-db"
wait_for_service "demo-neo4j"
wait_for_service "demo-redis"
wait_for_service "demo-wordpress"
wait_for_service "demo-api"

# Give WordPress a bit more time to fully initialize
print_header "Waiting for WordPress to fully initialize..."
sleep 10

# Install WordPress core
print_header "Installing WordPress..."
wp_cli core install \
    --url="${DEMO_SITE_URL}" \
    --title="${DEMO_SITE_TITLE}" \
    --admin_user="${DEMO_ADMIN_USER}" \
    --admin_password="${DEMO_ADMIN_PASSWORD}" \
    --admin_email="${DEMO_ADMIN_EMAIL}" \
    --skip-email || print_warning "WordPress may already be installed"
print_success "WordPress installed"

# Update permalink structure for better URLs
print_header "Configuring WordPress..."
wp_cli rewrite structure '/%postname%/' || true
wp_cli rewrite flush || true
print_success "Permalinks configured"

# Install and activate WooCommerce
print_header "Installing WooCommerce..."
wp_cli plugin install woocommerce --activate || print_warning "WooCommerce may already be installed"
print_success "WooCommerce installed and activated"

# Configure WooCommerce basics
print_header "Configuring WooCommerce..."
wp_cli option update woocommerce_store_address "123 Demo Street"
wp_cli option update woocommerce_store_city "Adelaide"
wp_cli option update woocommerce_default_country "AU:SA"
wp_cli option update woocommerce_store_postcode "5000"
wp_cli option update woocommerce_currency "AUD"
wp_cli option update woocommerce_calc_taxes "no"
print_success "WooCommerce configured"

# Activate Agentic Brain plugin
print_header "Activating Agentic Brain plugin..."
wp_cli plugin activate agentic-brain || print_warning "Plugin may already be active"
print_success "Agentic Brain plugin activated"

# Configure Agentic Brain plugin
print_header "Configuring Agentic Brain plugin..."
wp_cli option update agbrain_api_url "http://demo-api:8000"
wp_cli option update agbrain_enabled_on "all"
wp_cli option update agbrain_welcome_message "Hi! I'm the Agentic Brain demo assistant."
print_success "Plugin configured"

# Import sample products
print_header "Creating sample products..."

# Create sample products directly using wp-cli
products=(
    "Wireless Bluetooth Headphones|Premium wireless headphones with noise cancellation|199.99|Electronics"
    "Smart Fitness Tracker|Track your health and fitness goals|149.99|Electronics"
    "Organic Coffee Beans|Premium single-origin organic coffee beans|24.99|Food & Beverage"
    "Yoga Mat Premium|Non-slip eco-friendly yoga mat|79.99|Fitness"
    "Stainless Steel Water Bottle|Insulated 750ml water bottle|34.99|Accessories"
    "Running Shoes Pro|Professional running shoes for athletes|159.99|Footwear"
    "Protein Powder Vanilla|High-quality whey protein powder|49.99|Supplements"
    "Laptop Backpack|Durable backpack with laptop compartment|89.99|Accessories"
    "Wireless Mouse|Ergonomic wireless mouse|39.99|Electronics"
    "Desk Lamp LED|Adjustable LED desk lamp with USB charging|59.99|Home Office"
)

for product in "${products[@]}"; do
    IFS='|' read -r name desc price category <<< "$product"
    
    # Create product
    product_id=$(wp_cli wc product create \
        --name="$name" \
        --type=simple \
        --regular_price="$price" \
        --description="$desc" \
        --status=publish \
        --user=admin \
        --porcelain 2>/dev/null || echo "")
    
    if [ -n "$product_id" ]; then
        # Set stock status
        wp_cli wc product update "$product_id" --stock_status=instock --user=admin 2>/dev/null || true
        echo -n "."
    fi
done
echo ""
print_success "Sample products created"

# Create a sample page with chatbot
print_header "Creating demo pages..."
wp_cli post create \
    --post_type=page \
    --post_title="AI Assistant Demo" \
    --post_content="<h2>Try our AI Shopping Assistant</h2><p>The chatbot widget should appear in the bottom right corner. Ask it questions about our products!</p><p>Example questions:</p><ul><li>What electronics do you have?</li><li>Show me products under $50</li><li>I need a gift for a fitness enthusiast</li><li>What's your most popular product?</li></ul>" \
    --post_status=publish \
    || print_warning "Demo page may already exist"
print_success "Demo pages created"

# Print completion message and access information
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║               Demo Setup Complete! 🎉                          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Access Information:${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  🛍️  WordPress Store:    ${GREEN}http://localhost:8080${NC}"
echo -e "  🔐 Admin Dashboard:     ${GREEN}http://localhost:8080/wp-admin${NC}"
echo -e "  🤖 Agentic Brain API:   ${GREEN}http://localhost:8000${NC}"
echo -e "  📊 API Documentation:   ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  🧠 Neo4j Browser:       ${GREEN}http://localhost:7475${NC}"
echo ""
echo -e "${BLUE}Credentials:${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  WordPress Admin:"
echo -e "    Username: ${YELLOW}${DEMO_ADMIN_USER}${NC}"
echo -e "    Password: ${YELLOW}${DEMO_ADMIN_PASSWORD}${NC}"
echo ""
echo -e "  Neo4j Browser:"
echo -e "    Username: ${YELLOW}neo4j${NC}"
echo -e "    Password: ${YELLOW}demo_neo4j_2026${NC}"
echo ""
echo -e "${BLUE}Test the Chatbot:${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  1. Visit: ${GREEN}http://localhost:8080${NC}"
echo -e "  2. Look for the chatbot widget in the bottom right"
echo -e "  3. Try asking: ${YELLOW}\"What products do you have?\"${NC}"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "  View logs:        ${YELLOW}docker-compose -f docker-compose.demo.yml logs -f${NC}"
echo -e "  Stop demo:        ${YELLOW}docker-compose -f docker-compose.demo.yml stop${NC}"
echo -e "  Restart demo:     ${YELLOW}docker-compose -f docker-compose.demo.yml restart${NC}"
echo -e "  Clean up:         ${YELLOW}docker-compose -f docker-compose.demo.yml down -v${NC}"
echo -e "  WP-CLI:           ${YELLOW}docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp --allow-root${NC}"
echo ""
echo -e "${GREEN}Happy testing! 🚀${NC}"
echo ""
