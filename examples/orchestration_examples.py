"""
Examples demonstrating the orchestration system.

This file shows how to use Crew and Workflow for managing multiple agents
and complex multi-step processes.
"""

from agentic_brain.orchestration import (
    Crew,
    CrewConfig,
    ExecutionStrategy,
    AgentRole,
    Workflow,
    WorkflowStep,
)
from agentic_brain.orchestration.crew import MockAgent
from agentic_brain.orchestration.workflow import (
    Transition,
    TransitionType,
    branch_if,
    on_success,
    on_failure,
)


# ============================================================================
# Example 1: Simple Sequential Crew
# ============================================================================

def example_sequential_crew():
    """Example: Run agents sequentially."""
    print("\n" + "="*60)
    print("Example 1: Sequential Crew Execution")
    print("="*60)
    
    # Create agents
    researcher = MockAgent(
        name="researcher",
        role=AgentRole.RESEARCHER.value,
        process_fn=lambda task, ctx: f"Researched: {task[:30]}..."
    )
    analyst = MockAgent(
        name="analyst",
        role=AgentRole.ANALYST.value,
        process_fn=lambda task, ctx: f"Analyzed: {task[:30]}..."
    )
    
    # Create crew with sequential strategy
    crew = Crew(
        agents=[researcher, analyst],
        strategy=ExecutionStrategy.SEQUENTIAL,
        config=CrewConfig(verbose=True)
    )
    
    # Run crew
    results = crew.run("Analyze market trends for Q1 2024")
    
    # Print results
    for result in results:
        print(f"\n{result.agent_name}:")
        print(f"  Result: {result.result}")
        print(f"  Success: {result.success}")
        print(f"  Duration: {result.duration_ms:.2f}ms")


# ============================================================================
# Example 2: Parallel Crew Execution
# ============================================================================

def example_parallel_crew():
    """Example: Run agents in parallel."""
    print("\n" + "="*60)
    print("Example 2: Parallel Crew Execution")
    print("="*60)
    
    # Create multiple agents
    agents = [
        MockAgent(name=f"worker_{i}", process_fn=lambda task, ctx, i=i: f"Worker {i} completed")
        for i in range(4)
    ]
    
    # Create crew with parallel strategy
    crew = Crew(
        agents=agents,
        strategy=ExecutionStrategy.PARALLEL,
        config=CrewConfig(max_workers=4, verbose=True)
    )
    
    # Run crew
    results = crew.run("Process data batch")
    
    print(f"\nProcessed {len(results)} tasks in parallel")
    for result in results:
        print(f"  ✓ {result.agent_name}: {result.duration_ms:.2f}ms")


# ============================================================================
# Example 3: Hierarchical Crew
# ============================================================================

def example_hierarchical_crew():
    """Example: Hierarchical crew with manager and workers."""
    print("\n" + "="*60)
    print("Example 3: Hierarchical Crew (Manager + Workers)")
    print("="*60)
    
    # Create manager and workers
    manager = MockAgent(
        name="project_manager",
        role=AgentRole.MANAGER.value,
        process_fn=lambda task, ctx: "Coordinating team tasks"
    )
    
    workers = [
        MockAgent(
            name=f"developer_{i}",
            role=AgentRole.WORKER.value,
            process_fn=lambda task, ctx, i=i: f"Developer {i} completed task"
        )
        for i in range(3)
    ]
    
    # Create hierarchical crew
    crew = Crew(
        agents=[manager] + workers,
        strategy=ExecutionStrategy.HIERARCHICAL,
        config=CrewConfig(verbose=True)
    )
    
    # Run crew
    results = crew.run("Build new feature")
    
    print(f"\nHierarchical execution completed")
    for result in results:
        print(f"  {result.agent_name}: {result.result}")


# ============================================================================
# Example 4: Shared Memory Between Agents
# ============================================================================

def example_shared_memory():
    """Example: Agents sharing data through shared memory."""
    print("\n" + "="*60)
    print("Example 4: Shared Memory Between Agents")
    print("="*60)
    
    def producer_fn(task: str, context: dict):
        # Producer agent creates data
        data = {"count": 42, "name": "test"}
        # Results are automatically stored in shared memory
        return data
    
    def consumer_fn(task: str, context: dict):
        # Consumer agent reads from context
        producer_result = context.get("producer_result")
        if producer_result:
            return f"Consumed: {producer_result}"
        return "No data available"
    
    producer = MockAgent(name="producer", process_fn=producer_fn)
    consumer = MockAgent(name="consumer", process_fn=consumer_fn)
    
    # Create crew (sequential so data flows)
    crew = Crew(
        agents=[producer, consumer],
        strategy=ExecutionStrategy.SEQUENTIAL,
        config=CrewConfig(verbose=True)
    )
    
    # Run crew
    results = crew.run("Share data")
    
    print("\nShared memory in action:")
    for result in results:
        print(f"  {result.agent_name}: {result.result}")


# ============================================================================
# Example 5: Simple Linear Workflow
# ============================================================================

def example_linear_workflow():
    """Example: Simple step-by-step workflow."""
    print("\n" + "="*60)
    print("Example 5: Linear Workflow")
    print("="*60)
    
    def fetch_data(ctx):
        print("  → Fetching data...")
        ctx["data"] = [1, 2, 3, 4, 5]
        return "Data fetched"
    
    def process_data(ctx):
        print("  → Processing data...")
        data = ctx.get("data", [])
        ctx["result"] = sum(data)
        return f"Sum: {ctx['result']}"
    
    def save_result(ctx):
        print("  → Saving result...")
        return f"Saved: {ctx.get('result')}"
    
    # Create workflow
    workflow = Workflow(start_step="fetch")
    workflow.add_steps([
        WorkflowStep(
            name="fetch",
            execute=fetch_data,
            transitions=[Transition(to_step="process")]
        ),
        WorkflowStep(
            name="process",
            execute=process_data,
            transitions=[Transition(to_step="save")]
        ),
        WorkflowStep(name="save", execute=save_result),
    ])
    
    # Run workflow
    result = workflow.run()
    
    print(f"\nWorkflow completed: {result.state.value}")
    print(f"  Steps executed: {result.steps_executed}")
    print(f"  Duration: {result.duration_ms:.2f}ms")


