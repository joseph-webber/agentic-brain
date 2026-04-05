# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
API Examples - Quick Start Guide

This file demonstrates the new ergonomic API improvements:
1. Shortcuts - one-liner convenience functions
2. Fluent Builder - chainable configuration
"""

from agentic_brain.api import (
    AgenticBrain,
    quick_eval,
    quick_graph,
    quick_rag,
    quick_search,
)


def example_shortcuts():
    """Demonstrate quick-start shortcuts."""
    print("\n" + "=" * 60)
    print("SHORTCUTS - Dead Simple One-Liners")
    print("=" * 60)

    # RAG - one-liner Q&A
    print("\n1. RAG Query (question + documents):")
    print("   result = quick_rag('How do I deploy?', docs=['deployment.md'])")
    print("   print(result.answer)")

    # Search - unified interface
    print("\n2. Unified Search (across all sources):")
    print("   results = quick_search('neural networks', num_results=10)")
    print("   for r in results:")
    print('       print(f\'{r["source"]}: {r["content"][:100]}\')')

    # Graph - instant knowledge graph
    print("\n3. Knowledge Graph (instant creation):")
    print("   graph = quick_graph(")
    print("       entities=['User', 'Project', 'Task'],")
    print("       relationships=[")
    print("           ('User', 'owns', 'Project'),")
    print("           ('Project', 'contains', 'Task'),")
    print("       ]")
    print("   )")

    # Evaluate - fast metrics on results
    print("\n4. Evaluation (quality metrics):")
    print("   results = [quick_rag('Q1'), quick_rag('Q2')]")
    print("   metrics = quick_eval(results)")
    print('   print(f\'Avg confidence: {metrics["generation"]["avg_confidence"]}\')')


def example_fluent_builder():
    """Demonstrate fluent builder pattern."""
    print("\n" + "=" * 60)
    print("FLUENT BUILDER - Readable Method Chaining")
    print("=" * 60)

    print("\n1. Basic Setup (LLM only):")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm_openai('gpt-4')")
    print("   )")
    print("   result = brain.query('What is 2 + 2?')")

    print("\n2. With Graph and RAG:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm_groq()                    # Fast free provider")
    print("       .with_graph()                        # Enable knowledge graph")
    print("       .with_rag(cache_ttl_hours=24)      # Enable RAG with caching")
    print("   )")

    print("\n3. Load and Query:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm_openai()")
    print("       .with_rag()")
    print("       .ingest_documents(['docs/', 'wiki/'])")
    print("   )")
    print("   result = brain.query('How to deploy?')")

    print("\n4. Add Entities and Relationships:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_graph()")
    print("       .add_entities(['User', 'Project', 'Task'])")
    print("       .add_relationships([")
    print("           ('User', 'manages', 'Project'),")
    print("           ('Project', 'has', 'Task'),")
    print("       ])")
    print("   )")

    print("\n5. Query History and Evaluation:")
    print("   brain = AgenticBrain().with_llm_openai().with_rag()")
    print("   ")
    print("   # Run multiple queries")
    print("   result1 = brain.query('Q1')")
    print("   result2 = brain.query('Q2')")
    print("   ")
    print("   # Check history")
    print("   history = brain.get_query_history(limit=10)")
    print("   ")
    print("   # Evaluate")
    print("   metrics = brain.evaluate_recent_queries()")
    print("   print(f'Avg confidence: {metrics[\"avg_confidence\"]}')")

    print("\n6. Show Configuration:")
    print("   print(brain.describe())")
    print("   print(repr(brain))")


def example_provider_shortcuts():
    """Demonstrate LLM provider shortcuts."""
    print("\n" + "=" * 60)
    print("LLM PROVIDER SHORTCUTS")
    print("=" * 60)

    print("\n   # Local (free, fast)")
    print("   brain = AgenticBrain().with_llm_ollama()")
    print("")
    print("   # Cloud (fast, free tier)")
    print("   brain = AgenticBrain().with_llm_groq()")
    print("")
    print("   # Best quality")
    print("   brain = AgenticBrain().with_llm_openai('gpt-4')")
    print("")
    print("   # Alternative providers")
    print("   brain = AgenticBrain().with_llm_anthropic()")


def example_advanced_workflows():
    """Demonstrate advanced multi-step workflows."""
    print("\n" + "=" * 60)
    print("ADVANCED WORKFLOWS")
    print("=" * 60)

    print("\n1. Research Pipeline:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm_openai()")
    print("       .with_graph()")
    print("       .with_rag()")
    print("   )")
    print("   ")
    print("   # Ingest research papers")
    print("   brain.ingest_folder('research_papers', recursive=True)")
    print("   ")
    print("   # Query with graph context")
    print("   result = brain.query('Summarize findings on AI safety')")
    print("   ")
    print("   # Evaluate result quality")
    print("   metrics = brain.evaluate_recent_queries()")

    print("\n2. Knowledge Base with Evaluation:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm_groq()           # Cost-effective")
    print("       .with_rag(cache_ttl_hours=8)")
    print("   )")
    print("   ")
    print("   # Golden answers for evaluation")
    print("   golden_answers = [")
    print("       'Answer to question 1',")
    print("       'Answer to question 2',")
    print("   ]")
    print("   ")
    print("   queries = ['Question 1', 'Question 2']")
    print("   results = [brain.query(q) for q in queries]")
    print("   ")
    print("   metrics = quick_eval(results, golden_answers=golden_answers)")
    print(
        '   print(f\'Accuracy: {metrics["generation"]["avg_similarity_to_golden"]}\')'
    )


def example_error_handling():
    """Demonstrate error handling."""
    print("\n" + "=" * 60)
    print("ERROR HANDLING")
    print("=" * 60)

    print("\n1. Graceful Failures:")
    print("   # All shortcuts handle errors gracefully")
    print("   result = quick_rag('question')  # Returns error in result.answer")
    print("   if result.confidence == 0.0:")
    print("       print('Query failed, but didn\\'t crash')")

    print("\n2. Configuration Fallbacks:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_llm('nonexistent')  # Falls back to defaults")
    print("       .with_graph()              # Skips if Neo4j unavailable")
    print("       .with_rag()                # Works without graph")
    print("   )")

    print("\n3. Document Ingestion:")
    print("   # Failures in one document don't stop others")
    print("   brain.ingest_documents([")
    print("       'good.md',      # Succeeds")
    print("       'broken.txt',   # Fails silently")
    print("       'good2.md',     # Succeeds")
    print("   ])")


def example_chaining_rules():
    """Document chaining rules."""
    print("\n" + "=" * 60)
    print("CHAINING RULES")
    print("=" * 60)

    print("\n1. Method chaining always returns self:")
    print("   brain = AgenticBrain()")
    print("   result_type = type(brain.with_llm('ollama'))")
    print("   assert result_type is AgenticBrain  # ✓")

    print("\n2. Order doesn't matter (mostly):")
    print("   brain1 = AgenticBrain().with_llm().with_graph().with_rag()")
    print("   brain2 = AgenticBrain().with_rag().with_llm().with_graph()")
    print("   # Both work, but RAG needs LLM config internally")

    print("\n3. Enable/disable modules independently:")
    print("   brain = (")
    print("       AgenticBrain()")
    print("       .with_graph()")
    print("       .with_rag()")
    print("       .without_graph()  # Remove graph, keep RAG")
    print("   )")


if __name__ == "__main__":
    example_shortcuts()
    example_fluent_builder()
    example_provider_shortcuts()
    example_advanced_workflows()
    example_error_handling()
    example_chaining_rules()

    print("\n" + "=" * 60)
    print("QUICK REFERENCE")
    print("=" * 60)
    print(
        """
SHORTCUTS (agentic_brain.api):
  • quick_rag()     - RAG query with documents
  • quick_graph()   - Knowledge graph creation
  • quick_search()  - Unified search interface
  • quick_eval()    - Fast evaluation metrics

FLUENT BUILDER (agentic_brain.api.AgenticBrain):
  • .with_llm()           - Configure LLM
  • .with_llm_openai()    - Quick OpenAI setup
  • .with_llm_groq()      - Quick Groq setup
  • .with_llm_ollama()    - Quick Ollama setup
  • .with_graph()         - Enable Neo4j graph
  • .with_rag()           - Enable RAG pipeline
  • .ingest_documents()   - Load files/URLs
  • .add_entities()       - Add graph entities
  • .add_relationships()  - Add graph links
  • .query()              - Execute query
  • .search()             - Execute search
  • .get_query_history()  - Retrieve recent queries
  • .evaluate_recent_queries() - Quality metrics
  • .describe()           - Show configuration

DESIGN PRINCIPLES:
  ✓ Chainable - every method returns self
  ✓ Graceful - errors return results, don't crash
  ✓ Lazy - components init on first use
  ✓ Explicit - clear method names
  ✓ Composable - mix and match components
    """
    )
