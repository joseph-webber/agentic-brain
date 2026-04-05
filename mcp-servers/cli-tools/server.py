#!/usr/bin/env python3
"""
CLI Tools MCP Server - Wrapper for powerful CLI utilities
Tools: ripgrep, fd, bat, fzf, eza, tldr, sox, lazygit
"""

import subprocess
import json
import os
from pathlib import Path

# MCP SDK
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("cli-tools")


def run_command(cmd: list, cwd: str = None) -> dict:
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd or os.path.expanduser("~/brain"),
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "command": " ".join(cmd),
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out",
            "command": " ".join(cmd),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "command": " ".join(cmd)}


# ============== RIPGREP (Fast Search) ==============


@mcp.tool()
def rg_search(
    pattern: str,
    path: str = "~/brain",
    file_type: str = None,
    case_insensitive: bool = True,
    max_results: int = 50,
) -> dict:
    """
    Fast text search with ripgrep (10x faster than grep).

    Args:
        pattern: Text or regex pattern to search for
        path: Directory to search in (default: ~/brain)
        file_type: Filter by type: py, js, ts, md, json, yaml, sh, etc.
        case_insensitive: Ignore case (default: True)
        max_results: Maximum results to return (default: 50)
    """
    cmd = ["rg", "--json", "-m", str(max_results)]

    if case_insensitive:
        cmd.append("-i")
    if file_type:
        cmd.extend(["-t", file_type])

    cmd.append(pattern)
    cmd.append(os.path.expanduser(path))

    result = run_command(cmd)

    if result["success"]:
        # Parse JSON output
        matches = []
        for line in result["output"].strip().split("\n"):
            if line:
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data.get("data", {})
                        matches.append(
                            {
                                "file": match_data.get("path", {}).get("text", ""),
                                "line_number": match_data.get("line_number", 0),
                                "text": match_data.get("lines", {})
                                .get("text", "")
                                .strip(),
                            }
                        )
                except json.JSONDecodeError:
                    pass

        return {
            "success": True,
            "count": len(matches),
            "matches": matches[:max_results],
        }

    return result


@mcp.tool()
def rg_count(pattern: str, path: str = "~/brain", file_type: str = None) -> dict:
    """
    Count occurrences of a pattern across files.

    Args:
        pattern: Text or regex pattern to count
        path: Directory to search in
        file_type: Filter by type: py, js, md, etc.
    """
    cmd = ["rg", "-c", "-i", pattern]

    if file_type:
        cmd.extend(["-t", file_type])

    cmd.append(os.path.expanduser(path))

    result = run_command(cmd)

    if result["success"]:
        counts = {}
        total = 0
        for line in result["output"].strip().split("\n"):
            if ":" in line:
                file_path, count = line.rsplit(":", 1)
                counts[file_path] = int(count)
                total += int(count)

        return {
            "success": True,
            "total": total,
            "by_file": dict(sorted(counts.items(), key=lambda x: -x[1])[:20]),
        }

    return {"success": True, "total": 0, "by_file": {}}


# ============== FD (Fast Find) ==============


@mcp.tool()
def fd_find(
    pattern: str = "",
    path: str = "~/brain",
    extension: str = None,
    file_type: str = None,
    max_depth: int = None,
    max_results: int = 50,
) -> dict:
    """
    Fast file/directory finder (faster than 'find').

    Args:
        pattern: Filename pattern to match (regex supported)
        path: Directory to search in
        extension: Filter by extension: py, js, md, json, etc.
        file_type: 'f' for files, 'd' for directories
        max_depth: Maximum directory depth to search
        max_results: Maximum results (default: 50)
    """
    cmd = ["fd"]

    if extension:
        cmd.extend(["-e", extension])
    if file_type:
        cmd.extend(["-t", file_type])
    if max_depth:
        cmd.extend(["-d", str(max_depth)])

    if pattern:
        cmd.append(pattern)
    else:
        cmd.append(".")  # Match all if no pattern

    cmd.append(os.path.expanduser(path))

    result = run_command(cmd)

    if result["success"]:
        files = [f for f in result["output"].strip().split("\n") if f][:max_results]
        return {"success": True, "count": len(files), "files": files}

    return result


