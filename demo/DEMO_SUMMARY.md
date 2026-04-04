# Docker Demo Environment - Summary

## ✅ Created Files

### Core Files
- **docker-compose.demo.yml** - Complete multi-service stack
- **setup-demo.sh** - Automated one-click setup script (executable)
- **cleanup-demo.sh** - Easy cleanup script (executable)
- **README.md** - Comprehensive documentation
- **QUICKSTART.md** - Quick reference guide
- **TROUBLESHOOTING.md** - Common issues and solutions
- **.env.demo** - Default environment variables template

### Sample Data
- **sample-data/products.json** - 10 diverse products with full details
- **sample-data/customers.json** - 3 sample customers with addresses
- **sample-data/orders.json** - 5 sample orders (various statuses)

## 🎯 What It Does

The demo environment provides a **complete, fully-functional** test setup:

### Services Included
1. **WordPress (latest)** - http://localhost:8080
2. **MariaDB 10.11** - MySQL database for WordPress
3. **WooCommerce** - Auto-installed e-commerce plugin
4. **Agentic Brain Plugin** - Your WordPress plugin (mounted from source)
5. **FastAPI Backend** - Python API at http://localhost:8000
6. **Neo4j 5.15** - Knowledge graph at http://localhost:7475
7. **Redis 7** - Caching layer
8. **WP-CLI** - Command-line WordPress management

### Auto-Configuration
- ✅ WordPress installed and configured
- ✅ WooCommerce installed and activated
- ✅ Agentic Brain plugin activated and configured
- ✅ 10 sample products created
- ✅ Demo pages with chatbot
- ✅ All services connected and talking to each other

## 🚀 Quick Start

```bash
cd $HOME/brain/agentic-brain/demo
./setup-demo.sh
```

**Wait 2-3 minutes. That's it!**

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Demo Network                      │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  WordPress   │─────▶│   MariaDB    │                    │
│  │  :8080       │      │   Database   │                    │
│  └──────┬───────┘      └──────────────┘                    │
│         │                                                    │
│         │ Plugin                                            │
│         ▼                                                    │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │ Agentic API  │─────▶│   Neo4j      │                    │
│  │  :8000       │      │   :7475      │                    │
│  └──────┬───────┘      └──────────────┘                    │
│         │                                                    │
│         │ Cache                                             │
│         ▼                                                    │
│  ┌──────────────┐                                           │
│  │    Redis     │                                           │
│  │    :6380     │                                           │
│  └──────────────┘                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔑 Default Credentials

### WordPress Admin
- URL: http://localhost:8080/wp-admin
- Username: `admin`
- Password: `Admin123!Demo`

### Neo4j Browser
- URL: http://localhost:7475
- Username: `neo4j`
- Password: `demo_neo4j_2026`

### API
- URL: http://localhost:8000
- Docs: http://localhost:8000/docs
- No authentication in demo mode

## 🧪 Test Scenarios

### 1. Basic Chatbot Test
1. Visit http://localhost:8080
2. See chatbot in bottom-right
3. Ask: "What products do you have?"
4. Get AI-powered response with product list

### 2. Product Search Test
- "Show me electronics under $200"
- "I need a gift for fitness enthusiasts"
- "Do you have coffee?"

### 3. API Test
```bash
# Health check
curl http://localhost:8000/health

# Chat endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me all products", "session_id": "test"}'
```

### 4. Neo4j Test
```cypher
// View products
MATCH (p:Product) RETURN p LIMIT 10;

// View interactions
MATCH (i:Interaction)-[:ABOUT]->(p:Product)
RETURN i, p;
```

## 📁 Directory Structure

```
demo/
├── docker-compose.demo.yml     # Main Docker configuration
├── setup-demo.sh              # Automated setup (EXECUTABLE)
├── cleanup-demo.sh            # Cleanup script (EXECUTABLE)
├── README.md                  # Full documentation
├── QUICKSTART.md              # Quick reference
├── TROUBLESHOOTING.md         # Common issues
├── .env.demo                  # Environment template
└── sample-data/
    ├── products.json          # 10 sample products
    ├── customers.json         # 3 sample customers
    └── orders.json            # 5 sample orders
```

## 🛠️ Common Commands

```bash
# Start demo
./setup-demo.sh

# View logs
docker-compose -f docker-compose.demo.yml logs -f

# Stop (keep data)
docker-compose -f docker-compose.demo.yml stop

# Start again
docker-compose -f docker-compose.demo.yml start

# Restart service
docker-compose -f docker-compose.demo.yml restart demo-api

# Check status
docker-compose -f docker-compose.demo.yml ps

# WP-CLI command
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp --allow-root plugin list

# Clean up everything
./cleanup-demo.sh
```

## 🎯 What Works Out of the Box

- ✅ **WordPress + WooCommerce** - Full e-commerce setup
- ✅ **AI Chatbot Widget** - Appears on all pages
- ✅ **Product Search** - Natural language queries
- ✅ **Knowledge Graph** - Neo4j stores interactions
- ✅ **Caching** - Redis speeds up responses
- ✅ **API Documentation** - Interactive Swagger UI
- ✅ **Sample Data** - 10 products ready to test
- ✅ **Health Checks** - All services monitor themselves
- ✅ **Volume Persistence** - Data survives restarts
- ✅ **Hot Reload** - Plugin changes reflect immediately

