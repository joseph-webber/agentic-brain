#!/usr/bin/env python3
"""
Communications Hub MCP Server
==============================

UNIFIED communications intelligence for enterprise support.
Integrates: Teams, Outlook, Neo4j knowledge, Hermes, and real-time alerts.

TOOLS:
1. comms_dashboard    - Full communications overview
2. comms_urgent       - What needs attention NOW
3. comms_search       - Search all communications
4. comms_person       - Get all context for a person
5. comms_ticket       - Get all comms about a JIRA ticket
6. comms_unread       - Unread/unanswered items
7. comms_knowledge    - Enterprise knowledge lookup
8. comms_sync         - Force sync all channels
9. comms_alert        - Set up alerts for keywords/people
10. comms_speak       - Speak important updates aloud

ALERTS:
- New messages from Steve Taylor → immediate notify
- JIRA tickets mentioned → track context
- Keywords: "urgent", "ASAP", "today", "blocker" → alert
- Unanswered questions older than 24h → remind

Start: python server.py
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser("~/brain"))

from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/brain/.env"))

# MCP protocol
# Fuzzy search
from core.fuzzy_search import fuzzy_best, fuzzy_filter, fuzzy_match, fuzzy_ratio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Neo4j
from neo4j import GraphDatabase

# Brain paths
BRAIN_ROOT = Path.home() / "brain"
CONTINUITY_DIR = Path.home() / ".brain-continuity"
ALERTS_FILE = CONTINUITY_DIR / "comm_alerts.json"

# Alert keywords
URGENT_KEYWORDS = [
    "urgent",
    "asap",
    "immediately",
    "today",
    "blocker",
    "critical",
    "emergency",
]
IMPORTANT_PEOPLE = [
    "User Two",
    "Team Member A",
    "Team Member B",
    "Team Member C",
    "Team Member D",
]


# Neo4j connection
def get_neo4j():
    return GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "brain2026"))


# ==================== CORE FUNCTIONS ====================


def get_communications_dashboard() -> Dict[str, Any]:
    """Get full communications overview."""
    driver = get_neo4j()
    dashboard = {
        "generated_at": datetime.now().isoformat(),
        "summary": {},
        "recent_from_steve": [],
        "urgent_items": [],
        "pending_actions": [],
        "jira_tickets_active": [],
        "knowledge_available": [],
    }

    with driver.session() as session:
        # Summary counts
        queries = {
            "total_teams_messages": "MATCH (m:TeamsMessage) RETURN count(m)",
            "total_emails": "MATCH (e) WHERE e:OutlookEmail OR e:ScrapedEmail RETURN count(e)",
            "steve_messages": "MATCH (m:TeamsMessage {sender:'Steve Taylor'}) RETURN count(m)",
            "jira_tickets": "MATCH (t:JiraTicketRef) RETURN count(t)",
            "knowledge_nodes": "MATCH (k:CITBKnowledge) RETURN count(k)",
        }

        for key, query in queries.items():
            result = session.run(query)
            dashboard["summary"][key] = result.single()[0]

        # Recent from Steve (last 10)
        result = session.run(
            """
            MATCH (m:TeamsMessage {sender: 'Steve Taylor'})
            RETURN m.text as text, m.time as time, m.date as date
            ORDER BY m.scraped_at DESC
            LIMIT 10
        """
        )
        dashboard["recent_from_steve"] = [
            {"text": r["text"][:200], "time": r["time"], "date": r["date"]}
            for r in result
        ]

        # Find urgent items (keywords)
        for keyword in URGENT_KEYWORDS:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE toLower(m.text) CONTAINS $keyword
                RETURN m.sender as sender, m.text as text, m.time as time
                ORDER BY m.scraped_at DESC
                LIMIT 5
            """,
                keyword=keyword,
            )
            for r in result:
                dashboard["urgent_items"].append(
                    {
                        "keyword": keyword,
                        "sender": r["sender"],
                        "text": r["text"][:150],
                        "time": r["time"],
                    }
                )

        # Active JIRA tickets
        result = session.run(
            """
            MATCH (t:JiraTicketRef)<-[:MENTIONS]-(m)
            WITH t.key as ticket, count(m) as mentions
            ORDER BY mentions DESC
            RETURN ticket, mentions
            LIMIT 15
        """
        )
        dashboard["jira_tickets_active"] = [
            {"ticket": r["ticket"], "mentions": r["mentions"]} for r in result
        ]

        # Knowledge available
        result = session.run(
            "MATCH (k:CITBKnowledge) RETURN k.topic as topic, k.id as id"
        )
        dashboard["knowledge_available"] = [
            {"topic": r["topic"], "id": r["id"]} for r in result
        ]

    driver.close()
    return dashboard


