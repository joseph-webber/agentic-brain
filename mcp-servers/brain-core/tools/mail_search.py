#!/usr/bin/env python3
"""
FAST Mail Search Tools
======================

Ultra-fast email search using Neo4j index + Spotlight fallback.
Built for accessibility needs - speaks results!

Usage:
    from tools.mail_search import mail_search, mail_sync, mail_recent, mail_from

    # Fast search (uses cache, Neo4j, Spotlight)
    result = mail_search("velocity", sender="virgin")

    # Sync emails to Neo4j
    mail_sync()

    # Recent emails
    mail_recent(days=7)

    # Emails from specific sender
    mail_from("steve.taylor")
"""

import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.expanduser("~/brain"))

from core.mcp_cache import cache

# ============================================================
# MAIL CACHE - 1 hour TTL for search results
# ============================================================

MAIL_CACHE_TTL = 3600  # 1 hour


def _parse_relative_date(since: str) -> datetime:
    """
    Parse relative or absolute date strings.

    Args:
        since: "2025-11-01" or "30 days" or "2 weeks"

    Returns:
        datetime object
    """
    if not since:
        return datetime.now() - timedelta(days=30)  # Default 30 days

    since = since.lower().strip()

    # Check for relative format "N days/weeks/months"
    match = re.match(r"(\d+)\s*(day|week|month|hour)s?", since)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        if unit == "day":
            return datetime.now() - timedelta(days=value)
        elif unit == "week":
            return datetime.now() - timedelta(weeks=value)
        elif unit == "month":
            return datetime.now() - timedelta(days=value * 30)
        elif unit == "hour":
            return datetime.now() - timedelta(hours=value)

    # Try ISO format
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        pass

    # Try common formats
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
        try:
            return datetime.strptime(since, fmt)
        except ValueError:
            continue

    # Default to 30 days ago if parsing fails
    return datetime.now() - timedelta(days=30)


def _speak(text: str, wait: bool = True) -> None:
    """Speak text using macOS say command."""
    try:
        # Clean for VoiceOver
        text = re.sub(r"[^\w\s.,!?-]", "", text)
        cmd = ["say", "-v", "Samantha", "-r", "180", text]
        if wait:
            subprocess.run(cmd, capture_output=True)
        else:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # Silent fail - accessibility helper


def _search_neo4j(
    query: str, sender: Optional[str], since: datetime, limit: int
) -> List[Dict]:
    """
    Search emails in Neo4j graph database.
    FAST - uses indexes!
    """
    try:
        from core.neo4j_pool import query as neo4j_query

        # Build search conditions
        conditions = []
        params = {"limit": limit}

        # Full-text search on subject and preview
        # Note: use search_term instead of query to avoid Neo4j param conflict
        if query:
            conditions.append(
                """
                (toLower(e.subject) CONTAINS toLower($search_term) OR
                 toLower(e.preview) CONTAINS toLower($search_term))
            """
            )
            params["search_term"] = query

        # Sender filter
        if sender:
            conditions.append("toLower(e.sender) CONTAINS toLower($sender_filter)")
            params["sender_filter"] = sender

        # Date filter
        if since:
            iso_since = since.isoformat()
            conditions.append("e.timestamp >= $since_date")
            params["since_date"] = iso_since

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cypher = f"""
            MATCH (e:OutlookEmail)
            {where_clause}
            RETURN
                e.subject as subject,
                e.sender as sender,
                coalesce(e.timestamp, e.date) as date,
                coalesce(e.preview, '') as snippet
            ORDER BY e.timestamp DESC
            LIMIT $limit
        """

        results = neo4j_query(cypher, **params)

        return (
            [
                {
                    "subject": r.get("subject", "(no subject)"),
                    "sender": r.get("sender", "Unknown"),
                    "date": str(r.get("date", ""))[:10],
                    "snippet": r.get("snippet", "")[:200],
                }
                for r in results
            ]
            if results
            else []
        )

    except Exception:
        return []  # Fall through to Spotlight


