# Prompt Templates

Agentic Brain includes a small prompt management stack:

- `PromptTemplate` for Jinja2 templates, default variables, and validation
- `PromptLibrary` for reusable prompt registries
- `FewShotCollection` for example blocks
- `PromptOptimizer` for whitespace trimming and size reduction
- `PromptChain` for sequential prompt workflows

## Quick start

```python
from agentic_brain.prompts import PromptTemplate

template = PromptTemplate.from_string(
    "greeting",
    "Hello {{ name }}!",
)

print(template.render(name="Joseph"))
```

## Built-in RAG prompts

```python
from agentic_brain.prompts import get_default_prompt_library

library = get_default_prompt_library()
print(library.render("rag.answer", question="What is GraphRAG?", context="..."))
```

Available built-ins:

- `rag.answer`
- `rag.rewrite_query`
- `rag.summarize_context`
- `rag.rank_context`
- `rag.cite_sources`

## Validation

`PromptTemplate.validate()` checks:

- empty names
- empty templates
- Jinja2 syntax errors
- missing required variables

## Few-shot examples

Use `FewShotCollection.render()` to embed examples inside a prompt:

```python
from agentic_brain.prompts import FewShotCollection, FewShotExample

examples = FewShotCollection([
    FewShotExample("Input", "Output")
])

print(examples.render())
```

## Prompt chaining

```python
from agentic_brain.prompts import PromptChain, PromptChainStep, PromptTemplate

chain = PromptChain([
    PromptChainStep("rewrite", PromptTemplate.from_string("rewrite", "Rewrite: {{ question }}")),
    PromptChainStep("answer", PromptTemplate.from_string("answer", "Answer with {{ rewrite }}")),
])
result = chain.run({"question": "What is GraphRAG?"})
```

## Optimization

`PromptOptimizer` can trim prompt bloat by:

- stripping trailing whitespace
- removing consecutive duplicate lines
- collapsing blank lines
- truncating long prompts when requested