@mcp.tool()
def fd_recent(path: str = "~/brain", hours: int = 24, extension: str = None) -> dict:
    """
    Find recently modified files.

    Args:
        path: Directory to search
        hours: Modified within last N hours (default: 24)
        extension: Filter by extension
    """
    cmd = ["fd", "-t", "f", "--changed-within", f"{hours}h"]

    if extension:
        cmd.extend(["-e", extension])

    cmd.append(os.path.expanduser(path))

    result = run_command(cmd)

    if result["success"]:
        files = [f for f in result["output"].strip().split("\n") if f]
        return {"success": True, "count": len(files), "files": files[:50]}

    return result


# ============== BAT (Better Cat) ==============


@mcp.tool()
def bat_view(file: str, line_range: str = None, language: str = None) -> dict:
    """
    View file with syntax highlighting.

    Args:
        file: Path to file
        line_range: Line range like "10:20" or ":50" (first 50) or "50:" (from 50)
        language: Force language highlighting: python, javascript, json, yaml, etc.
    """
    cmd = ["bat", "--style=plain", "--color=never"]

    if line_range:
        cmd.extend(["-r", line_range])
    if language:
        cmd.extend(["-l", language])

    cmd.append(os.path.expanduser(file))

    result = run_command(cmd)

    if result["success"]:
        return {"success": True, "file": file, "content": result["output"]}

    return result


# ============== EZA (Modern ls) ==============


@mcp.tool()
def eza_list(
    path: str = ".",
    long: bool = True,
    all_files: bool = False,
    tree: bool = False,
    tree_depth: int = 2,
    sort: str = "name",
) -> dict:
    """
    List directory contents with modern formatting.

    Args:
        path: Directory path
        long: Long format with details (default: True)
        all_files: Include hidden files
        tree: Show as tree structure
        tree_depth: Max depth for tree view
        sort: Sort by: name, size, modified, created
    """
    cmd = ["eza", "--no-user", "--no-permissions"]

    if long:
        cmd.append("-l")
    if all_files:
        cmd.append("-a")
    if tree:
        cmd.extend(["--tree", f"--level={tree_depth}"])

    sort_map = {"size": "-S", "modified": "-m", "created": "-c"}
    if sort in sort_map:
        cmd.append(sort_map[sort])

    cmd.append(os.path.expanduser(path))

    result = run_command(cmd)

    if result["success"]:
        return {"success": True, "path": path, "listing": result["output"]}

    return result


# ============== TLDR (Simple Help) ==============


@mcp.tool()
def tldr_help(command: str) -> dict:
    """
    Get simplified help/examples for a command.

    Args:
        command: The command to get help for (e.g., 'git', 'ffmpeg', 'docker')
    """
    cmd = ["tldr", command]
    result = run_command(cmd)

    return {
        "success": result["success"],
        "command": command,
        "help": (
            result["output"]
            if result["success"]
            else result.get("error", "Command not found")
        ),
    }


# ============== SOX (Audio Tools) ==============


@mcp.tool()
def sox_info(file: str) -> dict:
    """
    Get detailed audio file information.

    Args:
        file: Path to audio file (wav, mp3, flac, ogg, etc.)
    """
    cmd = ["sox", "--info", os.path.expanduser(file)]
    result = run_command(cmd)

    if result["success"]:
        info = {}
        for line in result["output"].strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                info[key.strip()] = value.strip()

        return {"success": True, "file": file, "info": info}

    return result


@mcp.tool()
def sox_stats(file: str) -> dict:
    """
    Get audio statistics (RMS, peak, duration, etc.).

    Args:
        file: Path to audio file
    """
    cmd = ["sox", os.path.expanduser(file), "-n", "stats"]
    result = run_command(cmd)

    # sox outputs stats to stderr
    output = result.get("error", "") or result.get("output", "")

    stats = {}
    for line in output.strip().split("\n"):
        if ":" in line or "  " in line:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0].replace(":", "")
                stats[key] = " ".join(parts[1:])

    return {"success": True, "file": file, "stats": stats}


@mcp.tool()
def sox_convert(
    input_file: str, output_file: str, sample_rate: int = None, channels: int = None
) -> dict:
    """
    Convert audio file format.

    Args:
        input_file: Input audio file
        output_file: Output file (format determined by extension)
        sample_rate: Target sample rate (e.g., 44100, 48000)
        channels: Number of channels (1=mono, 2=stereo)
    """
    cmd = ["sox", os.path.expanduser(input_file)]

    if sample_rate:
        cmd.extend(["-r", str(sample_rate)])
    if channels:
        cmd.extend(["-c", str(channels)])

    cmd.append(os.path.expanduser(output_file))

    result = run_command(cmd)

    if result["success"]:
        return {
            "success": True,
            "input": input_file,
            "output": output_file,
            "message": "Conversion complete",
        }

    return result


