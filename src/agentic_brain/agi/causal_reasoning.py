"""Domain-neutral causal reasoning for agentic systems."""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


def _get_now_dt() -> datetime:
    return datetime.now(UTC)


def _get_now_str() -> str:
    return _get_now_dt().isoformat().replace("+00:00", "Z")


class CausalRelationType(Enum):
    CAUSES = "CAUSES"
    PREVENTS = "PREVENTS"
    ENABLES = "ENABLES"
    CONTRIBUTES = "CONTRIBUTES"
    INHIBITS = "INHIBITS"


class EvidenceType(Enum):
    OBSERVATION = "observation"
    INTERVENTION = "intervention"
    EXPERT_KNOWLEDGE = "expert"
    STATISTICAL = "statistical"
    USER_FEEDBACK = "user_feedback"
    COUNTERFACTUAL = "counterfactual"


class CausalStrength(Enum):
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    DETERMINISTIC = "deterministic"


@dataclass
class Evidence:
    id: str
    type: EvidenceType
    description: str
    timestamp: str
    source: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "timestamp": self.timestamp,
            "source": self.source,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            id=data["id"],
            type=EvidenceType(data["type"]),
            description=data["description"],
            timestamp=data["timestamp"],
            source=data["source"],
            weight=data.get("weight", 1.0),
        )


@dataclass
class CausalLink:
    id: str
    cause: str
    effect: str
    relation_type: CausalRelationType
    strength: float
    confidence: float
    mechanism: str
    evidence: list[Evidence] = field(default_factory=list)
    observation_count: int = 0
    last_observed: str | None = None
    created_at: str = field(default_factory=_get_now_str)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = f"cl_{uuid.uuid4().hex[:12]}"

    @property
    def strength_category(self) -> CausalStrength:
        if self.strength >= 0.8:
            return CausalStrength.DETERMINISTIC
        if self.strength >= 0.6:
            return CausalStrength.STRONG
        if self.strength >= 0.3:
            return CausalStrength.MODERATE
        return CausalStrength.WEAK

    def add_evidence(self, evidence: Evidence) -> None:
        self.evidence.append(evidence)
        self._update_confidence()

    def _update_confidence(self) -> None:
        if not self.evidence:
            return

        total_weight = sum(item.weight for item in self.evidence)
        if total_weight <= 0:
            return

        base_confidence = min(0.5 + (total_weight * 0.1), 0.95)
        diversity_bonus = len({item.type for item in self.evidence}) * 0.05
        self.confidence = min(base_confidence + diversity_bonus, 0.99)

    def observe(self) -> None:
        self.observation_count += 1
        self.last_observed = _get_now_str()
        observation_boost = 0.02 * (1 / (1 + math.log(self.observation_count + 1)))
        self.confidence = min(self.confidence + observation_boost, 0.99)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "cause": self.cause,
            "effect": self.effect,
            "relation_type": self.relation_type.value,
            "strength": self.strength,
            "confidence": self.confidence,
            "mechanism": self.mechanism,
            "evidence": [item.to_dict() for item in self.evidence],
            "observation_count": self.observation_count,
            "last_observed": self.last_observed,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CausalLink:
        evidence = [Evidence.from_dict(item) for item in data.get("evidence", [])]
        return cls(
            id=data["id"],
            cause=data["cause"],
            effect=data["effect"],
            relation_type=CausalRelationType(data["relation_type"]),
            strength=data["strength"],
            confidence=data["confidence"],
            mechanism=data["mechanism"],
            evidence=evidence,
            observation_count=data.get("observation_count", 0),
            last_observed=data.get("last_observed"),
            created_at=data.get("created_at", _get_now_str()),
            metadata=data.get("metadata", {}),
        )

    def describe(self) -> str:
        relation_word = {
            CausalRelationType.CAUSES: "causes",
            CausalRelationType.PREVENTS: "prevents",
            CausalRelationType.ENABLES: "enables",
            CausalRelationType.CONTRIBUTES: "contributes to",
            CausalRelationType.INHIBITS: "inhibits",
        }.get(self.relation_type, "relates to")
        return (
            f"{self.cause} {relation_word} {self.effect} "
            f"({self.strength_category.value} link, {int(self.confidence * 100)}% confident)"
        )


@dataclass
class CausalChain:
    links: list[CausalLink]
    total_strength: float
    confidence: float

    @property
    def start(self) -> str:
        return self.links[0].cause if self.links else ""

    @property
    def end(self) -> str:
        return self.links[-1].effect if self.links else ""

    @property
    def length(self) -> int:
        return len(self.links)

    def describe(self) -> str:
        if not self.links:
            return "No causal chain found."
        chain_text = " → ".join([self.links[0].cause] + [link.effect for link in self.links])
        return f"Causal chain: {chain_text}. Overall strength: {int(self.total_strength * 100)}%."


