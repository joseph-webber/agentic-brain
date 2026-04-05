# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
DSPy Compatibility Layer for Agentic Brain GraphRAG.

Stanford's DSPy enables programmatic prompt optimization through
declarative module composition. This layer provides:

- Signature classes for structured I/O (InputField, OutputField)
- Module base class with forward() method
- Retrieve module wrapping GraphRAG
- ChainOfThought reasoning module
- ReAct (Reasoning + Acting) module
- Teleprompter stubs for future optimization (BootstrapFewShot, COPRO)
- Evaluation framework for testing modules against datasets

Usage:
    from agentic_brain.rag.dspy_compat import (
        Module, Signature, InputField, OutputField,
        Retrieve, ChainOfThought, ReAct,
        Evaluate,
    )

    # Define a QA signature
    class QASignature(Signature):
        '''Answer questions based on context.'''
        context = InputField(desc="Retrieved context")
        question = InputField(desc="User question")
        answer = OutputField(desc="Generated answer")

    # Build a RAG pipeline
    class RAGModule(Module):
        def __init__(self, retriever):
            super().__init__()
            self.retrieve = Retrieve(retriever=retriever, k=5)
            self.generate = ChainOfThought(QASignature)

        def forward(self, question: str):
            context = self.retrieve(question).passages
            return self.generate(context=context, question=question)

    # Evaluate
    evaluator = Evaluate(devset=my_dataset, metric=exact_match)
    score = evaluator(rag_module)

DSPy Reference: https://github.com/stanfordnlp/dspy
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

# Check for native DSPy availability
try:
    import dspy as native_dspy

    DSPY_NATIVE_AVAILABLE = True
except ImportError:
    DSPY_NATIVE_AVAILABLE = False
    native_dspy = None

if TYPE_CHECKING:
    from .graph_rag import GraphRAG
    from .pipeline import RAGPipeline
    from .retriever import Retriever


# ============================================================================
# Field Descriptors (DSPy-compatible)
# ============================================================================


@dataclass
class FieldInfo:
    """Metadata for a signature field."""

    name: str
    desc: str = ""
    prefix: str = ""
    format: Optional[str] = None
    required: bool = True
    default: Any = None

    def __post_init__(self):
        if not self.prefix:
            self.prefix = f"{self.name.replace('_', ' ').title()}:"


class InputField:
    """
    DSPy-compatible input field descriptor.

    Marks a field as an input to a signature. Used in Signature class
    definitions to declare expected inputs.

    Args:
        desc: Human-readable description of the field
        prefix: Custom prefix for prompt formatting (default: field name)
        format: Optional format specification (json, list, etc.)

    Example:
        class QA(Signature):
            question = InputField(desc="The user's question")
            context = InputField(desc="Retrieved passages", format="list")
    """

    def __init__(
        self,
        desc: str = "",
        prefix: str = "",
        format: Optional[str] = None,
        required: bool = True,
        default: Any = None,
    ):
        self.desc = desc
        self.prefix = prefix
        self.format = format
        self.required = required
        self.default = default
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def to_field_info(self) -> FieldInfo:
        """Convert to FieldInfo dataclass."""
        return FieldInfo(
            name=self._name,
            desc=self.desc,
            prefix=self.prefix or f"{self._name.replace('_', ' ').title()}:",
            format=self.format,
            required=self.required,
            default=self.default,
        )


class OutputField:
    """
    DSPy-compatible output field descriptor.

    Marks a field as an output from a signature. Used in Signature class
    definitions to declare expected outputs.

    Args:
        desc: Human-readable description of the field
        prefix: Custom prefix for prompt formatting
        format: Optional format specification (json, list, etc.)

    Example:
        class QA(Signature):
            answer = OutputField(desc="The answer to the question")
            confidence = OutputField(desc="Confidence score 0-1", format="float")
    """

    def __init__(
        self,
        desc: str = "",
        prefix: str = "",
        format: Optional[str] = None,
    ):
        self.desc = desc
        self.prefix = prefix
        self.format = format
        self._name: str = ""

    def __set_name__(self, owner: type, name: str) -> None:
        self._name = name

    def to_field_info(self) -> FieldInfo:
        """Convert to FieldInfo dataclass."""
        return FieldInfo(
            name=self._name,
            desc=self.desc,
            prefix=self.prefix or f"{self._name.replace('_', ' ').title()}:",
            format=self.format,
            required=True,
        )


# ============================================================================
# Signature Base Class
# ============================================================================


class SignatureMeta(type):
    """Metaclass for Signature that collects input/output fields."""

    def __new__(
        mcs, name: str, bases: tuple, namespace: dict, **kwargs: Any
    ) -> "SignatureMeta":
        cls = super().__new__(mcs, name, bases, namespace)

        # Collect fields from class and bases
        input_fields: Dict[str, FieldInfo] = {}
        output_fields: Dict[str, FieldInfo] = {}

        for base in reversed(bases):
            if hasattr(base, "_input_fields"):
                input_fields.update(base._input_fields)
            if hasattr(base, "_output_fields"):
                output_fields.update(base._output_fields)

        for key, value in namespace.items():
            if isinstance(value, InputField):
                value._name = key
                input_fields[key] = value.to_field_info()
            elif isinstance(value, OutputField):
                value._name = key
                output_fields[key] = value.to_field_info()

        cls._input_fields = input_fields
        cls._output_fields = output_fields

        return cls


