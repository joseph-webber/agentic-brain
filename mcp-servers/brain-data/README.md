# Brain Data MCP Server

Full Core Data access for Claude via Model Context Protocol (MCP).

## 26 Tools Available

### Neo4j Data Tools (12)
| Tool | Description |
|------|-------------|
| `brain_ask` | Natural language queries |
| `brain_emails` | Get emails (filter by sender/subject) |
| `brain_jira` | Get JIRA tickets from cache |
| `brain_teams` | Get Teams messages |
| `brain_sage` | Get Sage/Intacct failures |
| `brain_search` | Search all data types |
| `brain_status` | Database status (9,583+ nodes) |
| `brain_anomalies` | Detect data anomalies |
| `brain_digest` | Weekly summary |
| `brain_who` | Find who talked about topic |
| `brain_timeline` | Chronological activity |
| `brain_query` | Raw Cypher queries |

### JIRA API Tools (5)
| Tool | Description |
|------|-------------|
| `jira_get_ticket` | Get ticket by key (e.g., SD-1330) |
| `jira_search` | JQL search |
| `jira_create_ticket` | Create new ticket |
| `jira_add_comment` | Add comment to ticket |
| `jira_sprint_status` | Current sprint overview |

### BitBucket API Tools (4)
| Tool | Description |
|------|-------------|
| `bitbucket_get_pr` | Get PR by number |
| `bitbucket_list_prs` | List PRs (filter by state/author) |
| `bitbucket_pr_diff` | Get PR diff URL |
| `bitbucket_recent_commits` | Get recent commits |

### Brain Health Tools (3)
| Tool | Description |
|------|-------------|
| `brain_health` | Check all systems |
| `brain_freshness` | Data freshness report |
| `brain_metrics` | Performance metrics |

### Sync & Management (2)
| Tool | Description |
|------|-------------|
| `brain_sync` | Sync all data to Neo4j |
| `brain_sync_selective` | Sync specific data types |

## Installation

```bash
cd ~/brain/mcp-servers/brain-data
pip install -e .
```

## Configuration

Add to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "brain-data": {
      "command": "/Users/joe/brain/venv/bin/python",
      "args": ["/Users/joe/brain/mcp-servers/brain-data/server.py"],
      "env": {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "brain2026",
        "PYTHONPATH": "/Users/joe/brain"
      }
    }
  }
}
```

## Usage Examples

```
# Natural language
brain_ask("emails from Steve this week")

# JIRA operations
jira_get_ticket("SD-1330")
jira_search("assignee = steve.taylor AND status = 'In Progress'")
jira_add_comment("SD-1330", "Investigation complete")

# BitBucket
bitbucket_list_prs(state="OPEN", author="user")

# Health check
brain_health()
```

## Architecture

```
Claude Desktop / Copilot CLI
    ↓ MCP Protocol
Brain Data Server (26 tools)
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│   Neo4j         │   JIRA API      │   BitBucket     │
│   (9,583 nodes) │   (live)        │   (live)        │
└─────────────────┴─────────────────┴─────────────────┘
```

## Key Features

- **Connection Pooling**: 50 max connections to Neo4j
- **Query Caching**: 300s TTL for repeated queries  
- **Retry Logic**: 3 attempts with exponential backoff
- **Smart Queries**: Natural language → Cypher translation
- **Full-Text Search**: Indexed email and teams content