@dataclass
class RootCauseAnalysis:
    symptom: str
    root_causes: list[tuple[str, float]]
    causal_chains: list[CausalChain]
    contributing_factors: list[str]
    recommendations: list[str]
    confidence: float

    def describe(self) -> str:
        if not self.root_causes:
            return f"Could not determine root cause of '{self.symptom}'."

        top_cause, probability = self.root_causes[0]
        output = (
            f"Root cause analysis of '{self.symptom}': "
            f"Primary root cause: {top_cause} ({int(probability * 100)}% likely). "
        )

        if len(self.root_causes) > 1:
            alternatives = [cause for cause, _ in self.root_causes[1:3]]
            output += f"Other possible causes: {', '.join(alternatives)}. "

        if self.recommendations:
            output += f"Recommendation: {self.recommendations[0]}."

        return output


@dataclass
class CounterfactualResult:
    original_event: str
    hypothetical_change: str
    affected_outcomes: list[tuple[str, str, float]]
    explanation: str
    confidence: float

    def describe(self) -> str:
        output = f"What if {self.hypothetical_change}? "
        if not self.affected_outcomes:
            return output + "Likely no significant changes."

        changes = []
        for outcome, direction, magnitude in self.affected_outcomes[:3]:
            qualifier = (
                "slightly"
                if magnitude < 0.3
                else "significantly"
                if magnitude < 0.7
                else "dramatically"
            )
            changes.append(f"{outcome} would {qualifier} {direction}")
        return output + " Also, ".join(changes) + "."


