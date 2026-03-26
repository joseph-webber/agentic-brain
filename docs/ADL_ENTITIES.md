# ADL Entity System

> **agentic-brain** - A better JHipster with RAG-powered entities

## Overview

ADL (Agentic Definition Language) supports full entity generation with both **RAG** (semantic search) and **DAO** (traditional CRUD) patterns.

## Entity Syntax

```adl
entity Note {
  # Fields with types and constraints
  title String required maxLength(100)
  content Text searchable           # Indexed for RAG semantic search
  userId Integer foreignKey(User)
  tags List[String] searchable      # Also RAG-indexed
  createdAt DateTime default(now)
  
  # Access control (RBAC)
  access {
    read: USER, ADMIN
    write: owner, ADMIN
    delete: ADMIN
  }
  
  # Storage pattern (optional - defaults to hybrid)
  storage {
    pattern: hybrid    # Options: dao, rag, hybrid
    vectorDb: chromadb # Options: chromadb, lancedb, neo4j
  }
}
```

## Field Types

| Type | Python | SQLite | Description |
|------|--------|--------|-------------|
| String | str | TEXT | Short text (use maxLength) |
| Text | str | TEXT | Long text, markdown |
| Integer | int | INTEGER | Whole numbers |
| Float | float | REAL | Decimal numbers |
| Boolean | bool | INTEGER | True/False |
| DateTime | datetime | TEXT | ISO 8601 format |
| List[T] | List[T] | JSON | Array of values |

## Field Modifiers

| Modifier | Description |
|----------|-------------|
| `required` | Field cannot be null |
| `searchable` | Indexed for RAG semantic search |
| `maxLength(n)` | Maximum string length |
| `minLength(n)` | Minimum string length |
| `default(value)` | Default value |
| `foreignKey(Entity)` | Relationship to another entity |
| `unique` | Unique constraint |

## Storage Patterns

### DAO Pattern (Traditional)
```adl
storage {
  pattern: dao
}
```
- SQL-based CRUD operations
- Exact matching queries
- Fast for known queries
- Best for: structured data, reports

### RAG Pattern (AI-Powered)
```adl
storage {
  pattern: rag
  vectorDb: chromadb
}
```
- Semantic search via embeddings
- Natural language queries
- Best for: knowledge bases, search

### Hybrid Pattern (Recommended)
```adl
storage {
  pattern: hybrid
  vectorDb: chromadb
}
```
- DAO for CRUD operations
- RAG for semantic search
- Best of both worlds!

## Generated Layers

For each entity, agentic-brain generates 7 layers:

| Layer | File | Description |
|-------|------|-------------|
| Model | `models/{entity}_model.py` | Pydantic + SQLModel |
| DAO | `dao/{entity}_dao.py` | CRUD operations |
| Service | `services/{entity}_service.py` | Business logic |
| Business Object | `business/{entity}_bo.py` | Domain rules |
| API Routes | `api/{entity}_routes.py` | FastAPI endpoints |
| React Component | `web/components/{Entity}Manager.tsx` | CRUD UI |
| CLI Commands | `cli/{entity}_commands.py` | Terminal management |

## Access Control

```adl
access {
  read: USER, ADMIN       # Who can read
  write: owner, ADMIN     # Who can write (owner = creator)
  delete: ADMIN           # Who can delete
}
```

Roles:
- `ADMIN` - Full access to everything
- `USER` - Access to own entities
- `GUEST` - Read-only (if allowed)
- `owner` - Special: matches entity creator

## CLI Commands

```bash
# Generate entity
agentic entity Note --fields "title:String content:Text"

# List entities
agentic entity list

# Regenerate entity (preserves custom code)
agentic entity regenerate Note

# Search entities (RAG)
agentic entity search "notes about budget meetings"
```

## Example: Full Note Entity

```adl
entity Note {
  title String required maxLength(100)
  content Text searchable
  userId Integer foreignKey(User)
  tags List[String] searchable
  priority Integer default(0)
  isPublic Boolean default(false)
  createdAt DateTime default(now)
  updatedAt DateTime
  
  validation {
    title: notEmpty, noHtml
    content: maxLength(50000)
    priority: range(0, 5)
  }
  
  access {
    read: USER, ADMIN
    write: owner, ADMIN
    delete: owner, ADMIN
  }
  
  storage {
    pattern: hybrid
    vectorDb: chromadb
  }
}
```

## Comparison: agentic-brain vs JHipster

| Feature | JHipster | agentic-brain |
|---------|----------|---------------|
| Language | Java/TypeScript | Python/TypeScript |
| Database | SQL, MongoDB | SQLite, Neo4j, Vector DBs |
| Search | Elasticsearch | RAG (semantic) |
| AI Integration | None | Built-in LLM routing |
| Generator CLI | Yeoman | Typer |
| Templates | EJS | Jinja2 |
| Frontend | Angular/React/Vue | React |
| Auth | JWT, OAuth2 | JWT, Demo users |
| Accessibility | Basic | WCAG 2.1 AA |

## Next Steps

1. Define your entities in `.adl` files
2. Run `agentic generate` to create all layers
3. Customize generated code (preserved on regenerate)
4. Use RAG search in your app!

---

*agentic-brain: AI-powered application generator with semantic search*
