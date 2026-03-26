#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Career Opportunity Matcher - Internal Mobility Platform
========================================================

Connects talent with opportunities within the organisation:
- Skills-based opportunity matching
- Candidate recommendation for hiring managers
- Application tracking and status
- Career path suggestions

This enables internal talent mobility and reduces external hiring costs.

Usage:
    python examples/enterprise/career_opportunity_matcher.py

Requirements:
    - pip install agentic-brain

Example:
    >>> from examples.enterprise.career_opportunity_matcher import OpportunityMatcherAgent
    >>> agent = OpportunityMatcherAgent()
    >>> matches = await agent.find_opportunities_for_candidate("emp_001")
    >>> candidates = await agent.find_candidates_for_role(role_id="sr_eng_001")

Key Patterns:
    - Skills-based matching algorithms
    - Application pipeline management
    - Career trajectory analysis
    - Internal mobility analytics
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class OpportunityType(Enum):
    """Types of career opportunities."""

    FULL_TIME = "full_time"
    PROJECT = "project"
    ROTATION = "rotation"
    MENTORSHIP = "mentorship"
    SECONDMENT = "secondment"
    STRETCH = "stretch_assignment"


class ApplicationStatus(Enum):
    """Application pipeline stages."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    SCREENING = "screening"
    INTERVIEW = "interview"
    FINAL = "final_review"
    OFFER = "offer"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"


class MatchStrength(Enum):
    """How well a candidate matches an opportunity."""

    EXCELLENT = "excellent"  # 90%+ match
    STRONG = "strong"  # 75-89% match
    MODERATE = "moderate"  # 60-74% match
    PARTIAL = "partial"  # 40-59% match
    DEVELOPING = "developing"  # <40% match but has growth potential


@dataclass
class Skill:
    """A skill with proficiency level."""

    name: str
    level: int  # 1-5
    years: float = 0
    verified: bool = False
    last_used: datetime | None = None


@dataclass
class CandidateProfile:
    """A candidate's profile for opportunity matching."""

    candidate_id: str
    name: str
    current_title: str
    current_department: str
    skills: list[Skill] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    career_interests: list[str] = field(default_factory=list)
    mobility_preference: str = "local"  # local, regional, global
    availability: str = "active"  # active, passive, unavailable
    years_experience: int = 0
    education: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)

    def skill_level(self, skill_name: str) -> int:
        """Get proficiency level for a skill (0 if not possessed)."""
        for skill in self.skills:
            if skill.name.lower() == skill_name.lower():
                return skill.level
        return 0


@dataclass
class Opportunity:
    """A career opportunity (role, project, etc.)."""

    opportunity_id: str
    title: str
    department: str
    location: str
    opportunity_type: OpportunityType
    description: str
    required_skills: list[tuple[str, int]] = field(
        default_factory=list
    )  # (skill, min_level)
    preferred_skills: list[str] = field(default_factory=list)
    required_experience_years: int = 0
    team_size: int = 0
    hiring_manager_id: str = ""
    posted_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deadline: datetime | None = None
    is_active: bool = True
    applications_count: int = 0

    @property
    def required_skill_names(self) -> set[str]:
        return {skill for skill, _ in self.required_skills}


@dataclass
class MatchResult:
    """Result of matching a candidate to an opportunity."""

    candidate_id: str
    opportunity_id: str
    overall_score: float
    skill_match_score: float
    experience_score: float
    preference_score: float
    match_strength: MatchStrength
    matched_skills: list[str]
    missing_skills: list[str]
    exceeded_skills: list[str]
    recommendation: str

    @classmethod
    def from_scores(
        cls,
        candidate_id: str,
        opportunity_id: str,
        skill_score: float,
        exp_score: float,
        pref_score: float,
        matched: list[str],
        missing: list[str],
        exceeded: list[str],
    ) -> MatchResult:
        """Create match result from individual scores."""
        overall = skill_score * 0.5 + exp_score * 0.3 + pref_score * 0.2

        if overall >= 0.9:
            strength = MatchStrength.EXCELLENT
            rec = "Highly recommended - exceeds requirements"
        elif overall >= 0.75:
            strength = MatchStrength.STRONG
            rec = "Strong match - meets most requirements"
        elif overall >= 0.6:
            strength = MatchStrength.MODERATE
            rec = "Good potential - some skill development needed"
        elif overall >= 0.4:
            strength = MatchStrength.PARTIAL
            rec = "Partial match - consider for stretch assignment"
        else:
            strength = MatchStrength.DEVELOPING
            rec = "Development opportunity - significant upskilling required"

        return cls(
            candidate_id=candidate_id,
            opportunity_id=opportunity_id,
            overall_score=overall,
            skill_match_score=skill_score,
            experience_score=exp_score,
            preference_score=pref_score,
            match_strength=strength,
            matched_skills=matched,
            missing_skills=missing,
            exceeded_skills=exceeded,
            recommendation=rec,
        )


