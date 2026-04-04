#!/usr/bin/env python3
"""
Brain Core MCP Server (FastMCP version)
========================================

Fast, focused server with essential brain tools.
Uses connection pooling and caching for maximum speed.

Tools: Neo4j, JIRA, Bitbucket, Cache
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.expanduser('~/brain'))

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/brain/.env'))

from mcp.server.fastmcp import FastMCP

# LAZY IMPORTS - Neo4j-dependent modules loaded on first use
# This allows server to start INSTANTLY even if Neo4j is down

mcp = FastMCP("brain-core")

# Lazy-loaded instances
_core = None
_cache = None
_brain_data = None

def get_core():
    """Lazy load CoreData - connects to Neo4j on first use."""
    global _core
    if _core is None:
        from core_data.core import CoreData
        _core = CoreData()
    return _core

def get_cache():
    """Lazy load MCP cache."""
    global _cache
    if _cache is None:
        from core.mcp_cache import cache
        _cache = cache
    return _cache

def get_brain_data():
    """Lazy load brain_data - connects to Neo4j on first use."""
    global _brain_data
    if _brain_data is None:
        from core_data.neo4j_claude import brain_data
        _brain_data = brain_data
    return _brain_data

def neo4j_health():
    """Lazy health check - imports neo4j_pool on first call."""
    from core.neo4j_pool import health_check
    return health_check()

def neo4j_query(cypher, params=None):
    """Lazy query - imports neo4j_pool on first call."""
    from core.neo4j_pool import query
    return query(cypher, params)


# === NEO4J TOOLS ===

@mcp.tool()
def ask(question: str) -> dict:
    """Quick question about brain data. Uses fuzzy search."""
    return get_brain_data().ask(question)


@mcp.tool()
def search(term: str) -> dict:
    """Search all brain data (emails, teams, jira) with fuzzy matching."""
    cache = get_cache()
    cache_key = f"search:{term}"
    cached_result = cache.get(cache_key)
    if cached_result:
        cached_result["_cached"] = True
        return cached_result
    
    result = get_brain_data().search(term)
    cache.set(cache_key, result, ttl=120)
    return result


@mcp.tool()
def status() -> dict:
    """Get brain status - Neo4j health, node counts, cache stats."""
    neo4j = neo4j_health()
    return {
        "neo4j": neo4j,
        "cache": get_cache().stats(),
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def neo4j_health_check() -> dict:
    """
    Get comprehensive Neo4j health score and any active alerts.
    
    Returns:
    - score: 0-100 health score
    - status: 'healthy', 'degraded', or 'critical'
    - alerts: list of any active alerts with details
    - checks: breakdown by category (connectivity, query, data, resources)
    """
    try:
        from core_data.neo4j_monitor import Neo4jMonitor
        monitor = Neo4jMonitor()
        report = monitor.get_full_report()
        monitor.close()
        return report
    except Exception as e:
        return {
            "score": 0,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@mcp.tool()
def neo4j_query(cypher: str) -> Any:
    """Run raw Cypher query."""
    return query(cypher)


@mcp.tool()
def neo4j_emails(sender: str = None, subject: str = None, limit: int = 20) -> dict:
    """Get recent emails from Neo4j."""
    return brain_data.emails(sender=sender, subject=subject, limit=limit)


@mcp.tool()
def neo4j_teams(sender: str = None, contains: str = None) -> dict:
    """Get Teams messages."""
    return brain_data.teams(sender=sender, contains=contains)


# === JIRA TOOLS ===

@mcp.tool()
def jira_get(key: str) -> dict:
    """Get JIRA ticket by key (e.g. SD-1330)."""
    key = key.upper()
    cache_key = f"jira:{key}"
    cached = cache.get(cache_key)
    if cached:
        cached["_cached"] = True
        return cached
    
    core = get_core()
    result = core.jira.get_ticket(key)
    cache.set(cache_key, result, ttl=300)
    return result


@mcp.tool()
def jira_search(jql: str, max: int = 20) -> dict:
    """Search JIRA with JQL."""
    core = get_core()
    return core.jira.search_tickets(jql=jql, max_results=max)


@mcp.tool()
def jira_sprint() -> dict:
    """Get current sprint status."""
    cache_key = "jira:sprint"
    cached = cache.get(cache_key)
    if cached:
        cached["_cached"] = True
        return cached
    
    core = get_core()
    result = core.jira.get_sprint_status()
    cache.set(cache_key, result, ttl=600)
    return result


# === JIRA AI TOOLS ===
# Uses Safari/AppleScript to query Atlassian Intelligence (Rovo)

@mcp.tool()
def jira_ai_summarize(ticket_key: str) -> dict:
    """
    Get AI summary of a JIRA ticket using Atlassian Intelligence (Rovo).
    Requires Safari to be logged into JIRA.
    Returns AI-generated summary and follow-up questions.
    """
    from tools.jira_ai_query import JiraAIQuery
    ai = JiraAIQuery()
    return ai.summarize_ticket(ticket_key)


@mcp.tool()
def jira_ai_questions(ticket_key: str) -> dict:
    """
    Get AI-generated follow-up questions for a JIRA ticket.
    These are questions the AI thinks need answering.
    """
    from tools.jira_ai_query import JiraAIQuery
    ai = JiraAIQuery()
    result = ai.summarize_ticket(ticket_key)
    return {
        "ticket": ticket_key,
        "questions": result.get('follow_up_questions', []),
        "success": result.get('success', False)
    }


@mcp.tool()
def jira_ai_batch(ticket_keys: str) -> dict:
    """
    Batch summarize multiple JIRA tickets using AI.
    Pass comma-separated ticket keys (e.g., "SD-1345,SD-1333,SD-1330").
    """
    from tools.jira_ai_query import JiraAIQuery
    keys = [k.strip().upper() for k in ticket_keys.split(',')]
    ai = JiraAIQuery()
    results = ai.batch_summarize(keys)
    return {
        "tickets_processed": len(results),
        "successful": sum(1 for r in results if r.get('success')),
        "results": results
    }


# === JIRA INSIGHTS TOOLS ===
# Unified intelligence layer connecting Neo4j + Redpanda + JIRA AI

@mcp.tool()
def jira_insights_sync(include_ai: bool = False) -> dict:
    """
    Full sync of JIRA tickets and PRs to Neo4j graph.
    Creates relationships between tickets, PRs, users, and modules.
    Set include_ai=True to also fetch JIRA AI summaries (slower).
    """
    from tools.jira_insights import JiraInsights
    insights = JiraInsights()
    return insights.full_sync(include_ai=include_ai)


@mcp.tool()
def jira_insights_steve() -> dict:
    """
    Get Steve Taylor's workload and predict what he'll need.
    Returns workload level, active tickets, and predictions.
    """
    from tools.jira_insights import JiraInsights
    insights = JiraInsights()
    return insights.predict_steve_needs()


@mcp.tool()
def jira_insights_work() -> dict:
    """
    Get prioritized work recommendations for Joseph.
    Returns priority_1 (today), priority_2 (this week), priority_3 (can take on).
    """
    from tools.jira_insights import JiraInsights
    insights = JiraInsights()
    return insights.get_work_recommendations()


@mcp.tool()
def jira_insights_report() -> str:
    """
    Generate comprehensive JIRA insights report.
    Includes stats, Steve status, predictions, and priorities.
    """
    from tools.jira_insights import JiraInsights
    insights = JiraInsights()
    return insights.generate_insights_report()


@mcp.tool()
def jira_insights_ask(question: str) -> dict:
    """
    Ask a natural language question about JIRA data.
    Examples: "blocked tickets", "steve's workload", "my priorities"
    """
    from tools.jira_insights import JiraInsights
    insights = JiraInsights()
    return insights.ask(question)


# === ROVO CHAT TOOLS ===
# Cross-product search (JIRA + Confluence + Bitbucket) via Rovo AI

@mcp.tool()
def rovo_search(query: str) -> dict:
    """
    Search across JIRA, Confluence, and Bitbucket using Rovo AI.
    Rovo understands natural language - ask questions naturally.
    
    Examples:
    - "Find all tuition claims documentation"
    - "What PRs were merged last week?"
    - "Documentation about TALAS batch processing"
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.search(query)


