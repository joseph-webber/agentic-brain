#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Professional Community Network - Internal Talent Platform
==========================================================

Build internal professional communities where employees can:
- Maintain professional profiles with skills and endorsements
- Discover colleagues working in similar domains
- Share knowledge and engage with internal content
- Build cross-departmental connections

This is the foundation for knowledge-sharing enterprise cultures.

Usage:
    python examples/enterprise/professional_community.py

Requirements:
    - pip install agentic-brain

Example:
    >>> from examples.enterprise.professional_community import ProfessionalCommunityAgent
    >>> agent = ProfessionalCommunityAgent()
    >>> await agent.create_profile(user_id="emp_001", skills=["Python", "ML"])
    >>> connections = await agent.find_similar_professionals("emp_001")

Key Patterns:
    - Graph-based professional networking
    - Skill endorsement relationships
    - Content engagement tracking
    - Personalised feed algorithms
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConnectionStrength(Enum):
    """Relationship strength between professionals."""

    WEAK = "weak"  # Same company
    MODERATE = "moderate"  # Same department or shared project
    STRONG = "strong"  # Direct collaboration
    ENDORSED = "endorsed"  # Mutual skill endorsements


class ContentType(Enum):
    """Types of shareable professional content."""

    ARTICLE = "article"
    UPDATE = "update"
    ACHIEVEMENT = "achievement"
    PROJECT = "project"
    INSIGHT = "insight"


@dataclass
class SkillEndorsement:
    """An endorsement of a skill by another professional."""

    skill: str
    endorser_id: str
    endorsed_at: datetime
    relationship: str  # "colleague", "manager", "collaborator"
    note: str | None = None


@dataclass
class ProfessionalProfile:
    """A professional's internal network profile."""

    user_id: str
    display_name: str
    title: str
    department: str
    location: str
    summary: str
    skills: list[str] = field(default_factory=list)
    endorsements: list[SkillEndorsement] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    experience_years: int = 0
    connections: list[str] = field(default_factory=list)
    visibility: str = "internal"  # "internal", "team", "department"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def skill_strengths(self) -> dict[str, int]:
        """Calculate skill strength based on endorsement count."""
        strengths = {}
        for skill in self.skills:
            count = sum(1 for e in self.endorsements if e.skill == skill)
            strengths[skill] = count
        return strengths


