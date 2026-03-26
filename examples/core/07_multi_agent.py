#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
07 - Multi-Agent Orchestration
================================

Coordinate multiple AI agents working together!
Use Crew and Workflow systems for complex multi-step tasks.

Patterns demonstrated:
- Sequential execution (agents run one after another)
- Parallel execution (agents run simultaneously)
- Hierarchical teams (manager + workers)
- Workflow branching (conditional paths)

Run:
    python examples/07_multi_agent.py

Requirements:
    - Ollama or OpenAI configured
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from agentic_brain.orchestration import (
    Crew,
    CrewConfig,
    ExecutionStrategy,
    AgentRole,
    Workflow,
    WorkflowStep,
)
from agentic_brain.orchestration.crew import MockAgent
from agentic_brain.orchestration.workflow import Transition, branch_if

# ============================================================================
# Example 1: Sequential Agent Crew
# ============================================================================


async def example_sequential_crew():
    """
    Agents run one after another, passing results forward.

    Use case: Research → Analysis → Report generation
    """
    print("\n" + "=" * 60)
    print("Example 1: Sequential Crew")
    print("=" * 60)

    # Create specialized agents
    researcher = MockAgent(
        name="researcher",
        role=AgentRole.RESEARCHER.value,
        process_fn=lambda task, ctx: {
            "findings": ["AI adoption up 40%", "Cost reduced 25%", "3 new trends"],
            "sources": 5,
        },
    )

    analyst = MockAgent(
        name="analyst",
        role=AgentRole.ANALYST.value,
        process_fn=lambda task, ctx: {
            "insights": "Strong growth trajectory with cost benefits",
            "confidence": 0.85,
        },
    )

    writer = MockAgent(
        name="writer",
        role=AgentRole.WORKER.value,
        process_fn=lambda task, ctx: "📊 Market Report: AI shows 40% growth...",
    )

    # Create crew (sequential = one after another)
    crew = Crew(
        agents=[researcher, analyst, writer],
        strategy=ExecutionStrategy.SEQUENTIAL,
        config=CrewConfig(verbose=True),
    )

    print("\n🚀 Running sequential crew...")
    results = crew.run("Analyze Q1 2024 AI market trends")

    print("\n📋 Results:")
    for result in results:
        print(f"  {result.agent_name}: {result.result}")


# ============================================================================
# Example 2: Parallel Agent Crew
# ============================================================================


async def example_parallel_crew():
    """
    Agents run simultaneously for faster execution.

    Use case: Search multiple data sources at once
    """
    print("\n" + "=" * 60)
    print("Example 2: Parallel Crew")
    print("=" * 60)

    # Create agents that can run in parallel
    search_agents = [
        MockAgent(
            name=f"searcher_{source}",
            process_fn=lambda task, ctx, s=source: f"Found 10 results from {s}",
        )
        for source in ["web", "database", "documents", "api"]
    ]

    # Create crew (parallel = all at once)
    crew = Crew(
        agents=search_agents,
        strategy=ExecutionStrategy.PARALLEL,
        config=CrewConfig(max_workers=4, verbose=True),
    )

    print("\n🚀 Running parallel crew...")
    results = crew.run("Search for 'machine learning'")

    print(f"\n✅ All {len(results)} agents completed in parallel:")
    for result in results:
        print(f"  ✓ {result.agent_name}: {result.duration_ms:.0f}ms")


# ============================================================================
# Example 3: Hierarchical Team
# ============================================================================


async def example_hierarchical_team():
    """
    Manager coordinates worker agents.

    Use case: Project manager delegating to team members
    """
    print("\n" + "=" * 60)
    print("Example 3: Hierarchical Team")
    print("=" * 60)

    # Manager coordinates workers
    manager = MockAgent(
        name="project_manager",
        role=AgentRole.MANAGER.value,
        process_fn=lambda task, ctx: {
            "plan": "Divide into 3 subtasks",
            "assignments": {"dev_1": "frontend", "dev_2": "backend", "dev_3": "tests"},
        },
    )

    workers = [
        MockAgent(
            name=f"developer_{i}",
            role=AgentRole.WORKER.value,
            process_fn=lambda task, ctx, i=i: f"Completed subtask {i}",
        )
        for i in range(1, 4)
    ]

    # Create hierarchical crew
    crew = Crew(
        agents=[manager] + workers,
        strategy=ExecutionStrategy.HIERARCHICAL,
        config=CrewConfig(verbose=True),
    )

    print("\n🚀 Running hierarchical team...")
    results = crew.run("Build user authentication feature")

    print("\n📋 Team output:")
    for result in results:
        role = "📊 Manager" if "manager" in result.agent_name else "👷 Worker"
        print(f"  {role} {result.agent_name}: {result.result}")


# ============================================================================
# Example 4: Workflow with Branching
# ============================================================================


