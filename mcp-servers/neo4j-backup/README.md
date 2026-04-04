# Neo4j iCloud Backup MCP Server

MCP server providing Claude access to Neo4j backup operations.

## Tools (12)

| Tool | Description |
|------|-------------|
| `backup_neo4j` | Run full backup to iCloud |
| `backup_status` | Get backup system status |
| `backup_list` | List all backups |
| `backup_browse` | Browse backup contents |
| `backup_compare` | Compare two backups |
| `backup_verify` | Verify backup integrity |
| `backup_restore` | Restore from backup |
| `backup_health` | Health report |
| `backup_metrics` | Performance metrics |
| `backup_estimate` | Estimate backup size |
| `backup_simulate_gfs` | Simulate GFS retention |
| `backup_self_test` | Run self-test |

## Installation

```bash
cd ~/brain/mcp-servers/neo4j-backup
pip install -e .
```

## Claude Desktop Config

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "neo4j-backup": {
      "command": "python",
      "args": ["/Users/joe/brain/mcp-servers/neo4j-backup/server.py"]
    }
  }
}
```

## Usage Examples

### Run a backup
```
Use backup_neo4j tool
```

### Check status
```
Use backup_status tool
```

### List recent backups
```
Use backup_list with limit: 5
```

### Browse a backup
```
Use backup_browse with filename: "neo4j-backup-20260223_230246.json.gz"
```

### Compare backups
```
Use backup_compare with:
  backup1: "neo4j-backup-20260223_225419.json.gz"
  backup2: "neo4j-backup-20260223_230246.json.gz"
```

### Verify a backup
```
Use backup_verify with filename: "neo4j-backup-20260223_230246.json.gz"
```

### Restore (CAUTION)
```
Use backup_restore with:
  filename: "neo4j-backup-20260223_230246.json.gz"
  confirm: true
```

## Features

- **12 tools** for complete backup management
- **Safe restore** - requires explicit confirmation
- **JSON output** - structured data for Claude
- **Path resolution** - accepts filenames or full paths
- **Timeout protection** - 5 minute max per operation

## Architecture

```
Claude → MCP Protocol → server.py → neo4j-icloud-backup.py → Neo4j/iCloud
```

The MCP server wraps the v5.0 backup script, executing commands via subprocess
and returning structured JSON responses.