@mcp.tool()
def rovo_confluence(topic: str) -> dict:
    """
    Search Confluence documentation via Rovo AI.
    Rovo searches across all Confluence spaces you have access to.
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.ask_about_confluence(topic)


@mcp.tool()
def rovo_bitbucket(topic: str) -> dict:
    """
    Search Bitbucket (PRs, code, repos) via Rovo AI.
    Rovo can find code changes, PR descriptions, and repository content.
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.ask_about_bitbucket(topic)


@mcp.tool()
def rovo_pr_summary(pr_number: int) -> dict:
    """
    Get Rovo AI to summarize a Bitbucket PR.
    Returns AI-generated summary of the PR changes.
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.summarize_pr(pr_number)


@mcp.tool()
def rovo_related(ticket_key: str) -> dict:
    """
    Find all related content for a ticket across JIRA, Confluence, and Bitbucket.
    Rovo will search for linked PRs, related tickets, and relevant documentation.
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.find_related(ticket_key)


@mcp.tool()
def rovo_steve() -> dict:
    """
    Get context about Steve Taylor's recent work via Rovo.
    Searches across JIRA tickets, PRs, and Confluence updates.
    """
    from tools.jira_ai_query import RovoChat
    rovo = RovoChat()
    return rovo.get_steve_context()