@dataclass
class Application:
    """An application to an opportunity."""

    application_id: str
    candidate_id: str
    opportunity_id: str
    status: ApplicationStatus
    match_result: MatchResult | None = None
    cover_note: str = ""
    submitted_at: datetime | None = None
    status_history: list[tuple[ApplicationStatus, datetime]] = field(
        default_factory=list
    )
    notes: list[dict] = field(default_factory=list)

    def advance_status(self, new_status: ApplicationStatus, note: str = ""):
        """Move application to next status."""
        self.status_history.append((self.status, datetime.now(timezone.utc)))
        self.status = new_status
        if note:
            self.notes.append(
                {
                    "status": new_status.value,
                    "note": note,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )


class OpportunityMatcherAgent:
    """
    Agent for matching candidates to internal opportunities.

    Uses skills-based matching with configurable weights
    to recommend candidates for roles and opportunities for candidates.
    """

    def __init__(
        self,
        neo4j_uri: str | None = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        skill_weight: float = 0.5,
        experience_weight: float = 0.3,
        preference_weight: float = 0.2,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password

        # Matching weights
        self.skill_weight = skill_weight
        self.experience_weight = experience_weight
        self.preference_weight = preference_weight

        # In-memory stores
        self._candidates: dict[str, CandidateProfile] = {}
        self._opportunities: dict[str, Opportunity] = {}
        self._applications: dict[str, Application] = {}

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

    async def register_candidate(
        self,
        candidate_id: str,
        name: str,
        current_title: str,
        current_department: str,
        skills: list[dict] | None = None,
        certifications: list[str] | None = None,
        career_interests: list[str] | None = None,
        years_experience: int = 0,
    ) -> CandidateProfile:
        """
        Register a candidate in the talent pool.

        Args:
            candidate_id: Unique identifier
            name: Candidate name
            current_title: Current job title
            current_department: Current department
            skills: List of skill dicts with name, level, years
            certifications: Professional certifications
            career_interests: Areas of career interest
            years_experience: Total years of experience

        Returns:
            Created CandidateProfile
        """
        skill_objects = [
            Skill(
                name=s["name"],
                level=s.get("level", 3),
                years=s.get("years", 1),
                verified=s.get("verified", False),
            )
            for s in (skills or [])
        ]

        profile = CandidateProfile(
            candidate_id=candidate_id,
            name=name,
            current_title=current_title,
            current_department=current_department,
            skills=skill_objects,
            certifications=certifications or [],
            career_interests=career_interests or [],
            years_experience=years_experience,
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MERGE (c:Candidate {candidateId: $candidate_id})
                    SET c.name = $name,
                        c.currentTitle = $current_title,
                        c.currentDepartment = $current_department,
                        c.certifications = $certifications,
                        c.careerInterests = $career_interests,
                        c.yearsExperience = $years_experience,
                        c.updatedAt = datetime()
                    """,
                    candidate_id=candidate_id,
                    name=name,
                    current_title=current_title,
                    current_department=current_department,
                    certifications=certifications or [],
                    career_interests=career_interests or [],
                    years_experience=years_experience,
                )

                # Create skill relationships
                for skill in skill_objects:
                    await session.run(
                        """
                        MERGE (s:Skill {name: $skill_name})
                        WITH s
                        MATCH (c:Candidate {candidateId: $candidate_id})
                        MERGE (c)-[r:HAS_SKILL]->(s)
                        SET r.level = $level,
                            r.years = $years,
                            r.verified = $verified
                        """,
                        candidate_id=candidate_id,
                        skill_name=skill.name,
                        level=skill.level,
                        years=skill.years,
                        verified=skill.verified,
                    )

        self._candidates[candidate_id] = profile
        logger.info(f"Registered candidate: {name}")
        return profile

    async def create_opportunity(
        self,
        title: str,
        department: str,
        location: str,
        opportunity_type: OpportunityType,
        description: str,
        required_skills: list[tuple[str, int]] | None = None,
        preferred_skills: list[str] | None = None,
        required_experience_years: int = 0,
        hiring_manager_id: str = "",
        deadline: datetime | None = None,
    ) -> Opportunity:
        """
        Create a new career opportunity.

        Args:
            title: Opportunity title
            department: Target department
            location: Location
            opportunity_type: Type of opportunity
            description: Full description
            required_skills: List of (skill_name, min_level) tuples
            preferred_skills: Nice-to-have skills
            required_experience_years: Minimum experience
            hiring_manager_id: Hiring manager's ID
            deadline: Application deadline

        Returns:
            Created Opportunity
        """
        opportunity_id = str(uuid4())[:8]

        opportunity = Opportunity(
            opportunity_id=opportunity_id,
            title=title,
            department=department,
            location=location,
            opportunity_type=opportunity_type,
            description=description,
            required_skills=required_skills or [],
            preferred_skills=preferred_skills or [],
            required_experience_years=required_experience_years,
            hiring_manager_id=hiring_manager_id,
            deadline=deadline,
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    CREATE (o:Opportunity {
                        opportunityId: $opportunity_id,
                        title: $title,
                        department: $department,
                        location: $location,
                        opportunityType: $opportunity_type,
                        description: $description,
                        preferredSkills: $preferred_skills,
                        requiredExperienceYears: $required_experience_years,
                        hiringManagerId: $hiring_manager_id,
                        postedDate: datetime(),
                        isActive: true
                    })
                    """,
                    opportunity_id=opportunity_id,
                    title=title,
                    department=department,
                    location=location,
                    opportunity_type=opportunity_type.value,
                    description=description,
                    preferred_skills=preferred_skills or [],
                    required_experience_years=required_experience_years,
                    hiring_manager_id=hiring_manager_id,
                )

                # Create skill requirement relationships
                for skill_name, min_level in required_skills or []:
                    await session.run(
                        """
                        MERGE (s:Skill {name: $skill_name})
                        WITH s
                        MATCH (o:Opportunity {opportunityId: $opportunity_id})
                        CREATE (o)-[r:REQUIRES_SKILL {minLevel: $min_level}]->(s)
                        """,
                        opportunity_id=opportunity_id,
                        skill_name=skill_name,
                        min_level=min_level,
                    )

        self._opportunities[opportunity_id] = opportunity
        logger.info(f"Created opportunity: {title}")
        return opportunity

    async def find_opportunities_for_candidate(
        self,
        candidate_id: str,
        limit: int = 10,
        min_match_score: float = 0.4,
    ) -> list[MatchResult]:
        """
        Find matching opportunities for a candidate.

        Uses skills-based matching to rank opportunities
        by fit with the candidate's profile.

        Args:
            candidate_id: Candidate to match
            limit: Maximum results
            min_match_score: Minimum score threshold

        Returns:
            List of MatchResults sorted by score
        """
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            logger.warning(f"Candidate {candidate_id} not found")
            return []

        matches = []

        for opp_id, opportunity in self._opportunities.items():
            if not opportunity.is_active:
                continue

            match_result = self._calculate_match(candidate, opportunity)

            if match_result.overall_score >= min_match_score:
                matches.append(match_result)

        matches.sort(key=lambda m: m.overall_score, reverse=True)
        return matches[:limit]

    async def find_candidates_for_role(
        self,
        opportunity_id: str,
        limit: int = 20,
        min_match_score: float = 0.4,
        include_passive: bool = True,
    ) -> list[MatchResult]:
        """
        Find matching candidates for an opportunity.

        Enables hiring managers to discover internal talent
        that matches their requirements.

        Args:
            opportunity_id: Opportunity to match against
            limit: Maximum results
            min_match_score: Minimum score threshold
            include_passive: Include passive candidates

        Returns:
            List of MatchResults sorted by score
        """
        opportunity = self._opportunities.get(opportunity_id)
        if not opportunity:
            logger.warning(f"Opportunity {opportunity_id} not found")
            return []

        matches = []

        for cand_id, candidate in self._candidates.items():
            if not include_passive and candidate.availability == "passive":
                continue
            if candidate.availability == "unavailable":
                continue

            match_result = self._calculate_match(candidate, opportunity)

            if match_result.overall_score >= min_match_score:
                matches.append(match_result)

        matches.sort(key=lambda m: m.overall_score, reverse=True)
        return matches[:limit]

    def _calculate_match(
        self,
        candidate: CandidateProfile,
        opportunity: Opportunity,
    ) -> MatchResult:
        """Calculate match score between candidate and opportunity."""
        # Skill matching
        matched_skills = []
        missing_skills = []
        exceeded_skills = []
        skill_scores = []

        for skill_name, min_level in opportunity.required_skills:
            candidate_level = candidate.skill_level(skill_name)

            if candidate_level >= min_level:
                matched_skills.append(skill_name)
                if candidate_level > min_level + 1:
                    exceeded_skills.append(skill_name)
                skill_scores.append(min(1.0, candidate_level / min_level))
            else:
                missing_skills.append(skill_name)
                skill_scores.append(candidate_level / min_level if min_level > 0 else 0)

        # Bonus for preferred skills
        for pref_skill in opportunity.preferred_skills:
            if candidate.skill_level(pref_skill) >= 2:
                skill_scores.append(0.5)  # Partial bonus

        skill_score = sum(skill_scores) / len(skill_scores) if skill_scores else 0.5

        # Experience matching
        if opportunity.required_experience_years == 0:
            exp_score = 1.0
        elif candidate.years_experience >= opportunity.required_experience_years:
            exp_score = 1.0
        else:
            exp_score = (
                candidate.years_experience / opportunity.required_experience_years
            )

        # Preference matching (career interests)
        interest_overlap = len(
            set(candidate.career_interests)
            & {opportunity.department, opportunity.opportunity_type.value}
        )
        pref_score = min(1.0, interest_overlap * 0.5 + 0.5)  # Base 0.5, +0.5 per match

        return MatchResult.from_scores(
            candidate_id=candidate.candidate_id,
            opportunity_id=opportunity.opportunity_id,
            skill_score=skill_score,
            exp_score=exp_score,
            pref_score=pref_score,
            matched=matched_skills,
            missing=missing_skills,
            exceeded=exceeded_skills,
        )

    async def apply(
        self,
        candidate_id: str,
        opportunity_id: str,
        cover_note: str = "",
    ) -> Application:
        """
        Submit an application to an opportunity.

        Args:
            candidate_id: Applying candidate
            opportunity_id: Target opportunity
            cover_note: Optional cover message

        Returns:
            Created Application
        """
        application_id = str(uuid4())[:12]

        # Get match result for the application
        candidate = self._candidates.get(candidate_id)
        opportunity = self._opportunities.get(opportunity_id)

        match_result = None
        if candidate and opportunity:
            match_result = self._calculate_match(candidate, opportunity)

        application = Application(
            application_id=application_id,
            candidate_id=candidate_id,
            opportunity_id=opportunity_id,
            status=ApplicationStatus.SUBMITTED,
            match_result=match_result,
            cover_note=cover_note,
            submitted_at=datetime.now(timezone.utc),
        )

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (c:Candidate {candidateId: $candidate_id})
                    MATCH (o:Opportunity {opportunityId: $opportunity_id})
                    CREATE (a:Application {
                        applicationId: $application_id,
                        status: $status,
                        coverNote: $cover_note,
                        matchScore: $match_score,
                        submittedAt: datetime()
                    })
                    CREATE (c)-[:APPLIED]->(a)
                    CREATE (a)-[:FOR_OPPORTUNITY]->(o)
                    
                    WITH o
                    SET o.applicationsCount = coalesce(o.applicationsCount, 0) + 1
                    """,
                    candidate_id=candidate_id,
                    opportunity_id=opportunity_id,
                    application_id=application_id,
                    status=ApplicationStatus.SUBMITTED.value,
                    cover_note=cover_note,
                    match_score=match_result.overall_score if match_result else 0,
                )

        # Update in-memory
        self._applications[application_id] = application
        if opportunity:
            opportunity.applications_count += 1

        logger.info(f"Application {application_id} submitted for {opportunity_id}")
        return application

    async def update_application_status(
        self,
        application_id: str,
        new_status: ApplicationStatus,
        note: str = "",
    ) -> Application | None:
        """
        Update an application's status in the pipeline.

        Args:
            application_id: Application to update
            new_status: New status
            note: Status change note

        Returns:
            Updated Application or None
        """
        application = self._applications.get(application_id)
        if not application:
            logger.warning(f"Application {application_id} not found")
            return None

        application.advance_status(new_status, note)

        await self._ensure_neo4j()

        if self._neo4j_driver:
            async with self._neo4j_driver.session() as session:
                await session.run(
                    """
                    MATCH (a:Application {applicationId: $application_id})
                    SET a.status = $status,
                        a.updatedAt = datetime()
                    
                    CREATE (a)-[:STATUS_CHANGE {
                        toStatus: $status,
                        note: $note,
                        timestamp: datetime()
                    }]->(a)
                    """,
                    application_id=application_id,
                    status=new_status.value,
                    note=note,
                )

        logger.info(f"Application {application_id} moved to {new_status.value}")
        return application

    async def get_application_pipeline(
        self,
        opportunity_id: str,
    ) -> dict[str, list[Application]]:
        """
        Get applications grouped by pipeline stage.

        Args:
            opportunity_id: Opportunity to get pipeline for

        Returns:
            Dict of status -> list of applications
        """
        pipeline: dict[str, list[Application]] = {
            status.value: [] for status in ApplicationStatus
        }

        for app in self._applications.values():
            if app.opportunity_id == opportunity_id:
                pipeline[app.status.value].append(app)

        return pipeline

    async def get_candidate_applications(
        self,
        candidate_id: str,
    ) -> list[Application]:
        """
        Get all applications for a candidate.

        Args:
            candidate_id: Candidate ID

        Returns:
            List of applications
        """
        return [
            app
            for app in self._applications.values()
            if app.candidate_id == candidate_id
        ]

    async def suggest_career_paths(
        self,
        candidate_id: str,
        max_steps: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Suggest career progression paths for a candidate.

        Analyzes skill gaps and opportunities to suggest
        realistic career development paths.

        Args:
            candidate_id: Candidate to analyze
            max_steps: Maximum career steps to project

        Returns:
            List of career path suggestions
        """
        candidate = self._candidates.get(candidate_id)
        if not candidate:
            return []

        current_skills = {s.name for s in candidate.skills}
        paths = []

        # Group opportunities by required experience level
        entry_level = []
        mid_level = []
        senior_level = []

        for opp in self._opportunities.values():
            if not opp.is_active:
                continue

            # Categorize by experience requirement
            if opp.required_experience_years <= candidate.years_experience:
                entry_level.append(opp)
            elif opp.required_experience_years <= candidate.years_experience + 3:
                mid_level.append(opp)
            else:
                senior_level.append(opp)

        # Build career paths
        for immediate_opp in entry_level[:3]:
            path = {
                "path_name": f"Path to {immediate_opp.title}",
                "steps": [],
                "total_skill_gap": 0,
            }

            # Step 1: Immediate opportunity
            match = self._calculate_match(candidate, immediate_opp)
            path["steps"].append(
                {
                    "step": 1,
                    "opportunity": immediate_opp.title,
                    "department": immediate_opp.department,
                    "match_score": match.overall_score,
                    "skills_to_develop": match.missing_skills,
                }
            )
            path["total_skill_gap"] += len(match.missing_skills)

            # Step 2: Find progression opportunity
            new_skills = current_skills | set(match.matched_skills)
            for next_opp in mid_level[:2]:
                if next_opp.opportunity_id == immediate_opp.opportunity_id:
                    continue

                next_missing = next_opp.required_skill_names - new_skills
                path["steps"].append(
                    {
                        "step": 2,
                        "opportunity": next_opp.title,
                        "department": next_opp.department,
                        "skills_to_develop": list(next_missing),
                    }
                )
                path["total_skill_gap"] += len(next_missing)
                break

            if len(path["steps"]) >= 1:
                paths.append(path)

        # Sort by total skill gap (easier paths first)
        paths.sort(key=lambda p: p["total_skill_gap"])

        return paths[:5]

    async def get_talent_pool_analytics(self) -> dict[str, Any]:
        """
        Get analytics about the talent pool.

        Returns:
            Analytics dict with pool statistics
        """
        total_candidates = len(self._candidates)
        total_opportunities = len(
            [o for o in self._opportunities.values() if o.is_active]
        )
        total_applications = len(self._applications)

        # Skill distribution
        skill_counts: dict[str, int] = {}
        for candidate in self._candidates.values():
            for skill in candidate.skills:
                skill_counts[skill.name] = skill_counts.get(skill.name, 0) + 1

        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Application funnel
        funnel: dict[str, int] = {status.value: 0 for status in ApplicationStatus}
        for app in self._applications.values():
            funnel[app.status.value] += 1

        # Match quality distribution
        match_quality = {strength.value: 0 for strength in MatchStrength}
        for app in self._applications.values():
            if app.match_result:
                match_quality[app.match_result.match_strength.value] += 1

        return {
            "talent_pool_size": total_candidates,
            "active_opportunities": total_opportunities,
            "total_applications": total_applications,
            "top_skills": top_skills,
            "application_funnel": funnel,
            "match_quality_distribution": match_quality,
        }

    async def close(self):
        """Clean up resources."""
        if self._neo4j_driver:
            await self._neo4j_driver.close()


# Example usage
async def main():
    """Demonstrate opportunity matching features."""
    agent = OpportunityMatcherAgent()

    # Register candidates
    await agent.register_candidate(
        candidate_id="alice_001",
        name="Alice Chen",
        current_title="Data Analyst",
        current_department="Analytics",
        skills=[
            {"name": "Python", "level": 4, "years": 5},
            {"name": "SQL", "level": 5, "years": 6},
            {"name": "Machine Learning", "level": 3, "years": 2},
            {"name": "Data Visualization", "level": 4, "years": 4},
        ],
        career_interests=["Data Science", "Leadership"],
        years_experience=6,
    )

    await agent.register_candidate(
        candidate_id="bob_002",
        name="Bob Martinez",
        current_title="Junior Developer",
        current_department="Engineering",
        skills=[
            {"name": "Python", "level": 3, "years": 2},
            {"name": "JavaScript", "level": 4, "years": 3},
            {"name": "React", "level": 3, "years": 2},
        ],
        career_interests=["Backend Development", "Cloud"],
        years_experience=3,
    )

    # Create opportunities
    ds_role = await agent.create_opportunity(
        title="Senior Data Scientist",
        department="Data Science",
        location="Remote",
        opportunity_type=OpportunityType.FULL_TIME,
        description="Lead ML initiatives and mentor junior team members",
        required_skills=[("Python", 4), ("Machine Learning", 4), ("SQL", 3)],
        preferred_skills=["TensorFlow", "PyTorch"],
        required_experience_years=5,
    )

    eng_role = await agent.create_opportunity(
        title="Full Stack Engineer",
        department="Engineering",
        location="Sydney",
        opportunity_type=OpportunityType.FULL_TIME,
        description="Build scalable web applications",
        required_skills=[("Python", 3), ("JavaScript", 4), ("React", 3)],
        preferred_skills=["AWS", "Docker"],
        required_experience_years=2,
    )

    # Find opportunities for Alice
    print("\n=== Opportunities for Alice ===")
    alice_matches = await agent.find_opportunities_for_candidate("alice_001")
    for match in alice_matches:
        print(f"  {match.match_strength.value}: Score {match.overall_score:.2f}")
        print(f"    Matched skills: {', '.join(match.matched_skills)}")
        print(f"    Missing skills: {', '.join(match.missing_skills) or 'None'}")
        print(f"    {match.recommendation}")

    # Find candidates for engineering role
    print("\n=== Candidates for Full Stack Engineer ===")
    eng_candidates = await agent.find_candidates_for_role(eng_role.opportunity_id)
    for match in eng_candidates:
        candidate = agent._candidates.get(match.candidate_id)
        if candidate:
            print(
                f"  {candidate.name}: {match.match_strength.value} ({match.overall_score:.2f})"
            )

    # Submit application
    print("\n=== Submitting Application ===")
    application = await agent.apply(
        candidate_id="bob_002",
        opportunity_id=eng_role.opportunity_id,
        cover_note="Excited about this opportunity to grow my full stack skills!",
    )
    print(f"Application {application.application_id} submitted")

    # Move through pipeline
    await agent.update_application_status(
        application.application_id,
        ApplicationStatus.SCREENING,
        "Initial screening passed",
    )

    # Get career paths for Alice
    print("\n=== Career Paths for Alice ===")
    paths = await agent.suggest_career_paths("alice_001")
    for path in paths:
        print(f"  {path['path_name']}")
        for step in path["steps"]:
            print(f"    Step {step['step']}: {step['opportunity']}")

    # Analytics
    print("\n=== Talent Pool Analytics ===")
    analytics = await agent.get_talent_pool_analytics()
    print(f"  Pool size: {analytics['talent_pool_size']}")
    print(f"  Active opportunities: {analytics['active_opportunities']}")
    print(f"  Top skills: {[s[0] for s in analytics['top_skills'][:5]]}")

    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
