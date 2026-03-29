# Agentic Brain WooCommerce Plugin - Demo Environment

Complete Docker-based demo environment for testing the Agentic Brain WooCommerce plugin locally.

## 🚀 Quick Start

### Prerequisites

- **Docker Desktop** installed and running
  - macOS: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Minimum 4GB RAM allocated to Docker
  - 10GB free disk space

### One-Command Setup

```bash
cd demo
./setup-demo.sh
```

That's it! The script will:
1. ✅ Start all required services (WordPress, MariaDB, Neo4j, Redis, API)
2. ✅ Install and configure WordPress + WooCommerce
3. ✅ Activate the Agentic Brain plugin
4. ✅ Create 10 sample products
5. ✅ Configure the AI chatbot
6. ✅ Print access URLs and credentials

**Setup time:** ~2-3 minutes (first run may take longer for image downloads)

## 🌐 Access URLs

Once setup completes, you can access:

| Service | URL | Description |
|---------|-----|-------------|
| **WordPress Store** | http://localhost:8080 | Main storefront with chatbot |
| **WordPress Admin** | http://localhost:8080/wp-admin | Admin dashboard |
| **Agentic Brain API** | http://localhost:8000 | FastAPI backend |
| **API Documentation** | http://localhost:8000/docs | Interactive API docs |
| **Neo4j Browser** | http://localhost:7475 | Knowledge graph database |

## 🔑 Default Credentials

### WordPress Admin
- **Username:** `admin`
- **Password:** `Admin123!Demo`

### Neo4j Browser
- **Username:** `neo4j`
- **Password:** `demo_neo4j_2026`

### API Access
- No authentication required in demo mode
- All endpoints available at http://localhost:8000

## 🧪 Test Scenarios

### 1. Test the AI Chatbot Widget

1. Visit http://localhost:8080
2. Look for the chatbot widget in the bottom right corner
3. Try these example queries:
   - "What products do you have?"
   - "Show me electronics under $200"
   - "I need a gift for someone who likes fitness"
   - "What's your best-selling product?"
   - "Do you have any coffee?"

### 2. Test Product Search

The chatbot can search products by:
- **Category:** "Show me all electronics"
- **Price range:** "Products under $50"
- **Keywords:** "wireless headphones"
- **Features:** "organic coffee"

### 3. Test Order Assistance

- "How do I track my order?"
- "What's your return policy?"
- "Do you offer free shipping?"

### 4. Test the Admin Interface

1. Go to http://localhost:8080/wp-admin
2. Login with admin credentials
3. Navigate to **Agentic Brain** in the sidebar
4. Configure chatbot settings:
   - Enable/disable chatbot
   - Customize welcome message
   - Set API endpoint
   - Configure appearance

### 5. Test the API Directly

```bash
# Health check
curl http://localhost:8000/health

# Search products
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me all products", "session_id": "test123"}'

# Get product recommendations
curl http://localhost:8000/api/v1/products/recommendations?limit=5
```

### 6. Explore the Knowledge Graph

1. Open http://localhost:7475
2. Login with Neo4j credentials
3. Run these Cypher queries:

```cypher
// View all products
MATCH (p:Product) RETURN p LIMIT 10;

// View product categories
MATCH (c:Category)<-[:IN_CATEGORY]-(p:Product)
RETURN c.name, count(p) as product_count;

// View chat interactions
MATCH (i:Interaction)-[:ABOUT]->(p:Product)
RETURN i, p LIMIT 20;
```

## 📊 Sample Data

The demo includes:

- **10 Sample Products** across different categories:
  - Electronics (Headphones, Mouse, Fitness Tracker)
  - Fitness (Yoga Mat, Running Shoes, Protein Powder)
  - Food & Beverage (Organic Coffee)
  - Accessories (Water Bottle, Backpack)
  - Home Office (Desk Lamp)

- **Product Categories:**
  - Electronics
  - Fitness
  - Food & Beverage
  - Accessories
  - Home Office
  - Supplements
  - Footwear

## 🛠️ Management Commands

### View Logs

```bash
# All services
docker-compose -f docker-compose.demo.yml logs -f

# Specific service
docker-compose -f docker-compose.demo.yml logs -f demo-api
docker-compose -f docker-compose.demo.yml logs -f demo-wordpress
```

### Service Management

```bash
# Stop all services (keeps data)
docker-compose -f docker-compose.demo.yml stop

# Start services again
docker-compose -f docker-compose.demo.yml start

# Restart a specific service
docker-compose -f docker-compose.demo.yml restart demo-api

# View service status
docker-compose -f docker-compose.demo.yml ps
```

### WordPress Management via WP-CLI

