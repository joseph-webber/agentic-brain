# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unified Conversation Summarization System
=========================================

Compatible with brain-core's session_stitcher format.
Provides both real-time (mid-conversation) and session-level summarization.

Features:
    - Real-time compression (compress during conversation)
    - Session summarization (end of session)
    - Topic extraction
    - Entity extraction
    - Key fact extraction
    - Auto-summarize old sessions
    - Neo4j storage with brain-core schema compatibility

Example:
    >>> from agentic_brain.memory import UnifiedSummarizer, SummaryType
    >>>
    >>> summarizer = UnifiedSummarizer(llm_router=my_llm)
    >>>
    >>> # Compress mid-conversation
    >>> compressed, summary = await summarizer.compress_conversation(messages)
    >>>
    >>> # Session summary
    >>> summary = await summarizer.summarize_session("session-123", messages)
    >>>
    >>> # Extract topics
    >>> topics = await summarizer.extract_topics(messages)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Any, cast

logger = logging.getLogger(__name__)


class SummaryType(Enum):
    """
    Type of summary.

    Attributes:
        REALTIME: Mid-conversation compression (for context management)
        SESSION: End of session summary (for long-term storage)
        TOPIC: Topic-specific summary
        ENTITY: Entity-focused summary
    """

    REALTIME = "realtime"
    SESSION = "session"
    TOPIC = "topic"
    ENTITY = "entity"


@dataclass
class ConversationSummary:
    """
    Unified summary format - compatible with brain-core.

    This format is designed to work seamlessly with brain-core's
    SessionStitcher and PerfectMemory systems.

    Attributes:
        id: Unique summary identifier
        session_id: Session this summary belongs to
        summary_type: Type of summary (realtime, session, topic, entity)
        content: The summary text
        message_count: Number of messages summarized
        start_time: Timestamp of first message
        end_time: Timestamp of last message
        topics: Main topics discussed
        entities: Named entities mentioned (people, places, things)
        key_facts: Key facts and decisions
        sentiment: Overall sentiment (optional)
        metadata: Additional metadata

    Example:
        >>> summary = ConversationSummary(
        ...     id="abc123",
        ...     session_id="session-456",
        ...     summary_type=SummaryType.SESSION,
        ...     content="Discussed PR review for SD-1330...",
        ...     message_count=25,
        ...     start_time=datetime.now(),
        ...     end_time=datetime.now(),
        ...     topics=["PR review", "JIRA", "testing"],
        ...     entities=["Steve", "SD-1330"],
        ...     key_facts=["Need to add unit tests", "Approved for merge"],
        ... )
    """

    id: str
    session_id: str
    summary_type: SummaryType
    content: str
    message_count: int
    start_time: datetime
    end_time: datetime
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    sentiment: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dict for storage/serialization.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary_type": self.summary_type.value,
            "content": self.content,
            "message_count": self.message_count,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "topics": self.topics,
            "entities": self.entities,
            "key_facts": self.key_facts,
            "sentiment": self.sentiment,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationSummary:
        """
        Create from dict.

        Args:
            data: Dictionary with summary data

        Returns:
            ConversationSummary instance
        """
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            summary_type=SummaryType(data["summary_type"]),
            content=data["content"],
            message_count=data["message_count"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            topics=data.get("topics", []),
            entities=data.get("entities", []),
            key_facts=data.get("key_facts", []),
            sentiment=data.get("sentiment"),
            metadata=data.get("metadata", {}),
        )

    def to_neo4j(self) -> dict[str, Any]:
        """
        Convert to Neo4j-compatible format (brain-core compatible).

        Uses JSON strings for list fields to ensure Neo4j compatibility.

        Returns:
            Dictionary suitable for Neo4j property storage
        """
        return {
            "id": self.id,
            "session_id": self.session_id,
            "summary_type": self.summary_type.value,
            "content": self.content,
            "message_count": self.message_count,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "topics_json": json.dumps(self.topics),
            "entities_json": json.dumps(self.entities),
            "key_facts_json": json.dumps(self.key_facts),
            "sentiment": self.sentiment,
        }

    @classmethod
    def from_neo4j(cls, data: dict[str, Any]) -> ConversationSummary:
        """
        Create from Neo4j record.

        Args:
            data: Neo4j node properties

        Returns:
            ConversationSummary instance
        """
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            summary_type=SummaryType(data["summary_type"]),
            content=data["content"],
            message_count=data["message_count"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            topics=json.loads(data.get("topics_json", "[]")),
            entities=json.loads(data.get("entities_json", "[]")),
            key_facts=json.loads(data.get("key_facts_json", "[]")),
            sentiment=data.get("sentiment"),
            metadata={},
        )