@mcp.tool()
def rovo_capabilities() -> dict:
    """
    List all known Rovo AI capabilities.
    Returns what Rovo can search, what actions it can take, and available integrations.
    """
    from tools.jira_ai_query import RovoCapabilities
    return RovoCapabilities.list_all()


# === ROVO DEV GUARDIAN - AI at every stage ===

@mcp.tool()
def rovo_planning(ticket_id: str) -> dict:
    """
    📋 PLANNING STAGE: Get full context before coding.
    Asks Rovo about requirements, related work, docs, similar code.
    Run this BEFORE starting any ticket work!
    """
    from tools.rovo_dev_guardian import RovoGuardian
    guardian = RovoGuardian()
    return guardian.planning_check(ticket_id)


@mcp.tool()
def rovo_coding(ticket_id: str, question: str) -> dict:
    """
    🔨 CODING STAGE: Ask Rovo a question during development.
    Examples: "How should I handle auth?", "What's the standard pattern?"
    """
    from tools.rovo_dev_guardian import RovoGuardian
    guardian = RovoGuardian()
    response = guardian.coding_check(ticket_id, question)
    return {'ticket': ticket_id, 'question': question, 'response': response}


@mcp.tool()
def rovo_pre_commit(ticket_id: str, changed_files: list, commit_message: str = None) -> dict:
    """
    📝 PRE-COMMIT STAGE: Validate changes match requirements before committing.
    Checks alignment, missing items, commit message.
    """
    from tools.rovo_dev_guardian import RovoGuardian
    guardian = RovoGuardian()
    return guardian.pre_commit_check(ticket_id, changed_files, commit_message)


@mcp.tool()
def rovo_pr_readiness(ticket_id: str, branch_name: str, repo_path: str = None) -> dict:
    """
    🔀 PR CREATION STAGE: Check if PR is ready to create.
    Validates completeness, test coverage, generates PR description.
    """
    from tools.rovo_dev_guardian import RovoGuardian
    guardian = RovoGuardian()
    return guardian.pr_readiness_check(ticket_id, branch_name, repo_path)


