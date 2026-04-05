# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Graph Benchmark — Brain Neo4j Health Scoring

Adapted from Arraz's HappySkies brain_benchmark.py (v3).

Three independent sections, each testing something different:

  STRUCTURE  (40%) — coverage & completeness metrics
  REASONING  (40%) — cross-node questions requiring graph traversal
  FRICTION   (20%) — real failures logged from live sessions

The key principle: high scores should be earned, not constructed.
  - Structure: targets are aspirational, not just what we put in
  - Reasoning: tests RELATIONSHIPS — can't be faked by adding node properties
  - Friction:  starts unproven at 100, degrades with real session failures

Usage:
    python -m agentic_brain.benchmark.graph_benchmark

    # Or programmatically:
    from agentic_brain.benchmark.graph_benchmark import GraphBenchmark
    result = GraphBenchmark().run()
    print(f"Score: {result['combined']}")
"""

import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════════
# CONFIG — Agentic Brain schema
# ══════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    # ─── Connection ───────────────────────────────────────────────────
    "bolt": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
    "auth": (
        os.environ.get("NEO4J_USER", "neo4j"),
        os.environ.get("NEO4J_PASSWORD", "Brain2026"),
    ),
    "brain_name": os.environ.get("BRAIN_NAME", "AgenticBrain"),
    # ─── Node labels ──────────────────────────────────────────────────
    "n_task": "Task",
    "n_learning": "Learning",
    "n_memory": "Memory",
    "n_session": "Session",
    "n_checkpoint": "Checkpoint",
    "n_topic": "Topic",
    "n_event": "HookEvent",
    "n_entity": "Entity",
    "n_workflow": "Workflow",
    "n_agent": "Agent",
    "n_friction": "FrictionEvent",
    "n_people": ["Person"],
    # ─── Relationship types ───────────────────────────────────────────
    "r_discusses": "DISCUSSES",
    "r_mentions": "MENTIONS",
    "r_continues": "CONTINUES",
    "r_part_of": "PART_OF",
    "r_has_checkpoint": "HAS_CHECKPOINT",
    "r_tagged": ["RELATES_TO", "TAGGED", "ABOUT"],
    # ─── Structure targets (aspirational — set these high) ────────────
    "t_ratio": 3.0,  # Rel/node ratio target
    "t_node_types": 25,  # Variety of node types
    "t_tasks": 30,  # Tasks tracked
    "t_learnings": 50,  # Learnings captured
    "t_memories": 100,  # Memories stored
    "t_sessions": 50,  # Sessions recorded
    "t_topics": 40,  # Topics defined
    "t_people": 15,  # People tracked
    "t_events": 500,  # Hook events captured
    "t_entities": 100,  # Named entities extracted
    "t_workflows": 10,  # Workflows defined
    "t_agents": 10,  # Agents configured
    # ─── Scoring weights (must sum to 1.0) ────────────────────────────
    "w_structure": 0.40,
    "w_reasoning": 0.40,
    "w_friction": 0.20,
    "friction_cost": 10,  # pts deducted per friction event in last 30 days
}


@dataclass
class GraphBenchmarkResult:
    """Result of a graph benchmark run."""

    combined: float
    structure_score: float
    reasoning_score: float
    friction_score: float
    total_nodes: int
    total_rels: int
    ratio: float
    timestamp: str
    details: dict = field(default_factory=dict)


class GraphBenchmark:
    """
    Neo4j graph health benchmarking.

    Measures how well-connected and useful the brain's knowledge graph is.
    """

    def __init__(self, config: dict | None = None):
        """Initialize with optional config overrides."""
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._driver = None
        self._people_where = " OR ".join(f"n:{l}" for l in self.config["n_people"])
        self._tagged_rels = "|".join(f":{r}" for r in self.config["r_tagged"])

    def _get_driver(self):
        """Lazy-load Neo4j driver."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    self.config["bolt"], auth=self.config["auth"]
                )
                self._driver.verify_connectivity()
            except Exception as e:
                raise ConnectionError(f"Cannot connect to Neo4j: {e}")
        return self._driver

    def _query(self, cypher: str, **params) -> list[dict]:
        """Run a Cypher query and return results."""
        driver = self._get_driver()
        with driver.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]

    def _val(self, cypher: str, key: str = "c", **params) -> int | float:
        """Run query and return single value."""
        result = self._query(cypher, **params)
        return result[0][key] if result and key in result[0] else 0

    def run(self, verbose: bool = True) -> GraphBenchmarkResult:
        """
        Run the full benchmark.

        Args:
            verbose: If True, print detailed output

        Returns:
            GraphBenchmarkResult with scores and details
        """
        C = self.config

        # ─── Basic stats ──────────────────────────────────────────────
        total_nodes = self._val("MATCH (n) RETURN count(n) as c")
        total_rels = self._val("MATCH ()-[r]->() RETURN count(r) as c")
        isolated = self._val("MATCH (n) WHERE NOT (n)--() RETURN count(n) as c")

        # Ratio scoped to business nodes only (exclude session layer)
        biz_nodes = self._val(
            "MATCH (n) WHERE NOT (n:Session OR n:HookEvent OR n:Checkpoint) RETURN count(n) as c"
        )
        biz_rels = self._val(
            "MATCH (a)-[r]->(b) WHERE NOT (a:Session OR a:HookEvent OR a:Checkpoint) "
            "AND NOT (b:Session OR b:HookEvent OR b:Checkpoint) RETURN count(r) as c"
        )
        ratio = round(biz_rels / biz_nodes, 2) if biz_nodes else 0

        # ─── Structure metrics ────────────────────────────────────────
        types = len(self._query("MATCH (n) RETURN DISTINCT labels(n)[0] as l"))
        tasks = self._val(f"MATCH (t:{C['n_task']}) RETURN count(t) as c")
        learnings = self._val(f"MATCH (l:{C['n_learning']}) RETURN count(l) as c")
        memories = self._val(f"MATCH (m:{C['n_memory']}) RETURN count(m) as c")
        sessions = self._val(f"MATCH (s:{C['n_session']}) RETURN count(s) as c")
        topics = self._val(f"MATCH (t:{C['n_topic']}) RETURN count(t) as c")
        people = self._val(f"MATCH (n) WHERE {self._people_where} RETURN count(n) as c")
        events = self._val(f"MATCH (e:{C['n_event']}) RETURN count(e) as c")
        entities = self._val(f"MATCH (e:{C['n_entity']}) RETURN count(e) as c")
        workflows = self._val(f"MATCH (w:{C['n_workflow']}) RETURN count(w) as c")
        agents = self._val(f"MATCH (a:{C['n_agent']}) RETURN count(a) as c")

        struct_metrics = [
            ("Rel/node ratio (biz)", ratio, C["t_ratio"], "CONNECTIVITY"),
            ("Connected nodes", total_nodes - isolated, total_nodes, "CONNECTIVITY"),
            ("Node type variety", types, C["t_node_types"], "COVERAGE"),
            ("Tasks tracked", tasks, C["t_tasks"], "COVERAGE"),
            ("Learnings captured", learnings, C["t_learnings"], "COVERAGE"),
            ("Memories stored", memories, C["t_memories"], "COVERAGE"),
            ("Sessions recorded", sessions, C["t_sessions"], "COVERAGE"),
            ("Topics defined", topics, C["t_topics"], "COVERAGE"),
            ("People tracked", people, C["t_people"], "COVERAGE"),
            ("Hook events", events, C["t_events"], "FRESHNESS"),
            ("Entities extracted", entities, C["t_entities"], "DEPTH"),
            ("Workflows defined", workflows, C["t_workflows"], "DEPTH"),
            ("Agents configured", agents, C["t_agents"], "DEPTH"),
        ]

        struct_scores = []
        for _name, current, target, _group in struct_metrics:
            pct = min(round((current / target) * 100), 100) if target else 0
            struct_scores.append(pct)

        struct_avg = (
            round(sum(struct_scores) / len(struct_scores)) if struct_scores else 0
        )

        # ─── Reasoning tests ──────────────────────────────────────────
        reason_tests = []

        # Test 1: Most connected Topic
        result = self._query(
            f"MATCH (t:{C['n_topic']})<-[r]-() RETURN t.name, count(r) as c "
            f"ORDER BY c DESC LIMIT 1"
        )
        reason_tests.append(
            {
                "name": "Most connected Topic?",
                "passed": bool(result),
                "value": (
                    f"{result[0]['t.name']} ({result[0]['c']} links)"
                    if result
                    else "No Topics"
                ),
            }
        )

        # Test 2: Node types linking into Topics
        result = self._query(
            f"MATCH (n)-[]->(t:{C['n_topic']}) RETURN count(DISTINCT labels(n)[0]) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Node types → Topic",
                "passed": count >= 3,
                "value": f"{count} types",
            }
        )

        # Test 3: Sessions have checkpoints
        result = self._query(
            f"MATCH (s:{C['n_session']})-[:{C['r_has_checkpoint']}]->(c:{C['n_checkpoint']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Session → Checkpoint links",
                "passed": count > 0,
                "value": f"{count} links",
            }
        )

        # Test 4: Sessions discuss Topics
        result = self._query(
            f"MATCH (s:{C['n_session']})-[:{C['r_discusses']}]->(t:{C['n_topic']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Session → Topic (DISCUSSES)",
                "passed": count >= 5,
                "value": f"{count} links",
            }
        )

        # Test 5: Sessions continue from previous
        result = self._query(
            f"MATCH (s:{C['n_session']})-[:{C['r_continues']}]->(prev:{C['n_session']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Session stitching (CONTINUES)",
                "passed": count > 0,
                "value": f"{count} links",
            }
        )

        # Test 6: Entities mentioned in sessions
        result = self._query(
            f"MATCH (s:{C['n_session']})-[:{C['r_mentions']}]->(e:{C['n_entity']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Session → Entity (MENTIONS)",
                "passed": count > 0,
                "value": f"{count} links",
            }
        )

        # Test 7: Learnings linked to topics
        result = self._query(
            f"MATCH (l:{C['n_learning']})-[{self._tagged_rels}]->(t:{C['n_topic']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Learning → Topic links",
                "passed": count > 0,
                "value": f"{count} links",
            }
        )

        # Test 8: Memories linked to topics
        result = self._query(
            f"MATCH (m:{C['n_memory']})-[{self._tagged_rels}]->(t:{C['n_topic']}) "
            f"RETURN count(*) as c"
        )
        count = result[0]["c"] if result else 0
        reason_tests.append(
            {
                "name": "Memory → Topic links",
                "passed": count > 0,
                "value": f"{count} links",
            }
        )

        reason_pass = sum(1 for t in reason_tests if t["passed"])
        reason_score = (
            round(reason_pass / len(reason_tests) * 100) if reason_tests else 0
        )

        # ─── Friction score ───────────────────────────────────────────
        friction_recent = self._val(
            f"MATCH (f:{C['n_friction']}) "
            f"WHERE f.timestamp > datetime() - duration('P30D') "
            f"RETURN count(f) as c"
        )
        friction_all = self._val(f"MATCH (f:{C['n_friction']}) RETURN count(f) as c")
        friction_score = max(0, 100 - friction_recent * C["friction_cost"])
        unproven = friction_all == 0

        # ─── Combined score ───────────────────────────────────────────
        w_struct = C["w_structure"]
        w_reason = C["w_reasoning"]
        w_fric = C["w_friction"]

        struct_contrib = struct_avg * w_struct
        reason_contrib = reason_score * w_reason
        fric_contrib = friction_score * w_fric

        combined = round(struct_contrib + reason_contrib + fric_contrib, 1)

        # ─── Output ───────────────────────────────────────────────────
        if verbose:
            self._print_results(
                total_nodes,
                total_rels,
                ratio,
                isolated,
                struct_metrics,
                struct_scores,
                struct_avg,
                reason_tests,
                reason_score,
                friction_recent,
                friction_score,
                unproven,
                combined,
                w_struct,
                w_reason,
                w_fric,
            )

        # ─── Save to Neo4j ────────────────────────────────────────────
        self._save_result(
            combined,
            struct_avg,
            reason_score,
            friction_score,
            total_nodes,
            total_rels,
            ratio,
        )

        return GraphBenchmarkResult(
            combined=combined,
            structure_score=struct_avg,
            reasoning_score=reason_score,
            friction_score=friction_score,
            total_nodes=total_nodes,
            total_rels=total_rels,
            ratio=ratio,
            timestamp=datetime.now().isoformat(),
            details={
                "struct_metrics": struct_metrics,
                "reason_tests": reason_tests,
                "friction_events": friction_recent,
            },
        )

    def _print_results(
        self,
        total_nodes,
        total_rels,
        ratio,
        isolated,
        struct_metrics,
        struct_scores,
        struct_avg,
        reason_tests,
        reason_score,
        friction_recent,
        friction_score,
        unproven,
        combined,
        w_struct,
        w_reason,
        w_fric,
    ):
        """Print formatted benchmark results."""

        def bar(pct, w=20):
            f = round(pct / 100 * w)
            return "█" * f + "░" * (w - f)

        def status(pct):
            return "✅" if pct >= 80 else "🟡" if pct >= 50 else "🔴"

        SEP = "─" * 72
        DSEP = "═" * 72
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        print(f"\n🧠  {self.config['brain_name']} Graph Benchmark  —  {now}")
        print(
            f"    Nodes: {total_nodes}  |  Rels: {total_rels}  |  Ratio: {ratio}  |  Isolated: {isolated}"
        )

        # Structure section
        print(f"\n{DSEP}")
        print(
            f"  SECTION 1 — STRUCTURE                                         (weight: {int(w_struct*100)}%)"
        )
        print(DSEP)
        print(f"  {'Metric':<30}  {'Current':>8}  {'Target':>7}  {'Score':>5}  Bar")
        print(SEP)

        cur_group = None
        for (name, current, target, group), pct in zip(
            struct_metrics, struct_scores, strict=False
        ):
            if group != cur_group:
                cur_group = group
                print(f"  {group}")
            st = status(pct)
            print(
                f"  {st} {name:<28}  {current:>8}  {target:>7}  {pct:>4}%  {bar(pct, 16)}"
            )

        print(SEP)
        print(f"  STRUCTURE SCORE  {bar(struct_avg)}  {struct_avg}%")

        # Reasoning section
        print(f"\n{DSEP}")
        print(
            f"  SECTION 2 — REASONING                                         (weight: {int(w_reason*100)}%)"
        )
        print(DSEP)
        print(f"  {'Question':<40}  {'Result'}")
        print(SEP)

        for test in reason_tests:
            st = "✅" if test["passed"] else "❌"
            print(f"  {st} {test['name']:<40}  {test['value']}")

        print(SEP)
        passed = sum(1 for t in reason_tests if t["passed"])
        print(
            f"  REASONING SCORE  {bar(reason_score)}  {passed}/{len(reason_tests)} pass  ({reason_score}%)"
        )

        # Friction section
        print(f"\n{DSEP}")
        print(
            f"  SECTION 3 — FRICTION LOG                                      (weight: {int(w_fric*100)}%)"
        )
        print(DSEP)
        print(f"  Events last 30 days : {friction_recent}")
        print(
            f"  Score               : 100 − ({friction_recent} × 10) = {friction_score}%"
        )
        if unproven:
            print("\n  ⚠️  No friction events logged yet (unproven).")
        print(SEP)
        print(f"  FRICTION SCORE  {bar(friction_score)}  {friction_score}%")

        # Combined
        print(f"\n{DSEP}")
        print("  FINAL SCORE")
        print(DSEP)
        print(
            f"  Structure:  {int(w_struct*100)}% × {struct_avg}% = {round(struct_avg * w_struct, 1)} pts"
        )
        print(
            f"  Reasoning:  {int(w_reason*100)}% × {reason_score}% = {round(reason_score * w_reason, 1)} pts"
        )
        print(
            f"  Friction:   {int(w_fric*100)}% × {friction_score}% = {round(friction_score * w_fric, 1)} pts"
        )
        print(f"  {'─'*40}")
        print(f"  COMBINED    {bar(combined)}  {combined}/100")
        print(DSEP)
        print()

    def _save_result(self, combined, struct, reason, friction, nodes, rels, ratio):
        """Save benchmark result to Neo4j."""
        try:
            driver = self._get_driver()
            with driver.session() as session:
                session.run(
                    """
                    CREATE (b:GraphBenchmark {
                        score: $combined,
                        structure_score: $struct,
                        reasoning_score: $reason,
                        friction_score: $friction,
                        timestamp: datetime(),
                        nodes: $nodes,
                        rels: $rels,
                        ratio: $ratio,
                        version: 1
                    })
                """,
                    combined=combined,
                    struct=struct,
                    reason=reason,
                    friction=friction,
                    nodes=nodes,
                    rels=rels,
                    ratio=ratio,
                )
        except Exception as e:
            print(f"  ⚠️  Could not save to Neo4j: {e}")

    def get_trend(self, limit: int = 10) -> list[dict]:
        """Get historical benchmark scores."""
        return self._query(
            """
            MATCH (b:GraphBenchmark)
            RETURN b.timestamp as timestamp, b.score as score,
                   b.structure_score as structure, b.reasoning_score as reasoning
            ORDER BY b.timestamp DESC
            LIMIT $limit
        """,
            limit=limit,
        )

    def close(self):
        """Close the Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None


def run_graph_benchmark(verbose: bool = True) -> GraphBenchmarkResult:
    """Run benchmark and return result."""
    bench = GraphBenchmark()
    try:
        return bench.run(verbose=verbose)
    finally:
        bench.close()


def get_graph_score() -> float:
    """Get just the combined score."""
    bench = GraphBenchmark()
    try:
        result = bench.run(verbose=False)
        return result.combined
    finally:
        bench.close()


if __name__ == "__main__":
    run_graph_benchmark()
