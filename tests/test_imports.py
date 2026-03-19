"""
Import verification tests for agentic-brain.

Tests that:
1. All public imports work correctly
2. Version is accessible
3. No circular imports occur
4. All exported symbols are available
"""

import pytest
import sys
from importlib import import_module


class TestPublicImports:
    """Test that all public APIs are importable."""
    
    def test_main_package_import(self):
        """Test importing main package works."""
        import agentic_brain
        assert agentic_brain is not None
    
    def test_version_accessible(self):
        """Test that version is accessible from main package."""
        import agentic_brain
        assert hasattr(agentic_brain, "__version__")
        assert isinstance(agentic_brain.__version__, str)
        assert agentic_brain.__version__ == "0.1.0"
    
    def test_agent_import(self):
        """Test Agent class is importable."""
        from agentic_brain import Agent
        assert Agent is not None
        assert callable(Agent)
    
    def test_neo4j_memory_import(self):
        """Test Neo4jMemory class is importable."""
        from agentic_brain import Neo4jMemory
        assert Neo4jMemory is not None
        assert callable(Neo4jMemory)
    
    def test_data_scope_import(self):
        """Test DataScope enum is importable."""
        from agentic_brain import DataScope
        assert DataScope is not None
        # Check enum members exist
        assert hasattr(DataScope, "PUBLIC")
        assert hasattr(DataScope, "PRIVATE")
        assert hasattr(DataScope, "CUSTOMER")
    
    def test_llm_router_import(self):
        """Test LLMRouter class is importable."""
        from agentic_brain import LLMRouter
        assert LLMRouter is not None
        assert callable(LLMRouter)
    
    def test_all_exports(self):
        """Test __all__ exports are actually available."""
        import agentic_brain
        
        for name in agentic_brain.__all__:
            assert hasattr(agentic_brain, name), f"{name} not found in module"
    
    def test_agent_submodule_imports(self):
        """Test agent submodule imports."""
        from agentic_brain.agent import Agent, AgentConfig
        assert Agent is not None
        assert AgentConfig is not None
    
    def test_memory_submodule_imports(self):
        """Test memory submodule imports."""
        from agentic_brain.memory import (
            Neo4jMemory,
            InMemoryStore,
            DataScope,
            Memory,
        )
        assert Neo4jMemory is not None
        assert InMemoryStore is not None
        assert DataScope is not None
        assert Memory is not None
    
    def test_router_submodule_imports(self):
        """Test router submodule imports."""
        from agentic_brain.router import LLMRouter, RouterConfig, Provider
        assert LLMRouter is not None
        assert RouterConfig is not None
        assert Provider is not None


class TestNoCircularImports:
    """Test that there are no problematic circular imports."""
    
    def test_direct_imports_no_error(self):
        """Test that direct imports don't cause circular import errors."""
        # These should not raise ImportError or CircularImportError
        try:
            import agentic_brain
            from agentic_brain import Agent
            from agentic_brain import Neo4jMemory
            from agentic_brain import LLMRouter
        except ImportError as e:
            pytest.fail(f"Import error: {e}")
    
    def test_submodule_imports_no_error(self):
        """Test that submodule imports don't cause errors."""
        try:
            import agentic_brain.agent
            import agentic_brain.memory
            import agentic_brain.router
        except ImportError as e:
            pytest.fail(f"Import error: {e}")
    
    def test_reimport_stability(self):
        """Test that reimporting modules is stable."""
        # Import once
        import agentic_brain
        version1 = agentic_brain.__version__
        
        # Reimport
        import importlib
        importlib.reload(agentic_brain)
        version2 = agentic_brain.__version__
        
        # Should be the same
        assert version1 == version2


class TestMetadata:
    """Test package metadata."""
    
    def test_author_metadata(self):
        """Test author metadata is set."""
        import agentic_brain
        assert hasattr(agentic_brain, "__author__")
        assert agentic_brain.__author__ == "Joseph Webber"
    
    def test_email_metadata(self):
        """Test email metadata is set."""
        import agentic_brain
        assert hasattr(agentic_brain, "__email__")
        assert isinstance(agentic_brain.__email__, str)
    
    def test_license_metadata(self):
        """Test license metadata is set."""
        import agentic_brain
        assert hasattr(agentic_brain, "__license__")
        assert isinstance(agentic_brain.__license__, str)


class TestModuleAttributes:
    """Test that modules have expected attributes."""
    
    def test_agent_module_has_agent_class(self):
        """Test agent module exports Agent class."""
        import agentic_brain.agent
        assert hasattr(agentic_brain.agent, "Agent")
        assert hasattr(agentic_brain.agent, "AgentConfig")
    
    def test_memory_module_has_required_classes(self):
        """Test memory module exports required classes."""
        import agentic_brain.memory
        assert hasattr(agentic_brain.memory, "Neo4jMemory")
        assert hasattr(agentic_brain.memory, "InMemoryStore")
        assert hasattr(agentic_brain.memory, "DataScope")
        assert hasattr(agentic_brain.memory, "Memory")
    
    def test_router_module_has_required_classes(self):
        """Test router module exports required classes."""
        import agentic_brain.router
        assert hasattr(agentic_brain.router, "LLMRouter")
        assert hasattr(agentic_brain.router, "RouterConfig")
        assert hasattr(agentic_brain.router, "Provider")


class TestImportPerformance:
    """Test that imports are reasonably fast."""
    
    def test_import_timing(self):
        """Test that initial import completes quickly."""
        import time
        
        start = time.time()
        import agentic_brain
        elapsed = time.time() - start
        
        # Should complete in under 1 second
        assert elapsed < 1.0, f"Import took {elapsed}s, expected < 1.0s"
    
    def test_submodule_import_timing(self):
        """Test that submodule imports are quick."""
        import time
        
        start = time.time()
        from agentic_brain import Agent, Neo4jMemory, LLMRouter
        elapsed = time.time() - start
        
        # Should complete quickly
        assert elapsed < 1.0, f"Import took {elapsed}s, expected < 1.0s"
