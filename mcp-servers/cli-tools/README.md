# CLI Tools MCP Server

MCP wrapper for powerful command-line utilities.

## Tools Available

### Search & Find
| Tool | Description |
|------|-------------|
| `rg_search` | Fast text search with ripgrep |
| `rg_count` | Count pattern occurrences |
| `fd_find` | Fast file finder |
| `fd_recent` | Find recently modified files |

### View & List
| Tool | Description |
|------|-------------|
| `bat_view` | View file with syntax highlighting |
| `eza_list` | Modern directory listing |
| `tldr_help` | Simplified command help |

### Audio (sox)
| Tool | Description |
|------|-------------|
| `sox_info` | Audio file information |
| `sox_stats` | Audio statistics (RMS, peak, etc.) |
| `sox_convert` | Convert audio formats |
| `sox_trim` | Cut/trim audio files |

### Git
| Tool | Description |
|------|-------------|
| `git_status_pretty` | Formatted git status |
| `git_log_pretty` | Formatted git log |

### Utility
| Tool | Description |
|------|-------------|
| `search_and_view` | Search and show context |
| `cli_tools_status` | Check all tools status |

## Examples

```python
# Fast search for "def " in Python files
rg_search(pattern="def ", file_type="py", max_results=20)

# Find all markdown files modified today
fd_recent(hours=24, extension="md")

# Get audio file stats
sox_stats(file="~/brain/sounds/kick.wav")

# Quick help for ffmpeg
tldr_help(command="ffmpeg")
```