@mcp.tool()
def rovo_post_merge(ticket_id: str, pr_number: int = None) -> dict:
    """
    ✅ POST-MERGE STAGE: Verify deployment and follow-up tasks.
    Checks deployment requirements, doc updates, related tickets.
    """
    from tools.rovo_dev_guardian import RovoGuardian
    guardian = RovoGuardian()
    return guardian.post_merge_check(ticket_id, pr_number)


@mcp.tool()
def rovo_weekly_report(weeks_ago: int = 0) -> dict:
    """
    📊 Generate weekly report using Rovo AI.
    Gathers completed work, in-progress, blockers, PRs, sprint status.
    Perfect for Joseph's weekly status updates.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.weekly_report(weeks_ago)


@mcp.tool()
def rovo_standup() -> dict:
    """
    🎤 Prepare standup notes using Rovo AI.
    Gets: what I did yesterday, what I'm doing today, blockers.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.standup_prep()


@mcp.tool()
def rovo_sprint() -> dict:
    """
    🏃 Get current sprint summary from Rovo.
    Status, my tickets, at-risk items, recommendations.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.sprint_summary()


@mcp.tool()
def rovo_backlog() -> dict:
    """
    📋 Analyze backlog health using Rovo.
    Total items, stale tickets, quick wins, grooming needed.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.backlog_analysis()


@mcp.tool()
def rovo_steve_tracker() -> dict:
    """
    👨‍💼 Track Steve Taylor's work via Rovo.
    Current work, PRs, what's blocked, what he might need from Joseph.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.steve_tracker()


@mcp.tool()
def rovo_discover_features() -> dict:
    """
    🆕 Discover Rovo AI capabilities - stay up to date!
    As JIRA Champion, Joseph needs to know ALL Rovo features.
    Asks Rovo about new features, capabilities, integrations, tips.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    return reporter.discover_new_features()


@mcp.tool()
def rovo_ask(question: str) -> dict:
    """
    🤖 Ask Rovo any CITB-related question.
    Free-form query to Atlassian's AI about JIRA, Confluence, Bitbucket.
    """
    from tools.rovo_reporting import RovoReporter
    reporter = RovoReporter()
    response = reporter.ask(question)
    return {'question': question, 'response': response}


# === UNIFIED ALERT RADAR ===
# Consolidated monitoring with priority queues, dedup, security

@mcp.tool()
def alert_status() -> dict:
    """
    Get unified alert radar status.
    Shows queue depth, dedup stats, active monitors, pending alerts.
    """
    from core.priority_alert_queue import AlertQueue
    from brain_core import UnifiedAlertDeduplicator as AlertDeduplicator
    from core.security_monitor import SecurityMonitor
    
    queue = AlertQueue()
    dedup = AlertDeduplicator()
    security = SecurityMonitor()
    
    return {
        "queue": {
            "depth": queue.queue.qsize(),
            "processed_today": queue.processed_count if hasattr(queue, 'processed_count') else 0,
            "critical_pending": sum(1 for _ in queue.queue.queue if _[0] == 1) if hasattr(queue.queue, 'queue') else 0
        },
        "deduplication": dedup.get_stats(),
        "security": {
            "baseline_learned": security.baseline is not None,
            "last_check": security.last_check.isoformat() if security.last_check else None
        },
        "timestamp": datetime.now().isoformat()
    }