class CausalReasoner:
    """Causal reasoning engine for cause-effect relationships."""

    DOMAIN_PATTERNS = [
        {
            "cause": "resource unavailable",
            "effect": "task cannot proceed",
            "relation": CausalRelationType.CAUSES,
            "strength": 0.95,
            "mechanism": "Task depends on resource; without it, task is blocked",
        },
        {
            "cause": "dependency failure",
            "effect": "dependent system failure",
            "relation": CausalRelationType.CAUSES,
            "strength": 0.9,
            "mechanism": "System relies on dependency; failure cascades",
        },
        {
            "cause": "insufficient permissions",
            "effect": "operation fails",
            "relation": CausalRelationType.CAUSES,
            "strength": 0.98,
            "mechanism": "Operation requires permissions; without them, access is denied",
        },
        {
            "cause": "invalid input",
            "effect": "processing error",
            "relation": CausalRelationType.CAUSES,
            "strength": 0.85,
            "mechanism": "System cannot process invalid data correctly",
        },
        {
            "cause": "timeout",
            "effect": "operation incomplete",
            "relation": CausalRelationType.CAUSES,
            "strength": 0.92,
            "mechanism": "Operation did not complete within time limit",
        },
    ]

    def __init__(self) -> None:
        self._memory_links: dict[tuple[str, str], CausalLink] = {}
        self._initialized = False

    def initialize(self, load_patterns: bool = True) -> None:
        if self._initialized:
            return

        try:
            if load_patterns:
                self._load_domain_patterns()
            self._initialized = True
            logger.info("CausalReasoner initialized successfully")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to initialize CausalReasoner: %s", exc)

    def _load_domain_patterns(self) -> None:
        for pattern in self.DOMAIN_PATTERNS:
            self.learn_causal_relationship(
                cause=pattern["cause"],
                effect=pattern["effect"],
                relation_type=pattern["relation"],
                strength=pattern["strength"],
                mechanism=pattern["mechanism"],
                source="domain_knowledge",
            )

    def learn_causal_relationship(
        self,
        cause: str,
        effect: str,
        relation_type: CausalRelationType = CausalRelationType.CAUSES,
        strength: float = 0.7,
        confidence: float = 0.5,
        mechanism: str | None = None,
        source: str = "observation",
    ) -> CausalLink:
        key = (cause.lower(), effect.lower())
        if key in self._memory_links:
            link = self._memory_links[key]
            link.strength = (link.strength + strength) / 2
            link.observation_count += 1
            link.observe()
            return link

        link = CausalLink(
            id="",
            cause=cause,
            effect=effect,
            relation_type=relation_type,
            strength=strength,
            confidence=confidence,
            mechanism=mechanism or f"{cause} leads to {effect}",
            observation_count=1,
        )
        link.add_evidence(
            Evidence(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                type=(
                    EvidenceType.OBSERVATION
                    if source == "observation"
                    else EvidenceType.EXPERT_KNOWLEDGE
                ),
                description=f"Initial learning: {source}",
                timestamp=_get_now_str(),
                source=source,
                weight=1.0,
            )
        )
        self._memory_links[key] = link
        logger.debug("Learned causal link: %s → %s", cause, effect)
        return link

    def add_observation(
        self,
        cause: str,
        effect: str,
        evidence_desc: str | None = None,
        source: str = "observation",
    ) -> CausalLink:
        key = (cause.lower(), effect.lower())
        if key not in self._memory_links:
            link = self.learn_causal_relationship(
                cause,
                effect,
                strength=0.7,
                confidence=0.5,
                source=source,
            )
        else:
            link = self._memory_links[key]

        link.observe()
        link.add_evidence(
            Evidence(
                id=f"ev_{uuid.uuid4().hex[:8]}",
                type=EvidenceType.OBSERVATION,
                description=evidence_desc or f"{cause} → {effect}",
                timestamp=_get_now_str(),
                source=source,
                weight=1.0,
            )
        )
        return link

    def infer_causes(self, effect: str, max_depth: int = 3) -> list[tuple[str, float]]:
        del max_depth
        causes: list[tuple[str, float]] = []
        for (_, candidate_effect), link in self._memory_links.items():
            if candidate_effect.lower() == effect.lower():
                causes.append((link.cause, link.strength * link.confidence))
        causes.sort(key=lambda item: item[1], reverse=True)
        return causes

    def predict_effects(self, cause: str, max_depth: int = 3) -> list[tuple[str, float]]:
        del max_depth
        effects: list[tuple[str, float]] = []
        for (candidate_cause, _), link in self._memory_links.items():
            if candidate_cause.lower() == cause.lower():
                effects.append((link.effect, link.strength * link.confidence))
        effects.sort(key=lambda item: item[1], reverse=True)
        return effects

    def find_root_causes(self, symptom: str) -> RootCauseAnalysis:
        direct_causes = self.infer_causes(symptom)
        root_causes: list[tuple[str, float]] = []
        causal_chains: list[CausalChain] = []
        contributing_factors: set[str] = set()

        for cause, probability in direct_causes:
            ancestors = self._trace_ancestors(cause, max_depth=5)
            if ancestors:
                root_cause, root_probability = ancestors[-1]
                root_causes.append((root_cause, probability * root_probability))
                chain_links = self._build_chain(root_cause, symptom)
                if chain_links:
                    causal_chains.append(
                        CausalChain(
                            links=chain_links,
                            total_strength=probability * root_probability,
                            confidence=sum(link.confidence for link in chain_links) / len(chain_links),
                        )
                    )
            else:
                root_causes.append((cause, probability))
                contributing_factors.add(cause)

        root_causes.sort(key=lambda item: item[1], reverse=True)
        overall_confidence = (
            sum(probability for _, probability in root_causes) / len(root_causes)
            if root_causes
            else 0.0
        )
        return RootCauseAnalysis(
            symptom=symptom,
            root_causes=root_causes,
            causal_chains=causal_chains,
            contributing_factors=sorted(contributing_factors),
            recommendations=self._generate_recommendations(root_causes),
            confidence=overall_confidence,
        )

    def _trace_ancestors(self, event: str, max_depth: int = 5) -> list[tuple[str, float]]:
        ancestors: list[tuple[str, float]] = []
        current = event
        depth = 0
        while depth < max_depth:
            causes = self.infer_causes(current)
            if not causes:
                break
            top_cause, probability = causes[0]
            ancestors.append((top_cause, probability))
            current = top_cause
            depth += 1
        return ancestors

    def _build_chain(self, start: str, end: str) -> list[CausalLink]:
        chain: list[CausalLink] = []
        current = start
        visited: set[str] = set()

        while current != end and current not in visited:
            visited.add(current)
            effects = self.predict_effects(current)
            if not effects:
                break

            next_effect = None
            for effect, _ in effects:
                key = (current.lower(), effect.lower())
                if key in self._memory_links:
                    chain.append(self._memory_links[key])
                    next_effect = effect
                    break

            if next_effect is None:
                break
            current = next_effect

        return chain

    def _generate_recommendations(self, root_causes: list[tuple[str, float]]) -> list[str]:
        recommendations: list[str] = []
        for cause, probability in root_causes[:3]:
            if probability > 0.7:
                recommendations.append(f"Address '{cause}' to prevent this symptom")
            elif probability > 0.4:
                recommendations.append(f"Consider addressing '{cause}' as a contributing factor")
        return recommendations or ["Investigate further to identify root cause"]

    def counterfactual_analysis(
        self,
        event: str,
        hypothetical_change: str,
    ) -> CounterfactualResult:
        effects = self.predict_effects(event)
        affected_outcomes: list[tuple[str, str, float]] = []
        explanation = f"If '{hypothetical_change}' instead of '{event}', "

        if not effects:
            explanation += "likely no causal effects would be prevented."
        else:
            prevented = []
            for effect, probability in effects:
                if probability > 0.5:
                    prevented.append(effect)
                    affected_outcomes.append((effect, "be prevented", probability))

            explanation += (
                f"these effects would be prevented: {', '.join(prevented)}"
                if prevented
                else "effects would be unlikely"
            )

        confidence = (
            sum(probability for _, _, probability in affected_outcomes) / len(affected_outcomes)
            if affected_outcomes
            else 0.3
        )
        return CounterfactualResult(
            original_event=event,
            hypothetical_change=hypothetical_change,
            affected_outcomes=affected_outcomes,
            explanation=explanation,
            confidence=confidence,
        )

    def intervention_analysis(self, action: str) -> dict[str, Any]:
        effects = self.predict_effects(action)
        summary = (
            ", ".join(f"{effect} ({int(probability * 100)}%)" for effect, probability in effects[:3])
            if effects
            else "no direct effects"
        )
        return {
            "action": action,
            "predicted_effects": effects,
            "summary": f"Action '{action}' would likely cause: {summary}",
        }

    def accept_feedback(
        self,
        cause: str,
        effect: str,
        is_correct: bool,
        correction: str | None = None,
    ) -> None:
        if is_correct:
            link = self.add_observation(
                cause,
                effect,
                evidence_desc="Confirmed by user feedback",
                source="user_feedback",
            )
            link.add_evidence(
                Evidence(
                    id=f"fb_{uuid.uuid4().hex[:8]}",
                    type=EvidenceType.USER_FEEDBACK,
                    description="User confirmed this causal relationship",
                    timestamp=_get_now_str(),
                    source="user_feedback",
                    weight=2.0,
                )
            )
            return

        key = (cause.lower(), effect.lower())
        if key in self._memory_links:
            link = self._memory_links[key]
            link.confidence *= 0.5
            link.add_evidence(
                Evidence(
                    id=f"fb_{uuid.uuid4().hex[:8]}",
                    type=EvidenceType.USER_FEEDBACK,
                    description=f"User disputed this link: {correction or 'Not actually causal'}",
                    timestamp=_get_now_str(),
                    source="user_feedback",
                    weight=-1.0,
                )
            )

        if correction:
            self.add_observation(
                cause,
                correction,
                evidence_desc="User corrected causal relationship",
                source="user_feedback",
            )

    def explain_why(self, event: str) -> str:
        causes = self.infer_causes(event)
        if not causes:
            return f"No known causes for '{event}'. This might be spontaneous or unknown."

        top_cause, probability = causes[0]
        key = (top_cause.lower(), event.lower())
        if key not in self._memory_links:
            return f"'{event}' likely resulted from '{top_cause}' ({int(probability * 100)}% likely)"

        link = self._memory_links[key]
        return (
            f"'{event}' occurred because '{top_cause}'. "
            f"Mechanism: {link.mechanism} "
            f"(Confidence: {int(link.confidence * 100)}%)"
        )

    def explain_what_if(self, action: str) -> str:
        return self.intervention_analysis(action)["summary"]

    def get_all_links(self) -> list[CausalLink]:
        return list(self._memory_links.values())

    def get_link_count(self) -> int:
        return len(self._memory_links)

    def get_statistics(self) -> dict[str, Any]:
        if not self._memory_links:
            return {
                "total_links": 0,
                "average_strength": 0,
                "average_confidence": 0,
                "relations_by_type": {},
            }

        links = list(self._memory_links.values())
        relations_by_type: dict[str, int] = {}
        for link in links:
            relation_name = link.relation_type.value
            relations_by_type[relation_name] = relations_by_type.get(relation_name, 0) + 1

        return {
            "total_links": len(links),
            "average_strength": sum(link.strength for link in links) / len(links),
            "average_confidence": sum(link.confidence for link in links) / len(links),
            "most_observed": max(links, key=lambda link: link.observation_count).cause,
            "relations_by_type": relations_by_type,
            "evidence_count": sum(len(link.evidence) for link in links),
        }


_reasoner: CausalReasoner | None = None


def get_reasoner() -> CausalReasoner:
    global _reasoner
    if _reasoner is None:
        _reasoner = CausalReasoner()
        _reasoner.initialize()
    return _reasoner


__all__ = [
    "CausalChain",
    "CausalLink",
    "CausalReasoner",
    "CausalRelationType",
    "CausalStrength",
    "CounterfactualResult",
    "Evidence",
    "EvidenceType",
    "RootCauseAnalysis",
    "get_reasoner",
]
