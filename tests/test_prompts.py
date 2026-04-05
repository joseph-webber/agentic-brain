from __future__ import annotations

from pathlib import Path

import pytest

from agentic_brain.prompts import (
    FewShotCollection,
    FewShotExample,
    PromptChain,
    PromptChainStep,
    PromptLibrary,
    PromptOptimizer,
    PromptTemplate,
    get_default_prompt_library,
    get_rag_prompts,
)
from agentic_brain.prompts.template import PromptValidationError


def test_template_renders_simple_variable():
    template = PromptTemplate.from_string("hello", "Hello {{ name }}!")
    assert template.render(name="Joseph") == "Hello Joseph!"


def test_template_uses_default_variables():
    template = PromptTemplate.from_string(
        "default",
        "Hello {{ name }} from {{ city }}!",
        variables={"city": "Adelaide"},
    )
    assert template.render(name="Joseph") == "Hello Joseph from Adelaide!"


def test_template_renders_conditionals():
    template = PromptTemplate.from_string(
        "conditional",
        "{% if urgent %}URGENT{% else %}normal{% endif %}",
    )
    assert template.render(urgent=True) == "URGENT"


def test_template_renders_loops():
    template = PromptTemplate.from_string(
        "loop",
        "{% for item in items %}{{ item }}{% if not loop.last %}, {% endif %}{% endfor %}",
    )
    assert template.render(items=["a", "b", "c"]) == "a, b, c"


def test_template_validate_returns_no_errors_when_valid():
    template = PromptTemplate.from_string("valid", "Hi {{ name }}")
    assert template.validate({"name": "Joseph"}) == []


def test_template_validate_reports_missing_variables():
    template = PromptTemplate.from_string("missing", "Hi {{ name }} and {{ city }}")
    errors = template.validate({"name": "Joseph"})
    assert "Missing variables: city" in errors[0]


def test_template_validate_reports_empty_name():
    template = PromptTemplate.from_string("", "Hi {{ name }}")
    errors = template.validate({"name": "Joseph"})
    assert "Template name cannot be empty." in errors


def test_template_validate_reports_empty_template():
    template = PromptTemplate.from_string("empty", "")
    errors = template.validate()
    assert "Template text cannot be empty." in errors


def test_template_bind_adds_defaults():
    template = PromptTemplate.from_string("bind", "Hello {{ name }} from {{ city }}")
    bound = template.bind(city="Adelaide")
    assert bound.render(name="Joseph") == "Hello Joseph from Adelaide"


def test_template_bind_keeps_original_unchanged():
    template = PromptTemplate.from_string("bind", "Hello {{ name }} from {{ city }}")
    bound = template.bind(city="Adelaide")
    assert template.validate({"name": "Joseph"})[0].startswith("Missing variables")
    assert bound.render(name="Joseph") == "Hello Joseph from Adelaide"


def test_template_from_file(tmp_path: Path):
    file_path = tmp_path / "example.txt"
    file_path.write_text("Hello {{ name }}")
    template = PromptTemplate.from_file(file_path)
    assert template.name == "example"
    assert template.render(name="Joseph") == "Hello Joseph"


def test_template_to_dict_roundtrip():
    template = PromptTemplate.from_string(
        "roundtrip",
        "Hello {{ name }}",
        description="desc",
        variables={"name": "Joseph"},
        tags=("a", "b"),
    )
    restored = PromptTemplate.from_dict(template.to_dict())
    assert restored.render() == "Hello Joseph"
    assert restored.tags == ("a", "b")


def test_template_assert_valid_raises_for_missing_variable():
    template = PromptTemplate.from_string("missing", "Hi {{ name }}")
    with pytest.raises(PromptValidationError):
        template.assert_valid()


def test_template_assert_valid_raises_for_bad_syntax():
    template = PromptTemplate.from_string("bad", "{% if name %}")
    with pytest.raises(PromptValidationError):
        template.assert_valid({"name": "Joseph"})


def test_template_required_variables_exclude_defaults():
    template = PromptTemplate.from_string(
        "required",
        "Hello {{ name }} from {{ city }}",
        variables={"city": "Adelaide"},
    )
    assert template.required_variables == ("name",)


def test_template_render_errors_on_missing_variable():
    template = PromptTemplate.from_string("missing", "Hi {{ name }}")
    with pytest.raises(PromptValidationError):
        template.render()


def test_few_shot_example_format_basic():
    example = FewShotExample("What is GraphRAG?", "A graph-based RAG approach.")
    assert "Input: What is GraphRAG?" in example.format()
    assert "Output: A graph-based RAG approach." in example.format()