@mcp.tool()
def alert_send(message: str, source: str = "manual", priority: str = "normal", alert_type: str = "info") -> dict:
    """
    Send an alert through the unified radar system.
    Priority: critical, high, normal, low
    Alert types: info, warning, error, security, sage, jira, pr
    """
    from core.priority_alert_queue import AlertQueue
    from brain_core import UnifiedAlertDeduplicator as AlertDeduplicator
    
    queue = AlertQueue()
    dedup = AlertDeduplicator()
    
    # Check if duplicate
    alert_id = f"{source}:{alert_type}:{hash(message) % 100000}"
    if dedup.is_duplicate(alert_id, message):
        return {"sent": False, "reason": "duplicate", "alert_id": alert_id}
    
    # Map priority string to level
    priority_map = {"critical": 1, "high": 2, "normal": 5, "low": 10}
    level = priority_map.get(priority, 5)
    
    queue.add_alert({
        "id": alert_id,
        "message": message,
        "source": source,
        "type": alert_type,
        "timestamp": datetime.now().isoformat()
    }, level)
    
    return {"sent": True, "alert_id": alert_id, "priority": priority}


@mcp.tool()
def alert_security_check() -> dict:
    """
    Run security anomaly check NOW.
    Checks login patterns, device changes, network anomalies, rate limits.
    """
    from core.security_monitor import SecurityMonitor
    security = SecurityMonitor()
    return security.check_suspicious_activity()


@mcp.tool()
def alert_security_baseline(days: int = 30) -> dict:
    """
    Learn security baseline from last N days.
    Call this to establish normal patterns before anomaly detection works well.
    """
    from core.security_monitor import SecurityMonitor
    security = SecurityMonitor()
    return security.learn_baseline(days=days)


@mcp.tool()
def alert_dedup_stats() -> dict:
    """Get detailed deduplication statistics."""
    from brain_core import UnifiedAlertDeduplicator as AlertDeduplicator
    dedup = AlertDeduplicator()
    return dedup.get_stats()


@mcp.tool()
def alert_queue_flush() -> dict:
    """
    Process all pending alerts in queue immediately.
    Useful after Focus mode ends or to clear backlog.
    """
    from core.priority_alert_queue import AlertQueue
    queue = AlertQueue()
    processed = 0
    while not queue.queue.empty():
        try:
            queue.queue.get_nowait()
            processed += 1
        except:
            break
    return {"flushed": processed}


@mcp.tool()
def alert_focus_status() -> dict:
    """
    Get current Apple Focus mode and how it affects alerts.
    Shows which alerts will be delivered vs queued.
    """
    from core.focus_mode_handler import FocusModeHandler
    handler = FocusModeHandler()
    return handler.get_status()


@mcp.tool()
def vpn_status() -> dict:
    """
    Get unified VPN/network status (single source of truth).
    Replaces 4 separate implementations.
    """
    from core.network_health import NetworkHealth
    health = NetworkHealth()
    return health.get_full_status()


@mcp.tool()
def sage_fix_effectiveness(fix_type: str = None, days: int = 30) -> dict:
    """
    Check if Sage fixes actually reduced errors.
    Shows before/after stats for deployments.
    """
    from core_data.sage_fix_tracker import SageFixTracker
    tracker = SageFixTracker()
    return tracker.get_effectiveness_report(fix_type=fix_type, days=days)


# === BITBUCKET TOOLS ===

@mcp.tool()
def bitbucket_prs(state: str = "OPEN") -> dict:
    """List PRs by state."""
    core = get_core()
    return core.bitbucket.get_pull_requests(state=state)


@mcp.tool()
def bitbucket_pr(number: int) -> dict:
    """Get PR details by number."""
    core = get_core()
    return core.bitbucket.get_pr_details(number)


# === CACHE TOOLS ===

@mcp.tool()
def cache_stats() -> dict:
    """Get cache statistics."""
    return cache.stats()


@mcp.tool()
def cache_clear(pattern: str = None) -> dict:
    """Clear cache (pattern optional, clears all if empty)."""
    cleared = cache.invalidate(pattern)
    return {"cleared": cleared, "pattern": pattern or "all"}


# === SPEECH INPUT TOOLS ===
# Whisper-powered speech-to-text for Joseph (accessibility)

