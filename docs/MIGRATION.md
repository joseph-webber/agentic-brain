# Migration Guide

This guide helps you upgrade between major versions of Agentic Brain.

## Version Compatibility

| Version | Python | Neo4j | Status |
|---------|--------|-------|--------|
| 2.10.x | 3.10+ | 5.x | Current |
| 2.9.x | 3.10+ | 5.x | Supported |
| 2.8.x | 3.10+ | 5.x | Supported |
| 2.x | 3.10+ | 4.x/5.x | Legacy |
| 1.x | 3.9+ | 4.x | EOL |

## Migrating to 2.10.x

### Breaking Changes

1. **Router module restructured** - Now a subpackage

```python
# Before (2.9.x)
from agentic_brain.router import LLMRouter

# After (2.10.x) - Still works (backward compatible)
from agentic_brain.router import LLMRouter

# New explicit imports available
from agentic_brain.router.providers import LLMProvider
from agentic_brain.router.routing import LLMRouter
```

2. **API route registration refactored**

The monolithic `register_routes()` function has been split:

```python
# Before - single function
from agentic_brain.api.routes import register_routes

# After - modular registration
from agentic_brain.api.routes import (
    register_health_routes,
    register_chat_routes,
    register_session_routes,
    register_rag_routes,
    register_admin_routes,
    register_auth_routes,
)
```

3. **Environment variable changes**

New environment variables:

```bash
# CORS configuration
CORS_ORIGINS=http://localhost:3000,https://app.example.com

# Ollama configuration  
OLLAMA_HOST=http://localhost:11434

# API URL configuration
AGENTIC_BRAIN_API_URL=http://localhost:8000
AGENTIC_BRAIN_WS_URL=ws://localhost:8000/ws
```

### Migration Steps

1. **Update dependencies**

```bash
pip install --upgrade agentic-brain>=2.10.0
```

2. **Update environment variables**

Add new variables to your `.env`:

```bash
# Required for production
CORS_ORIGINS=https://your-domain.com

# Optional - defaults provided
OLLAMA_HOST=http://localhost:11434
```

3. **Test your application**

```bash
pytest tests/ -v
```

## Migrating from 2.8.x to 2.9.x

### Breaking Changes

1. **Exception hierarchy updated**

```python
# Before
from agentic_brain.exceptions import BrainError

# After
from agentic_brain.exceptions import AgenticBrainError
```

2. **Auth providers reorganized**

```python
# Before
from agentic_brain.auth import LDAPProvider

# After
from agentic_brain.auth.providers import LDAPAuth
from agentic_brain.auth.enterprise_providers import LDAPProvider
```

### Migration Steps

1. Update exception imports
2. Update auth provider imports
3. Run tests to verify

## Migrating from 1.x to 2.x

This is a major upgrade with significant changes.

### Breaking Changes

1. **Minimum Python version**: 3.10+ (was 3.9+)
2. **Neo4j 5.x required** (4.x deprecated)
3. **New authentication system**
4. **Transport layer rewritten**

### Migration Steps

1. **Upgrade Python** to 3.10 or later

2. **Upgrade Neo4j** to 5.x

```bash
# Backup data first!
neo4j-admin database dump --database=neo4j --to-path=/backup

# Upgrade Neo4j
# Then restore
neo4j-admin database load --database=neo4j --from-path=/backup
```

3. **Update imports**

```python
# Old 1.x style
from brain import Brain
brain = Brain()

# New 2.x style
from agentic_brain import create_agent
from agentic_brain.router import LLMRouter

router = LLMRouter()
agent = create_agent(router=router)
```

4. **Update configuration**

```bash
# Copy new .env.example
cp .env.example .env

# Update with your values
```

5. **Run migration scripts**

```bash
# Neo4j schema updates
python -m agentic_brain.cli migrate
```

## Database Migrations

### Neo4j Schema Updates

Check for required schema updates:

```bash
python -m agentic_brain.cli db check
```

Apply migrations:

```bash
python -m agentic_brain.cli db migrate
```

Rollback if needed:

```bash
python -m agentic_brain.cli db rollback --version 2.9.0
```

### Creating Migrations

For custom migrations:

```python
# migrations/20240301_add_index.py
from agentic_brain.migrations import Migration

class AddUserIndex(Migration):
    version = "2.10.0"
    
    def up(self):
        self.execute("CREATE INDEX user_email FOR (u:User) ON (u.email)")
    
    def down(self):
        self.execute("DROP INDEX user_email")
```

## Configuration Migration

### Environment Variables

Compare your `.env` with `.env.example`:

```bash
diff .env .env.example
```

Key changes by version:

| Version | New Variables | Removed |
|---------|--------------|---------|
| 2.10.0 | CORS_ORIGINS, OLLAMA_HOST | - |
| 2.9.0 | JWT_ALGORITHM, TOKEN_EXPIRE_HOURS | OLD_JWT_KEY |
| 2.8.0 | TRANSPORT_MODE | FIREBASE_ONLY |

## Rollback Procedures

### Quick Rollback

```bash
# Pin to previous version
pip install agentic-brain==2.9.0
```

### Full Rollback

1. Stop services
2. Restore database backup
3. Install previous version
4. Restart services

```bash
# Stop
systemctl stop agentic-brain

# Restore
neo4j-admin database load --from-path=/backup/pre-upgrade

# Downgrade
pip install agentic-brain==2.9.0

# Start
systemctl start agentic-brain
```

## Getting Help

- **Documentation**: [docs/](./README.md)
- **Issues**: [GitHub Issues](https://github.com/yourusername/agentic-brain/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/agentic-brain/discussions)

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for detailed version history.