class Signature(metaclass=SignatureMeta):
    """
    DSPy-compatible Signature base class.

    Signatures define the input/output schema for DSPy modules.
    Use class attributes with InputField/OutputField to declare fields.

    The docstring becomes the task instruction.

    Example:
        class Summarize(Signature):
            '''Summarize the given text concisely.'''
            text = InputField(desc="Text to summarize")
            summary = OutputField(desc="Concise summary")

        class QAWithReasoning(Signature):
            '''Answer questions with step-by-step reasoning.'''
            context = InputField(desc="Retrieved passages")
            question = InputField(desc="User question")
            reasoning = OutputField(desc="Step-by-step reasoning")
            answer = OutputField(desc="Final answer")
    """

    _input_fields: Dict[str, FieldInfo] = {}
    _output_fields: Dict[str, FieldInfo] = {}

    def __init__(self, **kwargs: Any):
        """Initialize signature with field values."""
        self._values: Dict[str, Any] = {}
        for name, info in self._input_fields.items():
            if info.default is not None:
                self._values[name] = info.default
        for name, info in self._output_fields.items():
            if info.default is not None:
                self._values[name] = info.default
        for key, value in kwargs.items():
            if key in self._input_fields or key in self._output_fields:
                self._values[key] = value
            else:
                raise ValueError(f"Unknown field: {key}")
        missing = [
            name
            for name, info in self._input_fields.items()
            if info.required and name not in self._values
        ]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        values = super().__getattribute__("_values")
        if name in values:
            return values[name]
        input_fields = super().__getattribute__("_input_fields")
        output_fields = super().__getattribute__("_output_fields")
        if name in input_fields or name in output_fields:
            return values.get(name)
        return super().__getattribute__(name)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        raise AttributeError(f"Field '{name}' not set")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        elif name in self._input_fields or name in self._output_fields:
            self._values[name] = value
        else:
            super().__setattr__(name, value)

    @classmethod
    def instructions(cls) -> str:
        """Get task instructions from docstring."""
        return inspect.getdoc(cls) or ""

    @classmethod
    def input_fields(cls) -> Dict[str, FieldInfo]:
        """Get all input fields."""
        return cls._input_fields.copy()

    @classmethod
    def output_fields(cls) -> Dict[str, FieldInfo]:
        """Get all output fields."""
        return cls._output_fields.copy()

    @classmethod
    def all_fields(cls) -> Dict[str, FieldInfo]:
        """Get all fields (input + output)."""
        return {**cls._input_fields, **cls._output_fields}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self._values.copy()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signature":
        """Create signature instance from dictionary."""
        return cls(**data)

    def format_prompt(self) -> str:
        """Format as prompt string."""
        lines = [self.instructions(), ""]

        for name, info in self._input_fields.items():
            if name in self._values:
                value = self._values[name]
                if value is None:
                    continue
                if info.format == "list" and isinstance(value, list):
                    value = "\n".join(f"- {v}" for v in value)
                elif info.format == "json":
                    value = json.dumps(value, indent=2)
                lines.append(f"{info.prefix} {value}")

        lines.append("")
        for name, info in self._output_fields.items():
            lines.append(f"{info.prefix}")

        return "\n".join(lines)


# ============================================================================
# Prediction Result
# ============================================================================