```bash
# Run WP-CLI commands
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp --allow-root

# Examples:
# List plugins
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp plugin list --allow-root

# List products
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp wc product list --user=admin --allow-root

# Create a new product
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp wc product create \
  --name="New Product" \
  --regular_price=99.99 \
  --user=admin \
  --allow-root
```

### Database Access

```bash
# Access MariaDB
docker-compose -f docker-compose.demo.yml exec demo-db mysql -u wp_demo -pdemo_wp_pass_2026 wordpress_demo

# Backup WordPress database
docker-compose -f docker-compose.demo.yml exec demo-db mysqldump \
  -u wp_demo -pdemo_wp_pass_2026 wordpress_demo > backup.sql
```

### Redis Access

```bash
# Access Redis CLI
docker-compose -f docker-compose.demo.yml exec demo-redis redis-cli -a demo_redis_2026

# Monitor cache activity
docker-compose -f docker-compose.demo.yml exec demo-redis redis-cli -a demo_redis_2026 MONITOR
```

## 🧹 Cleanup

### Reset Demo Environment

To completely reset the demo (removes all data):

```bash
cd demo
docker-compose -f docker-compose.demo.yml down -v
```

This will:
- Stop all containers
- Remove all volumes (database, uploads, etc.)
- Reset to clean state

Then run `./setup-demo.sh` again for a fresh install.

### Partial Cleanup

```bash
# Remove only containers (keep volumes/data)
docker-compose -f docker-compose.demo.yml down

# Remove unused images
docker image prune -f
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the `demo/` directory to customize:

```bash
# WordPress
DEMO_WP_PORT=8080
DEMO_ADMIN_USER=admin
DEMO_ADMIN_PASSWORD=Admin123!Demo
DEMO_ADMIN_EMAIL=admin@agenticbrain.demo

# Database
DEMO_DB_NAME=wordpress_demo
DEMO_DB_USER=wp_demo
DEMO_DB_PASSWORD=demo_wp_pass_2026
DEMO_DB_ROOT_PASSWORD=demo_root_pass_2026

# Neo4j
DEMO_NEO4J_PASSWORD=demo_neo4j_2026
DEMO_NEO4J_HTTP_PORT=7475
DEMO_NEO4J_BOLT_PORT=7688

# Redis
DEMO_REDIS_PASSWORD=demo_redis_2026
DEMO_REDIS_PORT=6380

# API
DEMO_API_PORT=8000
```

### Port Conflicts

If ports are already in use, change them in `.env`:

```bash
# If 8080 is taken, use 8081
DEMO_WP_PORT=8081

# If 8000 is taken, use 8001
DEMO_API_PORT=8001
```

Then restart:
```bash
docker-compose -f docker-compose.demo.yml down
./setup-demo.sh
```

## 🐛 Troubleshooting

### Docker Not Running
```
Error: Cannot connect to the Docker daemon
```
**Solution:** Start Docker Desktop

### Port Already in Use
```
Error: port is already allocated
```
**Solution:** Change ports in `.env` file or stop conflicting service

### WordPress Installation Fails
```
Error: WordPress is already installed
```
**Solution:** This is usually fine. The script will continue.

### Plugin Not Activating
```
Error: Plugin 'agentic-brain' not found
```
**Solution:** Check that plugin files exist at `../plugins/wordpress/agentic-brain/`

### API Not Starting
```
Error: demo-api is unhealthy
```
**Solution:** Check logs: `docker-compose -f docker-compose.demo.yml logs demo-api`

### Services Not Healthy

Check service status:
```bash
docker-compose -f docker-compose.demo.yml ps
```

Restart unhealthy service:
```bash
docker-compose -f docker-compose.demo.yml restart demo-api
```

### Reset Everything

If things are broken, start fresh:
```bash
docker-compose -f docker-compose.demo.yml down -v
docker system prune -f
./setup-demo.sh
```

## 📁 Directory Structure

```
demo/
├── docker-compose.demo.yml    # Main Docker Compose configuration
├── setup-demo.sh              # Automated setup script
├── README.md                  # This file
└── sample-data/               # Sample data files
    ├── products.json          # 10 sample products
    ├── customers.json         # 3 sample customers
    └── orders.json            # 5 sample orders
