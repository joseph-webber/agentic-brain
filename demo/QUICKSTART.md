# 🚀 Agentic Brain Demo - Quick Start

## One Command Setup

```bash
cd /Users/joe/brain/agentic-brain/demo
./setup-demo.sh
```

**Wait 2-3 minutes for setup to complete.**

## Access the Demo

### Main URLs
- 🛍️ **Store:** http://localhost:8080
- 🔐 **Admin:** http://localhost:8080/wp-admin
- 🤖 **API:** http://localhost:8000
- 📚 **Docs:** http://localhost:8000/docs
- 🧠 **Neo4j:** http://localhost:7475

### Login Credentials
- **WordPress:** `admin` / `Admin123!Demo`
- **Neo4j:** `neo4j` / `demo_neo4j_2026`

## Quick Tests

### 1. Test the Chatbot
1. Go to http://localhost:8080
2. Look bottom-right for chatbot widget
3. Ask: *"What products do you have?"*

### 2. Check API
```bash
curl http://localhost:8000/health
```

### 3. Browse Products
```bash
curl http://localhost:8000/api/v1/products
```

## Useful Commands

```bash
# View logs
docker-compose -f docker-compose.demo.yml logs -f

# Restart a service
docker-compose -f docker-compose.demo.yml restart demo-api

# Stop demo
docker-compose -f docker-compose.demo.yml stop

# Clean up everything
./cleanup-demo.sh
```

## Troubleshooting

### Port Conflicts
Edit `.env` and change ports:
```bash
DEMO_WP_PORT=8081
DEMO_API_PORT=8001
```

### Services Not Starting
```bash
# Check status
docker-compose -f docker-compose.demo.yml ps

# View specific service logs
docker-compose -f docker-compose.demo.yml logs demo-api
```

### Complete Reset
```bash
./cleanup-demo.sh
./setup-demo.sh
```

## What's Included

- ✅ WordPress 6.x with WooCommerce
- ✅ 10 sample products
- ✅ Agentic Brain AI plugin
- ✅ FastAPI backend
- ✅ Neo4j knowledge graph
- ✅ Redis caching
- ✅ Working chatbot widget

## Next Steps

1. **Customize Plugin:** Edit `plugins/wordpress/agentic-brain/`
2. **Add Products:** Use WP Admin or WP-CLI
3. **Extend API:** Modify `src/agentic_brain/`
4. **Explore Neo4j:** Run Cypher queries at http://localhost:7475

For full documentation, see [README.md](README.md)

---

**Need help?** Check logs with `docker-compose -f docker-compose.demo.yml logs -f`
