#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Skills Knowledge Graph - Workforce Capability Mapping
======================================================

Build a comprehensive skills taxonomy using graph relationships:
- Hierarchical skill categories (domains → skills → specialisations)
- Endorsement relationships between professionals
- Skill gap analysis for individuals and teams
- Capability trending and forecasting

This enables strategic workforce planning and development.

Usage:
    python examples/enterprise/skills_graph.py

Requirements:
    - Neo4j running on localhost:7687
    - pip install agentic-brain

Example:
    >>> from examples.enterprise.skills_graph import SkillsGraphAgent
    >>> agent = SkillsGraphAgent(neo4j_uri="bolt://localhost:7687")
    >>> await agent.add_skill("Machine Learning", domain="AI/ML")
    >>> gaps = await agent.analyse_skill_gaps(team_id="eng_team_001")

Key Patterns:
    - Neo4j graph-based skill taxonomy
    - Endorsement-weighted skill levels
    - Team capability aggregation
    - Learning path recommendations
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SkillLevel(Enum):
    """Proficiency levels for skills."""

    AWARENESS = 1  # Has heard of it
    BEGINNER = 2  # Learning, needs guidance
    INTERMEDIATE = 3  # Can work independently
    ADVANCED = 4  # Can mentor others
    EXPERT = 5  # Industry recognition


class EndorsementType(Enum):
    """Types of skill endorsements."""

    PEER = "peer"  # Colleague endorsement
    MANAGER = "manager"  # Manager confirmation
    PROJECT = "project"  # Based on project work
    CERTIFICATION = "certification"  # External validation
    SELF_ASSESSED = "self"  # Self-reported


class TrendDirection(Enum):
    """Skill demand trend."""

    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"
    EMERGING = "emerging"


@dataclass
class SkillNode:
    """A skill in the knowledge graph."""

    skill_id: str
    name: str
    domain: str
    parent_skill: str | None = None
    child_skills: list[str] = field(default_factory=list)
    related_skills: list[str] = field(default_factory=list)
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    demand_score: float = 0.5  # 0-1 market demand
    trend: TrendDirection = TrendDirection.STABLE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SkillAssessment:
    """A professional's skill assessment."""

    professional_id: str
    skill_id: str
    level: SkillLevel
    years_experience: float = 0
    last_used: datetime | None = None
    endorsements: list[dict] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)

    @property
    def endorsement_count(self) -> int:
        return len(self.endorsements)

    @property
    def verified_level(self) -> SkillLevel:
        """Level adjusted by endorsements and certifications."""
        base = self.level.value

        # Endorsement bonus
        if self.endorsement_count >= 5:
            base = min(5, base + 1)

        # Certification bonus
        if self.certifications:
            base = min(5, base + 1)

        return SkillLevel(base)


@dataclass
class SkillGap:
    """Identified skill gap."""

    skill_name: str
    required_level: SkillLevel
    current_level: SkillLevel | None
    gap_severity: float  # 0-1
    recommended_actions: list[str]
    estimated_time_to_close: str


@dataclass
class TeamCapability:
    """Aggregated team capability for a skill."""

    skill_name: str
    team_size: int
    practitioners: int
    average_level: float
    highest_level: SkillLevel
    coverage: float  # percentage of team with skill
    depth_score: float  # weighted by level


