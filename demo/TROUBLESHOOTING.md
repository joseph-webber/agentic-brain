# Demo Troubleshooting Guide

## Common Issues and Solutions

### 1. Docker Not Running

**Error:**
```
Cannot connect to the Docker daemon
```

**Solution:**
- Open Docker Desktop
- Wait for it to fully start (whale icon in menu bar)
- Try again: `./setup-demo.sh`

---

### 2. Port Already in Use

**Error:**
```
port is already allocated
```

**Solution:**

Option A: Change ports in `.env`:
```bash
cp .env.demo .env
# Edit .env and change conflicting ports
DEMO_WP_PORT=8081  # if 8080 is taken
DEMO_API_PORT=8001 # if 8000 is taken
```

Option B: Stop conflicting service:
```bash
# Find what's using the port
lsof -i :8080

# Stop it or kill the process
kill -9 <PID>
```

---

### 3. WordPress Installation Hangs

**Symptoms:**
- Setup script stuck at "Waiting for WordPress..."
- Timeout after 60 attempts

**Solution:**
```bash
# Check WordPress logs
docker-compose -f docker-compose.demo.yml logs demo-wordpress

# Common fixes:
# 1. Restart WordPress
docker-compose -f docker-compose.demo.yml restart demo-wordpress

# 2. Check database connection
docker-compose -f docker-compose.demo.yml exec demo-db mysql -u wp_demo -pdemo_wp_pass_2026 -e "SHOW DATABASES;"

# 3. Complete reset
./cleanup-demo.sh
./setup-demo.sh
```

---

### 4. API Not Starting

**Error:**
```
demo-api is unhealthy
```

**Solution:**
```bash
# Check API logs
docker-compose -f docker-compose.demo.yml logs demo-api

# Common causes:
# 1. Neo4j not ready - wait 30 seconds and check again
# 2. Redis not ready - wait and check again
# 3. Python dependencies - rebuild image

# Rebuild API
docker-compose -f docker-compose.demo.yml build demo-api
docker-compose -f docker-compose.demo.yml up -d demo-api
```

---

### 5. Plugin Not Found

**Error:**
```
Plugin 'agentic-brain' not found
```

**Solution:**
```bash
# Verify plugin exists
ls -la ../plugins/wordpress/agentic-brain/

# Should see:
# agentic-brain.php
# includes/
# admin/
# etc.

# If missing, check your working directory:
pwd  # Should be in /Users/joe/brain/agentic-brain/demo

# Re-run setup
./setup-demo.sh
```

---

### 6. Chatbot Not Appearing

**Symptoms:**
- WordPress loads fine
- No chatbot widget visible

**Solutions:**

**A. Check plugin is activated:**
```bash
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp plugin list --allow-root

# Should show agentic-brain as 'active'
```

**B. Check plugin settings:**
1. Go to http://localhost:8080/wp-admin
2. Navigate to Agentic Brain settings
3. Ensure "Enable Chatbot" is checked
4. Verify API URL: `http://demo-api:8000`

**C. Check browser console:**
1. Open browser DevTools (F12)
2. Look for JavaScript errors
3. Check Network tab for failed API calls

**D. Clear WordPress cache:**
```bash
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp cache flush --allow-root
```

---

### 7. API Returns 500 Errors

**Symptoms:**
- Chatbot fails to respond
- API docs work but endpoints fail

**Solution:**
```bash
# Check API logs for stack traces
docker-compose -f docker-compose.demo.yml logs demo-api | tail -50

# Common causes:
# 1. Neo4j connection issue
docker-compose -f docker-compose.demo.yml exec demo-neo4j cypher-shell -u neo4j -p demo_neo4j_2026 "RETURN 1;"

# 2. Redis connection issue
docker-compose -f docker-compose.demo.yml exec demo-redis redis-cli -a demo_redis_2026 PING

# 3. Restart API
docker-compose -f docker-compose.demo.yml restart demo-api
```

---

### 8. Neo4j Login Fails

**Error:**
```
Invalid username or password
```

**Solution:**
```bash
# Default password is: demo_neo4j_2026

# Reset Neo4j (will lose data):
docker-compose -f docker-compose.demo.yml stop demo-neo4j
docker volume rm agentic-brain_demo-neo4j-data
docker-compose -f docker-compose.demo.yml up -d demo-neo4j

# Wait 30 seconds for Neo4j to start
# Try logging in again
```

---

### 9. Services Keep Restarting

**Symptoms:**
- `docker ps` shows services constantly restarting
- "Restarting (1) 3 seconds ago" status

**Solution:**
```bash
# Check which service is failing
docker-compose -f docker-compose.demo.yml ps

# View logs of failing service
docker-compose -f docker-compose.demo.yml logs <service-name>

# Common fixes:
# 1. Increase Docker memory allocation (Docker Desktop > Settings > Resources)
# 2. Check disk space: df -h
# 3. Restart Docker Desktop
# 4. Complete cleanup and retry
./cleanup-demo.sh
./setup-demo.sh
```

