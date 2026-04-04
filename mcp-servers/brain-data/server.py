#!/usr/bin/env python3
"""
Brain Data MCP Server - Ultimate Edition v2.0
==============================================

Full Core Data access for Claude via MCP protocol.

CATEGORIES:
1. Neo4j Data Tools (12 tools)
2. JIRA API Tools (5 tools) 
3. BitBucket API Tools (4 tools)
4. Brain Health Tools (3 tools)
5. Sync & Management (2 tools)
6. Observer Tools (4 tools)
7. Event Tools (4 tools)
8. Orchestrator Tools (6 tools)
9. FreqTrade Tools (6 tools)
10. Cerberus Tools (5 tools) - NEW!
11. Hermes Tools (6 tools) - NEW!
12. Neo4j Backup Quick (3 tools) - NEW!

Total: 60 tools for complete brain access!

Start with: python server.py
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser('~/brain'))

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/brain/.env'))

# MCP protocol
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# LAZY IMPORTS - All Neo4j and heavy modules loaded on first use
# This allows server to start INSTANTLY even if Neo4j is down

# Fuzzy search - lazy loaded (takes ~2s to import)
_fuzzy_loaded = False
fuzzy_match = fuzzy_filter = fuzzy_best = fuzzy_ratio = None

def _load_fuzzy():
    global _fuzzy_loaded, fuzzy_match, fuzzy_filter, fuzzy_best, fuzzy_ratio
    if not _fuzzy_loaded:
        from brain_core.fuzzy_search import fuzzy_match as fm, fuzzy_filter as ff, fuzzy_best as fb, fuzzy_ratio as fr
        fuzzy_match, fuzzy_filter, fuzzy_best, fuzzy_ratio = fm, ff, fb, fr
        _fuzzy_loaded = True

# Core Speech System - lazy loaded
_speech = None
def get_brain_speech():
    global _speech
    if _speech is None:
        try:
            import warnings
            warnings.filterwarnings('ignore')
            from core.speech.brain_speech import get_speech
            _speech = get_speech()
        except ImportError:
            return None
    return _speech


# Create MCP server
server = Server("brain-data")

# Lazy-loaded instances
_core = None
_brain_data = None
_neo4j_brain = None
_neo4j_advanced = None
_neo4j_smart = None
_observer = None
_events = None
_orchestrator = None
_freqtrade = None


def get_core():
    """Lazy load CoreData - connects to Neo4j on first use."""
    global _core
    if _core is None:
        from core_data.core import CoreData
        _core = CoreData()
    return _core


def get_brain_data():
    """Lazy load brain_data module."""
    global _brain_data
    if _brain_data is None:
        from core_data.neo4j_claude import brain_data
        _brain_data = brain_data
    return _brain_data


def get_neo4j_brain():
    """Lazy load Neo4jBrain."""
    global _neo4j_brain
    if _neo4j_brain is None:
        from core_data.neo4j_integration import Neo4jBrain
        _neo4j_brain = Neo4jBrain()
    return _neo4j_brain


def get_neo4j_advanced():
    """Lazy load Neo4jAdvanced."""
    global _neo4j_advanced
    if _neo4j_advanced is None:
        from core_data.neo4j_advanced import Neo4jAdvanced
        _neo4j_advanced = Neo4jAdvanced()
    return _neo4j_advanced


def get_neo4j_smart():
    """Lazy load Neo4jSmart."""
    global _neo4j_smart
    if _neo4j_smart is None:
        from core_data.neo4j_smart import get_smart
        _neo4j_smart = get_smart()
    return _neo4j_smart


def get_observer_instance():
    """Lazy load unified observer."""
    global _observer
    if _observer is None:
        from core_data.unified_observer import get_observer
        _observer = get_observer()
    return _observer


def get_events_instance():
    """Lazy load event system."""
    global _events
    if _events is None:
        from core_data.event_system import get_events
        _events = get_events()
    return _events


def get_orchestrator():
    """Lazy load orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        from core_data.orchestrator_integration import brain_orchestrator
        _orchestrator = brain_orchestrator
    return _orchestrator