def get_urgent_items() -> Dict[str, Any]:
    """Get items that need attention NOW."""
    driver = get_neo4j()
    urgent = {
        "generated_at": datetime.now().isoformat(),
        "needs_attention": [],
        "from_important_people": [],
        "questions_unanswered": [],
        "action_items": [],
    }

    with driver.session() as session:
        # Messages with urgent keywords
        for keyword in URGENT_KEYWORDS:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE toLower(m.text) CONTAINS $keyword
                AND m.date >= date() - duration('P7D')
                RETURN m.sender as sender, m.text as text, m.time as time, m.date as date
                ORDER BY m.scraped_at DESC
                LIMIT 3
            """,
                keyword=keyword,
            )
            for r in result:
                urgent["needs_attention"].append(
                    {
                        "trigger": keyword,
                        "sender": r["sender"],
                        "text": r["text"][:200],
                        "time": r["time"],
                        "date": str(r["date"]) if r["date"] else "unknown",
                    }
                )

        # Recent from important people
        for person in IMPORTANT_PEOPLE:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE m.sender CONTAINS $person
                RETURN m.text as text, m.time as time, m.date as date
                ORDER BY m.scraped_at DESC
                LIMIT 3
            """,
                person=person,
            )
            for r in result:
                urgent["from_important_people"].append(
                    {"person": person, "text": r["text"][:200], "time": r["time"]}
                )

        # Find questions (messages ending with ?)
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE m.text ENDS WITH '?'
            AND m.sender <> 'Joseph Webber'
            RETURN m.sender as sender, m.text as text, m.time as time
            ORDER BY m.scraped_at DESC
            LIMIT 10
        """
        )
        urgent["questions_unanswered"] = [
            {"sender": r["sender"], "question": r["text"][:200], "time": r["time"]}
            for r in result
        ]

        # Action items (look for keywords)
        action_keywords = ["please", "can you", "could you", "need you to", "would you"]
        for keyword in action_keywords:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE toLower(m.text) CONTAINS $keyword
                AND m.sender <> 'Joseph Webber'
                RETURN m.sender as sender, m.text as text, m.time as time
                ORDER BY m.scraped_at DESC
                LIMIT 3
            """,
                keyword=keyword,
            )
            for r in result:
                urgent["action_items"].append(
                    {"sender": r["sender"], "text": r["text"][:200], "time": r["time"]}
                )

    driver.close()
    return urgent