---

### 10. Slow Performance

**Symptoms:**
- Pages load slowly
- API responses take 5+ seconds

**Solutions:**

**A. Check Docker resources:**
- Open Docker Desktop
- Go to Settings > Resources
- Increase RAM to 4GB minimum
- Increase CPUs to 2 minimum

**B. Reduce running services:**
```bash
# Stop services you're not actively using
docker-compose -f docker-compose.demo.yml stop demo-neo4j
docker-compose -f docker-compose.demo.yml stop demo-redis
```

**C. Check system resources:**
```bash
# macOS
top

# Look for high CPU/memory usage
# Close other applications
```

---

### 11. WooCommerce Not Installing

**Error:**
```
Plugin 'woocommerce' installation failed
```

**Solution:**
```bash
# Manual installation via WP-CLI
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp plugin install woocommerce --activate --allow-root

# If that fails, download directly
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp plugin install https://downloads.wordpress.org/plugin/woocommerce.latest-stable.zip --activate --allow-root
```

---

### 12. Database Connection Errors

**Error:**
```
Error establishing a database connection
```

**Solution:**
```bash
# Check MariaDB is running
docker-compose -f docker-compose.demo.yml ps demo-db

# Should show "Up (healthy)"

# Test database connection
docker-compose -f docker-compose.demo.yml exec demo-db mysql -u wp_demo -pdemo_wp_pass_2026 -e "SELECT 1;"

# If fails, restart database
docker-compose -f docker-compose.demo.yml restart demo-db

# Wait 30 seconds for it to be healthy
docker-compose -f docker-compose.demo.yml ps demo-db
```

---

### 13. Products Not Showing

**Symptoms:**
- WordPress works
- No products visible in store or admin

**Solution:**
```bash
# Check if products were created
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp wc product list --user=admin --allow-root

# If empty, create them manually
docker-compose -f docker-compose.demo.yml exec demo-wp-cli wp wc product create \
  --name="Test Product" \
  --regular_price=99.99 \
  --status=publish \
  --user=admin \
  --allow-root

# Or re-run setup section (safer - won't duplicate)
# Products section of setup-demo.sh
```

---

### 14. Permission Errors

**Error:**
```
Permission denied: /var/www/html/wp-content
```

**Solution:**
```bash
# Fix WordPress file permissions
docker-compose -f docker-compose.demo.yml exec demo-wordpress chown -R www-data:www-data /var/www/html/wp-content

# Or restart WordPress
docker-compose -f docker-compose.demo.yml restart demo-wordpress
```

---

### 15. Complete Reset Needed

**When nothing else works:**

```bash
# Nuclear option - removes everything
./cleanup-demo.sh

# Wait for completion, then:
./setup-demo.sh
```

**This will:**
- ✅ Stop all containers
- ✅ Remove all volumes (data)
- ✅ Prune unused Docker resources
- ✅ Give you a clean slate

---

## Getting Help

### Check Logs First
```bash
# All services
docker-compose -f docker-compose.demo.yml logs -f

# Specific service
docker-compose -f docker-compose.demo.yml logs -f demo-api
docker-compose -f docker-compose.demo.yml logs -f demo-wordpress
docker-compose -f docker-compose.demo.yml logs -f demo-neo4j
```

### Verify Service Health
```bash
docker-compose -f docker-compose.demo.yml ps

# All services should show "Up (healthy)"
```

### Test Individual Components
```bash
# WordPress
curl http://localhost:8080

# API
curl http://localhost:8000/health

# Neo4j
curl http://localhost:7475

# Redis (from inside container)
docker-compose -f docker-compose.demo.yml exec demo-redis redis-cli -a demo_redis_2026 PING
```

### Still Stuck?

1. **Collect logs:**
   ```bash
   docker-compose -f docker-compose.demo.yml logs > demo-logs.txt
   ```

2. **Check system info:**
   ```bash
   docker version
   docker-compose version
   df -h  # Disk space
   ```

3. **Open GitHub issue** with:
   - Your OS and Docker versions
   - Error messages
   - Logs from failing services
   - Steps to reproduce

---

## Prevention Tips

### Before Running Demo
- ✅ Ensure Docker Desktop is running
- ✅ Check you have 10GB free disk space
- ✅ Close unnecessary applications
- ✅ Allocate 4GB+ RAM to Docker

### Regular Maintenance
```bash
# Clean up unused Docker resources weekly
docker system prune -f

# Remove old demo volumes if not needed
docker volume prune -f
```

### Best Practices
- Don't modify files while containers are running
- Use `docker-compose restart` instead of `stop`/`start`
- Check logs when something seems slow
- Keep Docker Desktop updated

---

**Most issues resolve with a simple restart or cleanup!**
