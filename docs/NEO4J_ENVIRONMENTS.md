# Neo4j Environments - Complete Guide

**3 separate Neo4j instances for different purposes**

---

## Overview

| Environment | Port | Password | Purpose | Data | Can Reset? |
|------------|------|----------|---------|------|------------|
| **Production** | 7687 | `Brain2026` | Production brain | 60,000+ nodes | ❌ NEVER |
| **Local Demo** | 7688 | `demo2026` | Testing & demos | Clean seed data | ✅ Anytime |
| **CI/CD** | 7687 | `test2026` | Automated tests | Test fixtures | ✅ Auto |

---

## 1. Production (the user's Brain)

### Details
- **Location**: Homebrew install (local macOS)
- **Port**: 7687 (default)
- **Data**: 60,000+ nodes - the user's real data
  - JIRA tickets
  - Teams messages
  - Bitbucket PRs
  - Email history
  - Personal learnings
  - Session continuity
- **Password**: `Brain2026`
- **Used by**: 
  - brain-core
  - private-brain
  - Daily work tools
  - All production scripts

### How to Check Status
```bash
# Check if running
neo4j status

# Start if needed
neo4j start

# Access browser
open http://localhost:7474
```

### Connection String
```
bolt://localhost:7687
Username: neo4j
Password: Brain2026
```

### ⚠️ CRITICAL RULES
- **NEVER** reset or clear this database
- **NEVER** run test scripts against port 7687
- **ALWAYS** backup before maintenance
- This is the user's memory - treat it with care

### Backup
```bash
# Via Brain MCP tool
brain-backup_now

# Manual backup
neo4j-admin backup --backup-dir=/path/to/backup
```

---

## 2. Local Demo

### Details
- **Location**: Docker container
- **Port**: 7688 (deliberately different!)
- **Data**: Clean demo dataset
  - Sample JIRA tickets
  - Sample messages
  - Demo users
  - Test relationships
- **Password**: `demo2026`
- **Used by**:
  - Testing chat features
  - Demos for new users
  - Development testing
  - Learning the system

### How to Start
```bash
cd ~/brain/agentic-brain

# Start demo Neo4j
docker compose -f docker/docker-compose.demo.yml up -d

# Check logs
docker compose -f docker/docker-compose.demo.yml logs -f

# Access browser
open http://localhost:7475
```

### How to Stop
```bash
cd ~/brain/agentic-brain
docker compose -f docker/docker-compose.demo.yml down
```

### Connection String
```
bolt://localhost:7688
Username: neo4j
Password: demo2026
```

### Reset Demo Data
```bash
# Stop and remove volumes
docker compose -f docker/docker-compose.demo.yml down -v

# Start fresh
docker compose -f docker/docker-compose.demo.yml up -d

# Load seed data
python3 scripts/seed_demo_data.py
```

### ✅ Safe Operations
- Reset anytime
- Clear all data
- Experiment freely
- No risk to production

---

## 3. CI/CD Pipeline

### Details
- **Location**: Docker in GitHub Actions
- **Port**: 7687 (isolated in CI)
- **Data**: Test fixtures only
  - Minimal test data
  - Ephemeral - destroyed after run
- **Password**: `test2026`
- **Used by**:
  - Automated tests (pytest)
  - GitHub Actions workflows
  - Integration tests
  - PR validation

### How It Works
```yaml
# Automatic in .github/workflows/test.yml
services:
  neo4j:
    image: neo4j:5.15.0
    ports:
      - 7687:7687
    env:
      NEO4J_AUTH: neo4j/test2026
      NEO4J_PLUGINS: '["apoc"]'
```

### Connection String (in CI)
```
bolt://neo4j:7687
Username: neo4j
Password: test2026
```

### Lifecycle
1. GitHub Action starts
2. Docker creates Neo4j container
3. Tests run against fresh database
4. Tests complete
5. Container destroyed automatically

### ✅ Test Isolation
- Each workflow run gets fresh database
- No data persists between runs
- No conflicts with production or demo
- Completely isolated environment

---

## Environment Variables

### For Production
```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="Brain2026"
```

### For Demo
```bash
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="demo2026"
```

### For CI/CD
```yaml
# In GitHub Actions secrets
NEO4J_URI: bolt://neo4j:7687
NEO4J_USER: neo4j
NEO4J_PASSWORD: test2026
```

---

## Common Mistakes to Avoid

### ❌ DON'T
- Run tests against port 7687 (production!)
- Clear production database "to test something"
- Use demo password on production
- Assume port 7687 is always safe

### ✅ DO
- Always check which port you're connecting to
- Use demo (7688) for testing
- Backup production before changes
- Use environment variables to switch environments

---

## Quick Reference

### Check Which Environment You're Using
```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "Brain2026"))
with driver.session() as session:
    result = session.run("MATCH (n) RETURN count(n) as count")
    count = result.single()["count"]
    print(f"Connected to database with {count} nodes")
    
    if count > 50000:
        print("⚠️ WARNING: This is PRODUCTION!")
    elif count < 1000:
        print("✅ Safe: This is DEMO or CI")
```

### Port Quick Check
```bash
# List all Neo4j processes
ps aux | grep neo4j

# Check what's listening on Neo4j ports
lsof -i :7687  # Production
lsof -i :7688  # Demo
```

---

## Troubleshooting

### Production Won't Start
```bash
# Check logs
tail -f ~/Library/Application\ Support/Neo4j/logs/neo4j.log

# Check if port is in use
lsof -i :7687
```

### Demo Won't Start
```bash
# Check Docker
docker ps -a

# View logs
docker compose -f docker/docker-compose.demo.yml logs

# Restart
docker compose -f docker/docker-compose.demo.yml restart
```

### CI Tests Fail
```bash
# Check GitHub Actions logs
gh run view --log

# Run locally with Docker
docker compose -f docker/docker-compose.ci.yml up
pytest tests/
docker compose -f docker/docker-compose.ci.yml down
```

---

## Migration Between Environments

### Export from Production to Demo
```bash
# Export production data
neo4j-admin dump --database=neo4j --to=production.dump

# Import to demo (while demo is stopped)
docker compose -f docker/docker-compose.demo.yml down
docker compose -f docker/docker-compose.demo.yml up -d
# ... use neo4j-admin load inside container ...
```

### Copy Test Data to Demo
```bash
# Export test fixtures
python3 scripts/export_test_fixtures.py

# Import to demo
python3 scripts/import_to_demo.py
```

---

## Security Notes

### Passwords
- Production: Strong password, never commit to repo
- Demo: Simple password, okay in docker-compose
- CI: Simple password, okay in public repo (ephemeral)

### Network
- Production: Local only (127.0.0.1)
- Demo: Docker internal network + localhost
- CI: Docker internal network only

### Backups
- Production: Daily backups to iCloud
- Demo: No backups needed
- CI: No backups needed

---

## Summary

**Use Production (7687) for:**
- Real work
- Daily operations
- Production scripts
- the user's actual brain

**Use Demo (7688) for:**
- Testing new features
- Demos
- Learning
- Breaking things safely

**Use CI/CD (7687 in Actions) for:**
- Automated tests
- PR validation
- Integration testing
- No manual interaction

---

**Created**: 2026-03-22  
**Last Updated**: 2026-03-22  
**Status**: ACTIVE