def search_communications(
    query: str, limit: int = 20, fuzzy_threshold: int = 70
) -> Dict[str, Any]:
    """Search across all communications with fuzzy matching."""
    driver = get_neo4j()
    results = {
        "query": query,
        "fuzzy_enabled": True,
        "fuzzy_threshold": fuzzy_threshold,
        "teams_messages": [],
        "emails": [],
        "knowledge": [],
    }

    # Get more results from Neo4j, then fuzzy filter
    fetch_limit = limit * 3  # Over-fetch for fuzzy filtering

    with driver.session() as session:
        # Search Teams - fetch broadly, fuzzy filter
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE toLower(m.text) CONTAINS toLower($query)
               OR toLower(m.sender) CONTAINS toLower($query)
            RETURN m.sender as sender, m.text as text, m.time as time, m.date as date
            ORDER BY m.scraped_at DESC
            LIMIT $limit
        """,
            query=query,
            limit=fetch_limit,
        )
        raw_teams = [
            {
                "sender": r["sender"],
                "text": r["text"][:300],
                "time": r["time"],
                "date": str(r["date"]) if r["date"] else None,
            }
            for r in result
        ]
        # Fuzzy rank results
        for msg in raw_teams:
            score = max(
                fuzzy_ratio(query, msg["text"]), fuzzy_ratio(query, msg["sender"])
            )
            msg["_fuzzy_score"] = round(score)
        raw_teams.sort(key=lambda x: x["_fuzzy_score"], reverse=True)
        results["teams_messages"] = [
            m for m in raw_teams if m["_fuzzy_score"] >= fuzzy_threshold
        ][:limit]

        # Search Emails - fuzzy filter
        result = session.run(
            """
            MATCH (e)
            WHERE (e:OutlookEmail OR e:ScrapedEmail)
            AND (toLower(e.subject) CONTAINS toLower($query)
                 OR toLower(COALESCE(e.preview, '')) CONTAINS toLower($query)
                 OR toLower(e.sender) CONTAINS toLower($query))
            RETURN e.sender as sender, e.subject as subject, e.preview as preview
            LIMIT $limit
        """,
            query=query,
            limit=fetch_limit,
        )
        raw_emails = [
            {
                "sender": r["sender"],
                "subject": r["subject"],
                "preview": r["preview"][:200] if r["preview"] else None,
            }
            for r in result
        ]
        for email in raw_emails:
            search_text = (
                f"{email['sender']} {email['subject']} {email.get('preview', '')}"
            )
            email["_fuzzy_score"] = round(fuzzy_ratio(query, search_text))
        raw_emails.sort(key=lambda x: x["_fuzzy_score"], reverse=True)
        results["emails"] = [
            e for e in raw_emails if e["_fuzzy_score"] >= fuzzy_threshold
        ][:limit]

        # Search Knowledge - fuzzy filter
        result = session.run(
            """
            MATCH (k:CITBKnowledge)
            WHERE toLower(k.topic) CONTAINS toLower($query) OR toLower(k.knowledge) CONTAINS toLower($query)
            RETURN k.topic as topic, k.knowledge as knowledge
        """,
            query=query,
        )
        raw_knowledge = [
            {"topic": r["topic"], "knowledge": r["knowledge"][:500]} for r in result
        ]
        for k in raw_knowledge:
            k["_fuzzy_score"] = round(
                fuzzy_ratio(query, f"{k['topic']} {k['knowledge']}")
            )
        raw_knowledge.sort(key=lambda x: x["_fuzzy_score"], reverse=True)
        results["knowledge"] = [
            k for k in raw_knowledge if k["_fuzzy_score"] >= fuzzy_threshold
        ]

    driver.close()
    return results


def get_person_context(person: str) -> Dict[str, Any]:
    """Get all context for a person."""
    driver = get_neo4j()
    context = {
        "person": person,
        "messages_sent": [],
        "messages_about": [],
        "emails": [],
        "tickets_mentioned": [],
        "knowledge": None,
    }

    with driver.session() as session:
        # Messages sent by person
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE m.sender CONTAINS $person
            RETURN m.text as text, m.time as time, m.date as date
            ORDER BY m.scraped_at DESC
            LIMIT 20
        """,
            person=person,
        )
        context["messages_sent"] = [
            {
                "text": r["text"][:300],
                "time": r["time"],
                "date": str(r["date"]) if r["date"] else None,
            }
            for r in result
        ]

        # Messages mentioning person
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE m.text CONTAINS $person AND NOT m.sender CONTAINS $person
            RETURN m.sender as sender, m.text as text, m.time as time
            ORDER BY m.scraped_at DESC
            LIMIT 10
        """,
            person=person,
        )
        context["messages_about"] = [
            {"sender": r["sender"], "text": r["text"][:300], "time": r["time"]}
            for r in result
        ]

        # Emails from/about person
        result = session.run(
            """
            MATCH (e)
            WHERE (e:OutlookEmail OR e:ScrapedEmail)
            AND (e.sender CONTAINS $person OR e.subject CONTAINS $person)
            RETURN e.sender as sender, e.subject as subject
            LIMIT 10
        """,
            person=person,
        )
        context["emails"] = [
            {"sender": r["sender"], "subject": r["subject"]} for r in result
        ]

        # Knowledge about person
        result = session.run(
            """
            MATCH (k:CITBKnowledge)
            WHERE k.topic CONTAINS $person OR k.knowledge CONTAINS $person
            RETURN k.topic as topic, k.knowledge as knowledge
        """,
            person=person,
        )
        for r in result:
            context["knowledge"] = {"topic": r["topic"], "knowledge": r["knowledge"]}
            break

    driver.close()
    return context


def get_ticket_context(ticket: str) -> Dict[str, Any]:
    """Get all communications about a JIRA ticket."""
    driver = get_neo4j()
    context = {
        "ticket": ticket,
        "total_mentions": 0,
        "messages": [],
        "emails": [],
        "knowledge": [],
        "timeline": [],
    }

    with driver.session() as session:
        # Count mentions
        result = session.run(
            """
            MATCH (t:JiraTicketRef {key: $ticket})<-[:MENTIONS]-(m)
            RETURN count(m) as mentions
        """,
            ticket=ticket,
        )
        context["total_mentions"] = result.single()["mentions"]

        # Get all mentioning messages
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE m.text CONTAINS $ticket
            RETURN m.sender as sender, m.text as text, m.time as time, m.date as date
            ORDER BY m.scraped_at DESC
        """,
            ticket=ticket,
        )
        context["messages"] = [
            {
                "sender": r["sender"],
                "text": r["text"][:400],
                "time": r["time"],
                "date": str(r["date"]) if r["date"] else None,
            }
            for r in result
        ]

        # Get mentioning emails
        result = session.run(
            """
            MATCH (e)
            WHERE (e:OutlookEmail OR e:ScrapedEmail)
            AND (e.subject CONTAINS $ticket OR COALESCE(e.preview, '') CONTAINS $ticket)
            RETURN e.sender as sender, e.subject as subject, e.preview as preview
        """,
            ticket=ticket,
        )
        context["emails"] = [
            {
                "sender": r["sender"],
                "subject": r["subject"],
                "preview": r["preview"][:200] if r["preview"] else None,
            }
            for r in result
        ]

        # Related knowledge
        result = session.run(
            """
            MATCH (k:CITBKnowledge)
            WHERE k.knowledge CONTAINS $ticket
            RETURN k.topic as topic, k.knowledge as knowledge
        """,
            ticket=ticket,
        )
        context["knowledge"] = [
            {"topic": r["topic"], "knowledge": r["knowledge"]} for r in result
        ]

    driver.close()
    return context


