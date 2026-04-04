# 🚀 Start Here - Agentic Brain Demo

## Quick Start (3 Minutes)

```bash
cd $HOME/brain/agentic-brain/demo
./setup-demo.sh
```

Wait for completion, then visit: **http://localhost:8080**

---

## What You'll Get

✅ WordPress + WooCommerce store  
✅ AI chatbot widget (bottom-right)  
✅ 10 sample products  
✅ FastAPI backend  
✅ Neo4j knowledge graph  
✅ Redis caching  
✅ Full admin access  

---

## Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **WordPress Store** | http://localhost:8080 | - |
| **Admin Dashboard** | http://localhost:8080/wp-admin | admin / Admin123!Demo |
| **API Backend** | http://localhost:8000 | - |
| **API Docs** | http://localhost:8000/docs | - |
| **Neo4j Browser** | http://localhost:7475 | neo4j / demo_neo4j_2026 |

---

## Test the Chatbot

1. Go to http://localhost:8080
2. See chatbot in bottom-right corner
3. Ask: **"What products do you have?"**
4. Get AI-powered response!

---

## Documentation

- **New to this?** → [QUICKSTART.md](QUICKSTART.md)
- **Want details?** → [README.md](README.md)
- **Having issues?** → [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Need overview?** → [DEMO_SUMMARY.md](DEMO_SUMMARY.md)

---

## Common Commands

```bash
# Check everything is ready
./verify-demo.sh

# View logs
docker-compose -f docker-compose.demo.yml logs -f

# Restart a service
docker-compose -f docker-compose.demo.yml restart demo-api

# Stop (keeps data)
docker-compose -f docker-compose.demo.yml stop

# Start again
docker-compose -f docker-compose.demo.yml start

# Clean up everything
./cleanup-demo.sh
```

---

## Need Help?

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) first
2. Run `./verify-demo.sh` to diagnose
3. View logs: `docker-compose -f docker-compose.demo.yml logs`
4. Complete reset: `./cleanup-demo.sh && ./setup-demo.sh`

---

## 🎉 That's It!

You now have a **fully functional** e-commerce store with an AI chatbot. 

**Start testing in under 3 minutes!**
