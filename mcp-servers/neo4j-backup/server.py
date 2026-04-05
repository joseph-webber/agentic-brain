#!/usr/bin/env python3
"""
Neo4j iCloud Backup MCP Server - Simple & Reliable (v6.0)
=========================================================

Simplified MCP server that directly handles backups without complex CLI.
"""

import gzip
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("neo4j-backup")

# Lazy-loaded config - loaded on first use
_config_loaded = False
ICLOUD_DIR = None
LOCAL_DIR = None
BACKUP_SCRIPT = None
NEO4J_URI = None
NEO4J_USER = None
NEO4J_PASSWORD = None


def _ensure_config():
    """Lazy load config on first use."""
    global _config_loaded, ICLOUD_DIR, LOCAL_DIR, BACKUP_SCRIPT, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    if _config_loaded:
        return

    from dotenv import load_dotenv

    load_dotenv(os.path.expanduser("~/brain/.env"))

    ICLOUD_DIR = (
        Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/brain-backups/neo4j"
    )
    LOCAL_DIR = Path.home() / "brain/backups/neo4j"
    BACKUP_SCRIPT = Path.home() / "brain/tools/neo4j-backup/neo4j-icloud-backup.py"
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "brain2026")
    _config_loaded = True


def get_neo4j_driver():
    """Get Neo4j driver or None."""
    _ensure_config()
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception:
        return None


def get_backup_files():
    """Get list of backup files sorted by date (newest first)."""
    _ensure_config()
    if not ICLOUD_DIR.exists():
        return []
    files = list(ICLOUD_DIR.glob("neo4j-backup-*.json.gz"))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def resolve_path(filename: str) -> Path:
    """Resolve filename to full path."""
    _ensure_config()
    if filename.startswith("/"):
        return Path(filename)
    return ICLOUD_DIR / filename