## 🔧 Customization

### Change Ports
Create `.env` from `.env.demo`:
```bash
cp .env.demo .env
# Edit and change ports
```

### Add More Products
```bash
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp wc product create \
  --name="New Product" \
  --regular_price=99.99 \
  --user=admin \
  --allow-root
```

### Modify Plugin
- Edit files in `../plugins/wordpress/agentic-brain/`
- Changes appear immediately (volume mounted)
- Refresh browser to see changes

### Extend API
- Edit files in `../src/agentic_brain/`
- Restart API: `docker-compose restart demo-api`

## 📈 Performance

### Resource Usage (Approximate)
- **CPU:** 1-2 cores
- **RAM:** 3-4 GB
- **Disk:** ~2 GB for images + data
- **Startup:** 2-3 minutes first run, 30-60s subsequent

### Optimization Tips
- Allocate 4GB+ RAM to Docker
- Use SSD for Docker storage
- Close unused applications
- Stop services you're not using

## 🐛 Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Port conflict | Change ports in `.env` |
| WordPress slow | Increase Docker RAM to 4GB |
| API 500 errors | Check Neo4j/Redis health |
| Plugin not found | Verify path to plugin directory |
| Services restarting | Check Docker logs, increase resources |
| Complete failure | Run `./cleanup-demo.sh` then `./setup-demo.sh` |

Full troubleshooting guide: See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 🎓 Learning Opportunities

This demo shows:

1. **Docker Compose** - Multi-service orchestration
2. **Service Health Checks** - Automated monitoring
3. **Volume Management** - Data persistence
4. **Network Configuration** - Inter-service communication
5. **WordPress Plugin Development** - Real integration
6. **FastAPI Backend** - Modern Python API
7. **Neo4j Graph Database** - Knowledge representation
8. **Redis Caching** - Performance optimization
9. **WP-CLI Automation** - WordPress management
10. **Production-Ready Patterns** - Scalable architecture

## 🚀 Next Steps

### For Development
1. Customize the plugin UI/UX
2. Add new AI capabilities to the API
3. Extend the knowledge graph schema
4. Create custom product recommendation algorithms

### For Testing
1. Test with real WooCommerce products
2. Load test the API endpoints
3. Test chatbot with various queries
4. Verify Neo4j query performance

### For Production
1. Review security settings
2. Set up proper secrets management
3. Configure SSL/TLS
4. Set up monitoring and logging
5. Use the production `docker-compose.yml`

## 📚 Documentation

- **README.md** - Comprehensive guide with all details
- **QUICKSTART.md** - One-page quick reference
- **TROUBLESHOOTING.md** - Solutions to common problems
- **../DOCKER_SETUP.md** - Production deployment guide

## ✨ Features Demonstrated

### WordPress Plugin
- ✅ Widget injection
- ✅ Settings page
- ✅ API integration
- ✅ React chatbot UI
- ✅ WooCommerce hooks

### FastAPI Backend
- ✅ Chat endpoint
- ✅ Product search
- ✅ Recommendations
- ✅ Session management
- ✅ Neo4j integration
- ✅ Redis caching

### Knowledge Graph
- ✅ Product nodes
- ✅ Category relationships
- ✅ Customer interactions
- ✅ Query patterns
- ✅ Learning from conversations

## 🎉 Success Criteria

Demo is working when:
- ✅ All services show "Up (healthy)"
- ✅ WordPress loads at http://localhost:8080
- ✅ Admin dashboard accessible
- ✅ Chatbot appears on pages
- ✅ Chatbot responds to queries
- ✅ API docs load at /docs
- ✅ Neo4j browser shows data
- ✅ Products visible in store

## 💡 Pro Tips

1. **Fast Iteration**: Plugin files are mounted - edit and refresh!
2. **Use Logs**: `docker-compose logs -f` is your friend
3. **WP-CLI**: Faster than clicking through admin
4. **Neo4j Browser**: Explore the graph to see AI learning
5. **API Docs**: Test endpoints at http://localhost:8000/docs
6. **Health Checks**: Monitor at http://localhost:8000/health

## 🆘 Getting Help

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Run `docker-compose -f docker-compose.demo.yml logs`
3. Check service status: `docker-compose ps`
4. Try complete reset: `./cleanup-demo.sh && ./setup-demo.sh`
5. Open GitHub issue with logs and error details

---

## Summary

This demo environment provides a **complete, production-like setup** for testing the Agentic Brain WooCommerce plugin. It's designed to be:

- **Easy**: One command to set up everything
- **Fast**: 2-3 minute setup time
- **Complete**: All services integrated and working
- **Realistic**: Real WordPress, real WooCommerce, real data
- **Developer-Friendly**: Hot reload, logs, debugging tools
- **Well-Documented**: Multiple guides for different use cases

**Ready to test in under 3 minutes!** 🚀

---

Built with ❤️ for demonstrating Agentic Brain capabilities
