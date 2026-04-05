# Connectors

Agentic Brain connectors provide a consistent polling and incremental-sync API for external data sources.

## Core types

- `ConnectorRecord`: normalized document/message/file record
- `ConnectorSyncCursor`: incremental state (`updated_after`, `page_token`, connector state)
- `ConnectorSchedule`: polling cadence and enable/disable controls
- `ConnectorSyncResult`: sync output with items and next-run metadata

## Supported connectors

- Notion
- Confluence
- GitHub repositories
- Slack
- Google Drive

## Sync model

1. `authenticate()` validates credentials.
2. `list_changes()` returns the next page of changed items.
3. `sync()` merges records, advances the cursor, and computes the next run time.
4. `incremental_sync()` starts from a saved cursor or timestamp.

Example:

```python
from agentic_brain.connectors import GitHubConnector

connector = GitHubConnector("octo-org", "brain", token="ghp_xxx")
result = connector.incremental_sync()
print(result.changed_count, result.cursor.to_dict())
```

## Incremental updates

Each connector stores source-specific state in `ConnectorSyncCursor.state`.
Examples include GitHub tree SHA values, Slack channel cursors, and Google Drive
modified-time filters. This allows polling jobs to avoid full refreshes when
nothing has changed.
