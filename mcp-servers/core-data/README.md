# Core Data MCP Server

**Purpose:** Auto-exposes ALL core_data modules as MCP tools  
**Zero manual wiring** - add a method to core_data, it becomes an MCP tool!

## How It Works

```
core_data/teams.py          →  teams_send_message
    TeamsAPI.send_message        teams_get_messages
                                 teams_search_messages

core_data/jira.py           →  jira_get_ticket
    JiraProvider.get_ticket      jira_add_comment
                                 jira_search
```

## Adding New Capabilities

1. Add method to the appropriate `core_data/*.py` module
2. Restart Claude Desktop
3. Tool is automatically available!

No need to edit the MCP server or wire anything up.

## Exposed Modules

| Module | Tools | Description |
|--------|-------|-------------|
| `teams` | send_message, get_messages, search, sync | Microsoft Teams |
| `jira` | get_ticket, search, add_comment, transition | JIRA tickets |
| `bitbucket` | get_pr, list_prs, post_comment, create_pr | Bitbucket PRs |
| `github` | get_commits, get_branches, get_status | GitHub repos |
| `outlook` | search, recent, sage_failures | Email |
| `freqtrade` | bots, trades, performance | Trading |
| `sage_tracker` | check_failures, classify_error | Sage/Intacct |

## Configuration

Add to Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "core-data": {
      "command": "python3",
      "args": ["/Users/joe/brain/mcp-servers/core-data/server.py"]
    }
  }
}
```

## Testing

```bash
# Check it starts
cd ~/brain/mcp-servers/core-data
python3 server.py

# Should print: "Core Data MCP Server starting with ~125 tools..."
```

## Tool Naming Convention

All tools are named: `{module}_{method}`

Examples:
- `teams_send_message` - Send Teams message
- `jira_get_ticket` - Get JIRA ticket
- `bitbucket_get_pull_requests` - List PRs
- `outlook_search` - Search emails