async def example_workflow_branching():
    """
    Conditional workflow that takes different paths based on results.

    Use case: Approval workflows, quality gates, error handling
    """
    print("\n" + "=" * 60)
    print("Example 4: Workflow with Branching")
    print("=" * 60)

    # Workflow steps
    def review_submission(ctx: Dict) -> str:
        ctx["score"] = 85  # Simulated review score
        return f"Reviewed: score = {ctx['score']}"

    def approve(ctx: Dict) -> str:
        return "✅ Approved! Sending confirmation..."

    def request_revision(ctx: Dict) -> str:
        return "📝 Revision requested. Please improve and resubmit."

    def finalize(ctx: Dict) -> str:
        return "🎉 Process complete!"

    # Build workflow with conditional branching
    workflow = Workflow(start_step="review")
    workflow.add_steps(
        [
            WorkflowStep(
                name="review",
                execute=review_submission,
                transitions=branch_if(
                    condition=lambda ctx: ctx.get("score", 0) >= 70,
                    true_step="approve",
                    false_step="revise",
                ),
            ),
            WorkflowStep(
                name="approve",
                execute=approve,
                transitions=[Transition(to_step="finalize")],
            ),
            WorkflowStep(
                name="revise",
                execute=request_revision,
                transitions=[Transition(to_step="finalize")],
            ),
            WorkflowStep(name="finalize", execute=finalize),
        ]
    )

    print("\n🚀 Running workflow...")
    result = workflow.run()

    print(f"\n📋 Workflow result:")
    print(f"  Status: {result.state.value}")
    print(f"  Path: {' → '.join(result.steps_executed)}")
    print(f"  Duration: {result.duration_ms:.0f}ms")


# ============================================================================
# Example 5: Error Handling Workflow
# ============================================================================


async def example_error_handling():
    """
    Workflow with retry logic and error recovery.

    Use case: API calls, external service integration
    """
    print("\n" + "=" * 60)
    print("Example 5: Error Handling & Retry")
    print("=" * 60)

    attempt_count = {"count": 0}

    def unreliable_api_call(ctx: Dict) -> str:
        attempt_count["count"] += 1
        print(f"  → Attempt {attempt_count['count']}...")

        # Simulate failing first 2 times
        if attempt_count["count"] < 3:
            raise ConnectionError("Service temporarily unavailable")

        return "API call successful!"

    def use_fallback(ctx: Dict) -> str:
        return "Using cached/fallback data"

    def process_result(ctx: Dict) -> str:
        return "Processing complete"

    # Build workflow with retry
    workflow = Workflow(start_step="api_call")
    workflow.add_steps(
        [
            WorkflowStep(
                name="api_call",
                execute=unreliable_api_call,
                retry_count=3,  # Retry up to 3 times
                on_error=lambda e, ctx: print(f"  ⚠️ Error: {e}"),
                transitions=[Transition(to_step="process", condition=lambda ctx: True)],
            ),
            WorkflowStep(
                name="fallback",
                execute=use_fallback,
                transitions=[Transition(to_step="process")],
            ),
            WorkflowStep(name="process", execute=process_result),
        ]
    )

    print("\n🚀 Running workflow with retries...")
    result = workflow.run()

    print(f"\n✅ Completed after {attempt_count['count']} attempts")
    print(f"  Final state: {result.state.value}")


# ============================================================================
# Example 6: Complex Multi-Stage Pipeline
# ============================================================================


async def example_complex_pipeline():
    """
    Real-world example: Content creation pipeline with multiple stages.
    """
    print("\n" + "=" * 60)
    print("Example 6: Content Creation Pipeline")
    print("=" * 60)

    # Stage 1: Research crew
    research_crew = Crew(
        agents=[
            MockAgent(
                name="web_researcher", process_fn=lambda t, c: {"web_data": "..."}
            ),
            MockAgent(name="data_analyst", process_fn=lambda t, c: {"stats": "..."}),
        ],
        strategy=ExecutionStrategy.PARALLEL,
    )

    # Stage 2: Writing crew
    writing_crew = Crew(
        agents=[
            MockAgent(name="writer", process_fn=lambda t, c: "Draft article..."),
            MockAgent(name="editor", process_fn=lambda t, c: "Edited article..."),
        ],
        strategy=ExecutionStrategy.SEQUENTIAL,
    )

    # Workflow combining crews
    def research_phase(ctx: Dict) -> str:
        print("  📚 Research phase...")
        results = research_crew.run(ctx.get("topic", "AI"))
        ctx["research"] = [r.result for r in results]
        return "Research complete"

    def writing_phase(ctx: Dict) -> str:
        print("  ✍️ Writing phase...")
        results = writing_crew.run(str(ctx.get("research", "")))
        ctx["content"] = results[-1].result
        return "Content created"

    def publish_phase(ctx: Dict) -> str:
        print("  🚀 Publishing...")
        return f"Published: {ctx.get('content', '')[:50]}..."

    # Build pipeline
    pipeline = Workflow(start_step="research")
    pipeline.add_steps(
        [
            WorkflowStep(
                name="research",
                execute=research_phase,
                transitions=[Transition(to_step="write")],
            ),
            WorkflowStep(
                name="write",
                execute=writing_phase,
                transitions=[Transition(to_step="publish")],
            ),
            WorkflowStep(name="publish", execute=publish_phase),
        ]
    )

    print("\n🚀 Running content pipeline...")
    result = pipeline.run(context={"topic": "AI in Healthcare"})

    print(f"\n✅ Pipeline complete!")
    print(f"  Stages: {' → '.join(result.steps_executed)}")
    print(f"  Duration: {result.duration_ms:.0f}ms")


# ============================================================================
# Main Entry Point
# ============================================================================


async def main():
    """Run all multi-agent examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Multi-Agent Orchestration".center(58) + "║")
    print("╚" + "=" * 58 + "╝")

    try:
        await example_sequential_crew()
        await example_parallel_crew()
        await example_hierarchical_team()
        await example_workflow_branching()
        await example_error_handling()
        await example_complex_pipeline()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