@dataclass
class ContentPost:
    """Professional content shared within the network."""

    post_id: str
    author_id: str
    content_type: ContentType
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    mentions: list[str] = field(default_factory=list)
    engagement: dict = field(
        default_factory=lambda: {"views": 0, "reactions": 0, "comments": 0, "shares": 0}
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConnectionRecommendation:
    """A recommended professional connection."""

    user_id: str
    display_name: str
    title: str
    reason: str
    shared_skills: list[str]
    mutual_connections: int
    relevance_score: float


class ProfessionalCommunityAgent:
    """
    Agent for managing enterprise professional communities.

    Enables internal talent discovery, skill-based networking,
    and knowledge sharing across organizational boundaries.
    """

    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # In-memory stores for demo/testing
        self._profiles: dict[str, ProfessionalProfile] = {}
        self._posts: dict[str, ContentPost] = {}
        self._feed_cache: dict[str, list[str]] = {}

        self._neo4j_driver = None

    async def _ensure_neo4j(self):
        """Lazily initialize Neo4j connection."""
        if self._neo4j_driver is None and self.neo4j_uri:
            try:
                from neo4j import AsyncGraphDatabase

                self._neo4j_driver = AsyncGraphDatabase.driver(
                    self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
                )
            except ImportError:
                logger.warning("neo4j package not installed, using in-memory store")

    async def create_profile(
        self,
        user_id: str,
        display_name: str,
        title: str,
        department: str,
        location: str = "",
        summary: str = "",
        skills: list[str] | None = None,
        interests: list[str] | None = None,
        experience_years: int = 0,
    ) -> ProfessionalProfile:
        """
        Create a professional profile in the talent network.

        Args:
            user_id: Unique employee identifier
            display_name: Professional display name
            title: Job title
            department: Organizational department
            location: Office location
            summary: Professional summary/bio
            skills: List of professional skills
            interests: Areas of interest
            experience_years: Years of professional experience

        Returns:
            Created ProfessionalProfile
        """
        profile = ProfessionalProfile(
            user_id=user_id,
            display_name=display_name,
            title=title,
            department=department,
            location=location,
            summary=summary,
            skills=skills or [],
            interests=interests or [],
            experience_years=experience_years,
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MERGE (p:Professional {userId: $user_id})
                    SET p.displayName = $display_name,
                        p.title = $title,
                        p.department = $department,
                        p.location = $location,
                        p.summary = $summary,
                        p.skills = $skills,
                        p.interests = $interests,
                        p.experienceYears = $experience_years,
                        p.createdAt = datetime(),
                        p.updatedAt = datetime()
                    """,
                    user_id=user_id,
                    display_name=display_name,
                    title=title,
                    department=department,
                    location=location,
                    summary=summary,
                    skills=skills or [],
                    interests=interests or [],
                    experience_years=experience_years,
                )

                # Create skill nodes and relationships
                for skill in skills or []:
                    await session.run(
                        """
                        MERGE (s:Skill {name: $skill})
                        WITH s
                        MATCH (p:Professional {userId: $user_id})
                        MERGE (p)-[:HAS_SKILL]->(s)
                        """,
                        skill=skill,
                        user_id=user_id,
                    )

        self._profiles[user_id] = profile
        logger.info(f"Created professional profile for {display_name}")
        return profile

    async def endorse_skill(
        self,
        endorser_id: str,
        endorsed_id: str,
        skill: str,
        relationship: str = "colleague",
        note: str | None = None,
    ) -> SkillEndorsement:
        """
        Endorse a colleague's skill.

        Args:
            endorser_id: ID of the endorsing professional
            endorsed_id: ID of the professional being endorsed
            skill: Skill being endorsed
            relationship: Professional relationship
            note: Optional endorsement note

        Returns:
            Created SkillEndorsement
        """
        endorsement = SkillEndorsement(
            skill=skill,
            endorser_id=endorser_id,
            endorsed_at=datetime.now(timezone.utc),
            relationship=relationship,
            note=note,
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (endorser:Professional {userId: $endorser_id})
                    MATCH (endorsed:Professional {userId: $endorsed_id})
                    MATCH (skill:Skill {name: $skill})
                    MERGE (endorser)-[e:ENDORSES {skill: $skill}]->(endorsed)
                    SET e.relationship = $relationship,
                        e.note = $note,
                        e.endorsedAt = datetime()
                    """,
                    endorser_id=endorser_id,
                    endorsed_id=endorsed_id,
                    skill=skill,
                    relationship=relationship,
                    note=note,
                )

        if endorsed_id in self._profiles:
            self._profiles[endorsed_id].endorsements.append(endorsement)

        logger.info(f"{endorser_id} endorsed {endorsed_id} for {skill}")
        return endorsement

    async def find_similar_professionals(
        self,
        user_id: str,
        limit: int = 10,
    ) -> list[ConnectionRecommendation]:
        """
        Find professionals with similar skills and interests.

        Uses graph-based similarity to recommend connections
        based on shared skills, mutual connections, and interests.

        Args:
            user_id: The user seeking recommendations
            limit: Maximum recommendations to return

        Returns:
            List of ConnectionRecommendations sorted by relevance
        """
        recommendations = []

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                # Find similar professionals using graph similarity
                result = await session.run(
                    """
                    MATCH (me:Professional {userId: $user_id})-[:HAS_SKILL]->(skill:Skill)
                    MATCH (other:Professional)-[:HAS_SKILL]->(skill)
                    WHERE other.userId <> $user_id
                    AND NOT (me)-[:CONNECTED_TO]-(other)
                    WITH other, collect(skill.name) as sharedSkills, count(skill) as skillOverlap
                    
                    OPTIONAL MATCH (me)-[:CONNECTED_TO]-(mutual)-[:CONNECTED_TO]-(other)
                    WITH other, sharedSkills, skillOverlap, count(distinct mutual) as mutualCount
                    
                    // Calculate relevance score
                    WITH other, sharedSkills, mutualCount,
                         (skillOverlap * 0.6 + mutualCount * 0.4) as relevanceScore
                    
                    ORDER BY relevanceScore DESC
                    LIMIT $limit
                    
                    RETURN other.userId as userId,
                           other.displayName as displayName,
                           other.title as title,
                           sharedSkills,
                           mutualCount,
                           relevanceScore
                    """,
                    user_id=user_id,
                    limit=limit,
                )

                async for record in result:
                    shared_skills = record["sharedSkills"]
                    reason = self._generate_connection_reason(
                        shared_skills,
                        record["mutualCount"],
                    )
                    recommendations.append(
                        ConnectionRecommendation(
                            user_id=record["userId"],
                            display_name=record["displayName"],
                            title=record["title"],
                            reason=reason,
                            shared_skills=shared_skills,
                            mutual_connections=record["mutualCount"],
                            relevance_score=record["relevanceScore"],
                        )
                    )
        else:
            # Fallback to in-memory similarity
            recommendations = await self._in_memory_similarity(user_id, limit)

        return recommendations

    async def _in_memory_similarity(
        self,
        user_id: str,
        limit: int,
    ) -> list[ConnectionRecommendation]:
        """Calculate similarity using in-memory data."""
        if user_id not in self._profiles:
            return []

        user = self._profiles[user_id]
        user_skills = set(user.skills)
        candidates = []

        for other_id, other in self._profiles.items():
            if other_id == user_id:
                continue
            if other_id in user.connections:
                continue

            other_skills = set(other.skills)
            shared = user_skills & other_skills

            if shared:
                mutual = len(set(user.connections) & set(other.connections))
                score = len(shared) * 0.6 + mutual * 0.4

                candidates.append(
                    ConnectionRecommendation(
                        user_id=other_id,
                        display_name=other.display_name,
                        title=other.title,
                        reason=self._generate_connection_reason(list(shared), mutual),
                        shared_skills=list(shared),
                        mutual_connections=mutual,
                        relevance_score=score,
                    )
                )

        candidates.sort(key=lambda x: x.relevance_score, reverse=True)
        return candidates[:limit]

    def _generate_connection_reason(
        self,
        shared_skills: list[str],
        mutual_count: int,
    ) -> str:
        """Generate a human-readable connection reason."""
        parts = []

        if shared_skills:
            if len(shared_skills) == 1:
                parts.append(f"You both know {shared_skills[0]}")
            elif len(shared_skills) == 2:
                parts.append(
                    f"You share expertise in {shared_skills[0]} and {shared_skills[1]}"
                )
            else:
                parts.append(
                    f"You share {len(shared_skills)} skills including {shared_skills[0]}"
                )

        if mutual_count > 0:
            parts.append(
                f"{mutual_count} mutual connection{'s' if mutual_count > 1 else ''}"
            )

        return " • ".join(parts) if parts else "Works in your organization"

    async def connect(
        self,
        user_id: str,
        target_id: str,
        strength: ConnectionStrength = ConnectionStrength.MODERATE,
    ) -> bool:
        """
        Create a connection between two professionals.

        Args:
            user_id: Requesting user ID
            target_id: Target user ID
            strength: Initial connection strength

        Returns:
            True if connection created successfully
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Professional {userId: $user_id})
                    MATCH (b:Professional {userId: $target_id})
                    MERGE (a)-[c:CONNECTED_TO]-(b)
                    SET c.strength = $strength,
                        c.connectedAt = datetime()
                    """,
                    user_id=user_id,
                    target_id=target_id,
                    strength=strength.value,
                )

        # Update in-memory
        if user_id in self._profiles:
            if target_id not in self._profiles[user_id].connections:
                self._profiles[user_id].connections.append(target_id)
        if target_id in self._profiles:
            if user_id not in self._profiles[target_id].connections:
                self._profiles[target_id].connections.append(user_id)

        logger.info(f"Connected {user_id} with {target_id}")
        return True

    async def post_content(
        self,
        author_id: str,
        content_type: ContentType,
        title: str,
        body: str,
        tags: list[str] | None = None,
        mentions: list[str] | None = None,
    ) -> ContentPost:
        """
        Post content to the professional feed.

        Args:
            author_id: ID of the author
            content_type: Type of content
            title: Post title
            body: Post body/content
            tags: Content tags for discovery
            mentions: User IDs mentioned

        Returns:
            Created ContentPost
        """
        post_id = str(uuid4())
        post = ContentPost(
            post_id=post_id,
            author_id=author_id,
            content_type=content_type,
            title=title,
            body=body,
            tags=tags or [],
            mentions=mentions or [],
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (author:Professional {userId: $author_id})
                    CREATE (p:Post {
                        postId: $post_id,
                        contentType: $content_type,
                        title: $title,
                        body: $body,
                        tags: $tags,
                        views: 0,
                        reactions: 0,
                        createdAt: datetime()
                    })
                    CREATE (author)-[:AUTHORED]->(p)
                    
                    // Create tag relationships for discovery
                    WITH p
                    UNWIND $tags as tagName
                    MERGE (t:Tag {name: tagName})
                    MERGE (p)-[:TAGGED]->(t)
                    """,
                    author_id=author_id,
                    post_id=post_id,
                    content_type=content_type.value,
                    title=title,
                    body=body,
                    tags=tags or [],
                )

        self._posts[post_id] = post

        # Invalidate feed caches for author's network
        self._feed_cache.clear()

        logger.info(f"Created {content_type.value} post: {title}")
        return post

    async def get_feed(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ContentPost]:
        """
        Get personalized content feed for a user.

        Feed includes content from connections, endorsed topics,
        and trending posts within the organization.

        Args:
            user_id: User requesting feed
            limit: Posts per page
            offset: Pagination offset

        Returns:
            List of ContentPosts
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (me:Professional {userId: $user_id})
                    
                    // Get posts from connections
                    OPTIONAL MATCH (me)-[:CONNECTED_TO]-(connection)-[:AUTHORED]->(post:Post)
                    
                    // Get posts with tags matching user's skills/interests
                    OPTIONAL MATCH (me)-[:HAS_SKILL]->(skill:Skill)
                    OPTIONAL MATCH (relevant:Post)-[:TAGGED]->(tag:Tag)
                    WHERE tag.name IN me.interests OR tag.name = skill.name
                    
                    WITH collect(distinct post) + collect(distinct relevant) as allPosts
                    UNWIND allPosts as p
                    
                    WITH DISTINCT p
                    ORDER BY p.createdAt DESC
                    SKIP $offset
                    LIMIT $limit
                    
                    MATCH (author:Professional)-[:AUTHORED]->(p)
                    
                    RETURN p.postId as postId,
                           author.userId as authorId,
                           p.contentType as contentType,
                           p.title as title,
                           p.body as body,
                           p.tags as tags,
                           p.views as views,
                           p.reactions as reactions,
                           p.createdAt as createdAt
                    """,
                    user_id=user_id,
                    limit=limit,
                    offset=offset,
                )

                posts = []
                async for record in result:
                    posts.append(
                        ContentPost(
                            post_id=record["postId"],
                            author_id=record["authorId"],
                            content_type=ContentType(record["contentType"]),
                            title=record["title"],
                            body=record["body"],
                            tags=record["tags"] or [],
                            engagement={
                                "views": record["views"] or 0,
                                "reactions": record["reactions"] or 0,
                            },
                        )
                    )
                return posts

        # In-memory fallback
        return self._get_in_memory_feed(user_id, limit, offset)

    def _get_in_memory_feed(
        self,
        user_id: str,
        limit: int,
        offset: int,
    ) -> list[ContentPost]:
        """Generate feed from in-memory data."""
        if user_id not in self._profiles:
            return []

        user = self._profiles[user_id]
        connection_ids = set(user.connections)
        user_interests = set(user.skills + user.interests)

        # Score and filter posts
        scored_posts = []
        for post in self._posts.values():
            score = 0

            # Connection bonus
            if post.author_id in connection_ids:
                score += 10

            # Interest/skill match
            post_topics = set(post.tags)
            overlap = len(user_interests & post_topics)
            score += overlap * 5

            # Engagement bonus
            score += post.engagement.get("reactions", 0) * 0.1

            if score > 0:
                scored_posts.append((score, post))

        scored_posts.sort(key=lambda x: x[0], reverse=True)

        return [p for _, p in scored_posts[offset : offset + limit]]

    async def record_engagement(
        self,
        user_id: str,
        post_id: str,
        engagement_type: str,  # "view", "react", "comment", "share"
    ) -> None:
        """
        Record engagement with a post.

        Args:
            user_id: User engaging with content
            post_id: Post being engaged with
            engagement_type: Type of engagement
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                if engagement_type == "view":
                    await session.run(
                        """
                        MATCH (p:Post {postId: $post_id})
                        SET p.views = coalesce(p.views, 0) + 1
                        """,
                        post_id=post_id,
                    )
                else:
                    await session.run(
                        """
                        MATCH (u:Professional {userId: $user_id})
                        MATCH (p:Post {postId: $post_id})
                        MERGE (u)-[e:ENGAGED {type: $engagement_type}]->(p)
                        SET e.timestamp = datetime()
                        
                        WITH p
                        SET p.reactions = coalesce(p.reactions, 0) + 1
                        """,
                        user_id=user_id,
                        post_id=post_id,
                        engagement_type=engagement_type,
                    )

        # Update in-memory
        if post_id in self._posts:
            if engagement_type == "view":
                self._posts[post_id].engagement["views"] += 1
            else:
                self._posts[post_id].engagement["reactions"] += 1

    async def get_network_stats(self, user_id: str) -> dict[str, Any]:
        """
        Get network statistics for a user.

        Returns:
            Dictionary of network stats
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (me:Professional {userId: $user_id})
                    
                    OPTIONAL MATCH (me)-[:CONNECTED_TO]-(connection)
                    WITH me, count(connection) as connectionCount
                    
                    OPTIONAL MATCH (me)-[:AUTHORED]->(post:Post)
                    WITH me, connectionCount, count(post) as postCount, sum(post.views) as totalViews
                    
                    OPTIONAL MATCH (endorser)-[:ENDORSES]->(me)
                    WITH me, connectionCount, postCount, totalViews, count(endorser) as endorsementCount
                    
                    RETURN connectionCount, postCount, totalViews, endorsementCount
                    """,
                    user_id=user_id,
                )

                record = await result.single()
                if record:
                    return {
                        "connections": record["connectionCount"],
                        "posts": record["postCount"],
                        "total_views": record["totalViews"] or 0,
                        "endorsements": record["endorsementCount"],
                    }

        # In-memory fallback
        profile = self._profiles.get(user_id)
        if profile:
            return {
                "connections": len(profile.connections),
                "posts": sum(1 for p in self._posts.values() if p.author_id == user_id),
                "total_views": sum(
                    p.engagement["views"]
                    for p in self._posts.values()
                    if p.author_id == user_id
                ),
                "endorsements": len(profile.endorsements),
            }

        return {"connections": 0, "posts": 0, "total_views": 0, "endorsements": 0}

    async def close(self):
        """Clean up resources."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()


# Example usage
async def main():
    """Demonstrate enterprise talent network features."""
    agent = ProfessionalCommunityAgent()

    # Create professional profiles
    alice = await agent.create_profile(
        user_id="alice_001",
        display_name="Alice Chen",
        title="Senior Data Scientist",
        department="Analytics",
        skills=["Python", "Machine Learning", "Data Visualization"],
        interests=["AI Ethics", "NLP"],
        experience_years=8,
    )

    bob = await agent.create_profile(
        user_id="bob_002",
        display_name="Bob Martinez",
        title="ML Engineer",
        department="Engineering",
        skills=["Python", "TensorFlow", "MLOps"],
        interests=["NLP", "Computer Vision"],
        experience_years=5,
    )

    # Endorse skills
    await agent.endorse_skill(
        endorser_id="bob_002",
        endorsed_id="alice_001",
        skill="Machine Learning",
        relationship="collaborator",
        note="Alice's ML expertise saved our project",
    )

    # Find similar professionals
    recommendations = await agent.find_similar_professionals("alice_001")
    print("\nRecommended connections for Alice:")
    for rec in recommendations:
        print(f"  - {rec.display_name}: {rec.reason}")

    # Create connection
    await agent.connect("alice_001", "bob_002")

    # Share content
    post = await agent.post_content(
        author_id="alice_001",
        content_type=ContentType.INSIGHT,
        title="Tips for Effective ML Model Validation",
        body="Here are 5 strategies we use to validate ML models...",
        tags=["Machine Learning", "Best Practices"],
    )

    # Get personalized feed
    feed = await agent.get_feed("bob_002")
    print(f"\nBob's feed has {len(feed)} posts")

    # Record engagement
    await agent.record_engagement("bob_002", post.post_id, "react")

    # Get network stats
    stats = await agent.get_network_stats("alice_001")
    print(
        f"\nAlice's network: {stats['connections']} connections, {stats['endorsements']} endorsements"
    )

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
