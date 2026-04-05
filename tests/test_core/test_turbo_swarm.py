"""
Tests for Turbo Chess Swarm - Maximum speed, zero rate limits!

The Turbo Chess Strategy ensures we never hit rate limits by using
cheap/fast models (pawns/knights) to protect expensive ones (king/queen).
"""

import pytest
from agentic_brain.core.rate_limiter import (
    TurboChessSwarm,
    SwarmTask,
    SwarmAgent,
    turbo_deploy,
    ProviderTier,
)


class TestTurboChessSwarm:
    """Test the Turbo Chess Swarm deployment strategy."""
    
    def test_swarm_creation(self):
        """Test creating a swarm instance."""
        swarm = TurboChessSwarm()
        assert swarm is not None
        assert swarm.TIER_MODELS is not None
        assert "pawn" in swarm.TIER_MODELS
        assert "king" in swarm.TIER_MODELS
    
    def test_simple_deployment(self):
        """Test deploying simple tasks."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="task1", prompt="Do something", complexity="simple"),
            SwarmTask(id="2", name="task2", prompt="Do another", complexity="simple"),
        ]
        assignments = swarm.plan_deployment(tasks)
        
        assert len(assignments) == 2
        # Simple tasks should NOT use king tier
        for a in assignments:
            assert a.tier in ["pawn", "knight"]
    
    def test_complex_deployment(self):
        """Test deploying complex tasks."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="complex1", prompt="Complex reasoning", complexity="complex"),
        ]
        assignments = swarm.plan_deployment(tasks)
        
        assert len(assignments) == 1
        assert assignments[0].tier in ["queen", "king"]
    
    def test_king_protection(self):
        """Test that king tier is protected (limited usage)."""
        swarm = TurboChessSwarm()
        # Create many critical tasks
        tasks = [
            SwarmTask(id=str(i), name=f"critical{i}", prompt="Critical", complexity="critical")
            for i in range(10)
        ]
        assignments = swarm.plan_deployment(tasks, max_king_usage=2)
        
        king_count = sum(1 for a in assignments if a.tier == "king")
        assert king_count <= 2, "King should be protected!"
    
    def test_tier_distribution(self):
        """Test that tasks are distributed across tiers."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id=str(i), name=f"task{i}", prompt="Task", complexity="medium")
            for i in range(12)
        ]
        assignments = swarm.plan_deployment(tasks)
        
        # Check distribution
        tiers_used = set(a.tier for a in assignments)
        assert len(tiers_used) >= 2, "Should use multiple tiers"
    
    def test_concurrency_limits(self):
        """Test that concurrency limits are respected."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id=str(i), name=f"task{i}", prompt="Task", complexity="simple")
            for i in range(20)
        ]
        assignments = swarm.plan_deployment(tasks)
        
        # Count per tier
        tier_counts = {}
        for a in assignments:
            tier_counts[a.tier] = tier_counts.get(a.tier, 0) + 1
        
        # Verify limits
        for tier, count in tier_counts.items():
            assert count <= swarm.TIER_CONCURRENCY[tier], f"{tier} exceeded limit"
    
    def test_deployment_summary(self):
        """Test getting deployment summary."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="task1", prompt="Task", complexity="medium"),
            SwarmTask(id="2", name="task2", prompt="Task", complexity="simple"),
        ]
        swarm.plan_deployment(tasks)
        summary = swarm.get_deployment_summary()
        
        assert "total_agents" in summary
        assert summary["total_agents"] == 2
        assert "tier_distribution" in summary
        assert "strategy" in summary
        assert summary["strategy"] == "TURBO_CHESS"
    
    def test_cost_estimation(self):
        """Test cost estimation per tier."""
        swarm = TurboChessSwarm()
        
        # Pawn should be free
        assert swarm._estimate_cost("pawn") == 0.0
        # Knight should be very cheap
        assert swarm._estimate_cost("knight") <= 0.01
        # King should be most expensive
        assert swarm._estimate_cost("king") > swarm._estimate_cost("queen")
    
    def test_time_estimation(self):
        """Test time estimation."""
        swarm = TurboChessSwarm()
        
        # Simple should be faster than complex
        simple_time = swarm._estimate_time("knight", "simple")
        complex_time = swarm._estimate_time("knight", "complex")
        assert simple_time < complex_time
    
    def test_quick_deploy(self):
        """Test quick_deploy helper."""
        models = TurboChessSwarm.quick_deploy(6, "medium")
        
        assert len(models) == 6
        assert all(isinstance(m, str) for m in models)
    
    def test_turbo_deploy_function(self):
        """Test turbo_deploy convenience function."""
        models = turbo_deploy(8, "simple")
        
        assert len(models) == 8
        # Simple tasks should use fast/cheap models
        # Should NOT have claude-opus or similar expensive models
    
    def test_requires_reasoning_bumps_tier(self):
        """Test that requires_reasoning moves task to higher tier."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="reasoning", prompt="Think", complexity="simple", requires_reasoning=True),
        ]
        assignments = swarm.plan_deployment(tasks)
        
        # Should NOT be pawn even though simple
        assert assignments[0].tier != "pawn"
    
    def test_requires_code_bumps_tier(self):
        """Test that requires_code moves task to higher tier."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="coding", prompt="Code", complexity="simple", requires_code=True),
        ]
        assignments = swarm.plan_deployment(tasks)
        
        # Should NOT be pawn even though simple
        assert assignments[0].tier != "pawn"
    
    def test_mixed_complexity_deployment(self):
        """Test deploying tasks of mixed complexity."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="simple", prompt="Easy", complexity="simple"),
            SwarmTask(id="2", name="medium", prompt="Medium", complexity="medium"),
            SwarmTask(id="3", name="complex", prompt="Hard", complexity="complex"),
            SwarmTask(id="4", name="critical", prompt="Critical", complexity="critical"),
        ]
        assignments = swarm.plan_deployment(tasks)
        
        assert len(assignments) == 4
        # Should use different tiers
        tiers = [a.tier for a in assignments]
        assert len(set(tiers)) >= 2
    
    def test_priority_ordering(self):
        """Test that high priority tasks are assigned first."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id="1", name="low", prompt="Low", complexity="critical", priority=10),
            SwarmTask(id="2", name="high", prompt="High", complexity="critical", priority=1),
        ]
        assignments = swarm.plan_deployment(tasks, max_king_usage=1)
        
        # High priority (id=2) should get king tier
        high_priority = next(a for a in assignments if a.task_id == "2")
        assert high_priority.tier == "king"
    
    def test_empty_task_list(self):
        """Test handling empty task list."""
        swarm = TurboChessSwarm()
        assignments = swarm.plan_deployment([])
        assert assignments == []
    
    def test_large_swarm_no_rate_limit_risk(self):
        """Test that large swarm has low rate limit risk."""
        swarm = TurboChessSwarm()
        tasks = [
            SwarmTask(id=str(i), name=f"task{i}", prompt="Task", complexity="medium")
            for i in range(20)
        ]
        swarm.plan_deployment(tasks, max_king_usage=2)
        summary = swarm.get_deployment_summary()
        
        # With king protected, risk should be low
        assert summary["rate_limit_risk"] == "LOW"


class TestSwarmDataClasses:
    """Test the swarm data classes."""
    
    def test_swarm_task_defaults(self):
        """Test SwarmTask default values."""
        task = SwarmTask(id="1", name="test", prompt="prompt")
        assert task.complexity == "medium"
        assert task.requires_reasoning == False
        assert task.requires_code == False
        assert task.priority == 5
    
    def test_swarm_agent_creation(self):
        """Test SwarmAgent creation."""
        agent = SwarmAgent(
            task_id="1",
            model="gpt-5-mini",
            tier="knight",
        )
        assert agent.task_id == "1"
        assert agent.model == "gpt-5-mini"
        assert agent.tier == "knight"
        assert agent.estimated_cost == 0.0
        assert agent.estimated_time_seconds == 300


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