@mcp.tool()
def speech_listen(seconds: float = 5.0) -> dict:
    """
    🎤 Listen and transcribe speech using Whisper.
    Records from microphone for specified duration.
    VoiceOver-friendly with status announcements.
    
    Args:
        seconds: Recording duration (default 5 seconds)
        
    Returns:
        Transcript with text, confidence, and detected type (command/question/etc)
    """
    try:
        from core_data.speech_input import SpeechInput
        speech = SpeechInput(model_size="base")
        result = speech.listen(seconds=seconds, announce=True)
        return {
            "text": result.text,
            "type": result.type.value,
            "confidence": result.confidence,
            "backend": result.backend,
            "duration_seconds": result.duration_seconds,
            "success": True
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def speech_continuous() -> dict:
    """
    🎤 Listen until silence is detected, then transcribe.
    Great for longer statements - stops automatically when you stop talking.
    Max 30 seconds.
    
    Returns:
        Transcript with text, confidence, and detected type
    """
    try:
        from core_data.speech_input import SpeechInput
        speech = SpeechInput(model_size="base")
        result = speech.listen_continuous(max_duration=30, announce=True)
        return {
            "text": result.text,
            "type": result.type.value,
            "confidence": result.confidence,
            "backend": result.backend,
            "success": True
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def speech_transcribe_file(audio_path: str) -> dict:
    """
    📁 Transcribe an audio file using Whisper.
    Supports WAV, MP3, and most common audio formats.
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        Transcript with text, confidence, and detected type
    """
    try:
        from core_data.speech_input import SpeechInput
        speech = SpeechInput(model_size="base")
        result = speech.transcribe_file(audio_path)
        return {
            "text": result.text,
            "type": result.type.value,
            "confidence": result.confidence,
            "backend": result.backend,
            "file": audio_path,
            "success": True
        }
    except FileNotFoundError:
        return {"success": False, "error": f"File not found: {audio_path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def speech_status() -> dict:
    """
    🎤 Get speech input system status.
    Shows available backends, microphone status, model info.
    """
    try:
        from core_data.speech_input import SpeechInput
        speech = SpeechInput(model_size="base")
        return speech.get_status()
    except Exception as e:
        return {"available": False, "error": str(e)}


@mcp.tool()
def speech_wake_word(timeout: int = 60) -> dict:
    """
    🔔 Wait for wake word ("Hey Brain").
    Returns when wake word is detected or timeout reached.
    Joseph can activate the brain hands-free!
    
    Args:
        timeout: Max seconds to wait (default 60)
        
    Returns:
        Whether wake word was detected
    """
    try:
        from core_data.speech_input import SpeechInput
        speech = SpeechInput(model_size="base", wake_word="hey brain")
        detected = speech.wait_for_wake_word(timeout=timeout)
        return {
            "detected": detected,
            "wake_word": "hey brain",
            "timeout_seconds": timeout
        }
    except Exception as e:
        return {"detected": False, "error": str(e)}


# === FAST MAIL SEARCH TOOLS ===
# Ultra-fast email search using Neo4j index + Spotlight fallback

@mcp.tool()
def mail_search(
    query: str,
    sender: str = None,
    since: str = None,
    limit: int = 20,
    speak: bool = True
) -> dict:
    """
    FAST email search - uses Neo4j index + Spotlight fallback.
    Caches results for 1 hour. Speaks result count for accessibility.
    
    Args:
        query: Search term (searches subject, body)
        sender: Filter by sender name/email (optional)
        since: Date filter - "2025-11-01" or "30 days" (optional)
        limit: Max results (default 20)
        speak: Announce result count (default True for accessibility)
    
    Examples:
        mail_search query="velocity"
        mail_search query="virgin" sender="rewards"
        mail_search query="tara" since="2025-10-01"
    """
    from tools.mail_search import mail_search as _mail_search
    return _mail_search(query=query, sender=sender, since=since, limit=limit, speak=speak)


@mcp.tool()
def mail_sync() -> dict:
    """
    Trigger email sync to Neo4j.
    Syncs recent Outlook emails to the graph for fast searching.
    Call this when Neo4j email data seems stale.
    
    Returns:
        {"success": bool, "emails_synced": int, "duration_ms": int}
    """
    from tools.mail_search import mail_sync as _mail_sync
    return _mail_sync()


@mcp.tool()
def mail_recent(days: int = 7, limit: int = 20, speak: bool = True) -> dict:
    """
    Get recent emails from last N days.
    Quick shortcut for common "what's new" queries.
    
    Args:
        days: Number of days to look back (default 7)
        limit: Max results (default 20)
        speak: Announce result count (default True)
    
    Examples:
        mail_recent
        mail_recent days=3
        mail_recent days=14 speak=False
    """
    from tools.mail_search import mail_recent as _mail_recent
    return _mail_recent(days=days, limit=limit, speak=speak)


@mcp.tool()
def mail_from(
    sender: str,
    since: str = None,
    limit: int = 20,
    speak: bool = True
) -> dict:
    """
    Get emails from a specific sender.
    Fast lookup using Neo4j index.
    
    Args:
        sender: Sender name or email to search for
        since: Date filter - "2025-11-01" or "30 days" (optional)
        limit: Max results (default 20)
        speak: Announce result count (default True)
    
    Examples:
        mail_from sender="steve.taylor"
        mail_from sender="virgin" since="30 days"
        mail_from sender="sharon" since="2025-10-01"
    """
    from tools.mail_search import mail_from as _mail_from
    return _mail_from(sender=sender, since=since, limit=limit, speak=speak)


# === SKILLS TOOLS ===

@mcp.tool()
def skills_list(category: str = None) -> dict:
    """
    List all available skills from brain-core and brain.
    
    Args:
        category: Optional filter by category (productivity, safety, testing, etc.)
    
    Returns list of skills with name, description, and category.
    """
    try:
        from brain_core.skills import list_skills, SkillCategory
        
        cat = None
        if category:
            try:
                cat = SkillCategory(category.lower())
            except ValueError:
                pass
        
        skills = list_skills(cat)
        return {
            "total": len(skills),
            "skills": [
                {
                    "name": s.name,
                    "description": s.description[:100] if s.description else "",
                    "category": s.category.value if s.category else "other"
                }
                for s in sorted(skills, key=lambda x: x.name)
            ]
        }
    except Exception as e:
        return {"error": str(e), "skills": []}


@mcp.tool()
def skills_search(query: str) -> dict:
    """
    Search skills by keyword.
    
    Args:
        query: Search term (matches name, description, tags)
    
    Examples:
        skills_search query="test"
        skills_search query="mcp"
        skills_search query="security"
    """
    try:
        from brain_core.skills import search_skills
        
        results = search_skills(query)
        return {
            "query": query,
            "found": len(results),
            "skills": [
                {
                    "name": s.name,
                    "description": s.description[:100] if s.description else "",
                    "category": s.category.value if s.category else "other"
                }
                for s in results[:20]  # Limit to 20 results
            ]
        }
    except Exception as e:
        return {"error": str(e), "skills": []}


@mcp.tool()
def skills_get(name: str) -> dict:
    """
    Get full details of a specific skill.
    
    Args:
        name: Skill name (e.g., "skill-creator", "mcp-builder", "cerberus")
    
    Returns full skill documentation and metadata.
    """
    try:
        from brain_core.skills import load_skill
        
        skill = load_skill(name)
        if not skill:
            return {"error": f"Skill '{name}' not found"}
        
        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category.value if skill.category else "other",
            "triggers": skill.triggers,
            "tags": skill.tags,
            "content": skill.content[:2000] if skill.content else "",  # First 2000 chars
            "path": str(skill.path) if skill.path else None
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("🧠 Brain Core MCP Server (FastMCP) starting...")
    mcp.run()