class UnifiedSummarizer:
    """
    Unified summarization compatible with brain-core.

    Supports:
    - Real-time summarization (compress during conversation)
    - Session summarization (end of session)
    - Topic extraction
    - Entity extraction
    - Key fact extraction
    - Auto-summarization of old sessions

    Example:
        >>> summarizer = UnifiedSummarizer(llm_router=my_llm, memory=neo4j_memory)
        >>>
        >>> # Real-time compression
        >>> compressed, summary = await summarizer.compress_conversation(messages)
        >>>
        >>> # Session summary
        >>> summary = await summarizer.summarize_session("session-123", messages)
        >>>
        >>> # Extract topics
        >>> topics = await summarizer.extract_topics(messages)
    """

    # Common words to exclude from keyword extraction
    COMMON_WORDS = frozenset(
        {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "it",
            "that",
            "this",
            "what",
            "which",
            "who",
            "how",
            "when",
            "where",
            "i",
            "you",
            "we",
            "they",
            "he",
            "she",
            "my",
            "your",
            "and",
            "or",
            "but",
            "not",
            "so",
            "if",
            "then",
            "than",
            "just",
            "also",
            "can",
            "about",
            "up",
            "out",
            "like",
            "get",
            "got",
            "going",
            "there",
            "their",
            "them",
            "these",
            "those",
            "some",
            "any",
            "all",
            "over",
            "through",
            "under",
            "before",
            "after",
            "above",
            "below",
            "between",
            "such",
            "very",
            "more",
            "most",
            "other",
            "each",
            "only",
            "same",
            "even",
            "here",
            "away",
            "back",
            "still",
        }
    )

    def __init__(
        self,
        llm_router: Any | None = None,
        memory: Any | None = None,
        use_local_llm: bool = True,
        max_summary_tokens: int = 500,
    ):
        """
        Initialize unified summarizer.

        Args:
            llm_router: LLM for generating summaries (optional)
            memory: Neo4jMemory for storage (optional)
            use_local_llm: Prefer local LLM when available
            max_summary_tokens: Maximum tokens for generated summaries
        """
        self.llm_router = llm_router
        self.memory = memory
        self.use_local_llm = use_local_llm
        self.max_summary_tokens = max_summary_tokens

    # =========================================================================
    # REAL-TIME SUMMARIZATION (mid-conversation)
    # =========================================================================

    async def compress_conversation(
        self,
        messages: list[dict[str, str]],
        keep_recent: int = 5,
    ) -> tuple[list[dict[str, str]], ConversationSummary | None]:
        """
        Compress old messages while keeping recent ones.

        This is for real-time context management during a conversation.
        Old messages are summarized and replaced with a summary.

        Args:
            messages: Full message history
            keep_recent: Number of recent messages to keep unchanged

        Returns:
            Tuple of (compressed_messages, summary) where summary is None
            if no compression was needed.

        Example:
            >>> compressed, summary = await summarizer.compress_conversation(
            ...     messages, keep_recent=5
            ... )
            >>> # compressed now has summary + last 5 messages
        """
        if len(messages) <= keep_recent:
            return messages, None

        old_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        summary = await self._generate_summary(old_messages, SummaryType.REALTIME)

        # Create compressed message list
        compressed = [
            {
                "role": "system",
                "content": f"[Previous conversation summary: {summary.content}]",
            }
        ] + recent_messages

        logger.debug(
            f"Compressed {len(old_messages)} messages into summary, keeping {keep_recent} recent"
        )

        return compressed, summary

    async def should_compress(
        self,
        messages: list[dict[str, str]],
        threshold: int = 20,
    ) -> bool:
        """
        Check if conversation needs compression.

        Args:
            messages: Message list
            threshold: Compress if more than this many messages

        Returns:
            True if compression recommended
        """
        return len(messages) > threshold

    def should_compress_sync(
        self,
        messages: list[dict[str, str]],
        threshold: int = 20,
    ) -> bool:
        """Synchronous version of should_compress."""
        return len(messages) > threshold

    # =========================================================================
    # SESSION SUMMARIZATION (brain-core compatible)
    # =========================================================================

    async def summarize_session(
        self,
        session_id: str,
        messages: list[dict[str, str]],
    ) -> ConversationSummary:
        """
        Create session-level summary (brain-core compatible).

        This is for end-of-session summarization, producing a summary
        that can be stored in Neo4j and queried later.

        Args:
            session_id: Session identifier
            messages: All messages from the session

        Returns:
            ConversationSummary with full metadata

        Example:
            >>> summary = await summarizer.summarize_session("sess-123", messages)
            >>> # summary.topics, summary.key_facts, etc. are populated
        """
        summary = await self._generate_summary(
            messages,
            SummaryType.SESSION,
            session_id=session_id,
        )

        # Enrich with extracted information
        if self.llm_router:
            try:
                summary.topics = await self.extract_topics(messages)
                summary.key_facts = await self.extract_key_facts(messages)
            except Exception as e:
                logger.warning(f"Failed to extract topics/facts: {e}")

        if self.memory:
            await self._store_summary(summary)

        logger.info(
            f"Created session summary for {session_id}: {len(summary.content)} chars"
        )

        return summary

    async def get_session_summary(
        self,
        session_id: str,
    ) -> ConversationSummary | None:
        """
        Retrieve session summary from storage.

        Args:
            session_id: Session identifier

        Returns:
            ConversationSummary if found, None otherwise
        """
        if not self.memory:
            return None

        try:
            if hasattr(self.memory, "query_async"):
                result = await self.memory.query_async(
                    "MATCH (s:SessionSummary {session_id: $sid}) RETURN s",
                    {"sid": session_id},
                )
            elif hasattr(self.memory, "query"):
                result = self.memory.query(
                    "MATCH (s:SessionSummary {session_id: $sid}) RETURN s",
                    {"sid": session_id},
                )
            else:
                return None

            if result:
                return ConversationSummary.from_neo4j(dict(result[0]["s"]))
        except Exception as e:
            logger.warning(f"Failed to get session summary: {e}")

        return None

    # =========================================================================
    # TOPIC & ENTITY EXTRACTION
    # =========================================================================

    async def extract_topics(
        self,
        messages: list[dict[str, str]],
        max_topics: int = 5,
    ) -> list[str]:
        """
        Extract main topics from conversation.

        Args:
            messages: Conversation messages
            max_topics: Maximum topics to return

        Returns:
            List of topic strings
        """
        text = self._messages_to_text(messages)

        if self.llm_router:
            try:
                prompt = f"""Extract the {max_topics} main topics from this conversation.
Return ONLY a comma-separated list of topics, nothing else.

Conversation:
{text[:3000]}

Topics:"""
                response = await self._call_llm(prompt)
                topics = [t.strip() for t in response.split(",") if t.strip()]
                return topics[:max_topics]
            except Exception as e:
                logger.warning(f"LLM topic extraction failed: {e}")

        # Fallback: simple keyword extraction
        return self._extract_keywords(text, max_topics)

    async def extract_entities(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """
        Extract named entities (people, places, things).

        Args:
            messages: Conversation messages

        Returns:
            List of dicts with 'name' and 'type' keys
        """
        text = self._messages_to_text(messages)

        if self.llm_router:
            try:
                prompt = f"""Extract named entities from this conversation.
Return as JSON list: [{{"name": "...", "type": "person|place|org|thing"}}]
Return ONLY valid JSON, nothing else.

Conversation:
{text[:3000]}

Entities:"""
                response = await self._call_llm(prompt)
                # Try to parse JSON from response
                response = response.strip()
                if response.startswith("["):
                    return cast(list[dict[str, str]], json.loads(response))
            except Exception as e:
                logger.warning(f"Entity extraction failed: {e}")

        # Fallback: extract capitalized words that might be names
        return self._extract_capitalized_entities(text)

    async def extract_key_facts(
        self,
        messages: list[dict[str, str]],
        max_facts: int = 10,
    ) -> list[str]:
        """
        Extract key facts/decisions from conversation.

        Args:
            messages: Conversation messages
            max_facts: Maximum facts to return

        Returns:
            List of fact strings
        """
        text = self._messages_to_text(messages)

        if self.llm_router:
            try:
                prompt = f"""Extract the {max_facts} most important facts or decisions from this conversation.
Return ONLY a numbered list, one fact per line.

Conversation:
{text[:3000]}

Key facts:"""
                response = await self._call_llm(prompt)
                facts = [
                    line.strip().lstrip("0123456789.-) ")
                    for line in response.split("\n")
                    if line.strip() and not line.strip().startswith("Key facts")
                ]
                return [f for f in facts if len(f) > 5][:max_facts]
            except Exception as e:
                logger.warning(f"Key fact extraction failed: {e}")

        return []

    # =========================================================================
    # AUTO-SUMMARIZE OLD MEMORIES (brain-core compatible)
    # =========================================================================

    async def auto_summarize_old(
        self,
        older_than_days: int = 7,
        min_messages: int = 50,
    ) -> list[ConversationSummary]:
        """
        Auto-summarize old sessions (brain-core compatible).

        Groups old sessions and creates summaries to save space.

        Args:
            older_than_days: Only summarize sessions older than this
            min_messages: Only summarize sessions with at least this many messages

        Returns:
            List of created summaries
        """
        if not self.memory:
            logger.warning("No memory configured for auto_summarize_old")
            return []

        try:
            # Find old sessions without summaries
            cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).isoformat()

            if hasattr(self.memory, "query_async"):
                old_sessions = await self.memory.query_async(
                    """
                    MATCH (m:Message)
                    WHERE m.timestamp < $cutoff
                    WITH m.session_id as sid, collect(m) as messages
                    WHERE size(messages) >= $min_msgs
                    AND NOT EXISTS {
                        MATCH (s:SessionSummary {session_id: sid})
                    }
                    RETURN sid, messages
                    ORDER BY messages[0].timestamp
                    LIMIT 10
                    """,
                    {"cutoff": cutoff, "min_msgs": min_messages},
                )
            else:
                old_sessions = []

            summaries = []
            for session in old_sessions:
                messages = [
                    {"role": m["role"], "content": m["content"]}
                    for m in session["messages"]
                ]
                summary = await self.summarize_session(session["sid"], messages)
                summaries.append(summary)

            logger.info(f"Auto-summarized {len(summaries)} old sessions")
            return summaries

        except Exception as e:
            logger.error(f"Auto-summarize failed: {e}")
            return []

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _generate_summary(
        self,
        messages: list[dict[str, str]],
        summary_type: SummaryType,
        session_id: str | None = None,
    ) -> ConversationSummary:
        """Generate summary using LLM or fallback."""
        text = self._messages_to_text(messages)

        if self.llm_router:
            try:
                prompt = f"""Summarize this conversation in {self.max_summary_tokens} tokens or less.
Focus on: key decisions, important facts, action items, and conclusions.

Conversation:
{text[:4000]}

Summary:"""
                content = await self._call_llm(prompt)
            except Exception as e:
                logger.warning(f"LLM summarization failed: {e}")
                content = self._extractive_summary(messages)
        else:
            # Fallback: extractive summary
            content = self._extractive_summary(messages)

        now = datetime.now(UTC)

        # Extract timestamps from messages if available
        start_time = now
        end_time = now
        if messages:
            # Try to get actual timestamps
            first_ts = messages[0].get("timestamp")
            last_ts = messages[-1].get("timestamp")
            if first_ts:
                with contextlib.suppress(ValueError, TypeError):
                    start_time = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            if last_ts:
                with contextlib.suppress(ValueError, TypeError):
                    end_time = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))

        return ConversationSummary(
            id=self._generate_id(session_id or "temp", now),
            session_id=session_id or f"temp_{now.timestamp()}",
            summary_type=summary_type,
            content=content,
            message_count=len(messages),
            start_time=start_time,
            end_time=end_time,
            topics=[],  # Populated by caller if needed
            entities=[],
            key_facts=[],
        )

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM router with prompt."""
        if hasattr(self.llm_router, "chat"):
            return await self.llm_router.chat([{"role": "user", "content": prompt}])
        elif hasattr(self.llm_router, "chat_async"):
            return await self.llm_router.chat_async(prompt)
        elif callable(self.llm_router):
            result = self.llm_router(prompt)
            if hasattr(result, "__await__"):
                return await result
            return result
        raise ValueError("LLM router doesn't support expected interface")

    async def _store_summary(self, summary: ConversationSummary) -> None:
        """Store summary to Neo4j."""
        try:
            query = """
            MERGE (s:SessionSummary {id: $id})
            SET s += $props
            """
            props = summary.to_neo4j()

            if hasattr(self.memory, "query_async"):
                await self.memory.query_async(query, {"id": summary.id, "props": props})
            elif hasattr(self.memory, "query"):
                self.memory.query(query, {"id": summary.id, "props": props})

            logger.debug(f"Stored summary {summary.id}")
        except Exception as e:
            logger.error(f"Failed to store summary: {e}")

    def _messages_to_text(self, messages: list[dict[str, str]]) -> str:
        """Convert messages to plain text."""
        return "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in messages
        )

    def _extractive_summary(
        self,
        messages: list[dict[str, str]],
        max_sentences: int = 5,
    ) -> str:
        """Simple extractive summary without LLM."""
        if not messages:
            return "No messages"

        # Take first and last few messages
        if len(messages) <= max_sentences:
            return self._messages_to_text(messages)

        first = messages[:2]
        last = messages[-2:]

        parts = []
        parts.append(f"Started with: {first[0].get('content', '')[:100]}")
        if len(messages) > 4:
            parts.append(f"[{len(messages) - 4} messages in between]")
        parts.append(f"Ended with: {last[-1].get('content', '')[:100]}")

        return " | ".join(parts)

    def _extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Simple keyword extraction without LLM."""
        # Tokenize and clean
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())

        # Count frequencies, excluding common words
        word_freq: dict[str, int] = {}
        for word in words:
            if word not in self.COMMON_WORDS:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]

    def _extract_capitalized_entities(self, text: str) -> list[dict[str, str]]:
        """Extract capitalized words as potential entities."""
        # Find capitalized words (potential names)
        pattern = r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
        matches = re.findall(pattern, text)

        # Dedupe and classify
        seen: set[str] = set()
        entities: list[dict[str, str]] = []

        for match in matches:
            if match not in seen and len(match) > 2:
                seen.add(match)
                # Simple heuristic for type
                entity_type = "person" if " " in match else "thing"
                entities.append({"name": match, "type": entity_type})

        return entities[:10]  # Limit results

    def _generate_id(self, session_id: str, timestamp: datetime) -> str:
        """Generate unique summary ID."""
        data = f"{session_id}:{timestamp.isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