def test_few_shot_example_format_includes_reasoning():
    example = FewShotExample(
        "What is GraphRAG?",
        "A graph-based RAG approach.",
        explanation="Use connected knowledge.",
    )
    assert "Reasoning: Use connected knowledge." in example.format()


def test_few_shot_to_from_dict_roundtrip():
    example = FewShotExample("A", "B", explanation="C", metadata={"k": "v"})
    restored = FewShotExample.from_dict(example.to_dict())
    assert restored == example


def test_few_shot_collection_render_basic():
    collection = FewShotCollection(
        [FewShotExample("A", "B"), FewShotExample("C", "D")],
        title="Examples",
    )
    rendered = collection.render()
    assert "## Examples" in rendered
    assert "### Example 1" in rendered
    assert "Input: A" in rendered


def test_few_shot_collection_render_can_hide_title():
    collection = FewShotCollection([FewShotExample("A", "B")])
    assert "## Few-shot examples" not in collection.render(include_title=False)


def test_few_shot_collection_render_can_hide_explanations():
    collection = FewShotCollection(
        [FewShotExample("A", "B", explanation="secret")],
    )
    rendered = collection.render(include_explanations=False)
    assert "Reasoning:" not in rendered


def test_few_shot_collection_add_increases_length():
    collection = FewShotCollection()
    collection.add(FewShotExample("A", "B"))
    assert len(collection.examples) == 1


def test_few_shot_collection_extend_adds_examples():
    collection = FewShotCollection()
    collection.extend([FewShotExample("A", "B"), FewShotExample("C", "D")])
    assert len(collection.examples) == 2


def test_few_shot_collection_from_pairs():
    collection = FewShotCollection.from_pairs([("A", "B"), ("C", "D")])
    assert len(collection.examples) == 2
    assert collection.examples[0].input_text == "A"


def test_few_shot_collection_to_from_dict_roundtrip():
    collection = FewShotCollection(
        [FewShotExample("A", "B", explanation="C")],
        title="Custom",
    )
    restored = FewShotCollection.from_dict(collection.to_dict())
    assert restored.title == "Custom"
    assert restored.examples[0].explanation == "C"


def test_optimizer_strips_trailing_whitespace():
    optimizer = PromptOptimizer()
    result = optimizer.optimize("hello  \nworld   ")
    assert result.optimized == "hello\nworld"
    assert "stripped trailing whitespace" in result.changes


def test_optimizer_removes_duplicate_lines():
    optimizer = PromptOptimizer()
    result = optimizer.optimize("a\na\nb")
    assert result.optimized == "a\nb"


def test_optimizer_collapses_blank_lines():
    optimizer = PromptOptimizer()
    result = optimizer.optimize("a\n\n\nb")
    assert result.optimized == "a\n\nb"


def test_optimizer_truncates_long_prompt():
    optimizer = PromptOptimizer(max_length=20)
    result = optimizer.optimize("abcdefghijklmnopqrstuvwxyz")
    assert len(result.optimized) <= 20
    assert "..." in result.optimized


def test_optimizer_optimize_template_returns_new_template():
    template = PromptTemplate.from_string("opt", "Hello   \n\nworld")
    optimized = PromptOptimizer().optimize_template(template)
    assert optimized.template == "Hello\n\nworld"
    assert optimized.name == "opt"


def test_optimizer_result_properties():
    result = PromptOptimizer().optimize("hello")
    assert result.original_length == 5
    assert result.optimized_length == 5
    assert result.savings == 0


def test_library_contains_built_in_prompts():
    library = get_default_prompt_library()
    names = library.names()
    assert "rag.answer" in names
    assert "rag.rewrite_query" in names


def test_library_get_returns_template():
    library = get_default_prompt_library()
    template = library.get("rag.answer")
    assert template is not None
    assert template.name == "rag.answer"


def test_library_render_answer_prompt():
    library = get_default_prompt_library()
    rendered = library.render(
        "rag.answer",
        question="What is GraphRAG?",
        context="GraphRAG combines graphs and retrieval.",
        citations="[1]",
    )
    assert "What is GraphRAG?" in rendered
    assert "GraphRAG combines graphs and retrieval." in rendered


def test_library_render_rewrite_prompt():
    rendered = get_default_prompt_library().render(
        "rag.rewrite_query",
        question="Tell me everything about sales.",
    )
    assert "Tell me everything about sales." in rendered


def test_library_render_summary_prompt():
    rendered = get_default_prompt_library().render(
        "rag.summarize_context",
        context="A short context",
    )
    assert "A short context" in rendered