class SkillsGraphAgent:
    """
    Agent for managing workforce skills as a knowledge graph.

    Uses Neo4j to build rich skill taxonomies with:
    - Hierarchical skill relationships
    - Endorsement networks
    - Gap analysis
    - Trend tracking
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

        # In-memory stores
        self._skills: dict[str, SkillNode] = {}
        self._assessments: dict[str, list[SkillAssessment]] = (
            {}
        )  # professional_id -> assessments
        self._teams: dict[str, list[str]] = {}  # team_id -> professional_ids

        self._neo4j_driver = None

    async def _ensure_neo4j(self):
        """Lazily initialize Neo4j connection."""
        if self._neo4j_driver is None and self.neo4j_uri:
            try:
                from neo4j import AsyncGraphDatabase

                self._neo4j_driver = AsyncGraphDatabase.driver(
                    self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
                )

                # Create indexes for skill graph
                async with self._neo4j_driver.session() as session:
                    await session.run(
                        "CREATE INDEX skill_name IF NOT EXISTS FOR (s:Skill) ON (s.name)"
                    )
                    await session.run(
                        "CREATE INDEX domain_name IF NOT EXISTS FOR (d:Domain) ON (d.name)"
                    )
            except ImportError:
                logger.warning("neo4j package not installed, using in-memory store")

    async def add_skill(
        self,
        name: str,
        domain: str,
        parent_skill: str | None = None,
        related_skills: list[str] | None = None,
        description: str = "",
        keywords: list[str] | None = None,
    ) -> SkillNode:
        """
        Add a skill to the taxonomy.

        Args:
            name: Skill name
            domain: Skill domain (e.g., "Engineering", "Data Science")
            parent_skill: Parent skill for hierarchy
            related_skills: Related/similar skills
            description: Skill description
            keywords: Search keywords

        Returns:
            Created SkillNode
        """
        skill_id = name.lower().replace(" ", "_")

        skill = SkillNode(
            skill_id=skill_id,
            name=name,
            domain=domain,
            parent_skill=parent_skill,
            related_skills=related_skills or [],
            description=description,
            keywords=keywords or [],
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                # Create skill node
                await session.run(
                    """
                    MERGE (d:Domain {name: $domain})
                    MERGE (s:Skill {skillId: $skill_id})
                    SET s.name = $name,
                        s.description = $description,
                        s.keywords = $keywords,
                        s.demandScore = 0.5,
                        s.trend = 'stable',
                        s.createdAt = datetime()
                    MERGE (s)-[:BELONGS_TO]->(d)
                    """,
                    skill_id=skill_id,
                    name=name,
                    domain=domain,
                    description=description,
                    keywords=keywords or [],
                )

                # Create parent relationship
                if parent_skill:
                    await session.run(
                        """
                        MATCH (child:Skill {skillId: $child_id})
                        MATCH (parent:Skill {name: $parent_name})
                        MERGE (child)-[:SPECIALIZATION_OF]->(parent)
                        """,
                        child_id=skill_id,
                        parent_name=parent_skill,
                    )

                # Create related skill relationships
                for related in related_skills or []:
                    await session.run(
                        """
                        MATCH (s1:Skill {skillId: $skill_id})
                        MERGE (s2:Skill {name: $related_name})
                        MERGE (s1)-[:RELATED_TO]->(s2)
                        """,
                        skill_id=skill_id,
                        related_name=related,
                    )

        self._skills[skill_id] = skill
        logger.info(f"Added skill: {name} in domain {domain}")
        return skill

    async def assess_skill(
        self,
        professional_id: str,
        skill_name: str,
        level: SkillLevel,
        years_experience: float = 0,
        projects: list[str] | None = None,
        certifications: list[str] | None = None,
    ) -> SkillAssessment:
        """
        Record a skill assessment for a professional.

        Args:
            professional_id: Professional's ID
            skill_name: Skill being assessed
            level: Proficiency level
            years_experience: Years using this skill
            projects: Projects demonstrating skill
            certifications: Relevant certifications

        Returns:
            Created SkillAssessment
        """
        skill_id = skill_name.lower().replace(" ", "_")

        assessment = SkillAssessment(
            professional_id=professional_id,
            skill_id=skill_id,
            level=level,
            years_experience=years_experience,
            last_used=datetime.now(UTC),
            projects=projects or [],
            certifications=certifications or [],
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (p:Professional {professionalId: $professional_id})
                    MERGE (s:Skill {name: $skill_name})
                    MERGE (p)-[r:HAS_SKILL]->(s)
                    SET r.level = $level,
                        r.yearsExperience = $years_experience,
                        r.projects = $projects,
                        r.certifications = $certifications,
                        r.lastUsed = datetime(),
                        r.assessedAt = datetime()
                    """,
                    professional_id=professional_id,
                    skill_name=skill_name,
                    level=level.value,
                    years_experience=years_experience,
                    projects=projects or [],
                    certifications=certifications or [],
                )

        # In-memory storage
        if professional_id not in self._assessments:
            self._assessments[professional_id] = []

        # Update or add assessment
        existing = next(
            (a for a in self._assessments[professional_id] if a.skill_id == skill_id),
            None,
        )
        if existing:
            existing.level = level
            existing.years_experience = years_experience
            existing.projects = projects or []
            existing.certifications = certifications or []
        else:
            self._assessments[professional_id].append(assessment)

        logger.info(f"Assessed {professional_id} at {level.name} for {skill_name}")
        return assessment

    async def endorse_skill(
        self,
        endorser_id: str,
        endorsed_id: str,
        skill_name: str,
        endorsement_type: EndorsementType,
        note: str = "",
    ) -> dict:
        """
        Record a skill endorsement.

        Args:
            endorser_id: Person giving endorsement
            endorsed_id: Person being endorsed
            skill_name: Skill being endorsed
            endorsement_type: Type of endorsement
            note: Optional endorsement note

        Returns:
            Endorsement record
        """
        endorsement = {
            "endorser_id": endorser_id,
            "endorsed_id": endorsed_id,
            "skill_name": skill_name,
            "type": endorsement_type.value,
            "note": note,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (endorser:Professional {professionalId: $endorser_id})
                    MATCH (endorsed:Professional {professionalId: $endorsed_id})
                    MATCH (skill:Skill {name: $skill_name})
                    
                    MERGE (endorser)-[e:ENDORSES {skill: $skill_name}]->(endorsed)
                    SET e.type = $endorsement_type,
                        e.note = $note,
                        e.timestamp = datetime()
                    
                    // Update endorsement count on skill relationship
                    WITH endorsed, skill
                    MATCH (endorsed)-[r:HAS_SKILL]->(skill)
                    SET r.endorsementCount = coalesce(r.endorsementCount, 0) + 1
                    """,
                    endorser_id=endorser_id,
                    endorsed_id=endorsed_id,
                    skill_name=skill_name,
                    endorsement_type=endorsement_type.value,
                    note=note,
                )

        # Update in-memory
        skill_id = skill_name.lower().replace(" ", "_")
        if endorsed_id in self._assessments:
            for assessment in self._assessments[endorsed_id]:
                if assessment.skill_id == skill_id:
                    assessment.endorsements.append(endorsement)
                    break

        logger.info(f"{endorser_id} endorsed {endorsed_id} for {skill_name}")
        return endorsement

    async def analyze_skill_gaps(
        self,
        professional_id: str | None = None,
        team_id: str | None = None,
        target_role: str | None = None,
        target_skills: list[tuple[str, SkillLevel]] | None = None,
    ) -> list[SkillGap]:
        """
        Analyze skill gaps for individual or team.

        Args:
            professional_id: Individual to analyze
            team_id: Team to analyze
            target_role: Role to compare against
            target_skills: Explicit skill requirements

        Returns:
            List of identified SkillGaps
        """
        gaps = []

        if target_skills is None:
            target_skills = []

        if professional_id:
            # Individual gap analysis
            current_skills = {
                a.skill_id: a.level for a in self._assessments.get(professional_id, [])
            }

            for skill_name, required_level in target_skills:
                skill_id = skill_name.lower().replace(" ", "_")
                current_level = current_skills.get(skill_id)

                if current_level is None:
                    # Skill not possessed
                    gap_severity = 1.0
                    actions = [
                        f"Begin learning {skill_name} fundamentals",
                        "Find a mentor with this skill",
                        "Take introductory course",
                    ]
                    time_estimate = (
                        f"{required_level.value * 3}-{required_level.value * 6} months"
                    )
                elif current_level.value < required_level.value:
                    # Skill below required level
                    level_diff = required_level.value - current_level.value
                    gap_severity = level_diff / 5.0
                    actions = [
                        f"Advance {skill_name} from {current_level.name} to {required_level.name}",
                        "Work on stretch projects",
                        "Get certified",
                    ]
                    time_estimate = f"{level_diff * 2}-{level_diff * 4} months"
                else:
                    continue  # No gap

                gaps.append(
                    SkillGap(
                        skill_name=skill_name,
                        required_level=required_level,
                        current_level=current_level,
                        gap_severity=gap_severity,
                        recommended_actions=actions,
                        estimated_time_to_close=time_estimate,
                    )
                )

        elif team_id:
            # Team gap analysis
            team_members = self._teams.get(team_id, [])

            for skill_name, required_level in target_skills:
                skill_id = skill_name.lower().replace(" ", "_")

                team_levels = []
                for member_id in team_members:
                    for assessment in self._assessments.get(member_id, []):
                        if assessment.skill_id == skill_id:
                            team_levels.append(assessment.level.value)
                            break

                coverage = len(team_levels) / len(team_members) if team_members else 0
                avg_level = sum(team_levels) / len(team_levels) if team_levels else 0

                if coverage < 0.3 or avg_level < required_level.value:
                    gap_severity = 1 - (coverage * (avg_level / 5))
                    actions = [
                        f"Hire for {skill_name} expertise",
                        f"Upskill {int((1 - coverage) * len(team_members))} team members",
                        "Bring in external consultants",
                    ]

                    gaps.append(
                        SkillGap(
                            skill_name=skill_name,
                            required_level=required_level,
                            current_level=(
                                SkillLevel(int(avg_level)) if avg_level >= 1 else None
                            ),
                            gap_severity=gap_severity,
                            recommended_actions=actions,
                            estimated_time_to_close="3-6 months for team",
                        )
                    )

        # Sort by severity
        gaps.sort(key=lambda g: g.gap_severity, reverse=True)
        return gaps

    async def get_team_capabilities(
        self,
        team_id: str,
    ) -> list[TeamCapability]:
        """
        Get aggregated skill capabilities for a team.

        Args:
            team_id: Team to analyze

        Returns:
            List of TeamCapability objects
        """
        team_members = self._teams.get(team_id, [])
        if not team_members:
            return []

        # Aggregate skills across team
        skill_data: dict[str, list[int]] = defaultdict(list)

        for member_id in team_members:
            for assessment in self._assessments.get(member_id, []):
                skill_name = self._skills.get(
                    assessment.skill_id,
                    SkillNode(
                        skill_id=assessment.skill_id,
                        name=assessment.skill_id.replace("_", " ").title(),
                        domain="Unknown",
                    ),
                ).name
                skill_data[skill_name].append(assessment.level.value)

        capabilities = []
        for skill_name, levels in skill_data.items():
            practitioners = len(levels)
            avg_level = sum(levels) / practitioners
            highest = max(levels)
            coverage = practitioners / len(team_members)

            # Depth score: weighted average favoring higher levels
            depth = sum(l * l for l in levels) / (5 * 5 * len(team_members))

            capabilities.append(
                TeamCapability(
                    skill_name=skill_name,
                    team_size=len(team_members),
                    practitioners=practitioners,
                    average_level=avg_level,
                    highest_level=SkillLevel(highest),
                    coverage=coverage,
                    depth_score=depth,
                )
            )

        # Sort by depth score
        capabilities.sort(key=lambda c: c.depth_score, reverse=True)
        return capabilities

    async def find_skill_experts(
        self,
        skill_name: str,
        min_level: SkillLevel = SkillLevel.ADVANCED,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find experts for a specific skill.

        Args:
            skill_name: Skill to find experts for
            min_level: Minimum proficiency level
            limit: Maximum results

        Returns:
            List of expert profiles
        """
        experts = []
        skill_id = skill_name.lower().replace(" ", "_")

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (p:Professional)-[r:HAS_SKILL]->(s:Skill {name: $skill_name})
                    WHERE r.level >= $min_level
                    
                    OPTIONAL MATCH (endorser)-[e:ENDORSES {skill: $skill_name}]->(p)
                    
                    WITH p, r, count(endorser) as endorsements
                    ORDER BY r.level DESC, endorsements DESC
                    LIMIT $limit
                    
                    RETURN p.professionalId as id,
                           p.name as name,
                           r.level as level,
                           r.yearsExperience as years,
                           endorsements
                    """,
                    skill_name=skill_name,
                    min_level=min_level.value,
                    limit=limit,
                )

                async for record in result:
                    experts.append(
                        {
                            "professional_id": record["id"],
                            "name": record["name"],
                            "level": SkillLevel(record["level"]).name,
                            "years_experience": record["years"],
                            "endorsements": record["endorsements"],
                        }
                    )
        else:
            # In-memory fallback
            for prof_id, assessments in self._assessments.items():
                for assessment in assessments:
                    if (
                        assessment.skill_id == skill_id
                        and assessment.level.value >= min_level.value
                    ):
                        experts.append(
                            {
                                "professional_id": prof_id,
                                "level": assessment.level.name,
                                "years_experience": assessment.years_experience,
                                "endorsements": assessment.endorsement_count,
                            }
                        )

            experts.sort(
                key=lambda x: (SkillLevel[x["level"]].value, x["endorsements"]),
                reverse=True,
            )
            experts = experts[:limit]

        return experts

    async def get_skill_hierarchy(
        self,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """
        Get skill hierarchy tree.

        Args:
            domain: Filter to specific domain

        Returns:
            Hierarchical skill tree
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                query = """
                    MATCH (d:Domain)
                    WHERE $domain IS NULL OR d.name = $domain
                    OPTIONAL MATCH (s:Skill)-[:BELONGS_TO]->(d)
                    OPTIONAL MATCH (s)-[:SPECIALIZATION_OF]->(parent:Skill)
                    
                    WITH d, collect({
                        skill: s.name,
                        parent: parent.name,
                        demand: s.demandScore,
                        trend: s.trend
                    }) as skills
                    
                    RETURN d.name as domain, skills
                """

                result = await session.run(query, domain=domain)

                hierarchy = {}
                async for record in result:
                    domain_name = record["domain"]
                    skills = record["skills"]

                    # Build tree structure
                    tree = {"name": domain_name, "children": []}
                    skill_nodes = {}

                    for skill_data in skills:
                        if skill_data["skill"]:
                            node = {
                                "name": skill_data["skill"],
                                "demand": skill_data["demand"],
                                "trend": skill_data["trend"],
                                "children": [],
                            }
                            skill_nodes[skill_data["skill"]] = node

                    # Link children to parents
                    for skill_data in skills:
                        if skill_data["skill"] and skill_data["parent"]:
                            parent_node = skill_nodes.get(skill_data["parent"])
                            child_node = skill_nodes.get(skill_data["skill"])
                            if parent_node and child_node:
                                parent_node["children"].append(child_node)

                    # Root level skills (no parent)
                    for skill_data in skills:
                        if skill_data["skill"] and not skill_data["parent"]:
                            tree["children"].append(skill_nodes[skill_data["skill"]])

                    hierarchy[domain_name] = tree

                return hierarchy

        # In-memory fallback
        hierarchy = {}
        for skill in self._skills.values():
            if domain and skill.domain != domain:
                continue

            if skill.domain not in hierarchy:
                hierarchy[skill.domain] = {"name": skill.domain, "children": []}

            if not skill.parent_skill:
                hierarchy[skill.domain]["children"].append(
                    {
                        "name": skill.name,
                        "demand": skill.demand_score,
                        "trend": skill.trend.value,
                        "children": [],
                    }
                )

        return hierarchy

    async def get_trending_skills(
        self,
        domain: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get skills with rising demand.

        Args:
            domain: Filter to domain
            limit: Maximum results

        Returns:
            List of trending skills
        """
        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                result = await session.run(
                    """
                    MATCH (s:Skill)-[:BELONGS_TO]->(d:Domain)
                    WHERE ($domain IS NULL OR d.name = $domain)
                    AND s.trend IN ['rising', 'emerging']
                    
                    // Count professionals with this skill
                    OPTIONAL MATCH (p:Professional)-[r:HAS_SKILL]->(s)
                    
                    WITH s, d, count(p) as practitioners, avg(r.level) as avgLevel
                    ORDER BY s.demandScore DESC
                    LIMIT $limit
                    
                    RETURN s.name as skill,
                           d.name as domain,
                           s.trend as trend,
                           s.demandScore as demand,
                           practitioners,
                           avgLevel
                    """,
                    domain=domain,
                    limit=limit,
                )

                trending = []
                async for record in result:
                    trending.append(
                        {
                            "skill": record["skill"],
                            "domain": record["domain"],
                            "trend": record["trend"],
                            "demand_score": record["demand"],
                            "practitioners": record["practitioners"],
                            "avg_level": record["avgLevel"],
                        }
                    )

                return trending

        # In-memory fallback
        trending = [
            s
            for s in self._skills.values()
            if s.trend in [TrendDirection.RISING, TrendDirection.EMERGING]
            and (domain is None or s.domain == domain)
        ]
        trending.sort(key=lambda s: s.demand_score, reverse=True)

        return [
            {
                "skill": s.name,
                "domain": s.domain,
                "trend": s.trend.value,
                "demand_score": s.demand_score,
            }
            for s in trending[:limit]
        ]

    async def suggest_learning_path(
        self,
        professional_id: str,
        target_skill: str,
        target_level: SkillLevel = SkillLevel.ADVANCED,
    ) -> dict[str, Any]:
        """
        Suggest a learning path to reach target skill level.

        Args:
            professional_id: Professional seeking development
            target_skill: Skill to develop
            target_level: Target proficiency

        Returns:
            Learning path recommendation
        """
        current_assessments = {
            a.skill_id: a.level for a in self._assessments.get(professional_id, [])
        }

        target_skill_id = target_skill.lower().replace(" ", "_")
        current_level = current_assessments.get(target_skill_id)

        # Get skill node for related skills
        skill_node = self._skills.get(target_skill_id)

        path = {
            "target_skill": target_skill,
            "current_level": current_level.name if current_level else "NONE",
            "target_level": target_level.name,
            "steps": [],
            "estimated_duration": "",
            "prerequisites": [],
            "mentors_available": [],
        }

        # Identify prerequisite skills
        if skill_node and skill_node.parent_skill:
            parent_id = skill_node.parent_skill.lower().replace(" ", "_")
            parent_level = current_assessments.get(parent_id)

            if not parent_level or parent_level.value < SkillLevel.INTERMEDIATE.value:
                path["prerequisites"].append(
                    {
                        "skill": skill_node.parent_skill,
                        "reason": "Foundation skill for learning path",
                        "current_level": parent_level.name if parent_level else "NONE",
                        "recommended_level": "INTERMEDIATE",
                    }
                )

        # Build learning steps
        start_level = current_level.value if current_level else 0

        for level in range(start_level + 1, target_level.value + 1):
            level_enum = SkillLevel(level)

            if level <= 2:
                activities = [
                    "Complete introductory course",
                    "Shadow experienced practitioners",
                    "Practice with guided exercises",
                ]
                duration = "1-2 months"
            elif level == 3:
                activities = [
                    "Work on independent projects",
                    "Contribute to team initiatives",
                    "Study advanced concepts",
                ]
                duration = "2-4 months"
            elif level == 4:
                activities = [
                    "Lead complex projects",
                    "Mentor junior team members",
                    "Obtain professional certification",
                ]
                duration = "4-6 months"
            else:
                activities = [
                    "Publish thought leadership content",
                    "Contribute to industry standards",
                    "Present at conferences",
                ]
                duration = "6-12 months"

            path["steps"].append(
                {
                    "level": level_enum.name,
                    "activities": activities,
                    "estimated_duration": duration,
                }
            )

        # Total duration estimate
        total_steps = target_level.value - start_level
        if total_steps <= 1:
            path["estimated_duration"] = "1-2 months"
        elif total_steps <= 2:
            path["estimated_duration"] = "3-6 months"
        elif total_steps <= 3:
            path["estimated_duration"] = "6-12 months"
        else:
            path["estimated_duration"] = "12-18 months"

        # Find potential mentors
        mentors = await self.find_skill_experts(
            target_skill,
            min_level=SkillLevel.ADVANCED,
            limit=3,
        )
        path["mentors_available"] = mentors

        return path

    async def register_team(
        self,
        team_id: str,
        member_ids: list[str],
    ) -> None:
        """Register a team for capability analysis."""
        self._teams[team_id] = member_ids

    async def close(self):
        """Clean up resources."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()


# Example usage
async def main():
    """Demonstrate skills graph capabilities."""
    agent = SkillsGraphAgent()

    # Build skill taxonomy
    await agent.add_skill(
        name="Programming",
        domain="Engineering",
        description="Core programming fundamentals",
    )

    await agent.add_skill(
        name="Python",
        domain="Engineering",
        parent_skill="Programming",
        related_skills=["Data Analysis", "Machine Learning"],
        keywords=["python", "scripting", "automation"],
    )

    await agent.add_skill(
        name="Machine Learning",
        domain="AI/ML",
        related_skills=["Python", "Statistics"],
        keywords=["ml", "ai", "neural networks"],
    )

    await agent.add_skill(
        name="Deep Learning",
        domain="AI/ML",
        parent_skill="Machine Learning",
        keywords=["tensorflow", "pytorch", "neural networks"],
    )

    # Assess skills for professionals
    await agent.assess_skill(
        professional_id="alice_001",
        skill_name="Python",
        level=SkillLevel.ADVANCED,
        years_experience=5,
        certifications=["Python Professional Certificate"],
    )

    await agent.assess_skill(
        professional_id="alice_001",
        skill_name="Machine Learning",
        level=SkillLevel.INTERMEDIATE,
        years_experience=2,
    )

    await agent.assess_skill(
        professional_id="bob_002",
        skill_name="Python",
        level=SkillLevel.EXPERT,
        years_experience=8,
    )

    await agent.assess_skill(
        professional_id="bob_002",
        skill_name="Machine Learning",
        level=SkillLevel.ADVANCED,
        years_experience=4,
    )

    # Endorsements
    await agent.endorse_skill(
        endorser_id="bob_002",
        endorsed_id="alice_001",
        skill_name="Python",
        endorsement_type=EndorsementType.PEER,
        note="Great Python skills!",
    )

    # Register team
    await agent.register_team(
        team_id="data_team",
        member_ids=["alice_001", "bob_002"],
    )

    # Team capabilities
    print("\n=== Team Capabilities ===")
    capabilities = await agent.get_team_capabilities("data_team")
    for cap in capabilities:
        print(
            f"  {cap.skill_name}: {cap.coverage:.0%} coverage, avg level {cap.average_level:.1f}"
        )

    # Gap analysis
    print("\n=== Skill Gap Analysis for Alice ===")
    gaps = await agent.analyze_skill_gaps(
        professional_id="alice_001",
        target_skills=[
            ("Deep Learning", SkillLevel.ADVANCED),
            ("Python", SkillLevel.EXPERT),
        ],
    )
    for gap in gaps:
        print(f"  {gap.skill_name}: severity {gap.gap_severity:.2f}")
        print(f"    Current: {gap.current_level.name if gap.current_level else 'None'}")
        print(f"    Required: {gap.required_level.name}")
        print(f"    Actions: {gap.recommended_actions[0]}")

    # Find experts
    print("\n=== Python Experts ===")
    experts = await agent.find_skill_experts("Python")
    for expert in experts:
        print(
            f"  {expert['professional_id']}: {expert['level']}, {expert['endorsements']} endorsements"
        )

    # Learning path
    print("\n=== Learning Path: Alice -> Deep Learning Advanced ===")
    path = await agent.suggest_learning_path(
        professional_id="alice_001",
        target_skill="Deep Learning",
        target_level=SkillLevel.ADVANCED,
    )
    print(f"  Estimated duration: {path['estimated_duration']}")
    for step in path["steps"]:
        print(f"  Level {step['level']}: {step['activities'][0]}")

    # Hierarchy
    print("\n=== Skill Hierarchy ===")
    hierarchy = await agent.get_skill_hierarchy()
    for domain, tree in hierarchy.items():
        print(f"  {domain}:")
        for child in tree.get("children", []):
            print(f"    - {child['name']}")

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