def get_freqtrade_instance():
    """Lazy load freqtrade."""
    global _freqtrade
    if _freqtrade is None:
        from core_data.freqtrade import get_freqtrade
        _freqtrade = get_freqtrade()
    return _freqtrade


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available brain data tools - 26 total."""
    return [
        # ===== NEO4J DATA TOOLS (12) =====
        Tool(
            name="brain_ask",
            description="Ask any question about brain data in natural language. Examples: 'emails from Steve', 'sage failures this week', 'what jira tickets are open?'",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Natural language question about the data"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="brain_emails",
            description="Get emails from Neo4j. Filter by sender or subject.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sender": {"type": "string", "description": "Filter by sender (partial match)"},
                    "subject": {"type": "string", "description": "Filter by subject (partial match)"},
                    "limit": {"type": "integer", "description": "Max results (default 20)"}
                }
            }
        ),
        Tool(
            name="brain_jira",
            description="Get JIRA tickets from Neo4j cache. Filter by status or assignee.",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status (e.g., 'In Progress', 'To Do')"},
                    "assignee": {"type": "string", "description": "Filter by assignee name"}
                }
            }
        ),
        Tool(
            name="brain_teams",
            description="Get Teams messages from Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "contains": {"type": "string", "description": "Filter by text content"},
                    "sender": {"type": "string", "description": "Filter by sender"}
                }
            }
        ),
        Tool(
            name="teams_send",
            description="Send a Microsoft Teams message to someone via Safari automation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "Name of person to message (e.g., 'Steve Taylor')"},
                    "message": {"type": "string", "description": "The message to send"}
                },
                "required": ["recipient", "message"]
            }
        ),
        Tool(
            name="brain_sage",
            description="Get Sage/Intacct failures from Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Failures in last N days (default 30)"}
                }
            }
        ),
        Tool(
            name="brain_search",
            description="Search across all data types (emails, teams, jira) for a term. Uses fuzzy matching for typo tolerance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Search term (typos OK - fuzzy matched)"},
                    "fuzzy_threshold": {"type": "integer", "description": "Fuzzy match threshold 0-100 (default 70)"}
                },
                "required": ["term"]
            }
        ),
        Tool(
            name="brain_status",
            description="Get full Neo4j database status - total nodes (9583+), all labels, top counts.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="brain_anomalies",
            description="Detect anomalies in the data - Sage spikes, stale tickets, missing emails.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="brain_digest",
            description="Generate weekly digest summary of all activity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "weeks_ago": {"type": "integer", "description": "0 for current week, 1 for last week, etc."}
                }
            }
        ),
        Tool(
            name="brain_who",
            description="Find who talked about a specific topic across emails and teams.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search for"}
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="brain_timeline",
            description="Get a chronological timeline of activity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to look back (default 7)"},
                    "types": {"type": "string", "description": "Comma-separated types: email,teams,jira,sage"}
                }
            }
        ),
        Tool(
            name="brain_query",
            description="Run raw Cypher query on Neo4j (advanced users).",
            inputSchema={
                "type": "object",
                "properties": {
                    "cypher": {"type": "string", "description": "Cypher query to execute"}
                },
                "required": ["cypher"]
            }
        ),
        
        # ===== JIRA API TOOLS (5) =====
        Tool(
            name="jira_get_ticket",
            description="Get a JIRA ticket by key (e.g., SD-1330). Returns full ticket details from live JIRA API.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "JIRA ticket key (e.g., SD-1330)"}
                },
                "required": ["key"]
            }
        ),
        Tool(
            name="jira_search",
            description="Search JIRA tickets with JQL query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string", "description": "JQL query (e.g., 'assignee = steve.taylor AND status = \"In Progress\"')"},
                    "max_results": {"type": "integer", "description": "Max results (default 50)"}
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="jira_create_ticket",
            description="Create a new JIRA ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Ticket summary/title"},
                    "description": {"type": "string", "description": "Ticket description"},
                    "issue_type": {"type": "string", "description": "Bug, Story, or Task (default Bug)"},
                    "priority": {"type": "string", "description": "Highest, High, Medium, Low, Lowest"},
                    "assignee": {"type": "string", "description": "Assignee username"}
                },
                "required": ["summary"]
            }
        ),
        Tool(
            name="jira_add_comment",
            description="Add a comment to a JIRA ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "JIRA ticket key (e.g., SD-1330)"},
                    "comment": {"type": "string", "description": "Comment text (plain text, not ADF)"}
                },
                "required": ["key", "comment"]
            }
        ),
        Tool(
            name="jira_sprint_status",
            description="Get current sprint status - all tickets, progress, blockers.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== BITBUCKET API TOOLS (4) =====
        Tool(
            name="bitbucket_get_pr",
            description="Get a BitBucket pull request by number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "PR number (e.g., 220)"}
                },
                "required": ["pr_number"]
            }
        ),
        Tool(
            name="bitbucket_list_prs",
            description="List BitBucket pull requests. Filter by state and author.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "OPEN, MERGED, DECLINED (default OPEN)"},
                    "author": {"type": "string", "description": "Filter by author username"}
                }
            }
        ),
        Tool(
            name="bitbucket_pr_diff",
            description="Get the diff/changes for a pull request.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pr_number": {"type": "integer", "description": "PR number"}
                },
                "required": ["pr_number"]
            }
        ),
        Tool(
            name="bitbucket_recent_commits",
            description="Get recent commits from a branch.",
            inputSchema={
                "type": "object",
                "properties": {
                    "branch": {"type": "string", "description": "Branch name (default: main)"},
                    "limit": {"type": "integer", "description": "Number of commits (default 20)"}
                }
            }
        ),
        
        # ===== BRAIN HEALTH TOOLS (3) =====
        Tool(
            name="brain_health",
            description="Check brain health - Neo4j connection, API availability, data freshness.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="brain_freshness",
            description="Check how fresh the data is - when was each data source last synced?",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="brain_metrics",
            description="Get brain performance metrics - query times, cache hits, sync stats.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== SYNC & MANAGEMENT (2) =====
        Tool(
            name="brain_sync",
            description="Sync all data files to Neo4j (emails, teams, sage).",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="brain_sync_selective",
            description="Sync specific data types only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "types": {"type": "string", "description": "Comma-separated: emails,teams,sage,jira"}
                },
                "required": ["types"]
            }
        ),
        
        # ===== OBSERVER TOOLS (4) =====
        Tool(
            name="observer_health",
            description="Get health status of ALL Core Data services (jira, bitbucket, outlook, teams, sage, mysql, ssh, neo4j, ebay).",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="observer_insights",
            description="Get learning insights - which methods are failing, recommendations for improvement.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="observer_best_method",
            description="Get the best method for a service action based on historical success rates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name: jira, bitbucket, outlook, teams, sage, mysql, ssh, neo4j, ebay"},
                    "action": {"type": "string", "description": "Action name: get_ticket, get_pr, get_emails, query, etc."}
                },
                "required": ["service", "action"]
            }
        ),
        Tool(
            name="observer_failures",
            description="Get recent failures across all services.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Look back hours (default 24)"}
                }
            }
        ),
        
        # ===== EVENT TOOLS (4) =====
        Tool(
            name="event_emit",
            description="Emit a brain event. Triggers handlers and logs to Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Event type (e.g., 'jira.ticket.created', 'sage.failure.detected')"},
                    "data": {"type": "object", "description": "Event data (key-value pairs)"}
                },
                "required": ["event_type"]
            }
        ),
        Tool(
            name="event_history",
            description="Get event history, optionally filtered by type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Filter by event type"},
                    "days": {"type": "integer", "description": "Days to look back (default 7)"}
                }
            }
        ),
        Tool(
            name="event_stats",
            description="Get event statistics - counts by type, subscriber info.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="event_types",
            description="List all known event types the brain can handle.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== ORCHESTRATOR TOOLS (6) =====
        Tool(
            name="skill_run",
            description="Run a brain skill. Examples: 'review-assassin', 'cerberus', 'standup'",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {"type": "string", "description": "Skill name (e.g., review-assassin, cerberus, standup)"},
                    "args": {"type": "string", "description": "Arguments as space-separated string"}
                },
                "required": ["skill"]
            }
        ),
        Tool(
            name="workflow_run",
            description="Run a multi-step workflow. Examples: 'review', 'check-stale-prs', 'pre-push'",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow": {"type": "string", "description": "Workflow name (e.g., review, check-stale-prs, pre-push, daily-summary)"}
                },
                "required": ["workflow"]
            }
        ),
        Tool(
            name="skill_list",
            description="List all available brain skills, optionally by category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Category filter (e.g., handlers, tools, automation)"}
                }
            }
        ),
        Tool(
            name="workflow_list",
            description="List all available workflows and their steps.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="orchestrator_status",
            description="Get full orchestrator status - health, recent executions, event stats.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="speak",
            description="Speak a message using the brain's core speech system with voice profiles.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to speak"},
                    "voice": {"type": "string", "description": "Voice: zara (warm lead), echo (tech expert), sage (wise mentor), spark (hype), ghost (mysterious), nova, rishi, robot, whisper, bells. Default: zara"},
                    "emotion": {"type": "string", "description": "Emotion: neutral, excited, calm, concerned, celebratory, mysterious, urgent. Default: neutral"}
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="audio_celebrate",
            description="Play celebration with sound and speech! For task completion, milestones, wins.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Celebration message (default: Great job!)"}
                }
            }
        ),
        Tool(
            name="audio_greet",
            description="Time-appropriate greeting from the brain (Good morning/afternoon/evening Joseph!).",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="audio_sound",
            description="Play a system sound effect.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sound": {"type": "string", "description": "Sound: hero, glass, ping, funk, basso, purr, pop, tink, submarine, sosumi, blow, bottle, complete, success, warning, error"}
                },
                "required": ["sound"]
            }
        ),
        Tool(
            name="audio_voices",
            description="List all available voice profiles.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== FREQTRADE TOOLS (6) =====
        Tool(
            name="freqtrade_bots",
            description="List all FreqTrade trading bots with status.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="freqtrade_trades",
            description="Get trades for a specific bot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bot": {"type": "string", "description": "Bot name (e.g., degen_v3, champion, whale)"},
                    "limit": {"type": "integer", "description": "Max trades to return (default 50)"},
                    "days": {"type": "integer", "description": "Only trades from last N days"}
                },
                "required": ["bot"]
            }
        ),
        Tool(
            name="freqtrade_performance",
            description="Get performance metrics for a bot (win rate, profit, best/worst trade).",
            inputSchema={
                "type": "object",
                "properties": {
                    "bot": {"type": "string", "description": "Bot name (or 'all' for all bots)"},
                    "days": {"type": "integer", "description": "Period in days (default 30)"}
                },
                "required": ["bot"]
            }
        ),
        Tool(
            name="freqtrade_open_trades",
            description="Get currently open trades for a bot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "bot": {"type": "string", "description": "Bot name"}
                },
                "required": ["bot"]
            }
        ),
        Tool(
            name="freqtrade_daily",
            description="Get daily trading summary across all bots.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="freqtrade_sync",
            description="Sync FreqTrade data to Neo4j brain memory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days of history to sync (default 30)"}
                }
            }
        ),
        
        # ===== CERBERUS TOOLS (5) - Code Quality Guardian =====
        Tool(
            name="cerberus_qa",
            description="Run Cerberus QA - the three-headed guardian checks for gremlins (Fury), security issues (Storm), and process compliance (Tide). Returns pass/fail with detailed issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to repository (default: citb-talas)"}
                }
            }
        ),
        Tool(
            name="cerberus_fury",
            description="Run Fury head only - checks for gremlins, line endings (CRLF→LF), whitespace, tabs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to repository"}
                }
            }
        ),
        Tool(
            name="cerberus_storm",
            description="Run Storm head only - security scan for SQL injection, XSS, hardcoded secrets, vulnerabilities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to repository"}
                }
            }
        ),
        Tool(
            name="cerberus_tide",
            description="Run Tide head only - process compliance, Steve's rules, JIRA ticket association, tests.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to repository"},
                    "ticket": {"type": "string", "description": "JIRA ticket (e.g., SD-1330)"}
                }
            }
        ),
        Tool(
            name="cerberus_status",
            description="Get Cerberus guardian status - last run results, total checks, pass rate.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== HERMES TOOLS (6) - Communication Oracle =====
        Tool(
            name="hermes_oracle",
            description="Consult Hermes oracle - queries Neo4j for ALL communications about a topic across emails, Teams, JIRA.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search for (e.g., 'SD-1330', 'Intacct', 'Steve')"}
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="hermes_concerns",
            description="Find unanswered concerns or questions in communications that need attention.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to search (default 7)"}
                }
            }
        ),
        Tool(
            name="hermes_steve",
            description="Get all recent communications with/about Steve Taylor for context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to search (default 7)"}
                }
            }
        ),
        Tool(
            name="hermes_prepare_jira",
            description="Prepare a professional, VoiceOver-friendly JIRA comment for a ticket.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "string", "description": "JIRA ticket key (e.g., SD-1330)"},
                    "content": {"type": "string", "description": "Key points to include in comment"},
                    "status": {"type": "string", "description": "Update status: investigating, in_progress, complete, blocked"}
                },
                "required": ["ticket", "content"]
            }
        ),
        Tool(
            name="hermes_prepare_pr",
            description="Prepare a professional PR description linking JIRA ticket to code changes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "string", "description": "JIRA ticket key"},
                    "changes": {"type": "string", "description": "Summary of code changes"},
                    "test_info": {"type": "string", "description": "Testing information"}
                },
                "required": ["ticket", "changes"]
            }
        ),
        Tool(
            name="hermes_deliver",
            description="Deliver prepared communications - posts JIRA comment and/or creates PR.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "What to deliver: 'jira', 'pr', 'both'"},
                    "ticket": {"type": "string", "description": "JIRA ticket key"},
                    "content": {"type": "string", "description": "Content to deliver"}
                },
                "required": ["action", "ticket", "content"]
            }
        ),
        
        # ===== NEO4J BACKUP TOOLS (3) - Quick access =====
        Tool(
            name="neo4j_backup_now",
            description="Run immediate Neo4j backup to iCloud with full verification.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="neo4j_backup_status",
            description="Get Neo4j backup status - last backup, total backups, disk space, health.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="neo4j_backup_list",
            description="List recent Neo4j backups.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max backups to show (default 5)"}
                }
            }
        ),
        
        # ===== QA TOOLS (10) - Unified Quality Assurance =====
        Tool(
            name="qa_quick",
            description="Quick QA status - PRs, JIRA, blockers in one call. Siri-friendly audio output.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_next",
            description="What should I work on next? Prioritized recommendations with audio.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_blockers",
            description="Get current blockers with AI suggestions on how to fix them.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_health",
            description="Full health check - Neo4j, JIRA, Git, services. Audio summary.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_pr_summary",
            description="PR summary - awaiting me, awaiting Steve, status of all open PRs.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_jira_summary",
            description="JIRA summary - in progress, sprint status, top priorities.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_git",
            description="Git QA - current branch, status, recent commits, diff summary.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "status, branch, commits, diff, stash"}
                }
            }
        ),
        Tool(
            name="qa_kb",
            description="Knowledge Base - paths, links, docker commands, credentials, ssh hosts. Single source of truth.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "paths, links, docker, creds, ssh, find, all"},
                    "search": {"type": "string", "description": "Search term for 'find' category"}
                }
            }
        ),
        Tool(
            name="qa_citb",
            description="CITB-specific QA - known ticket patterns, entity checks, deployment checklist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "tickets, entity, deploy, check"},
                    "ticket": {"type": "string", "description": "Ticket key for context lookup"}
                }
            }
        ),
        Tool(
            name="qa_java",
            description="Java code review - clean code principles, CITB patterns, common issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "review, principles, patterns, help"},
                    "file": {"type": "string", "description": "Java file to review"}
                }
            }
        ),
        Tool(
            name="qa_uat",
            description="UAT deployment & testing checker (Steve's process). Checks version deployed, evidence screenshots, JIRA status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {"type": "string", "description": "JIRA ticket (e.g., SD-1330)"},
                    "pr": {"type": "integer", "description": "PR number (optional)"},
                    "action": {"type": "string", "description": "check, steps, env, checklist"}
                },
                "required": ["ticket"]
            }
        ),
        Tool(
            name="qa_uat_steps",
            description="Get UAT deployment steps - Jenkins build, EAR deployment, verification.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="qa_uat_env",
            description="Get UAT environment info - server, URLs, ports, Jenkins.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # ===== SESSION CONTINUITY TOOLS (8) - Claude-Native Session Management =====
        Tool(
            name="continuity_save",
            description="Save session state for restart. Stores in plan.md, SQL, Neo4j, and iCloud. Use when user says 'wrap it up', 'time for restart', or 'park this'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What we're currently working on"},
                    "todos": {"type": "array", "description": "List of todo objects with id, title, priority, status"},
                    "blockers": {"type": "array", "description": "List of blocker strings"},
                    "learnings": {"type": "array", "description": "Key things learned this session"},
                    "investigations": {"type": "array", "description": "What was investigated/researched"}
                },
                "required": ["description"]
            }
        ),
        Tool(
            name="continuity_recover",
            description="Recover from last session. Shows plan.md, pending todos, git status, Neo4j context. Use on session start.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="continuity_status",
            description="Show current session continuity status - plan exists, todo counts, checkpoints, Neo4j connection.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="continuity_context",
            description="Get Neo4j context - recent sessions, pending todos across all sessions, learnings, related tickets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic to search for in emails/Teams"},
                    "days": {"type": "integer", "description": "Days of history (default 7)"}
                }
            }
        ),
        Tool(
            name="continuity_todo_add",
            description="Add a todo to the session. Stores in SQL and Neo4j for cross-session tracking.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Todo ID (kebab-case, e.g., 'fix-login-bug')"},
                    "title": {"type": "string", "description": "Todo title"},
                    "description": {"type": "string", "description": "Detailed description"},
                    "priority": {"type": "integer", "description": "Priority 1-5 (1=highest)"},
                    "depends_on": {"type": "array", "description": "List of todo IDs this depends on"}
                },
                "required": ["id", "title"]
            }
        ),
        Tool(
            name="continuity_todo_done",
            description="Mark a todo as done. Updates SQL and Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Todo ID to mark done"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="continuity_checkpoint",
            description="Create a checkpoint without full save. Quick state snapshot for recovery points.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Brief checkpoint description"}
                },
                "required": ["description"]
            }
        ),
        Tool(
            name="continuity_history",
            description="View checkpoint history - all session saves with timestamps and todo counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of checkpoints to show (default 10)"}
                }
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute a brain data tool."""
    try:
        result = None
        
        # ===== NEO4J DATA TOOLS =====
        if name == "brain_ask":
            result = get_brain_data().ask(arguments["question"])
        
        elif name == "brain_emails":
            result = get_brain_data().emails(
                sender=arguments.get("sender"),
                subject=arguments.get("subject"),
                limit=arguments.get("limit", 20)
            )
        
        elif name == "brain_jira":
            result = get_brain_data().jira(
                status=arguments.get("status"),
                assignee=arguments.get("assignee")
            )
        
        elif name == "brain_teams":
            result = get_brain_data().teams(
                contains=arguments.get("contains"),
                sender=arguments.get("sender")
            )
        
        elif name == "teams_send":
            # Send Teams message via core_data
            try:
                import sys
                sys.path.insert(0, os.path.expanduser("~/brain"))
                from core_data.teams import get_teams
                teams = get_teams()
                result = teams.send_message(
                    recipient=arguments["recipient"],
                    message=arguments["message"]
                )
            except Exception as e:
                result = {"success": False, "error": str(e)}
        
        elif name == "brain_sage":
            result = get_brain_data().sage(days=arguments.get("days", 30))
        
        elif name == "brain_search":
            term = arguments["term"]
            threshold = arguments.get("fuzzy_threshold", 70)
            raw_results = get_brain_data().search(term)
            
            # Apply fuzzy filtering to results if they have searchable text
            if isinstance(raw_results, dict):
                _load_fuzzy()  # Lazy load fuzzy search
                for key in ['emails', 'teams', 'jira', 'results']:
                    if key in raw_results and isinstance(raw_results[key], list):
                        items = raw_results[key]
                        if items and len(items) > 0:
                            # Extract text fields and fuzzy rank
                            def get_text(item):
                                if isinstance(item, dict):
                                    return ' '.join(str(v) for v in item.values() if isinstance(v, str))
                                return str(item)
                            
                            # Score and filter
                            scored = []
                            for item in items:
                                text = get_text(item)
                                score = fuzzy_ratio(term, text)
                                if score >= threshold:
                                    if isinstance(item, dict):
                                        item['_fuzzy_score'] = round(score)
                                    scored.append((item, score))
                            
                            # Sort by score
                            scored.sort(key=lambda x: x[1], reverse=True)
                            raw_results[key] = [item for item, _ in scored]
                
                raw_results['fuzzy_enabled'] = True
                raw_results['fuzzy_threshold'] = threshold
            result = raw_results
        
        elif name == "brain_status":
            result = get_brain_data().status()
        
        elif name == "brain_anomalies":
            adv = get_neo4j_advanced()
            result = adv.detect_anomalies()
        
        elif name == "brain_digest":
            adv = get_neo4j_advanced()
            result = adv.generate_weekly_digest(arguments.get("weeks_ago", 0))
        
        elif name == "brain_who":
            adv = get_neo4j_advanced()
            result = adv.who_talked_about(arguments["topic"])
        
        elif name == "brain_timeline":
            days = arguments.get("days", 7)
            types_str = arguments.get("types", "email,teams,jira,sage")
            types = [t.strip() for t in types_str.split(",")]
            adv = get_neo4j_advanced()
            result = adv.get_timeline(days=days, types=types) if hasattr(adv, 'get_timeline') else {"error": "timeline not implemented"}
        
        elif name == "brain_query":
            result = get_brain_data().query(arguments["cypher"])
        
        elif name == "brain_sync":
            neo = get_neo4j_brain()
            result = neo.sync_all()
        
        elif name == "brain_sync_selective":
            types_str = arguments["types"]
            types = [t.strip() for t in types_str.split(",")]
            neo = get_neo4j_brain()
            results = {}
            for t in types:
                if t == "emails":
                    results["emails"] = neo.sync_emails() if hasattr(neo, 'sync_emails') else "not implemented"
                elif t == "teams":
                    results["teams"] = neo.sync_teams() if hasattr(neo, 'sync_teams') else "not implemented"
                elif t == "sage":
                    results["sage"] = neo.sync_sage() if hasattr(neo, 'sync_sage') else "not implemented"
            result = results
        
        # ===== JIRA API TOOLS =====
        elif name == "jira_get_ticket":
            core = get_core()
            ticket = core.jira.get_ticket(arguments["key"])
            result = {
                "key": ticket.get("key"),
                "summary": ticket.get("fields", {}).get("summary"),
                "status": ticket.get("fields", {}).get("status", {}).get("name"),
                "assignee": ticket.get("fields", {}).get("assignee", {}).get("displayName") if ticket.get("fields", {}).get("assignee") else None,
                "priority": ticket.get("fields", {}).get("priority", {}).get("name"),
                "description": ticket.get("fields", {}).get("description"),
                "created": ticket.get("fields", {}).get("created"),
                "updated": ticket.get("fields", {}).get("updated"),
            }
        
        elif name == "jira_search":
            core = get_core()
            tickets = core.jira.search_tickets(
                jql=arguments["jql"],
                max_results=arguments.get("max_results", 50)
            )
            result = [{
                "key": t.get("key"),
                "summary": t.get("fields", {}).get("summary"),
                "status": t.get("fields", {}).get("status", {}).get("name"),
                "assignee": t.get("fields", {}).get("assignee", {}).get("displayName") if t.get("fields", {}).get("assignee") else None,
            } for t in tickets.get("issues", [])]
        
        elif name == "jira_create_ticket":
            core = get_core()
            key = core.jira.create_ticket(
                summary=arguments["summary"],
                description=arguments.get("description", ""),
                issue_type=arguments.get("issue_type", "Bug"),
                priority=arguments.get("priority"),
                assignee=arguments.get("assignee")
            )
            result = {"created": key, "url": f"https://citb.atlassian.net/browse/{key}"}
        
        elif name == "jira_add_comment":
            core = get_core()
            core.jira.add_comment(arguments["key"], arguments["comment"])
            result = {"success": True, "ticket": arguments["key"]}
        
        elif name == "jira_sprint_status":
            core = get_core()
            # Get current sprint tickets
            jql = 'project = SD AND sprint in openSprints() ORDER BY status'
            tickets = core.jira.search_tickets(jql=jql, max_results=100)
            
            # Categorize by status
            by_status = {}
            for t in tickets.get("issues", []):
                status = t.get("fields", {}).get("status", {}).get("name", "Unknown")
                if status not in by_status:
                    by_status[status] = []
                by_status[status].append({
                    "key": t.get("key"),
                    "summary": t.get("fields", {}).get("summary"),
                    "assignee": t.get("fields", {}).get("assignee", {}).get("displayName") if t.get("fields", {}).get("assignee") else None,
                })
            
            result = {
                "total_tickets": len(tickets.get("issues", [])),
                "by_status": by_status,
                "summary": {s: len(v) for s, v in by_status.items()}
            }
        
        # ===== BITBUCKET API TOOLS =====
        elif name == "bitbucket_get_pr":
            core = get_core()
            pr = core.bitbucket.get_pull_request(arguments["pr_number"])
            result = {
                "id": pr.get("id"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "author": pr.get("author", {}).get("display_name"),
                "source_branch": pr.get("source", {}).get("branch", {}).get("name"),
                "destination_branch": pr.get("destination", {}).get("branch", {}).get("name"),
                "created": pr.get("created_on"),
                "updated": pr.get("updated_on"),
            }
        
        elif name == "bitbucket_list_prs":
            core = get_core()
            state = arguments.get("state", "OPEN")
            prs = core.bitbucket.get_pull_requests(state=state)
            
            # Filter by author if specified
            author = arguments.get("author")
            if author:
                prs = [p for p in prs if author.lower() in p.get("author", {}).get("display_name", "").lower()]
            
            result = [{
                "id": p.get("id"),
                "title": p.get("title"),
                "state": p.get("state"),
                "author": p.get("author", {}).get("display_name"),
                "source_branch": p.get("source", {}).get("branch", {}).get("name"),
            } for p in prs[:20]]
        
        elif name == "bitbucket_pr_diff":
            core = get_core()
            pr = core.bitbucket.get_pull_request(arguments["pr_number"])
            # Get diff from PR - it might be in diffstat or we need separate call
            diff_url = pr.get("links", {}).get("diff", {}).get("href")
            result = {"pr_id": arguments["pr_number"], "diff_url": diff_url, "note": "Use diff_url to fetch full diff"}
        
        elif name == "bitbucket_recent_commits":
            core = get_core()
            # Use a ticket-based commit lookup or list recent
            # For now, return a helpful message
            result = {"note": "Use get_commits_for_ticket(ticket_key) for ticket-specific commits"}
        
        # ===== BRAIN HEALTH TOOLS =====
        elif name == "brain_health":
            health = {"status": "healthy", "checks": {}}
            
            # Check Neo4j
            try:
                status = get_brain_data().status()
                health["checks"]["neo4j"] = {
                    "status": "ok",
                    "nodes": status.get("total_nodes", 0),
                    "labels": status.get("total_labels", 0)
                }
            except Exception as e:
                health["checks"]["neo4j"] = {"status": "error", "error": str(e)}
                health["status"] = "degraded"
            
            # Check JIRA
            try:
                core = get_core()
                core.jira.get_ticket("SD-1")
                health["checks"]["jira"] = {"status": "ok"}
            except Exception as e:
                health["checks"]["jira"] = {"status": "error", "error": str(e)}
                health["status"] = "degraded"
            
            # Check BitBucket
            try:
                core = get_core()
                core.bitbucket.list_pull_requests(state="OPEN")
                health["checks"]["bitbucket"] = {"status": "ok"}
            except Exception as e:
                health["checks"]["bitbucket"] = {"status": "error", "error": str(e)}
                health["status"] = "degraded"
            
            result = health
        
        elif name == "brain_freshness":
            # Check when data files were last modified
            files_to_check = [
                ("outlook-brute-force-data.json", "emails"),
                ("teams-fresh-20260211-172143.txt", "teams"),
                ("velocity-history.json", "velocity"),
            ]
            
            freshness = {}
            brain_path = os.path.expanduser("~/brain")
            
            for filename, data_type in files_to_check:
                filepath = os.path.join(brain_path, filename)
                if os.path.exists(filepath):
                    mtime = os.path.getmtime(filepath)
                    mod_time = datetime.fromtimestamp(mtime)
                    age = datetime.now() - mod_time
                    freshness[data_type] = {
                        "file": filename,
                        "last_modified": mod_time.isoformat(),
                        "age_hours": round(age.total_seconds() / 3600, 1)
                    }
                else:
                    freshness[data_type] = {"file": filename, "status": "not found"}
            
            result = freshness
        
        elif name == "brain_metrics":
            # Get query metrics from hardened neo4j if available
            from core_data.neo4j_hardened import Neo4jHardened
            
            neo = Neo4jHardened()
            metrics = {
                "neo4j": {
                    "pool_size": neo._pool_size if hasattr(neo, '_pool_size') else "unknown",
                    "cache_ttl": neo._cache_ttl if hasattr(neo, '_cache_ttl') else "unknown",
                    "retry_count": neo._retry_count if hasattr(neo, '_retry_count') else "unknown",
                },
                "queries": {
                    "cached_queries": len(neo._cache._cache) if hasattr(neo, '_cache') and hasattr(neo._cache, '_cache') else 0,
                }
            }
            result = metrics
        
        # ===== OBSERVER TOOLS =====
        elif name == "observer_health":
            result = health()
        
        elif name == "observer_insights":
            result = insights()
        
        elif name == "observer_best_method":
            result = {
                "service": arguments["service"],
                "action": arguments["action"],
                "best_method": best_method(arguments["service"], arguments["action"])
            }
        
        elif name == "observer_failures":
            hours = arguments.get("hours", 24)
            failures = get_observer().get_recent_failures(hours)
            result = [{
                "service": f.service,
                "action": f.action,
                "method": f.method,
                "error": f.error,
                "timestamp": f.timestamp
            } for f in failures[:50]]
        
        # ===== EVENT TOOLS =====
        elif name == "event_emit":
            event_type = arguments["event_type"]
            data = arguments.get("data", {})
            event = events.emit(event_type, data, source="mcp")
            result = {
                "emitted": event_type,
                "timestamp": event.timestamp,
                "data": data
            }
        
        elif name == "event_history":
            event_type = arguments.get("event_type")
            days = arguments.get("days", 7)
            result = events.history(event_type, days)
        
        elif name == "event_stats":
            result = events.stats()
        
        elif name == "event_types":
            result = events.list_event_types()
        
        # ===== ORCHESTRATOR TOOLS =====
        elif name == "skill_run":
            skill = arguments["skill"]
            args_str = arguments.get("args", "")
            args = args_str.split() if args_str else []
            result = get_orchestrator().run_skill(skill, args)
        
        elif name == "workflow_run":
            workflow = arguments["workflow"]
            result = get_orchestrator().run_workflow(workflow)
        
        elif name == "skill_list":
            category = arguments.get("category")
            skills = get_orchestrator().list_skills(category)
            if category:
                result = [{"name": s.get("name"), "path": s.get("path")} for s in skills if s]
            else:
                # Group by category
                registry = get_orchestrator().registry
                result = {
                    "total_skills": registry.get("total_skills", 0),
                    "categories": {cat: len(skills) for cat, skills in registry.get("categories", {}).items()},
                    "aliases": list(registry.get("aliases", {}).keys())[:20]  # First 20 aliases
                }
        
        elif name == "workflow_list":
            result = get_orchestrator().list_workflows()
        
        elif name == "orchestrator_status":
            result = get_orchestrator().status()
        
        # ===== CORE SPEECH TOOLS =====
        elif name == "speak":
            message = arguments["message"]
            voice = arguments.get("voice", "zara")
            emotion_str = arguments.get("emotion", "neutral")
            
            if get_brain_speech:
                speech = get_brain_speech()
                emotion_map = {
                    'neutral': Emotion.NEUTRAL,
                    'excited': Emotion.EXCITED,
                    'calm': Emotion.CALM,
                    'concerned': Emotion.CONCERNED,
                    'celebratory': Emotion.CELEBRATORY,
                    'mysterious': Emotion.MYSTERIOUS,
                    'urgent': Emotion.URGENT
                }
                emotion = emotion_map.get(emotion_str.lower(), Emotion.NEUTRAL)
                speech.speak(message, voice=voice, emotion=emotion)
                result = {"spoken": message, "voice": voice, "emotion": emotion_str}
            else:
                # Fallback to orchestrator
                get_orchestrator().speak(message)
                result = {"spoken": message, "fallback": True}
        
        elif name == "audio_celebrate":
            message = arguments.get("message", "Great job!")
            if get_brain_speech:
                speech = get_brain_speech()
                speech.celebrate(message)
            else:
                subprocess.run(['say', '-v', 'Samantha', message])
            result = {"celebrated": message}
        
        elif name == "audio_greet":
            if get_brain_speech:
                speech = get_brain_speech()
                speech.greet()
            else:
                subprocess.run(['say', '-v', 'Samantha', 'Hello Joseph!'])
            result = {"greeted": True}
        
        elif name == "audio_sound":
            sound = arguments["sound"]
            if get_brain_speech:
                speech = get_brain_speech()
                speech.sound(sound)
            else:
                subprocess.run(['afplay', f'/System/Library/Sounds/{sound.capitalize()}.aiff'])
            result = {"played": sound}
        
        elif name == "audio_voices":
            if get_brain_speech:
                speech = get_brain_speech()
                result = {vid: {"name": v.name, "personality": v.personality} 
                         for vid, v in speech.voices.items()}
            else:
                result = {"error": "Core speech not available"}
        
        # ===== FREQTRADE TOOLS =====
        elif name == "freqtrade_bots":
            ft = get_freqtrade()
            result = ft.get_all_bots()
        
        elif name == "freqtrade_trades":
            ft = get_freqtrade()
            result = ft.get_trades(
                arguments["bot"],
                limit=arguments.get("limit", 50),
                days=arguments.get("days")
            )
        
        elif name == "freqtrade_performance":
            ft = get_freqtrade()
            bot = arguments["bot"]
            days = arguments.get("days", 30)
            if bot.lower() == 'all':
                result = ft.get_all_performance(days)
            else:
                result = ft.get_performance(bot, days)
        
        elif name == "freqtrade_open_trades":
            ft = get_freqtrade()
            result = ft.get_open_trades(arguments["bot"])
        
        elif name == "freqtrade_daily":
            ft = get_freqtrade()
            result = ft.get_daily_summary()
        
        elif name == "freqtrade_sync":
            ft = get_freqtrade()
            result = ft.sync_to_neo4j(arguments.get("days", 30))
        
        # ===== CERBERUS TOOLS =====
        elif name == "cerberus_qa":
            repo_path = arguments.get("repo_path", os.path.expanduser("~/adept/talas/citb-talas"))
            try:
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/skills/cerberus/cerberus.py"), repo_path],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                result = {
                    "success": proc.returncode == 0,
                    "output": proc.stdout + proc.stderr,
                    "repo": repo_path
                }
            except subprocess.TimeoutExpired:
                result = {"error": "Cerberus QA timed out (2 min limit)"}
            except Exception as e:
                result = {"error": str(e)}
        
        elif name == "cerberus_fury":
            # Run just gremlin checks
            repo_path = arguments.get("repo_path", os.path.expanduser("~/adept/talas/citb-talas"))
            try:
                # Use gremlin-checker directly
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/skills/review-assassin/gremlin-checker.py"), repo_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                result = {
                    "head": "Fury",
                    "domain": "Gremlins, Line Endings, Whitespace",
                    "success": proc.returncode == 0,
                    "output": proc.stdout + proc.stderr
                }
            except Exception as e:
                result = {"head": "Fury", "error": str(e)}
        
        elif name == "cerberus_storm":
            # Run security scan
            repo_path = arguments.get("repo_path", os.path.expanduser("~/adept/talas/citb-talas"))
            try:
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/skills/review-assassin/security-scanner.py"), repo_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                result = {
                    "head": "Storm",
                    "domain": "Security, SQL Injection, XSS, Secrets",
                    "success": proc.returncode == 0,
                    "output": proc.stdout + proc.stderr
                }
            except Exception as e:
                result = {"head": "Storm", "error": str(e)}
        
        elif name == "cerberus_tide":
            # Run process compliance
            repo_path = arguments.get("repo_path", os.path.expanduser("~/adept/talas/citb-talas"))
            ticket = arguments.get("ticket")
            try:
                cmd = ["python3", os.path.expanduser("~/brain/skills/review-assassin/steve-process-checker.py"), repo_path]
                if ticket:
                    cmd.append(ticket)
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                result = {
                    "head": "Tide",
                    "domain": "Process Compliance, Steve's Rules, Tests",
                    "success": proc.returncode == 0,
                    "output": proc.stdout + proc.stderr
                }
            except Exception as e:
                result = {"head": "Tide", "error": str(e)}
        
        elif name == "cerberus_status":
            # Get Cerberus status from Neo4j
            try:
                query = """
                MATCH (c:CerberusRun)
                WITH c ORDER BY c.timestamp DESC LIMIT 10
                RETURN c.timestamp, c.passed, c.issues
                """
                runs = get_brain_data().query(query)
                result = {
                    "guardian": "Cerberus",
                    "recent_runs": runs[:5] if runs else [],
                    "total_runs": len(runs),
                    "available": True
                }
            except:
                result = {
                    "guardian": "Cerberus",
                    "available": True,
                    "note": "No run history in Neo4j yet"
                }
        
        # ===== HERMES TOOLS =====
        elif name == "hermes_oracle":
            topic = arguments["topic"]
            # Search across all communication types
            results = {
                "topic": topic,
                "emails": [],
                "teams": [],
                "jira": []
            }
            
            # Search emails
            try:
                email_query = f"""
                MATCH (e:Email) 
                WHERE e.subject CONTAINS $topic OR e.body CONTAINS $topic
                RETURN e.subject, e.from, e.date
                ORDER BY e.date DESC LIMIT 10
                """
                emails = get_brain_data().query(email_query.replace("$topic", f"'{topic}'"))
                results["emails"] = emails if emails else []
            except:
                pass
            
            # Search teams
            try:
                teams_query = f"""
                MATCH (t:TeamsMessage) 
                WHERE t.content CONTAINS $topic
                RETURN t.content, t.sender, t.timestamp
                ORDER BY t.timestamp DESC LIMIT 10
                """
                teams = get_brain_data().query(teams_query.replace("$topic", f"'{topic}'"))
                results["teams"] = teams if teams else []
            except:
                pass
            
            # Search JIRA
            try:
                jira_query = f"""
                MATCH (j:Ticket) 
                WHERE j.key CONTAINS $topic OR j.summary CONTAINS $topic
                RETURN j.key, j.summary, j.status, j.updated
                ORDER BY j.updated DESC LIMIT 10
                """
                jira = get_brain_data().query(jira_query.replace("$topic", f"'{topic}'"))
                results["jira"] = jira if jira else []
            except:
                pass
            
            results["total_found"] = len(results["emails"]) + len(results["teams"]) + len(results["jira"])
            result = results
        
        elif name == "hermes_concerns":
            days = arguments.get("days", 7)
            # Find messages with questions that might need answers
            try:
                query = f"""
                MATCH (m) 
                WHERE (m:TeamsMessage OR m:Email) 
                AND (m.content CONTAINS '?' OR m.body CONTAINS '?')
                AND m.timestamp > datetime() - duration('P{days}D')
                RETURN labels(m)[0] as type, m.content, m.subject, m.sender, m.from, m.timestamp
                ORDER BY m.timestamp DESC LIMIT 20
                """
                concerns = get_brain_data().query(query)
                result = {
                    "days_searched": days,
                    "concerns_found": len(concerns) if concerns else 0,
                    "items": concerns[:10] if concerns else []
                }
            except Exception as e:
                result = {"error": str(e), "days_searched": days}
        
        elif name == "hermes_steve":
            days = arguments.get("days", 7)
            # Get all Steve communications
            try:
                query = f"""
                MATCH (m) 
                WHERE (m:TeamsMessage OR m:Email OR m:Ticket)
                AND (
                    toLower(m.sender) CONTAINS 'steve' OR 
                    toLower(m.from) CONTAINS 'steve' OR 
                    toLower(m.assignee) CONTAINS 'steve' OR
                    toLower(m.content) CONTAINS 'steve' OR
                    toLower(m.body) CONTAINS 'steve'
                )
                RETURN labels(m)[0] as type, 
                       coalesce(m.subject, m.summary, substring(m.content, 0, 100)) as preview,
                       coalesce(m.timestamp, m.date, m.updated) as date
                ORDER BY date DESC LIMIT 20
                """
                steve_comms = get_brain_data().query(query)
                result = {
                    "days_searched": days,
                    "steve_communications": len(steve_comms) if steve_comms else 0,
                    "items": steve_comms[:15] if steve_comms else []
                }
            except Exception as e:
                result = {"error": str(e)}
        
        elif name == "hermes_prepare_jira":
            ticket = arguments["ticket"]
            content = arguments["content"]
            status = arguments.get("status", "update")
            
            # Prepare VoiceOver-friendly JIRA comment
            status_map = {
                "investigating": "SECTION: Investigation Update",
                "in_progress": "SECTION: Implementation Progress",
                "complete": "SECTION: Completed",
                "blocked": "SECTION: Blocked - Need Input"
            }
            
            section = status_map.get(status, "SECTION: Update")
            
            prepared = f"""{section}

{content}

---
Prepared by Hermes Oracle
"""
            result = {
                "ticket": ticket,
                "prepared_comment": prepared,
                "status": status,
                "voiceover_friendly": True,
                "ready_to_post": True
            }
        
        elif name == "hermes_prepare_pr":
            ticket = arguments["ticket"]
            changes = arguments["changes"]
            test_info = arguments.get("test_info", "Manual testing completed")
            
            pr_description = f"""## {ticket} - Implementation

### Changes
{changes}

### Testing
{test_info}

### Checklist
- [ ] Code compiles successfully
- [ ] Unit tests pass
- [ ] Manual testing completed
- [ ] JIRA ticket updated

---
*PR prepared by Hermes*
"""
            result = {
                "ticket": ticket,
                "pr_description": pr_description,
                "ready": True
            }
        
        elif name == "hermes_deliver":
            action = arguments["action"]
            ticket = arguments["ticket"]
            content = arguments["content"]
            
            delivered = {"action": action, "ticket": ticket}
            
            if action in ["jira", "both"]:
                try:
                    core = get_core()
                    core.jira.add_comment(ticket, content)
                    delivered["jira_posted"] = True
                except Exception as e:
                    delivered["jira_error"] = str(e)
            
            if action in ["pr", "both"]:
                delivered["pr_note"] = "PR creation requires manual BitBucket interaction"
            
            result = delivered
        
        # ===== NEO4J BACKUP QUICK TOOLS =====
        elif name == "neo4j_backup_now":
            try:
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/tools/neo4j-backup/neo4j-icloud-backup.py"), "backup"],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                result = {
                    "success": proc.returncode == 0,
                    "output": proc.stdout + proc.stderr
                }
            except subprocess.TimeoutExpired:
                result = {"error": "Backup timed out (5 min limit)"}
            except Exception as e:
                result = {"error": str(e)}
        
        elif name == "neo4j_backup_status":
            try:
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/tools/neo4j-backup/neo4j-icloud-backup.py"), "status"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                result = {"output": proc.stdout + proc.stderr}
            except Exception as e:
                result = {"error": str(e)}
        
        elif name == "neo4j_backup_list":
            limit = arguments.get("limit", 5)
            try:
                proc = subprocess.run(
                    ["python3", os.path.expanduser("~/brain/tools/neo4j-backup/neo4j-icloud-backup.py"), "list"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                lines = proc.stdout.strip().split('\n')
                result = {
                    "total": len(lines),
                    "backups": lines[:limit]
                }
            except Exception as e:
                result = {"error": str(e)}
        
        # ===== QA TOOLS =====
        elif name == "qa_quick":
            from core.qa.qa_v19_ultimate import qa_quick
            result = qa_quick('quick')
        
        elif name == "qa_next":
            from core.qa.qa_v19_ultimate import qa_quick
            result = qa_quick('next')
        
        elif name == "qa_blockers":
            from core.qa.qa_v19_ultimate import qa_quick
            result = qa_quick('blocked')
        
        elif name == "qa_health":
            from core.qa.qa_v19_ultimate import qa_quick
            result = qa_quick('health')
        
        elif name == "qa_pr_summary":
            from core.qa.qa_v19_ultimate import qa_pr
            result = qa_pr('summary')
        
        elif name == "qa_jira_summary":
            from core.qa.qa_v19_ultimate import qa_jira
            result = qa_jira('summary')
        
        elif name == "qa_git":
            from core.qa.qa_v19_ultimate import qa_git
            action = arguments.get("action", "status")
            result = qa_git(action)
        
        elif name == "qa_kb":
            from core.qa.qa_v19_ultimate import qa_kb
            category = arguments.get("category", "all")
            search = arguments.get("search", "")
            result = qa_kb(category, search) if search else qa_kb(category)
        
        elif name == "qa_citb":
            from core.qa.qa_v19_ultimate import qa_citb
            action = arguments.get("action", "tickets")
            ticket = arguments.get("ticket", "")
            result = qa_citb(action, ticket)
        
        elif name == "qa_java":
            from core.qa.qa_v19_ultimate import qa_java
            action = arguments.get("action", "help")
            file_path = arguments.get("file", "")
            result = qa_java(action, file_path)
        
        # ===== UAT TOOLS (Steve's Process) =====
        elif name == "qa_uat":
            import importlib.util
            checker_path = os.path.expanduser("~/brain/skills/review-assassin/uat-checker.py")
            spec = importlib.util.spec_from_file_location("uat_checker", checker_path)
            uat_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(uat_module)
            
            ticket = arguments.get("ticket", "")
            pr = arguments.get("pr")
            action = arguments.get("action", "check")
            
            if action == "checklist":
                result = {"checklist": uat_module.format_uat_checklist(ticket)}
            else:
                result = uat_module.check_uat_requirements(ticket, pr)
        
        elif name == "qa_uat_steps":
            import importlib.util
            checker_path = os.path.expanduser("~/brain/skills/review-assassin/uat-checker.py")
            spec = importlib.util.spec_from_file_location("uat_checker", checker_path)
            uat_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(uat_module)
            result = {"steps": uat_module.get_uat_deployment_steps()}
        
        elif name == "qa_uat_env":
            import importlib.util
            checker_path = os.path.expanduser("~/brain/skills/review-assassin/uat-checker.py")
            spec = importlib.util.spec_from_file_location("uat_checker", checker_path)
            uat_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(uat_module)
            result = {
                "uat": uat_module.get_uat_environment(),
                "jenkins": uat_module.get_jenkins_info()
            }
        
        # ===== SESSION CONTINUITY TOOLS =====
        elif name == "continuity_save":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            description = arguments["description"]
            todos = arguments.get("todos", [])
            blockers = arguments.get("blockers", [])
            learnings = arguments.get("learnings", [])
            investigations = arguments.get("investigations", [])
            
            success = cont_module.save_state(
                description=description,
                todos=todos,
                blockers=blockers,
                learnings=learnings,
                investigations=investigations,
                backup_icloud=True,
                use_neo4j=True
            )
            
            result = {
                "saved": success,
                "description": description[:100],
                "todo_count": len(todos),
                "blocker_count": len(blockers),
                "learning_count": len(learnings),
                "message": "Session state saved to plan.md, SQL, Neo4j, and iCloud" if success else "Save failed"
            }
        
        elif name == "continuity_recover":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            recovery = cont_module.recover_state(speak_summary=False)
            if recovery:
                result = {
                    "recovered": True,
                    "session_folder": recovery.get("session_folder"),
                    "todos": recovery.get("todos", []),
                    "todo_count": len(recovery.get("todos", [])),
                    "git_branch": recovery.get("git_status", {}).get("branch"),
                    "uncommitted": recovery.get("git_status", {}).get("uncommitted_count", 0),
                    "plan_preview": recovery.get("plan_content", "")[:500]
                }
            else:
                result = {"recovered": False, "message": "No previous session found"}
        
        elif name == "continuity_status":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            status = cont_module.show_status()
            if status:
                result = status
            else:
                result = {"error": "Could not get status"}
        
        elif name == "continuity_context":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            topic = arguments.get("topic")
            days = arguments.get("days", 7)
            context = cont_module.get_context_from_neo4j(topic=topic, days=days)
            neo4j_todos = cont_module.get_pending_todos_from_neo4j()
            
            result = {
                "recent_sessions": context.get("recent_sessions", []),
                "pending_todos_all_sessions": neo4j_todos[:10],
                "recent_learnings": context.get("recent_learnings", [])[:5],
                "related_tickets": context.get("recent_tickets", []),
                "topic_emails": context.get("related_emails", []) if topic else [],
                "topic_teams": context.get("related_teams", []) if topic else []
            }
        
        elif name == "continuity_todo_add":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            todo = {
                "id": arguments["id"],
                "title": arguments["title"],
                "description": arguments.get("description", ""),
                "priority": arguments.get("priority", 5),
                "status": "pending",
                "depends_on": arguments.get("depends_on", [])
            }
            
            # Save single todo
            session_folder = cont_module.get_session_folder()
            if session_folder:
                import sqlite3
                db_path = cont_module.get_db_path(session_folder)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO todos (id, title, description, status, priority, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (todo["id"], todo["title"], todo["description"], todo["status"], todo["priority"]))
                for dep in todo.get("depends_on", []):
                    cursor.execute("INSERT OR IGNORE INTO todo_deps (todo_id, depends_on) VALUES (?, ?)", 
                                   (todo["id"], dep))
                conn.commit()
                conn.close()
                
                # Also store in Neo4j
                cont_module.store_session_in_neo4j(
                    session_id=session_folder.name,
                    description=f"Added todo: {todo['title']}",
                    todos=[todo],
                    blockers=[],
                    learnings=[],
                    investigations=[],
                    git_branch=cont_module.get_git_status()["branch"],
                    jira_tickets=cont_module.extract_jira_tickets(todo["title"])
                )
                
                result = {"added": True, "todo": todo}
            else:
                result = {"error": "No session folder found"}
        
        elif name == "continuity_todo_done":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            todo_id = arguments["id"]
            session_folder = cont_module.get_session_folder()
            if session_folder:
                import sqlite3
                db_path = cont_module.get_db_path(session_folder)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE todos SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                               (todo_id,))
                conn.commit()
                conn.close()
                result = {"marked_done": True, "id": todo_id}
            else:
                result = {"error": "No session folder found"}
        
        elif name == "continuity_checkpoint":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            description = arguments["description"]
            session_folder = cont_module.get_session_folder()
            if session_folder:
                cont_module.save_checkpoint(session_folder, description, 0)
                result = {"checkpoint_saved": True, "description": description}
            else:
                result = {"error": "No session folder found"}
        
        elif name == "continuity_history":
            import importlib.util
            continuity_path = os.path.expanduser("~/brain/skills/session-continuity/continuity.py")
            spec = importlib.util.spec_from_file_location("continuity", continuity_path)
            cont_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cont_module)
            
            limit = arguments.get("limit", 10)
            session_folder = cont_module.get_session_folder()
            if session_folder:
                checkpoints_path = session_folder / "checkpoints" / "index.json"
                if checkpoints_path.exists():
                    checkpoints = json.loads(checkpoints_path.read_text())
                    result = {
                        "total_checkpoints": len(checkpoints),
                        "checkpoints": checkpoints[-limit:][::-1]  # Most recent first
                    }
                else:
                    result = {"checkpoints": [], "message": "No checkpoints yet"}
            else:
                result = {"error": "No session folder found"}
        
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
    
    except Exception as e:
        import traceback
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }, indent=2)
        )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