def test_library_render_rank_prompt():
    rendered = get_default_prompt_library().render(
        "rag.rank_context",
        question="What matters?",
        passages="1. A\n2. B",
    )
    assert "What matters?" in rendered


def test_library_render_cite_prompt():
    rendered = get_default_prompt_library().render(
        "rag.cite_sources",
        notes="Notes",
        sources="[1]",
    )
    assert "Notes" in rendered
    assert "[1]" in rendered


def test_library_register_custom_prompt():
    library = PromptLibrary()
    library.register(PromptTemplate.from_string("custom", "Hi {{ name }}"))
    assert library.render("custom", name="Joseph") == "Hi Joseph"


def test_library_optimize_prompt():
    library = get_default_prompt_library()
    optimized = library.optimize("rag.answer", PromptOptimizer(max_length=1200))
    assert optimized.name == "rag.answer"


def test_get_rag_prompts_returns_copy():
    prompts = get_rag_prompts()
    prompts["x"] = PromptTemplate.from_string("x", "x")
    assert "x" not in get_rag_prompts()


def test_library_default_examples_are_in_answer_prompt():
    rendered = get_default_prompt_library().render(
        "rag.answer",
        question="Q",
        context="C",
    )
    assert "Reference examples:" in rendered


def test_chain_single_step():
    chain = PromptChain(
        [
            PromptChainStep(
                "first", PromptTemplate.from_string("first", "Hello {{ name }}")
            )
        ]
    )
    assert chain.render({"name": "Joseph"}) == "Hello Joseph"


def test_chain_two_steps_passes_output_forward():
    chain = PromptChain(
        [
            PromptChainStep(
                "rewrite",
                PromptTemplate.from_string("rewrite", "Rewrite {{ question }}"),
            ),
            PromptChainStep(
                "answer",
                PromptTemplate.from_string("answer", "Answer using {{ rewrite }}"),
            ),
        ]
    )
    result = chain.run({"question": "What is GraphRAG?"})
    assert result.step_outputs["rewrite"] == "Rewrite What is GraphRAG?"
    assert result.final_output == "Answer using Rewrite What is GraphRAG?"


def test_chain_context_accumulates_outputs():
    chain = PromptChain(
        [
            PromptChainStep("one", PromptTemplate.from_string("one", "1")),
            PromptChainStep("two", PromptTemplate.from_string("two", "{{ one }}2")),
        ]
    )
    result = chain.run({})
    assert result.context["one"] == "1"
    assert result.context["two"] == "12"


def test_chain_with_transform_updates_context():
    chain = PromptChain(
        [
            PromptChainStep(
                "base",
                PromptTemplate.from_string("base", "{{ word }}"),
                transform=lambda output, context: {"upper": output.upper()},
            ),
            PromptChainStep(
                "follow",
                PromptTemplate.from_string("follow", "{{ upper }}"),
            ),
        ]
    )
    assert chain.render({"word": "hello"}) == "HELLO"


def test_chain_add_step_returns_self():
    chain = PromptChain()
    returned = chain.add_step(
        PromptChainStep("first", PromptTemplate.from_string("first", "hello"))
    )
    assert returned is chain


def test_chain_extend_returns_self():
    chain = PromptChain()
    returned = chain.extend(
        [PromptChainStep("first", PromptTemplate.from_string("first", "hello"))]
    )
    assert returned is chain


def test_chain_len_reports_steps():
    chain = PromptChain(
        [PromptChainStep("first", PromptTemplate.from_string("first", "hello"))]
    )
    assert len(chain) == 1


def test_chain_result_exposes_named_outputs():
    chain = PromptChain(
        [PromptChainStep("first", PromptTemplate.from_string("first", "hello"))]
    )
    result = chain.run({})
    assert result.step_outputs == {"first": "hello"}


def test_chain_step_output_key_overrides_default():
    chain = PromptChain(
        [
            PromptChainStep(
                "first",
                PromptTemplate.from_string("first", "{{ name }}"),
                output_key="shared",
            ),
            PromptChainStep(
                "second",
                PromptTemplate.from_string("second", "{{ shared }}!"),
            ),
        ]
    )
    assert chain.render({"name": "Joseph"}) == "Joseph!"


def test_chain_can_use_binded_template_defaults():
    chain = PromptChain(
        [
            PromptChainStep(
                "first",
                PromptTemplate.from_string("first", "{{ greeting }} {{ name }}").bind(
                    greeting="Hello"
                ),
            )
        ]
    )
    assert chain.render({"name": "Joseph"}) == "Hello Joseph"