```

## 🔗 Integration Points

The demo environment shows:

1. **WordPress Plugin → FastAPI:**
   - Plugin sends chat messages to API
   - API processes with AI and returns responses

2. **FastAPI → Neo4j:**
   - Stores conversation history
   - Builds knowledge graph
   - Learns from interactions

3. **FastAPI → Redis:**
   - Caches product data
   - Session management
   - Rate limiting

4. **WordPress → WooCommerce:**
   - Product catalog
   - Shopping cart
   - Order management

## 🎯 Demo Objectives

This demo environment demonstrates:

- ✅ **AI-Powered Product Search:** Natural language queries
- ✅ **Conversational Commerce:** Chat-based shopping experience
- ✅ **Knowledge Graph:** Products, categories, customer intent
- ✅ **Real-time Recommendations:** Personalized suggestions
- ✅ **WordPress Integration:** Seamless plugin architecture
- ✅ **Scalable Backend:** FastAPI + Neo4j + Redis

## 📚 Next Steps

After testing the demo:

1. **Customize the Plugin:**
   - Edit `plugins/wordpress/agentic-brain/`
   - Changes reflect immediately (volumes are mounted)

2. **Extend the API:**
   - Modify `src/agentic_brain/`
   - Restart API: `docker-compose -f docker-compose.demo.yml restart demo-api`

3. **Add More Products:**
   - Use WP-CLI or WordPress admin
   - Or import via WooCommerce CSV

4. **Deploy to Production:**
   - See `DOCKER_SETUP.md` for production deployment
   - Use `docker-compose.yml` (not `.demo.yml`)

## 💡 Tips

- **Fast Iteration:** Plugin files are mounted as volumes—edit and refresh!
- **Check Logs:** Use `docker-compose logs -f` to debug issues
- **Use WP-CLI:** Faster than clicking through admin for bulk operations
- **Neo4j Queries:** Explore the knowledge graph to see AI learning
- **API Docs:** Visit `/docs` for interactive API testing

## 🚀 Automated Demo Deployment

The demo environment is **automatically built and deployed** on every release!

### How It Works

When a new version is tagged and released:

1. **Release Workflow** (`release.yml`):
   - ✅ Builds and publishes Docker images to `ghcr.io`
   - ✅ Creates demo package artifact (`agentic-brain-demo-vX.X.X.tar.gz`)
   - ✅ Attaches demo package to GitHub release
   - ✅ Pushes versioned images:
     - `ghcr.io/agentic-brain-project/agentic-brain/demo-api:vX.X.X`
     - `ghcr.io/agentic-brain-project/agentic-brain/demo-api:latest`

2. **Demo Workflow** (`demo.yml`):
   - ✅ Triggers automatically on release publication
   - ✅ Builds complete demo stack
   - ✅ Runs smoke tests
   - ✅ Creates downloadable demo artifact

### Using a Released Demo Package

Download the demo package from any GitHub release:

```bash
# Download latest release demo
curl -LO https://github.com/agentic-brain-project/agentic-brain/releases/latest/download/agentic-brain-demo-vX.X.X.tar.gz

# Extract
tar -xzf agentic-brain-demo-vX.X.X.tar.gz
cd agentic-brain-demo-vX.X.X/demo

# Run setup (uses pre-built images from ghcr.io)
./setup-demo.sh
```

### Manual Demo Trigger

You can also trigger a demo build manually via GitHub Actions:

```bash
# Via GitHub CLI
gh workflow run demo.yml --ref main

# Or via GitHub UI
# Go to Actions → Demo Deployment → Run workflow
```

### Demo Images

The release process publishes these container images:

| Image | Description | Tags |
|-------|-------------|------|
| `ghcr.io/.../demo-api` | FastAPI backend | `vX.X.X`, `latest` |
| `ghcr.io/.../demo-wordpress` | WordPress + plugin | `vX.X.X`, `latest` |

These images are **production-ready** and can be deployed anywhere!

### CI/CD Pipeline

```
Tag Push (v*) → Build → Test → Publish → Release → Demo Deploy
     ↓            ↓       ↓        ↓         ↓          ↓
  v2.12.0    PyPI pkg  Tests  ghcr.io  GitHub    Artifact
                                        Release    + Images
```

## 📞 Support

Issues with the demo?

1. Check logs: `docker-compose -f docker-compose.demo.yml logs`
2. Review troubleshooting section above
3. Open issue on GitHub with logs
4. Join Discord for community support

## 🎉 Success Indicators

Demo is working correctly when:

- ✅ All services show "Up (healthy)" in `docker ps`
- ✅ WordPress loads at http://localhost:8080
- ✅ Chatbot widget appears on store pages
- ✅ Chatbot responds to questions
- ✅ Products appear in search results
- ✅ API docs load at http://localhost:8000/docs
- ✅ Neo4j browser shows data at http://localhost:7475

---

**Built with ❤️ for demonstrating Agentic Brain's capabilities**

*For production deployment, see the main [DOCKER_SETUP.md](../DOCKER_SETUP.md)*