# ============================================================================
# Example 6: Workflow with Branching
# ============================================================================

def example_branching_workflow():
    """Example: Workflow with conditional branching."""
    print("\n" + "="*60)
    print("Example 6: Workflow with Branching")
    print("="*60)
    
    def evaluate_score(ctx):
        print("  → Evaluating score...")
        ctx["score"] = 85
        return f"Score: {ctx['score']}"
    
    def high_performance_path(ctx):
        print("  → Taking high performance path...")
        ctx["bonus"] = ctx.get("score", 0) * 0.1
        return f"Bonus awarded: {ctx['bonus']}"
    
    def training_path(ctx):
        print("  → Enrolling in training...")
        return "Training enrollment completed"
    
    def finalize(ctx):
        print("  → Finalizing...")
        return "Process complete"
    
    # Create workflow with branching
    workflow = Workflow(start_step="evaluate")
    workflow.add_steps([
        WorkflowStep(
            name="evaluate",
            execute=evaluate_score,
            transitions=branch_if(
                condition=lambda ctx: ctx.get("score", 0) >= 80,
                true_step="high_perf",
                false_step="training"
            )
        ),
        WorkflowStep(
            name="high_perf",
            execute=high_performance_path,
            transitions=[Transition(to_step="finalize")]
        ),
        WorkflowStep(
            name="training",
            execute=training_path,
            transitions=[Transition(to_step="finalize")]
        ),
        WorkflowStep(name="finalize", execute=finalize),
    ])
    
    # Run workflow
    result = workflow.run()
    
    print(f"\nBranching workflow completed: {result.state.value}")
    print(f"  Path taken: {result.steps_executed}")


# ============================================================================
# Example 7: Workflow with Error Handling and Retry
# ============================================================================

def example_error_handling_workflow():
    """Example: Workflow with error handling and retry logic."""
    print("\n" + "="*60)
    print("Example 7: Error Handling and Retry")
    print("="*60)
    
    attempt_count = {"count": 0}
    
    def unreliable_operation(ctx):
        attempt_count["count"] += 1
        print(f"  → Attempt {attempt_count['count']}...")
        
        if attempt_count["count"] < 3:
            raise ConnectionError("Service unavailable")
        
        return "Operation succeeded"
    
    def error_handler(error, ctx):
        print(f"  ⚠ Caught error: {error}")
    
    def fallback(ctx):
        print("  → Using fallback method...")
        return "Fallback result"
    
    # Create workflow with retry
    workflow = Workflow(start_step="risky")
    workflow.add_steps([
        WorkflowStep(
            name="risky",
            execute=unreliable_operation,
            retry_count=2,
            on_error=error_handler,
            transitions=on_success("done") + on_failure("fallback")
        ),
        WorkflowStep(name="fallback", execute=fallback),
        WorkflowStep(name="done", execute=lambda ctx: "Success!"),
    ])
    
    # Run workflow
    result = workflow.run()
    
    print(f"\nError handling workflow completed: {result.state.value}")
    print(f"  Attempts: {attempt_count['count']}")


# ============================================================================
# Example 8: Crew + Workflow Integration
# ============================================================================

def example_crew_in_workflow():
    """Example: Using Crew inside a Workflow step."""
    print("\n" + "="*60)
    print("Example 8: Crew + Workflow Integration")
    print("="*60)
    
    # Create agents for the crew
    agents = [
        MockAgent(name="analyzer", process_fn=lambda t, c: "Analysis complete"),
        MockAgent(name="validator", process_fn=lambda t, c: "Validation passed"),
    ]
    
    def run_crew_analysis(ctx):
        print("  → Running parallel crew analysis...")
        crew = Crew(
            agents=agents,
            strategy=ExecutionStrategy.PARALLEL,
            config=CrewConfig(verbose=False)
        )
        results = crew.run("Analyze results")
        ctx["crew_results"] = len(results)
        return f"Crew completed: {len(results)} results"
    
    def process_crew_results(ctx):
        print("  → Processing crew results...")
        count = ctx.get("crew_results", 0)
        return f"Processed {count} results"
    
    # Create workflow that uses crew
    workflow = Workflow(start_step="analyze")
    workflow.add_steps([
        WorkflowStep(
            name="analyze",
            execute=run_crew_analysis,
            transitions=[Transition(to_step="process")]
        ),
        WorkflowStep(name="process", execute=process_crew_results),
    ])
    
    # Run workflow
    result = workflow.run()
    
    print(f"\nIntegration workflow completed: {result.state.value}")
    print(f"  Result: {result.final_context.get('crew_results')} agents executed")


# ============================================================================
# Run All Examples
# ============================================================================

if __name__ == "__main__":
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█  Agentic Brain Orchestration Examples" + " "*20 + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    
    try:
        example_sequential_crew()
        example_parallel_crew()
        example_hierarchical_crew()
        example_shared_memory()
        example_linear_workflow()
        example_branching_workflow()
        example_error_handling_workflow()
        example_crew_in_workflow()
        
        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█  All examples completed successfully!" + " "*20 + "█")
        print("█" + " "*58 + "█")
        print("█"*60 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