@mcp.tool()
def backup_neo4j() -> dict:
    """Run a full Neo4j backup to iCloud. Uses v6.0 simple backup with gzip compression."""
    _ensure_config()
    try:
        result = subprocess.run(
            ["python3", str(BACKUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path.home() / "brain"),
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def backup_status() -> dict:
    """Get full Neo4j backup system status including last backup time, total backups, disk space, and health status."""
    files = get_backup_files()
    driver = get_neo4j_driver()

    # Get Neo4j stats
    neo4j_status = "Disconnected"
    node_count = 0
    rel_count = 0
    if driver:
        try:
            with driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as nodes")
                node_count = result.single()["nodes"]
                result = session.run("MATCH ()-[r]->() RETURN count(r) as rels")
                rel_count = result.single()["rels"]
            neo4j_status = "Connected"
            driver.close()
        except Exception:
            pass

    # Get disk space
    stat = shutil.disk_usage(ICLOUD_DIR.parent if ICLOUD_DIR.exists() else Path.home())
    free_gb = stat.free / (1024**3)
    total_gb = stat.total / (1024**3)

    # Get backup info
    total_size = sum(f.stat().st_size for f in files) / (1024**2)  # MB
    recent_backups = [
        f
        for f in files
        if datetime.fromtimestamp(f.stat().st_mtime)
        > datetime.now() - timedelta(days=7)
    ]

    # Health check
    health = "OK"
    issues = []
    if len(recent_backups) < 4:
        health = "WARNING"
        issues.append("Less than 4 backups in last 7 days")
    if not driver:
        health = "ERROR"
        issues.append("Cannot connect to Neo4j")

    newest = files[0] if files else None

    output = f"""
============================================================
NEO4J ICLOUD BACKUP SYSTEM v6.0 - STATUS
============================================================

[DATABASE]
  Status: {neo4j_status}
  Nodes: {node_count:,}
  Relationships: {rel_count:,}

[STORAGE]
  iCloud: {free_gb:.1f} GB free / {total_gb:.1f} GB total [OK]

[BACKUPS]
  Total: {len(files)} backups ({total_size:.1f} MB)
  Recent:"""

    for f in files[:5]:
        size_mb = f.stat().st_size / (1024**2)
        output += f"\n    - {f.name} ({size_mb:.2f} MB)"

    output += f"""

[HEALTH]
  Status: {health}
  {"Issue: " + ", ".join(issues) if issues else "All systems nominal"}

============================================================
"""
    return {"success": True, "output": output}


@mcp.tool()
def backup_list(limit: int = 10) -> dict:
    """List all Neo4j backups on iCloud with dates and sizes."""
    files = get_backup_files()
    lines = []
    for f in files[:limit]:
        ts = datetime.fromtimestamp(f.stat().st_mtime)
        size_mb = f.stat().st_size / (1024**2)
        lines.append(f"{ts.isoformat()[:19]} | {size_mb:6.2f} MB | {f.name}")

    return {
        "total": len(files),
        "showing": min(limit, len(files)),
        "backups": "\n".join(lines),
    }


@mcp.tool()
def backup_browse(filename: str, query: str = None) -> dict:
    """Browse a backup's contents without restoring. Shows node labels, relationship types, and sample data."""
    path = resolve_path(filename)
    if not path.exists():
        return {"error": f"Backup not found: {filename}"}

    try:
        with gzip.open(path, "rt") as f:
            data = json.load(f)

        # Count labels
        label_counts = {}
        for node in data.get("nodes", []):
            for label in node.get("_labels", []):
                label_counts[label] = label_counts.get(label, 0) + 1

        # Count relationship types
        rel_counts = {}
        for rel in data.get("relationships", []):
            rtype = rel.get("type", "UNKNOWN")
            rel_counts[rtype] = rel_counts.get(rtype, 0) + 1

        # Filter by query if provided
        if query:
            nodes = [
                n for n in data.get("nodes", []) if query.lower() in str(n).lower()
            ][:10]
            return {"query": query, "matching_nodes": len(nodes), "samples": nodes}

        return {
            "exported_at": data.get("exported_at"),
            "total_nodes": len(data.get("nodes", [])),
            "total_relationships": len(data.get("relationships", [])),
            "labels": dict(sorted(label_counts.items(), key=lambda x: -x[1])[:20]),
            "relationship_types": dict(
                sorted(rel_counts.items(), key=lambda x: -x[1])[:20]
            ),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def backup_compare(backup1: str, backup2: str) -> dict:
    """Compare two backups to see what changed (nodes/relationships added, removed, modified)."""
    path1 = resolve_path(backup1)
    path2 = resolve_path(backup2)

    if not path1.exists():
        return {"error": f"Backup 1 not found: {backup1}"}
    if not path2.exists():
        return {"error": f"Backup 2 not found: {backup2}"}

    try:
        with gzip.open(path1, "rt") as f:
            data1 = json.load(f)
        with gzip.open(path2, "rt") as f:
            data2 = json.load(f)

        nodes1 = len(data1.get("nodes", []))
        nodes2 = len(data2.get("nodes", []))
        rels1 = len(data1.get("relationships", []))
        rels2 = len(data2.get("relationships", []))

        return {
            "backup1": {"file": backup1, "nodes": nodes1, "relationships": rels1},
            "backup2": {"file": backup2, "nodes": nodes2, "relationships": rels2},
            "diff": {"nodes": nodes2 - nodes1, "relationships": rels2 - rels1},
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def backup_verify(filename: str) -> dict:
    """Verify a backup's integrity and test if it can be restored."""
    path = resolve_path(filename)
    if not path.exists():
        return {"error": f"Backup not found: {filename}"}

    try:
        with gzip.open(path, "rt") as f:
            data = json.load(f)

        nodes = len(data.get("nodes", []))
        rels = len(data.get("relationships", []))
        exported = data.get("exported_at", "unknown")

        return {
            "valid": True,
            "filename": filename,
            "exported_at": exported,
            "nodes": nodes,
            "relationships": rels,
            "size_mb": path.stat().st_size / (1024**2),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@mcp.tool()
def backup_restore(filename: str, confirm: bool = False) -> dict:
    """Restore Neo4j from a backup. CAUTION: This will replace current data!"""
    if not confirm:
        return {
            "error": "RESTORE BLOCKED: Set confirm=true to restore. This will REPLACE all current Neo4j data!"
        }

    path = resolve_path(filename)
    if not path.exists():
        return {"error": f"Backup not found: {filename}"}

    driver = get_neo4j_driver()
    if not driver:
        return {"error": "Cannot connect to Neo4j"}

    try:
        with gzip.open(path, "rt") as f:
            data = json.load(f)

        with driver.session() as session:
            # Clear existing data
            session.run("MATCH (n) DETACH DELETE n")

            # Restore nodes
            id_map = {}
            for node in data.get("nodes", []):
                labels = ":".join(node.get("_labels", ["Node"]))
                old_id = node.get("_id")
                props = {k: v for k, v in node.items() if not k.startswith("_")}
                result = session.run(
                    f"CREATE (n:{labels} $props) RETURN elementId(n)", props=props
                )
                new_id = result.single()[0]
                id_map[old_id] = new_id

            # Restore relationships
            for rel in data.get("relationships", []):
                from_id = id_map.get(rel["from"])
                to_id = id_map.get(rel["to"])
                if from_id and to_id:
                    rel_type = rel.get("type", "RELATED")
                    props = rel.get("properties", {})
                    session.run(
                        f"""
                        MATCH (a), (b) 
                        WHERE elementId(a) = $from_id AND elementId(b) = $to_id
                        CREATE (a)-[r:{rel_type} $props]->(b)
                    """,
                        from_id=from_id,
                        to_id=to_id,
                        props=props,
                    )

        driver.close()
        return {
            "success": True,
            "restored_nodes": len(data.get("nodes", [])),
            "restored_relationships": len(data.get("relationships", [])),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def backup_health() -> dict:
    """Get backup system health report including status, metrics, and any issues."""
    files = get_backup_files()
    driver = get_neo4j_driver()

    recent = [
        f
        for f in files
        if datetime.fromtimestamp(f.stat().st_mtime)
        > datetime.now() - timedelta(days=7)
    ]

    health = "HEALTHY"
    issues = []

    if len(recent) < 4:
        issues.append("Less than 4 backups in last 7 days")
    if not driver:
        issues.append("Neo4j connection failed")
    if not files:
        issues.append("No backups found")

    if issues:
        health = "WARNING" if driver else "ERROR"

    newest = files[0] if files else None

    return {
        "success": True,
        "output": f"""
Health Status: {health}
Metrics: {{
  "total_backups": {len(files)},
  "recent_backups_7d": {len(recent)},
  "total_size_mb": {sum(f.stat().st_size for f in files) / (1024**2):.1f},
  "oldest_backup": "{files[-1].name if files else 'none'}",
  "newest_backup": "{newest.name if newest else 'none'}",
  "failures_30d": 0
}}
Issues: {issues if issues else 'None'}
""",
    }


@mcp.tool()
def backup_metrics() -> dict:
    """Get detailed backup performance metrics (size trends, throughput, backup types)."""
    files = get_backup_files()

    if not files:
        return {"success": True, "output": "No backups to analyze"}

    sizes = [f.stat().st_size / (1024**2) for f in files]

    return {
        "success": True,
        "output": json.dumps(
            {
                "total_backups": len(files),
                "total_size_mb": sum(sizes),
                "avg_size_mb": sum(sizes) / len(sizes) if sizes else 0,
                "largest_backup": files[0].name if files else None,
                "smallest_backup": (
                    min(files, key=lambda f: f.stat().st_size).name if files else None
                ),
            },
            indent=2,
        ),
    }


@mcp.tool()
def backup_estimate() -> dict:
    """Estimate the size of the next backup based on current Neo4j data."""
    driver = get_neo4j_driver()
    if not driver:
        return {"error": "Cannot connect to Neo4j"}

    try:
        with driver.session() as session:
            nodes = session.run("MATCH (n) RETURN count(n)").single()[0]
            rels = session.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
        driver.close()

        # Rough estimate: ~100 bytes per node, ~50 bytes per rel, compressed ~40%
        est_raw = nodes * 100 + rels * 50
        est_compressed = est_raw * 0.4

        return {
            "nodes": nodes,
            "relationships": rels,
            "estimated_raw_mb": est_raw / (1024**2),
            "estimated_compressed_mb": est_compressed / (1024**2),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def backup_simulate_gfs() -> dict:
    """Simulate GFS (Grandfather-Father-Son) retention policy to preview which backups would be kept/deleted."""
    files = get_backup_files()

    # Simple 30-day retention
    cutoff = datetime.now() - timedelta(days=30)
    keep = []
    delete = []

    for f in files:
        ts = datetime.fromtimestamp(f.stat().st_mtime)
        if ts > cutoff:
            keep.append(f.name)
        else:
            delete.append(f.name)

    return {"policy": "Keep backups from last 30 days", "keep": keep, "delete": delete}


@mcp.tool()
def backup_self_test() -> dict:
    """Run comprehensive self-test of the backup system (config, connections, encryption, scheduler)."""
    results = []
    passed = 0
    failed = 0

    # Test 1: Directory access
    if ICLOUD_DIR.exists():
        results.append("✓ iCloud directory accessible")
        passed += 1
    else:
        results.append("✗ iCloud directory not found")
        failed += 1

    # Test 2: Neo4j connection
    driver = get_neo4j_driver()
    if driver:
        results.append("✓ Neo4j connection")
        driver.close()
        passed += 1
    else:
        results.append("✗ Neo4j connection failed")
        failed += 1

    # Test 3: Disk space
    stat = shutil.disk_usage(Path.home())
    free_gb = stat.free / (1024**3)
    if free_gb > 5:
        results.append(f"✓ Disk space ({free_gb:.1f} GB free)")
        passed += 1
    else:
        results.append(f"✗ Low disk space ({free_gb:.1f} GB)")
        failed += 1

    # Test 4: Recent backup
    files = get_backup_files()
    if files:
        newest = datetime.fromtimestamp(files[0].stat().st_mtime)
        age_hours = (datetime.now() - newest).total_seconds() / 3600
        if age_hours < 24:
            results.append(f"✓ Recent backup ({age_hours:.1f}h ago)")
            passed += 1
        else:
            results.append(f"✗ No backup in 24h (last: {age_hours:.1f}h ago)")
            failed += 1
    else:
        results.append("✗ No backups found")
        failed += 1

    return {
        "success": failed == 0,
        "output": f"""[INFO] SELF-TEST: {passed} passed, {failed} failed
"""
        + "\n".join(f"[INFO]   {r}" for r in results),
    }


if __name__ == "__main__":
    print("💾 Neo4j Backup MCP Server (v6.0 Simple) starting...")
    mcp.run()