def get_knowledge(topic: str = None) -> Dict[str, Any]:
    """Get CITB knowledge, optionally filtered by topic."""
    driver = get_neo4j()
    knowledge = {"items": []}

    with driver.session() as session:
        if topic:
            result = session.run(
                """
                MATCH (k:CITBKnowledge)
                WHERE toLower(k.topic) CONTAINS toLower($topic) OR toLower(k.knowledge) CONTAINS toLower($topic)
                RETURN k.id as id, k.topic as topic, k.knowledge as knowledge, k.source as source
            """,
                topic=topic,
            )
        else:
            result = session.run(
                """
                MATCH (k:CITBKnowledge)
                RETURN k.id as id, k.topic as topic, k.knowledge as knowledge, k.source as source
                ORDER BY k.id
            """
            )

        knowledge["items"] = [
            {
                "id": r["id"],
                "topic": r["topic"],
                "knowledge": r["knowledge"],
                "source": r["source"],
            }
            for r in result
        ]

    driver.close()
    return knowledge


def sync_all_channels() -> Dict[str, Any]:
    """Force sync all communication channels."""
    results = {
        "synced_at": datetime.now().isoformat(),
        "teams": None,
        "outlook": None,
        "knowledge_extraction": None,
    }

    # Run Teams sync
    try:
        result = subprocess.run(
            [
                str(BRAIN_ROOT / "venv/bin/python3"),
                str(BRAIN_ROOT / "tools/teams-safari-sync.py"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BRAIN_ROOT),
        )
        results["teams"] = (
            "success" if result.returncode == 0 else f"error: {result.stderr[:200]}"
        )
    except Exception as e:
        results["teams"] = f"error: {e}"

    # Run Outlook sync
    try:
        result = subprocess.run(
            [
                str(BRAIN_ROOT / "venv/bin/python3"),
                str(BRAIN_ROOT / "tools/outlook-safari-sync.py"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BRAIN_ROOT),
        )
        results["outlook"] = (
            "success" if result.returncode == 0 else f"error: {result.stderr[:200]}"
        )
    except Exception as e:
        results["outlook"] = f"error: {e}"

    # Run knowledge extraction
    try:
        result = subprocess.run(
            [
                str(BRAIN_ROOT / "venv/bin/python3"),
                "-c",
                "from core_data.citb_knowledge_extractor import run_extraction; run_extraction()",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(BRAIN_ROOT),
        )
        results["knowledge_extraction"] = (
            "success" if result.returncode == 0 else f"error: {result.stderr[:200]}"
        )
    except Exception as e:
        results["knowledge_extraction"] = f"error: {e}"

    return results


def speak_update(message: str, urgency: str = "normal") -> Dict[str, Any]:
    """Speak an important update aloud."""
    voices = {"low": "Samantha", "normal": "Daniel", "high": "Alex"}
    rates = {"low": 180, "normal": 175, "high": 160}

    voice = voices.get(urgency, "Daniel")
    rate = rates.get(urgency, 175)

    try:
        # Play attention sound for high urgency
        if urgency == "high":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], timeout=5)

        # Speak message
        subprocess.run(["say", "-v", voice, "-r", str(rate), message], timeout=30)
        return {"spoken": True, "message": message, "voice": voice, "urgency": urgency}
    except Exception as e:
        return {"spoken": False, "error": str(e)}


def manage_alerts(
    action: str, keyword: str = None, person: str = None
) -> Dict[str, Any]:
    """Manage communication alerts."""
    CONTINUITY_DIR.mkdir(exist_ok=True)

    # Load existing alerts
    alerts = {"keywords": [], "people": []}
    if ALERTS_FILE.exists():
        try:
            alerts = json.loads(ALERTS_FILE.read_text())
        except:
            pass

    if action == "list":
        return {"alerts": alerts}

    elif action == "add_keyword" and keyword:
        if keyword not in alerts["keywords"]:
            alerts["keywords"].append(keyword)
            ALERTS_FILE.write_text(json.dumps(alerts, indent=2))
        return {"added_keyword": keyword, "alerts": alerts}

    elif action == "add_person" and person:
        if person not in alerts["people"]:
            alerts["people"].append(person)
            ALERTS_FILE.write_text(json.dumps(alerts, indent=2))
        return {"added_person": person, "alerts": alerts}

    elif action == "remove_keyword" and keyword:
        if keyword in alerts["keywords"]:
            alerts["keywords"].remove(keyword)
            ALERTS_FILE.write_text(json.dumps(alerts, indent=2))
        return {"removed_keyword": keyword, "alerts": alerts}

    elif action == "remove_person" and person:
        if person in alerts["people"]:
            alerts["people"].remove(person)
            ALERTS_FILE.write_text(json.dumps(alerts, indent=2))
        return {"removed_person": person, "alerts": alerts}

    return {
        "error": "Invalid action. Use: list, add_keyword, add_person, remove_keyword, remove_person"
    }


def check_for_alerts() -> Dict[str, Any]:
    """Check all communications for alert triggers and return matches."""
    # Load configured alerts
    alerts = {"keywords": [], "people": []}
    if ALERTS_FILE.exists():
        try:
            alerts = json.loads(ALERTS_FILE.read_text())
        except:
            pass

    # Add default urgent keywords
    all_keywords = set(URGENT_KEYWORDS + alerts.get("keywords", []))
    all_people = set(IMPORTANT_PEOPLE + alerts.get("people", []))

    driver = get_neo4j()
    triggered = {
        "checked_at": datetime.now().isoformat(),
        "keyword_matches": [],
        "person_matches": [],
        "urgent_count": 0,
    }

    with driver.session() as session:
        # Check for keyword matches in last 24h
        for keyword in all_keywords:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE toLower(m.text) CONTAINS toLower($keyword)
                AND m.scraped_at >= datetime() - duration('PT24H')
                RETURN count(m) as count
            """,
                keyword=keyword,
            )
            count = result.single()["count"]
            if count > 0:
                triggered["keyword_matches"].append(
                    {"keyword": keyword, "count": count}
                )
                triggered["urgent_count"] += count

        # Check for messages from important people in last 24h
        for person in all_people:
            result = session.run(
                """
                MATCH (m:TeamsMessage)
                WHERE m.sender CONTAINS $person
                AND m.scraped_at >= datetime() - duration('PT24H')
                RETURN m.text as text, m.time as time
                ORDER BY m.scraped_at DESC
                LIMIT 3
            """,
                person=person,
            )
            messages = [{"text": r["text"][:100], "time": r["time"]} for r in result]
            if messages:
                triggered["person_matches"].append(
                    {"person": person, "recent_messages": messages}
                )

    driver.close()
    return triggered


# ==================== CONTINUITY INTEGRATION ====================


def save_comms_state_for_continuity() -> Dict[str, Any]:
    """Save communications state for session continuity."""
    state = {
        "saved_at": datetime.now().isoformat(),
        "pending_from_steve": [],
        "unanswered_questions": [],
        "active_tickets": [],
        "alerts_triggered": check_for_alerts(),
    }

    driver = get_neo4j()
    with driver.session() as session:
        # Recent from Steve not replied to
        result = session.run(
            """
            MATCH (m:TeamsMessage {sender: 'Steve Taylor'})
            RETURN m.text as text, m.time as time
            ORDER BY m.scraped_at DESC
            LIMIT 5
        """
        )
        state["pending_from_steve"] = [
            {"text": r["text"][:200], "time": r["time"]} for r in result
        ]

        # Questions that might need answers
        result = session.run(
            """
            MATCH (m:TeamsMessage)
            WHERE m.text CONTAINS '?'
            AND m.sender <> 'Joseph Webber'
            RETURN m.sender as sender, m.text as text
            ORDER BY m.scraped_at DESC
            LIMIT 5
        """
        )
        state["unanswered_questions"] = [
            {"sender": r["sender"], "question": r["text"][:200]} for r in result
        ]

        # Active tickets
        result = session.run(
            """
            MATCH (t:JiraTicketRef)<-[:MENTIONS]-(m)
            WHERE m.scraped_at >= datetime() - duration('P7D')
            WITH t.key as ticket, count(m) as mentions
            ORDER BY mentions DESC
            RETURN ticket, mentions
            LIMIT 10
        """
        )
        state["active_tickets"] = [
            {"ticket": r["ticket"], "mentions": r["mentions"]} for r in result
        ]

    driver.close()

    # Save to continuity dir
    CONTINUITY_DIR.mkdir(exist_ok=True)
    comms_state_file = CONTINUITY_DIR / "comms_state.json"
    comms_state_file.write_text(json.dumps(state, indent=2))

    return state


def get_comms_state_for_continuity() -> Dict[str, Any]:
    """Get saved communications state for session recovery."""
    comms_state_file = CONTINUITY_DIR / "comms_state.json"
    if comms_state_file.exists():
        try:
            return json.loads(comms_state_file.read_text())
        except:
            pass
    return {"error": "No saved communications state found"}


# ==================== MCP SERVER ====================

server = Server("communications")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available communications tools."""
    return [
        Tool(
            name="comms_dashboard",
            description="Get full communications overview - Teams, Outlook, knowledge, active tickets",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_urgent",
            description="What needs attention NOW - urgent messages, questions, action items from important people",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_search",
            description="Search ALL communications (Teams, Outlook, knowledge) for a term",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="comms_person",
            description="Get all context for a person - messages sent, mentioned, emails, knowledge",
            inputSchema={
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Person name (e.g., Steve Taylor, Sioban)",
                    }
                },
                "required": ["person"],
            },
        ),
        Tool(
            name="comms_ticket",
            description="Get all communications about a JIRA ticket",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {
                        "type": "string",
                        "description": "JIRA ticket key (e.g., SD-1330)",
                    }
                },
                "required": ["ticket"],
            },
        ),
        Tool(
            name="comms_knowledge",
            description="Get CITB knowledge - release process, PR workflow, Playwright, UAT guidelines, people context",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Optional topic filter (e.g., release, playwright, steve)",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="comms_sync",
            description="Force sync all communication channels (Teams, Outlook) and extract knowledge",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_speak",
            description="Speak an important update aloud (accessibility)",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to speak"},
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "description": "Urgency level",
                        "default": "normal",
                    },
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="comms_alert",
            description="Manage communication alerts - add/remove keywords and people to watch",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "list",
                            "add_keyword",
                            "add_person",
                            "remove_keyword",
                            "remove_person",
                        ],
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to add/remove",
                    },
                    "person": {"type": "string", "description": "Person to add/remove"},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="comms_steve",
            description="Quick access: All recent communications from/about Steve Taylor",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_check_alerts",
            description="Check for alert triggers in recent communications",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_save_state",
            description="Save communications state for session continuity",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="comms_get_state",
            description="Get saved communications state (for session recovery)",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "comms_dashboard":
            result = get_communications_dashboard()

        elif name == "comms_urgent":
            result = get_urgent_items()

        elif name == "comms_search":
            result = search_communications(
                query=arguments["query"], limit=arguments.get("limit", 20)
            )

        elif name == "comms_person":
            result = get_person_context(arguments["person"])

        elif name == "comms_ticket":
            result = get_ticket_context(arguments["ticket"])

        elif name == "comms_knowledge":
            result = get_knowledge(arguments.get("topic"))

        elif name == "comms_sync":
            result = sync_all_channels()

        elif name == "comms_speak":
            result = speak_update(
                message=arguments["message"], urgency=arguments.get("urgency", "normal")
            )

        elif name == "comms_alert":
            result = manage_alerts(
                action=arguments["action"],
                keyword=arguments.get("keyword"),
                person=arguments.get("person"),
            )

        elif name == "comms_steve":
            result = get_person_context("Steve Taylor")

        elif name == "comms_check_alerts":
            result = check_for_alerts()

        elif name == "comms_save_state":
            result = save_comms_state_for_continuity()

        elif name == "comms_get_state":
            result = get_comms_state_for_continuity()

        else:
            result = {"error": f"Unknown tool: {name}"}

        return [
            TextContent(type="text", text=json.dumps(result, indent=2, default=str))
        ]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