@mcp.tool()
def sox_trim(
    input_file: str, output_file: str, start: str, duration: str = None
) -> dict:
    """
    Trim/cut audio file.

    Args:
        input_file: Input audio file
        output_file: Output file
        start: Start time (e.g., "0:30" or "30" for 30 seconds)
        duration: Duration to keep (e.g., "1:00" or "60")
    """
    cmd = [
        "sox",
        os.path.expanduser(input_file),
        os.path.expanduser(output_file),
        "trim",
        start,
    ]

    if duration:
        cmd.append(duration)

    result = run_command(cmd)

    if result["success"]:
        return {
            "success": True,
            "output": output_file,
            "message": f"Trimmed from {start}"
            + (f" for {duration}" if duration else ""),
        }

    return result


# ============== LAZYGIT (Git UI) ==============


@mcp.tool()
def git_status_pretty() -> dict:
    """Get formatted git status with branch info."""

    # Get branch
    branch_result = run_command(["git", "branch", "--show-current"])
    branch = branch_result["output"].strip() if branch_result["success"] else "unknown"

    # Get status
    status_result = run_command(["git", "status", "--porcelain"])

    if status_result["success"]:
        changes = {"staged": [], "modified": [], "untracked": []}

        for line in status_result["output"].strip().split("\n"):
            if line:
                status = line[:2]
                file = line[3:]

                if status[0] in "MADRC":
                    changes["staged"].append(file)
                if status[1] == "M":
                    changes["modified"].append(file)
                if status == "??":
                    changes["untracked"].append(file)

        return {
            "success": True,
            "branch": branch,
            "changes": changes,
            "summary": f"{len(changes['staged'])} staged, {len(changes['modified'])} modified, {len(changes['untracked'])} untracked",
        }

    return status_result


@mcp.tool()
def git_log_pretty(count: int = 10, oneline: bool = True) -> dict:
    """
    Get formatted git log.

    Args:
        count: Number of commits to show
        oneline: Compact format (default: True)
    """
    fmt = "--oneline" if oneline else "--format=%h %s (%cr) <%an>"
    cmd = ["git", "log", fmt, f"-{count}"]

    result = run_command(cmd)

    if result["success"]:
        commits = [c for c in result["output"].strip().split("\n") if c]
        return {"success": True, "count": len(commits), "commits": commits}

    return result


# ============== COMBINED TOOLS ==============


@mcp.tool()
def search_and_view(pattern: str, file_type: str = None) -> dict:
    """
    Search for pattern and show context from matching files.

    Args:
        pattern: Text to search for
        file_type: Filter by type: py, js, md, etc.
    """
    # First search
    search_result = rg_search(pattern, file_type=file_type, max_results=5)

    if not search_result["success"] or search_result["count"] == 0:
        return {"success": True, "message": "No matches found", "matches": []}

    # Get context for each match
    results = []
    for match in search_result["matches"][:3]:
        line_num = match["line_number"]
        start = max(1, line_num - 2)
        end = line_num + 2

        view_result = bat_view(match["file"], line_range=f"{start}:{end}")

        results.append(
            {
                "file": match["file"],
                "line": line_num,
                "context": view_result.get("content", match["text"]),
            }
        )

    return {
        "success": True,
        "total_matches": search_result["count"],
        "results": results,
    }


@mcp.tool()
def cli_tools_status() -> dict:
    """Check status of all CLI tools."""
    tools = {
        "ripgrep": ["rg", "--version"],
        "fd": ["fd", "--version"],
        "bat": ["bat", "--version"],
        "eza": ["eza", "--version"],
        "tldr": ["tldr", "--version"],
        "sox": ["sox", "--version"],
        "lazygit": ["lazygit", "--version"],
    }

    status = {}
    for name, cmd in tools.items():
        result = run_command(cmd)
        if result["success"]:
            version = result["output"].split("\n")[0].strip()
            status[name] = {"installed": True, "version": version}
        else:
            status[name] = {
                "installed": False,
                "error": result.get("error", "Not found"),
            }

    installed = sum(1 for s in status.values() if s["installed"])

    return {"success": True, "installed": f"{installed}/{len(tools)}", "tools": status}


if __name__ == "__main__":
    mcp.run()