def _search_spotlight(
    query: str, sender: Optional[str], since: datetime, limit: int
) -> List[Dict]:
    """
    Search emails using macOS Spotlight (mdfind).
    Slower but works without Neo4j sync.
    """
    try:
        # Build mdfind query for emails
        search_terms = [
            'kMDItemContentType == "com.apple.mail.emlx"',
            'kMDItemContentType == "public.email-message"',
        ]

        if query:
            search_terms.append(
                f'(kMDItemTextContent == "*{query}*" || kMDItemSubject == "*{query}*")'
            )

        if sender:
            search_terms.append(f'kMDItemAuthors == "*{sender}*"')

        if since:
            # Spotlight date format
            date_str = since.strftime("%Y-%m-%d")
            search_terms.append(
                f"kMDItemContentModificationDate >= $time.iso({date_str})"
            )

        # Run mdfind
        mdfind_query = " && ".join([f"({t})" for t in search_terms])
        cmd = ["mdfind", "-limit", str(limit), mdfind_query]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return []

        # Parse results (file paths)
        files = [f for f in result.stdout.strip().split("\n") if f]

        emails = []
        for filepath in files[:limit]:
            try:
                # Try to extract email info from Spotlight metadata
                mdls = subprocess.run(
                    [
                        "mdls",
                        "-name",
                        "kMDItemSubject",
                        "-name",
                        "kMDItemAuthors",
                        filepath,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                subject = "(no subject)"
                sender_found = "Unknown"

                for line in mdls.stdout.split("\n"):
                    if "kMDItemSubject" in line and "=" in line:
                        subject = line.split("=", 1)[1].strip().strip('"')
                    if "kMDItemAuthors" in line and "=" in line:
                        sender_found = line.split("=", 1)[1].strip().strip('()"')

                emails.append(
                    {
                        "subject": subject,
                        "sender": sender_found,
                        "date": "",
                        "snippet": "",
                    }
                )
            except Exception:
                continue

        return emails

    except Exception:
        return []


def mail_search(
    query: str,
    sender: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 20,
    speak: bool = True,
) -> Dict[str, Any]:
    """
    FAST email search - uses Neo4j index + Spotlight fallback.

    Args:
        query: Search term (searches subject, body)
        sender: Filter by sender name/email (optional)
        since: Date filter - "2025-11-01" or "30 days" (optional)
        limit: Max results (default 20)
        speak: Announce result count (default True for accessibility)

    Returns:
        {
            "count": 3,
            "query": "velocity",
            "emails": [...],
            "source": "neo4j",
            "search_time_ms": 45
        }

    Examples:
        mail_search("velocity")
        mail_search("virgin", sender="rewards")
        mail_search("tara", since="2025-10-01")
    """
    start_time = time.time()

    # Build cache key
    cache_key = f"mail_search:{query}:{sender}:{since}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        cached["source"] = "cache"
        if speak:
            count = cached.get("count", 0)
            _speak(f"Found {count} cached emails about {query}")
        return cached

    # Parse date
    since_dt = _parse_relative_date(since) if since else None

    # Try Neo4j first (faster)
    emails = _search_neo4j(query, sender, since_dt, limit)
    source = "neo4j"

    # Fallback to Spotlight if Neo4j returns nothing
    if not emails:
        emails = _search_spotlight(query, sender, since_dt, limit)
        source = "spotlight"

    search_time_ms = int((time.time() - start_time) * 1000)

    result = {
        "count": len(emails),
        "query": query,
        "sender_filter": sender,
        "since_filter": since,
        "emails": emails,
        "source": source,
        "search_time_ms": search_time_ms,
    }

    # Cache for 1 hour
    cache.set(cache_key, result, ttl=MAIL_CACHE_TTL)

    # Speak results for accessibility
    if speak:
        count = len(emails)
        if count == 0:
            _speak(f"No emails found matching {query}")
        else:
            # Build natural speech
            msg = f"Found {count} email{'s' if count != 1 else ''} about {query}"
            if sender:
                msg += f" from {sender}"
            _speak(msg)

            # Read first result subject
            if emails:
                first = emails[0]
                _speak(f"Most recent: {first['subject']} from {first['sender']}")

    return result


def mail_sync() -> Dict[str, Any]:
    """
    Trigger email sync to Neo4j.
    Syncs recent Outlook emails to the graph for fast searching.

    Returns:
        {"success": bool, "emails_synced": int, "duration_ms": int}
    """
    start_time = time.time()

    try:
        from core_data.neo4j_hardened import Neo4jHardened
        from core_data.outlook import Outlook

        neo = Neo4jHardened()
        outlook = Outlook()

        # Get recent emails from Outlook
        recent = outlook.recent(folder="Inbox", limit=100)

        if not recent:
            return {
                "success": True,
                "emails_synced": 0,
                "message": "No new emails to sync",
                "duration_ms": int((time.time() - start_time) * 1000),
            }

        # Sync to Neo4j
        synced = 0
        for email in recent:
            try:
                # Create/update email node
                neo.query(
                    """
                    MERGE (e:OutlookEmail {id: $id})
                    SET e.subject = $subject,
                        e.sender = $sender,
                        e.timestamp = $timestamp,
                        e.content = $content,
                        e.synced_at = datetime()
                """,
                    {
                        "id": email.get("id", email.get("subject", str(time.time()))),
                        "subject": email.get("subject", "(no subject)"),
                        "sender": email.get("sender", email.get("from", "Unknown")),
                        "timestamp": email.get(
                            "date", email.get("timestamp", datetime.now().isoformat())
                        ),
                        "content": email.get("body", email.get("preview", ""))[:1000],
                    },
                )
                synced += 1
            except Exception:
                continue

        # Invalidate search cache after sync
        cache.invalidate("mail_search")

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "success": True,
            "emails_synced": synced,
            "total_processed": len(recent),
            "duration_ms": duration_ms,
            "cache_cleared": True,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "duration_ms": int((time.time() - start_time) * 1000),
        }


def mail_recent(days: int = 7, limit: int = 20, speak: bool = True) -> Dict[str, Any]:
    """
    Get recent emails from last N days.

    Args:
        days: Number of days to look back (default 7)
        limit: Max results (default 20)
        speak: Announce result count (default True)

    Returns:
        {"count": int, "emails": [...], "period": "7 days"}
    """
    since = f"{days} days"

    # Use mail_search with no query term
    result = mail_search(query="", sender=None, since=since, limit=limit, speak=False)

    # Customize response
    result["period"] = since

    if speak:
        count = result.get("count", 0)
        _speak(
            f"You have {count} email{'s' if count != 1 else ''} from the last {days} days"
        )

        # Announce unread count or first subjects
        if result.get("emails"):
            first = result["emails"][0]
            _speak(f"Latest: {first['subject']} from {first['sender']}")

    return result


def mail_from(
    sender: str, since: Optional[str] = None, limit: int = 20, speak: bool = True
) -> Dict[str, Any]:
    """
    Get emails from a specific sender.

    Args:
        sender: Sender name or email to search for
        since: Date filter - "2025-11-01" or "30 days" (optional)
        limit: Max results (default 20)
        speak: Announce result count (default True)

    Returns:
        {"count": int, "sender": str, "emails": [...]}

    Examples:
        mail_from("steve.taylor")
        mail_from("virgin", since="30 days")
        mail_from("sharon", since="2025-10-01")
    """
    # Use mail_search with sender filter
    result = mail_search(query="", sender=sender, since=since, limit=limit, speak=False)

    # Customize response
    result["sender_searched"] = sender

    if speak:
        count = result.get("count", 0)
        if count == 0:
            _speak(f"No emails found from {sender}")
        else:
            _speak(f"Found {count} email{'s' if count != 1 else ''} from {sender}")

            if result.get("emails"):
                first = result["emails"][0]
                _speak(f"Latest: {first['subject']}")

    return result


# ============================================================
# Quick tests
# ============================================================

if __name__ == "__main__":
    print("🧪 Testing Mail Search Tools...")

    # Test date parsing
    print("\n📅 Date parsing:")
    print(f"  '30 days' -> {_parse_relative_date('30 days')}")
    print(f"  '2 weeks' -> {_parse_relative_date('2 weeks')}")
    print(f"  '2025-11-01' -> {_parse_relative_date('2025-11-01')}")

    # Test search (no speak for test)
    print("\n🔍 Search test:")
    result = mail_search("test", speak=False)
    print("  Query: test")
    print(f"  Source: {result.get('source')}")
    print(f"  Count: {result.get('count')}")
    print(f"  Time: {result.get('search_time_ms')}ms")

    print("\n✅ Mail search tools ready!")
