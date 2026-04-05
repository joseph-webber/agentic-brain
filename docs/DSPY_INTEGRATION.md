# DSPy Integration

Agentic Brain includes a lightweight DSPy compatibility layer in `agentic_brain.rag.dspy_compat` so you can build structured RAG pipelines without depending on the full DSPy runtime.

## Highlights

- **Signature classes**: `InputField` and `OutputField` for structured I/O
- **Module base**: `Module` with `forward()` and composable submodules
- **Retrieve module**: DSPy-style retriever wrapping GraphRAG or any compatible retriever
- **ChainOfThought**: step-by-step reasoning module
- **ReAct**: reasoning + acting with tool invocation

## Quick Start

```python
from agentic_brain.rag.dspy_compat import (
    Module,
    Signature,
    InputField,
    OutputField,
    Retrieve,
    ChainOfThought,
    configure,
    MockLLM,
)

class QASignature(Signature):
    """Answer questions based on context."""
    context = InputField(desc="Retrieved context")
    question = InputField(desc="User question")
    answer = OutputField(desc="Final answer")

class RAGModule(Module):
    def __init__(self, retriever):
        super().__init__()
        self.retrieve = Retrieve(retriever=retriever, k=5)
        self.generate = ChainOfThought(QASignature)

    def forward(self, question: str):
        passages = self.retrieve(question).passages
        return self.generate(context=passages, question=question)

configure(lm=MockLLM({"Answer:": "Reasoning: ok\nAnswer: example"}))
result = RAGModule(retriever=None)("What is GraphRAG?")
print(result.answer)
```

## Signatures

```python
class Summarize(Signature):
    """Summarize text."""
    text = InputField(desc="Content")
    summary = OutputField(desc="Summary")
```

- `InputField(required=False, default="...")` supports optional fields with defaults.
- Use `format="list"` or `format="json"` for prompt rendering and parsing.

## Retrieve Module

`Retrieve` accepts any of the following retriever shapes:

- `GraphRAG` with async `search()`
- A retriever with `.search()` or `.retrieve()` methods
- A `RAGPipeline` with `.query()`
- A callable returning a list of strings, dicts, or objects with `content`

```python
from agentic_brain.rag import GraphRAG
from agentic_brain.rag.dspy_compat import Retrieve

retriever = GraphRAG()
retrieve = Retrieve(retriever=retriever, k=5, strategy="hybrid")
result = retrieve("What causes X?")
print(result.passages)
```

## ChainOfThought

```python
cot = ChainOfThought(QASignature)
result = cot(context="...", question="What is X?")
print(result.reasoning)
print(result.answer)
```

## ReAct

```python
def search_tool(query: str) -> str:
    return "Search result"

react = ReAct(QASignature, tools={"Search": search_tool}, max_steps=4)
result = react(question="Who invented Python?")
print(result.answer)
```

## Evaluation

```python
from agentic_brain.rag.dspy_compat import Evaluate, exact_match

dataset = [
    {"inputs": {"question": "2+2"}, "expected": {"answer": "4"}},
]

results = Evaluate(devset=dataset, metric=exact_match)(rag_module)
print(results.accuracy)
```

## Notes

- The compatibility layer mirrors DSPy APIs but does not require DSPy itself.
- If native DSPy is installed (`pip install dspy-ai`), you can build bridges with
  `to_native_dspy()` and `from_native_dspy()`.