@dataclass
class Prediction:
    """
    DSPy-compatible prediction result.

    Holds the output from a module's forward() call, with support for
    multiple completions and trace information.

    Attributes:
        **kwargs: Output field values (accessible as attributes)
    """

    _completions: List[Dict[str, Any]] = field(default_factory=list)
    _trace: List[Dict[str, Any]] = field(default_factory=list)

    def __init__(self, **kwargs: Any):
        self._completions = [kwargs] if kwargs else []
        self._trace = []
        self._values = kwargs

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._values:
            return self._values[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._values[name] = value

    def __repr__(self) -> str:
        return f"Prediction({self._values})"

    @property
    def completions(self) -> List[Dict[str, Any]]:
        """Get all completions."""
        return self._completions

    def add_trace(self, step: str, data: Dict[str, Any]) -> None:
        """Add trace information for debugging."""
        self._trace.append({"step": step, "data": data, "timestamp": time.time()})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self._values.copy()


# ============================================================================
# Module Base Class
# ============================================================================


class Module(ABC):
    """
    DSPy-compatible Module base class.

    All DSPy modules inherit from this and implement forward().
    Modules can be composed into pipelines.

    Example:
        class MyRAG(Module):
            def __init__(self):
                super().__init__()
                self.retrieve = Retrieve(k=5)
                self.generate = ChainOfThought(QASignature)

            def forward(self, question: str) -> Prediction:
                passages = self.retrieve(question).passages
                return self.generate(context=passages, question=question)
    """

    def __init__(self):
        self._submodules: Dict[str, "Module"] = {}
        self._parameters: Dict[str, Any] = {}
        self._compiled: bool = False

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Module):
            if not hasattr(self, "_submodules"):
                super().__setattr__("_submodules", {})
            self._submodules[name] = value
        super().__setattr__(name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Prediction:
        """Call forward() and return prediction."""
        return self.forward(*args, **kwargs)

    @abstractmethod
    def forward(self, *args: Any, **kwargs: Any) -> Prediction:
        """Execute the module. Must be implemented by subclasses."""
        ...

    def named_submodules(self) -> Iterator[Tuple[str, "Module"]]:
        """Iterate over all submodules with names."""
        for name, module in self._submodules.items():
            yield name, module
            yield from (
                (f"{name}.{sub_name}", sub_mod)
                for sub_name, sub_mod in module.named_submodules()
            )

    def parameters(self) -> Dict[str, Any]:
        """Get all parameters (for optimization)."""
        params = self._parameters.copy()
        for name, module in self.named_submodules():
            for param_name, param_value in module._parameters.items():
                params[f"{name}.{param_name}"] = param_value
        return params

    def set_parameter(self, name: str, value: Any) -> None:
        """Set a parameter value."""
        self._parameters[name] = value

    def save(self, path: str) -> None:
        """Save module state to file."""
        import pickle

        with open(path, "wb") as f:
            pickle.dump(
                {
                    "parameters": self.parameters(),
                    "compiled": self._compiled,
                },
                f,
            )

    def load(self, path: str) -> None:
        """Load module state from file."""
        import pickle

        with open(path, "rb") as f:
            data = pickle.load(f)
            self._parameters = data.get("parameters", {})
            self._compiled = data.get("compiled", False)

    def reset(self) -> None:
        """Reset module to initial state."""
        self._parameters.clear()
        self._compiled = False
        for _, module in self.named_submodules():
            module.reset()


# ============================================================================
# LLM Protocol
# ============================================================================


class LLMProtocol(Protocol):
    """Protocol for LLM backends."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text from prompt."""
        ...

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat-style generation."""
        ...


@dataclass
class LLMConfig:
    """Configuration for LLM."""

    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 1.0
    stop: Optional[List[str]] = None


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {}
        self.call_count = 0
        self.last_prompt = ""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate mock response."""
        self.call_count += 1
        self.last_prompt = prompt

        # Check for exact match
        if prompt in self.responses:
            return self.responses[prompt]

        # Check for pattern match
        for pattern, response in self.responses.items():
            if pattern in prompt:
                return response

        # Default response
        return "Mock response for: " + prompt[:50]

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> str:
        """Chat-style generation."""
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        return self.generate(prompt, **kwargs)


# Global LLM configuration
_default_lm: Optional[LLMProtocol] = None


def configure(lm: Optional[LLMProtocol] = None, **kwargs: Any) -> None:
    """Configure the default LLM."""
    global _default_lm
    _default_lm = lm


def get_lm() -> Optional[LLMProtocol]:
    """Get the configured LLM."""
    return _default_lm


# ============================================================================
# Retrieve Module
# ============================================================================


@dataclass
class RetrievalResult:
    """Result from retrieval operation."""

    passages: List[str]
    scores: List[float]
    metadata: List[Dict[str, Any]]

    def __iter__(self) -> Iterator[str]:
        return iter(self.passages)

    def __len__(self) -> int:
        return len(self.passages)


class Retrieve(Module):
    """
    DSPy-compatible Retrieve module.

    Wraps Agentic Brain's GraphRAG retriever for use in DSPy pipelines.
    Supports vector search, hybrid search, and graph-aware retrieval.

    Args:
        retriever: Agentic Brain retriever (GraphRAG, Retriever, or RAGPipeline)
        k: Number of passages to retrieve
        strategy: Search strategy (vector, hybrid, graph)

    Example:
        from agentic_brain.rag import GraphRAG
        from agentic_brain.rag.dspy_compat import Retrieve

        graph_rag = GraphRAG(neo4j_uri="bolt://localhost:7687")
        retrieve = Retrieve(retriever=graph_rag, k=5)
        result = retrieve("What is GraphRAG?")
        print(result.passages)  # List of retrieved passages
    """

    def __init__(
        self,
        retriever: Optional[Any] = None,
        k: int = 5,
        strategy: str = "hybrid",
    ):
        super().__init__()
        self.retriever = retriever
        self.k = k
        self.strategy = strategy
        self.set_parameter("k", k)
        self.set_parameter("strategy", strategy)

    def _resolve_strategy(self) -> Any:
        strategy: Any = self.strategy
        if isinstance(strategy, str):
            try:
                from .graph_rag import SearchStrategy

                for candidate in SearchStrategy:
                    if candidate.value == strategy:
                        return candidate
            except Exception:
                return strategy
        return strategy

    def _resolve_async(self, result: Any) -> Any:
        if inspect.iscoroutine(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(result)
            raise RuntimeError(
                "Async retriever used while an event loop is running. "
                "Use an async wrapper or await the retriever directly."
            )
        return result

    def forward(self, query: str, k: Optional[int] = None) -> RetrievalResult:
        """
        Retrieve passages for the given query.

        Args:
            query: Search query
            k: Override default k

        Returns:
            RetrievalResult with passages, scores, and metadata
        """
        k = k or self.k

        if self.retriever is None:
            # Return empty result if no retriever configured
            return RetrievalResult(passages=[], scores=[], metadata=[])

        # Handle different retriever types
        passages: List[str] = []
        scores: List[float] = []
        metadata: List[Dict[str, Any]] = []

        try:
            def append_item(item: Any) -> None:
                if isinstance(item, dict):
                    content = (
                        item.get("content")
                        or item.get("text")
                        or item.get("summary")
                        or ""
                    )
                    passages.append(content if content else str(item))
                    score = item.get("score", item.get("relevance_score", 0.0))
                    scores.append(float(score) if score is not None else 0.0)
                    metadata.append(item)
                    return
                if hasattr(item, "content"):
                    passages.append(getattr(item, "content"))
                    scores.append(float(getattr(item, "score", 0.0)))
                    metadata.append(getattr(item, "metadata", {}))
                    return
                passages.append(str(item))
                scores.append(0.0)
                metadata.append({})

            # Check for GraphRAG
            if hasattr(self.retriever, "search"):
                search = self.retriever.search
                search_kwargs: Dict[str, Any] = {}
                try:
                    params = inspect.signature(search).parameters
                except (TypeError, ValueError):
                    params = {}
                if "strategy" in params:
                    search_kwargs["strategy"] = self._resolve_strategy()
                if "top_k" in params:
                    search_kwargs["top_k"] = k
                elif "k" in params:
                    search_kwargs["k"] = k
                results = self._resolve_async(search(query, **search_kwargs))
                if hasattr(results, "chunks"):
                    for chunk in results.chunks:
                        append_item(chunk)
                elif isinstance(results, list):
                    for r in results:
                        append_item(r)

            # Check for Retriever
            elif hasattr(self.retriever, "retrieve"):
                results = self.retriever.retrieve(query, top_k=k)
                for r in results:
                    append_item(r)

            # Check for RAGPipeline
            elif hasattr(self.retriever, "query"):
                result = self.retriever.query(query)
                if hasattr(result, "sources"):
                    for source in result.sources[:k]:
                        append_item(source)

            # Callable retriever
            elif callable(self.retriever):
                results = self.retriever(query, k=k)
                if isinstance(results, list):
                    for r in results:
                        if isinstance(r, str):
                            passages.append(r)
                            scores.append(1.0)
                            metadata.append({})
                        else:
                            append_item(r)

        except Exception as e:
            logger.warning(f"Retrieval error: {e}")

        return RetrievalResult(passages=passages, scores=scores, metadata=metadata)


# ============================================================================
# ChainOfThought Module
# ============================================================================


class ChainOfThought(Module):
    """
    DSPy-compatible Chain of Thought module.

    Implements step-by-step reasoning before generating final output.
    Automatically adds reasoning to signatures.

    Args:
        signature: Signature class or instance defining I/O
        lm: Language model (uses default if not provided)
        rationale_prefix: Prefix for reasoning section

    Example:
        class QA(Signature):
            '''Answer questions based on context.'''
            context = InputField(desc="Retrieved context")
            question = InputField(desc="Question to answer")
            answer = OutputField(desc="Final answer")

        cot = ChainOfThought(QA)
        result = cot(context="...", question="What is X?")
        print(result.reasoning)  # Step-by-step reasoning
        print(result.answer)     # Final answer
    """

    def __init__(
        self,
        signature: Type[Signature],
        lm: Optional[LLMProtocol] = None,
        rationale_prefix: str = "Reasoning: Let's think step by step.",
    ):
        super().__init__()
        self.signature = signature
        self.lm = lm
        self.rationale_prefix = rationale_prefix
        self.set_parameter("rationale_prefix", rationale_prefix)

    def forward(self, **kwargs: Any) -> Prediction:
        """
        Execute chain of thought reasoning.

        Args:
            **kwargs: Input field values

        Returns:
            Prediction with reasoning and output fields
        """
        lm = self.lm or get_lm()

        # Build prompt with CoT
        sig = self.signature(**{k: v for k, v in kwargs.items() if k in self.signature._input_fields})
        prompt = sig.format_prompt()
        prompt = prompt.replace(
            list(self.signature._output_fields.values())[0].prefix,
            f"{self.rationale_prefix}\n\n{list(self.signature._output_fields.values())[0].prefix}",
        )

        # Generate
        if lm:
            response = lm.generate(prompt)
        else:
            response = f"[No LM configured] Would reason about: {kwargs}"

        # Parse response
        result = self._parse_response(response)
        result["reasoning"] = self._extract_reasoning(response)

        return Prediction(**result)

    def _extract_reasoning(self, response: str) -> str:
        """Extract reasoning from response."""
        # Look for reasoning section
        patterns = [
            r"Reasoning:(.+?)(?=\n[A-Z][A-Za-z ]+:|\Z)",
            r"Let's think step by step[.:](.+?)(?=\n[A-Z][A-Za-z ]+:|\Z)",
            r"Step \d+:(.+?)(?=Step \d+:|Answer:|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return response.split("\n")[0] if response else ""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse output fields from response."""
        result: Dict[str, Any] = {}

        for name, info in self.signature._output_fields.items():
            # Try to find field value
            pattern = rf"{re.escape(info.prefix)}\s*(.+?)(?=\n[A-Z]|\Z)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Convert format if specified
                if info.format == "json":
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                elif info.format == "float":
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                elif info.format == "int":
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                result[name] = value
            else:
                result[name] = response.strip()

        return result


# ============================================================================
# ReAct Module (Reasoning + Acting)
# ============================================================================


class ActionType(Enum):
    """Types of actions in ReAct."""

    SEARCH = "search"
    LOOKUP = "lookup"
    CALCULATE = "calculate"
    FINISH = "finish"


@dataclass
class Action:
    """An action in the ReAct loop."""

    type: ActionType
    input: str
    output: Optional[str] = None


@dataclass
class ReActTrace:
    """Trace of ReAct execution."""

    thoughts: List[str]
    actions: List[Action]
    observations: List[str]
    final_answer: str


class ReAct(Module):
    """
    DSPy-compatible ReAct (Reasoning + Acting) module.

    Implements the ReAct paradigm where the model alternates between
    thinking (reasoning) and acting (tool use) to solve problems.

    Args:
        signature: Signature class defining the task
        tools: Dict of tool_name -> callable
        max_steps: Maximum number of think-act cycles
        lm: Language model

    Example:
        def search_tool(query: str) -> str:
            return retriever.search(query)

        react = ReAct(
            QASignature,
            tools={"Search": search_tool},
            max_steps=5,
        )
        result = react(question="Who invented Python?")
    """

    def __init__(
        self,
        signature: Type[Signature],
        tools: Optional[Dict[str, Callable[[str], str]]] = None,
        max_steps: int = 5,
        lm: Optional[LLMProtocol] = None,
    ):
        super().__init__()
        self.signature = signature
        self.tools = tools or {}
        self.max_steps = max_steps
        self.lm = lm
        self.set_parameter("max_steps", max_steps)

        # Add default finish tool
        if "Finish" not in self.tools:
            self.tools["Finish"] = lambda x: x

    def forward(self, **kwargs: Any) -> Prediction:
        """
        Execute ReAct reasoning loop.

        Args:
            **kwargs: Input field values

        Returns:
            Prediction with final answer and trace
        """
        lm = self.lm or get_lm()
        trace = ReActTrace(thoughts=[], actions=[], observations=[], final_answer="")

        # Build initial prompt
        prompt = self._build_prompt(kwargs, trace)

        for step in range(self.max_steps):
            if lm:
                response = lm.generate(prompt)
            else:
                response = "Thought: I need to search.\nAction: Finish[answer based on input]"

            # Parse thought and action
            thought = self._extract_thought(response)
            action = self._extract_action(response)

            trace.thoughts.append(thought)

            if action:
                trace.actions.append(action)

                # Execute action
                if action.type == ActionType.FINISH:
                    trace.final_answer = action.input
                    break

                observation = self._execute_action(action)
                trace.observations.append(observation)
                action.output = observation

                # Update prompt with observation
                prompt += f"\nThought: {thought}\nAction: {action.type.value}[{action.input}]\nObservation: {observation}\n"
            else:
                # No valid action, finish
                trace.final_answer = thought
                break

        # Build prediction
        result: Dict[str, Any] = {
            "trace": trace,
            "reasoning": "\n".join(trace.thoughts),
        }

        # Add output fields
        for name in self.signature._output_fields:
            if name == "answer":
                result[name] = trace.final_answer
            elif name not in result:
                result[name] = trace.final_answer

        return Prediction(**result)

    def _build_prompt(self, inputs: Dict[str, Any], trace: ReActTrace) -> str:
        """Build ReAct prompt."""
        lines = [
            self.signature.instructions(),
            "",
            "You have access to the following tools:",
        ]

        for tool_name in self.tools:
            lines.append(f"- {tool_name}[input]: Execute {tool_name.lower()} action")

        lines.append("")
        lines.append("Use this format:")
        lines.append("Thought: your reasoning")
        lines.append("Action: ToolName[input]")
        lines.append("Observation: result")
        lines.append("... (repeat until done)")
        lines.append("Action: Finish[final answer]")
        lines.append("")

        for name, value in inputs.items():
            lines.append(f"{name.title()}: {value}")

        lines.append("")
        lines.append("Begin!")
        lines.append("")

        return "\n".join(lines)

    def _extract_thought(self, response: str) -> str:
        """Extract thought from response."""
        match = re.search(r"Thought:\s*(.+?)(?=\nAction:|\Z)", response, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_action(self, response: str) -> Optional[Action]:
        """Extract action from response."""
        match = re.search(r"Action:\s*(\w+)\[(.+?)\]", response)
        if not match:
            return None

        action_name = match.group(1)
        action_input = match.group(2)

        # Map to ActionType
        action_type = ActionType.FINISH
        for at in ActionType:
            if at.value.lower() == action_name.lower():
                action_type = at
                break

        return Action(type=action_type, input=action_input)

    def _execute_action(self, action: Action) -> str:
        """Execute an action using tools."""
        tool_name = action.type.value.title()

        # Find matching tool (case-insensitive)
        for name, tool in self.tools.items():
            if name.lower() == action.type.value.lower() or name.lower() == tool_name.lower():
                try:
                    return str(tool(action.input))
                except Exception as e:
                    return f"Error: {e}"

        return f"Unknown tool: {tool_name}"


# ============================================================================
# Predict Module (Simple generation)
# ============================================================================


class Predict(Module):
    """
    DSPy-compatible Predict module.

    Simple generation without chain-of-thought. Maps inputs to outputs
    using the signature.

    Args:
        signature: Signature class defining I/O
        lm: Language model

    Example:
        class Classify(Signature):
            '''Classify sentiment.'''
            text = InputField()
            label = OutputField()

        predict = Predict(Classify)
        result = predict(text="I love this!")
        print(result.label)  # "positive"
    """

    def __init__(
        self,
        signature: Type[Signature],
        lm: Optional[LLMProtocol] = None,
    ):
        super().__init__()
        self.signature = signature
        self.lm = lm

    def forward(self, **kwargs: Any) -> Prediction:
        """
        Generate prediction.

        Args:
            **kwargs: Input field values

        Returns:
            Prediction with output fields
        """
        lm = self.lm or get_lm()

        # Build prompt
        sig = self.signature(**{k: v for k, v in kwargs.items() if k in self.signature._input_fields})
        prompt = sig.format_prompt()

        # Generate
        if lm:
            response = lm.generate(prompt)
        else:
            response = f"[No LM configured] Prediction for: {kwargs}"

        # Parse response
        result = self._parse_response(response)

        return Prediction(**result)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse output fields from response."""
        result: Dict[str, Any] = {}

        for name, info in self.signature._output_fields.items():
            pattern = rf"{re.escape(info.prefix)}\s*(.+?)(?=\n[A-Z]|\Z)"
            match = re.search(pattern, response, re.DOTALL)
            if match:
                result[name] = match.group(1).strip()
            else:
                result[name] = response.strip()

        return result


# ============================================================================
# Teleprompter Stubs (Prompt Optimizers)
# ============================================================================


class Teleprompter(ABC):
    """
    Base class for DSPy teleprompters (prompt optimizers).

    Teleprompters optimize prompts by learning from examples.
    This is a stub for future implementation.
    """

    @abstractmethod
    def compile(
        self,
        module: Module,
        trainset: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Module:
        """Compile/optimize a module using training data."""
        ...


class BootstrapFewShot(Teleprompter):
    """
    DSPy BootstrapFewShot teleprompter stub.

    Bootstraps few-shot examples by running the module on training data
    and selecting successful examples.

    Args:
        metric: Evaluation metric function
        max_bootstrapped_demos: Maximum number of demos to include
        max_labeled_demos: Maximum labeled examples to use

    Example:
        optimizer = BootstrapFewShot(
            metric=exact_match,
            max_bootstrapped_demos=4,
        )
        optimized = optimizer.compile(my_module, trainset=train_data)
    """

    def __init__(
        self,
        metric: Optional[Callable[[Prediction, Dict[str, Any]], float]] = None,
        max_bootstrapped_demos: int = 4,
        max_labeled_demos: int = 16,
    ):
        self.metric = metric
        self.max_bootstrapped_demos = max_bootstrapped_demos
        self.max_labeled_demos = max_labeled_demos

    def compile(
        self,
        module: Module,
        trainset: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Module:
        """
        Compile module with bootstrapped few-shot examples.

        Args:
            module: Module to optimize
            trainset: Training examples

        Returns:
            Optimized module (stub: returns original)
        """
        logger.info(
            f"BootstrapFewShot: Would optimize with {len(trainset)} examples "
            f"(max_demos={self.max_bootstrapped_demos})"
        )

        # Stub: In full implementation, would:
        # 1. Run module on trainset
        # 2. Score outputs with metric
        # 3. Select best examples as demos
        # 4. Inject demos into module prompts

        module._compiled = True
        module.set_parameter("demos", trainset[: self.max_labeled_demos])

        return module


class COPRO(Teleprompter):
    """
    DSPy COPRO (Cooperative Prompt Optimization) teleprompter stub.

    Uses an LLM to iteratively improve prompt instructions.

    Args:
        metric: Evaluation metric function
        breadth: Number of candidate prompts per iteration
        depth: Number of optimization iterations
        init_temperature: Temperature for prompt generation

    Example:
        optimizer = COPRO(
            metric=f1_score,
            breadth=5,
            depth=3,
        )
        optimized = optimizer.compile(my_module, trainset=train_data)
    """

    def __init__(
        self,
        metric: Optional[Callable[[Prediction, Dict[str, Any]], float]] = None,
        breadth: int = 5,
        depth: int = 3,
        init_temperature: float = 1.0,
    ):
        self.metric = metric
        self.breadth = breadth
        self.depth = depth
        self.init_temperature = init_temperature

    def compile(
        self,
        module: Module,
        trainset: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Module:
        """
        Compile module with COPRO optimization.

        Args:
            module: Module to optimize
            trainset: Training examples

        Returns:
            Optimized module (stub: returns original)
        """
        logger.info(
            f"COPRO: Would optimize with breadth={self.breadth}, depth={self.depth}"
        )

        # Stub: In full implementation, would:
        # 1. Generate candidate instruction rewrites
        # 2. Evaluate each on trainset
        # 3. Select best and iterate

        module._compiled = True
        module.set_parameter("copro_optimized", True)

        return module


class MIPROv2(Teleprompter):
    """
    DSPy MIPROv2 teleprompter stub.

    Multi-stage Instruction and Prompt Optimization.

    Args:
        metric: Evaluation metric function
        num_candidates: Number of candidates per stage
        num_threads: Parallel threads for evaluation
    """

    def __init__(
        self,
        metric: Optional[Callable[[Prediction, Dict[str, Any]], float]] = None,
        num_candidates: int = 10,
        num_threads: int = 4,
    ):
        self.metric = metric
        self.num_candidates = num_candidates
        self.num_threads = num_threads

    def compile(
        self,
        module: Module,
        trainset: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> Module:
        """Compile with MIPROv2."""
        logger.info(f"MIPROv2: Would optimize with {self.num_candidates} candidates")
        module._compiled = True
        return module


# ============================================================================
# Evaluation Framework
# ============================================================================


@dataclass
class EvalExample:
    """A single evaluation example."""

    inputs: Dict[str, Any]
    expected: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result from evaluating a single example."""

    example: EvalExample
    prediction: Prediction
    score: float
    passed: bool
    error: Optional[str] = None


@dataclass
class EvalResults:
    """Aggregated evaluation results."""

    results: List[EvalResult]
    total: int
    passed: int
    failed: int
    errors: int
    mean_score: float
    scores: Dict[str, float]

    @property
    def accuracy(self) -> float:
        """Calculate accuracy."""
        return self.passed / self.total if self.total > 0 else 0.0


def exact_match(prediction: Prediction, expected: Dict[str, Any]) -> float:
    """Exact match metric."""
    for key, value in expected.items():
        pred_value = getattr(prediction, key, None)
        if pred_value != value:
            return 0.0
    return 1.0


def f1_score(prediction: Prediction, expected: Dict[str, Any]) -> float:
    """Token-level F1 score."""
    for key, value in expected.items():
        pred_value = getattr(prediction, key, "")
        if not pred_value or not value:
            return 0.0

        pred_tokens = set(str(pred_value).lower().split())
        exp_tokens = set(str(value).lower().split())

        if not pred_tokens or not exp_tokens:
            return 0.0

        intersection = pred_tokens & exp_tokens
        precision = len(intersection) / len(pred_tokens)
        recall = len(intersection) / len(exp_tokens)

        if precision + recall == 0:
            return 0.0

        return 2 * (precision * recall) / (precision + recall)


def semantic_similarity(prediction: Prediction, expected: Dict[str, Any]) -> float:
    """Semantic similarity metric (stub - returns 0.5 for non-empty)."""
    for key, value in expected.items():
        pred_value = getattr(prediction, key, "")
        if pred_value and value:
            # Stub: would use embeddings for real similarity
            return 0.5 if pred_value else 0.0
    return 0.0


class Evaluate:
    """
    DSPy-compatible evaluation framework.

    Evaluates modules against datasets using specified metrics.

    Args:
        devset: Evaluation dataset (list of examples)
        metric: Metric function (prediction, expected) -> score
        num_threads: Parallel evaluation threads
        display_progress: Show progress bar
        display_table: Show results table

    Example:
        dataset = [
            {"inputs": {"question": "What is 2+2?"}, "expected": {"answer": "4"}},
            ...
        ]

        evaluator = Evaluate(devset=dataset, metric=exact_match)
        results = evaluator(my_module)
        print(f"Accuracy: {results.accuracy:.2%}")
    """

    def __init__(
        self,
        devset: List[Dict[str, Any]],
        metric: Callable[[Prediction, Dict[str, Any]], float] = exact_match,
        num_threads: int = 1,
        display_progress: bool = True,
        display_table: bool = False,
        threshold: float = 0.5,
    ):
        self.devset = [self._to_eval_example(ex) for ex in devset]
        self.metric = metric
        self.num_threads = num_threads
        self.display_progress = display_progress
        self.display_table = display_table
        self.threshold = threshold

    def _to_eval_example(self, data: Dict[str, Any]) -> EvalExample:
        """Convert dict to EvalExample."""
        if isinstance(data, EvalExample):
            return data
        return EvalExample(
            inputs=data.get("inputs", {}),
            expected=data.get("expected", {}),
            metadata=data.get("metadata", {}),
        )

    def __call__(self, module: Module) -> EvalResults:
        """
        Evaluate module on devset.

        Args:
            module: Module to evaluate

        Returns:
            EvalResults with scores and statistics
        """
        results: List[EvalResult] = []
        scores: List[float] = []

        for i, example in enumerate(self.devset):
            if self.display_progress:
                logger.info(f"Evaluating {i + 1}/{len(self.devset)}")

            try:
                prediction = module(**example.inputs)
                score = self.metric(prediction, example.expected)
                passed = score >= self.threshold

                results.append(
                    EvalResult(
                        example=example,
                        prediction=prediction,
                        score=score,
                        passed=passed,
                    )
                )
                scores.append(score)

            except Exception as e:
                logger.error(f"Evaluation error: {e}")
                results.append(
                    EvalResult(
                        example=example,
                        prediction=Prediction(),
                        score=0.0,
                        passed=False,
                        error=str(e),
                    )
                )
                scores.append(0.0)

        # Aggregate
        passed = sum(1 for r in results if r.passed)
        errors = sum(1 for r in results if r.error)
        mean_score = sum(scores) / len(scores) if scores else 0.0

        return EvalResults(
            results=results,
            total=len(results),
            passed=passed,
            failed=len(results) - passed - errors,
            errors=errors,
            mean_score=mean_score,
            scores={"mean": mean_score, "accuracy": passed / len(results) if results else 0.0},
        )


# ============================================================================
# Agentic Brain Integration Modules
# ============================================================================


class GraphRAGRetrieve(Retrieve):
    """
    Specialized retriever for Agentic Brain GraphRAG.

    Provides enhanced retrieval using Neo4j knowledge graphs
    with community-aware and multi-hop capabilities.

    Args:
        neo4j_uri: Neo4j connection URI
        k: Number of passages to retrieve
        strategy: Search strategy (vector, hybrid, community, multi_hop)

    Example:
        retrieve = GraphRAGRetrieve(
            neo4j_uri="bolt://localhost:7687",
            k=5,
            strategy="hybrid",
        )
        result = retrieve("What causes X?")
    """

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        k: int = 5,
        strategy: str = "hybrid",
        **kwargs: Any,
    ):
        # Lazy load GraphRAG
        from .graph_rag import GraphRAG

        retriever = GraphRAG(neo4j_uri=neo4j_uri, **kwargs)
        super().__init__(retriever=retriever, k=k, strategy=strategy)
        self.neo4j_uri = neo4j_uri


class MultiHopRetrieve(Module):
    """
    Multi-hop retrieval module using Agentic Brain's reasoning.

    Chains multiple retrieval steps for complex queries.

    Args:
        base_retriever: Base retriever for individual hops
        max_hops: Maximum number of retrieval hops
        lm: Language model for reasoning
    """

    def __init__(
        self,
        base_retriever: Optional[Retrieve] = None,
        max_hops: int = 3,
        lm: Optional[LLMProtocol] = None,
    ):
        super().__init__()
        self.base_retriever = base_retriever or Retrieve()
        self.max_hops = max_hops
        self.lm = lm
        self.set_parameter("max_hops", max_hops)

    def forward(self, query: str) -> Prediction:
        """
        Execute multi-hop retrieval.

        Args:
            query: Initial query

        Returns:
            Prediction with accumulated passages and reasoning
        """
        all_passages: List[str] = []
        all_scores: List[float] = []
        hops: List[Dict[str, Any]] = []
        current_query = query

        for hop in range(self.max_hops):
            result = self.base_retriever(current_query)
            all_passages.extend(result.passages)
            all_scores.extend(result.scores)

            hops.append({
                "hop": hop + 1,
                "query": current_query,
                "passages": result.passages,
            })

            # Generate next query if LLM available
            if self.lm and result.passages:
                context = "\n".join(result.passages[:3])
                prompt = f"Based on this context:\n{context}\n\nOriginal question: {query}\n\nWhat follow-up question would help answer the original question? If no follow-up is needed, respond 'DONE'."
                next_query = self.lm.generate(prompt)
                if "DONE" in next_query.upper():
                    break
                current_query = next_query.strip()
            else:
                break

        return Prediction(
            passages=all_passages,
            scores=all_scores,
            hops=hops,
            num_hops=len(hops),
        )


# ============================================================================
# Example Signatures
# ============================================================================


class BasicQA(Signature):
    """Answer questions based on context."""

    context = InputField(desc="Relevant context passages")
    question = InputField(desc="Question to answer")
    answer = OutputField(desc="Direct answer")


class DetailedQA(Signature):
    """Answer questions with reasoning and confidence."""

    context = InputField(desc="Retrieved context")
    question = InputField(desc="User question")
    reasoning = OutputField(desc="Step-by-step reasoning")
    answer = OutputField(desc="Final answer")
    confidence = OutputField(desc="Confidence score 0-1", format="float")


class Summarize(Signature):
    """Summarize the given text."""

    text = InputField(desc="Text to summarize")
    summary = OutputField(desc="Concise summary")


class Classify(Signature):
    """Classify text into categories."""

    text = InputField(desc="Text to classify")
    label = OutputField(desc="Classification label")


class Extract(Signature):
    """Extract entities from text."""

    text = InputField(desc="Text to process")
    entities = OutputField(desc="Extracted entities", format="json")


# ============================================================================
# Convenience Functions
# ============================================================================


def make_signature(
    instructions: str,
    inputs: Dict[str, str],
    outputs: Dict[str, str],
) -> Type[Signature]:
    """
    Dynamically create a Signature class.

    Args:
        instructions: Task description
        inputs: Dict of input_name -> description
        outputs: Dict of output_name -> description

    Returns:
        New Signature class

    Example:
        QA = make_signature(
            "Answer questions",
            {"question": "The question"},
            {"answer": "The answer"},
        )
    """
    namespace: Dict[str, Any] = {"__doc__": instructions}

    for name, desc in inputs.items():
        namespace[name] = InputField(desc=desc)

    for name, desc in outputs.items():
        namespace[name] = OutputField(desc=desc)

    return SignatureMeta(
        "DynamicSignature",
        (Signature,),
        namespace,
    )


def compile_module(
    module: Module,
    trainset: List[Dict[str, Any]],
    optimizer: str = "bootstrap",
    metric: Callable[[Prediction, Dict[str, Any]], float] = exact_match,
    **kwargs: Any,
) -> Module:
    """
    Convenience function to compile/optimize a module.

    Args:
        module: Module to optimize
        trainset: Training examples
        optimizer: Optimizer type (bootstrap, copro, miprov2)
        metric: Evaluation metric
        **kwargs: Additional optimizer arguments

    Returns:
        Optimized module
    """
    optimizers = {
        "bootstrap": BootstrapFewShot,
        "copro": COPRO,
        "miprov2": MIPROv2,
    }

    if optimizer not in optimizers:
        raise ValueError(f"Unknown optimizer: {optimizer}. Use: {list(optimizers.keys())}")

    opt = optimizers[optimizer](metric=metric, **kwargs)
    return opt.compile(module, trainset)


# ============================================================================
# Native DSPy Bridge (when available)
# ============================================================================


def to_native_dspy(module: Module) -> Any:
    """
    Convert to native DSPy module if available.

    Args:
        module: Agentic Brain DSPy module

    Returns:
        Native DSPy module (if available) or original

    Raises:
        ImportError: If native DSPy not installed
    """
    if not DSPY_NATIVE_AVAILABLE:
        raise ImportError(
            "Native DSPy not available. Install with: pip install dspy-ai"
        )

    # Stub: Would implement conversion to native DSPy
    logger.warning("Native DSPy bridge not fully implemented")
    return module


def from_native_dspy(native_module: Any) -> Module:
    """
    Convert from native DSPy module.

    Args:
        native_module: Native DSPy module

    Returns:
        Agentic Brain DSPy-compatible module
    """
    if not DSPY_NATIVE_AVAILABLE:
        raise ImportError("Native DSPy not available")

    # Stub: Would implement conversion from native DSPy
    logger.warning("Native DSPy bridge not fully implemented")

    class WrappedModule(Module):
        def __init__(self, native: Any):
            super().__init__()
            self._native = native

        def forward(self, **kwargs: Any) -> Prediction:
            result = self._native(**kwargs)
            return Prediction(**vars(result) if hasattr(result, "__dict__") else {"output": result})

    return WrappedModule(native_module)


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Availability
    "DSPY_NATIVE_AVAILABLE",
    # Fields
    "InputField",
    "OutputField",
    "FieldInfo",
    # Signature
    "Signature",
    "SignatureMeta",
    # Prediction
    "Prediction",
    # Module
    "Module",
    # Retrieval
    "Retrieve",
    "RetrievalResult",
    "GraphRAGRetrieve",
    "MultiHopRetrieve",
    # Reasoning
    "ChainOfThought",
    "ReAct",
    "Predict",
    "Action",
    "ActionType",
    "ReActTrace",
    # Teleprompters
    "Teleprompter",
    "BootstrapFewShot",
    "COPRO",
    "MIPROv2",
    # Evaluation
    "Evaluate",
    "EvalExample",
    "EvalResult",
    "EvalResults",
    "exact_match",
    "f1_score",
    "semantic_similarity",
    # LLM
    "LLMProtocol",
    "LLMConfig",
    "MockLLM",
    "configure",
    "get_lm",
    # Example Signatures
    "BasicQA",
    "DetailedQA",
    "Summarize",
    "Classify",
    "Extract",
    # Utilities
    "make_signature",
    "compile_module",
    "to_native_dspy",
    "from_native_dspy",
]
