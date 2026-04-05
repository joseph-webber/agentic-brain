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
Haystack 2.0 Compatibility Layer for Agentic Brain GraphRAG.

Provides seamless integration with Haystack pipelines:
- Pipeline: DAG-based component composition
- @component decorator for creating pipeline nodes
- DocumentStore: InMemoryDocumentStore, Neo4jDocumentStore
- Retriever: EmbeddingRetriever, BM25Retriever patterns
- Reader: ExtractiveReader, GenerativeReader patterns
- PromptBuilder: Template-based prompt construction
- Serialization: Pipeline.dumps()/loads() for persistence

Usage:
    from agentic_brain.rag.haystack_compat import (
        Pipeline,
        component,
        InMemoryDocumentStore,
        EmbeddingRetriever,
        PromptBuilder,
    )

    # Build a RAG pipeline
    pipe = Pipeline()
    pipe.add_component("retriever", EmbeddingRetriever(document_store=store))
    pipe.add_component("prompt_builder", PromptBuilder(template=template))
    pipe.add_component("llm", generator)
    pipe.connect("retriever", "prompt_builder")
    pipe.connect("prompt_builder", "llm")

    result = pipe.run({"retriever": {"query": "What is GraphRAG?"}})

Haystack 2.0 API Reference:
    https://docs.haystack.deepset.ai/docs/intro
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import inspect
import json
import logging
import math
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
    runtime_checkable,
)

from .embeddings import EmbeddingProvider, get_embeddings
from .retriever import RetrievedChunk, Retriever
from .store import Document as AgenticDocument
from .store import DocumentStore as AgenticDocumentStore
from .store import InMemoryDocumentStore as AgenticInMemoryStore

logger = logging.getLogger(__name__)

# ============================================================================
# Core Data Structures (Haystack 2.0 compatible)
# ============================================================================


@dataclass
class Document:
    """
    Haystack 2.0 compatible Document.

    This maps to Haystack's Document class for seamless migration.

    Attributes:
        content: The main text content
        id: Unique document identifier (auto-generated if not provided)
        meta: Metadata dictionary
        embedding: Optional pre-computed embedding vector
        score: Relevance score (set during retrieval)
        dataframe: Optional pandas DataFrame for tabular data
        blob: Optional binary data
    """

    content: str
    id: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    score: Optional[float] = None
    dataframe: Optional[Any] = None  # pandas.DataFrame
    blob: Optional[bytes] = None

    def __post_init__(self):
        if self.id is None:
            self.id = hashlib.sha256(self.content.encode()).hexdigest()[:16]

    def to_dict(self, flatten: bool = True) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "id": self.id,
            "content": self.content,
            "meta": self.meta,
            "score": self.score,
        }
        if self.embedding is not None:
            result["embedding"] = self.embedding
        if self.dataframe is not None:
            result["dataframe"] = "DataFrame present"
        if self.blob is not None:
            result["blob"] = f"Binary data ({len(self.blob)} bytes)"
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Document":
        """Create Document from dictionary."""
        return cls(
            content=data.get("content", ""),
            id=data.get("id"),
            meta=data.get("meta", {}),
            embedding=data.get("embedding"),
            score=data.get("score"),
        )

    def to_agentic_document(self) -> AgenticDocument:
        """Convert to Agentic Brain Document."""
        return AgenticDocument(
            id=self.id or "",
            content=self.content,
            metadata=self.meta,
        )

    @classmethod
    def from_agentic_document(cls, doc: AgenticDocument) -> "Document":
        """Create from Agentic Brain Document."""
        return cls(
            content=doc.content,
            id=doc.id,
            meta=doc.metadata,
        )

    @classmethod
    def from_retrieved_chunk(cls, chunk: RetrievedChunk) -> "Document":
        """Create from RetrievedChunk."""
        return cls(
            content=chunk.content,
            id=chunk.metadata.get("id", chunk.source),
            meta={**chunk.metadata, "source": chunk.source},
            score=chunk.score,
        )


@dataclass
class ByteStream:
    """Haystack 2.0 compatible ByteStream for binary data."""

    data: bytes
    mime_type: str = "application/octet-stream"
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_string(self, encoding: str = "utf-8") -> str:
        """Decode bytes to string."""
        return self.data.decode(encoding)

    @classmethod
    def from_string(
        cls, text: str, encoding: str = "utf-8", mime_type: str = "text/plain"
    ) -> "ByteStream":
        """Create from string."""
        return cls(data=text.encode(encoding), mime_type=mime_type)

    @classmethod
    def from_file_path(cls, path: str) -> "ByteStream":
        """Load from file."""
        from pathlib import Path

        file_path = Path(path)
        # Determine MIME type from extension
        ext_to_mime = {
            ".txt": "text/plain",
            ".html": "text/html",
            ".json": "application/json",
            ".pdf": "application/pdf",
            ".md": "text/markdown",
        }
        mime = ext_to_mime.get(file_path.suffix.lower(), "application/octet-stream")
        return cls(data=file_path.read_bytes(), mime_type=mime, meta={"source": path})


# ============================================================================
# Component System (Haystack 2.0 @component decorator)
# ============================================================================


class ComponentMeta:
    """Metadata for a Haystack component."""

    def __init__(
        self,
        input_types: Dict[str, Type],
        output_types: Dict[str, Type],
        name: Optional[str] = None,
    ):
        self.input_types = input_types
        self.output_types = output_types
        self.name = name


_COMPONENT_REGISTRY: Dict[str, Type] = {}


def component(cls: Type) -> Type:
    """
    Decorator to mark a class as a Haystack 2.0 component.

    Components must have a `run` method that returns a dictionary.
    Input/output types are inferred from type hints.

    Usage:
        @component
        class MyComponent:
            @component.output_types(output=str)
            def run(self, input_text: str) -> Dict[str, str]:
                return {"output": input_text.upper()}

    Args:
        cls: The class to decorate

    Returns:
        The decorated class with component metadata
    """
    if not hasattr(cls, "run"):
        raise TypeError(f"Component {cls.__name__} must have a 'run' method")

    run_method = cls.run
    hints = get_type_hints(run_method) if hasattr(run_method, "__annotations__") else {}

    # Extract input types (excluding 'self' and 'return')
    input_types = {k: v for k, v in hints.items() if k not in ("self", "return")}

    # Extract output types from decorator or return hint
    output_types = getattr(run_method, "_output_types", {})
    if not output_types and "return" in hints:
        return_hint = hints["return"]
        if hasattr(return_hint, "__origin__") and return_hint.__origin__ is dict:
            output_types = {"output": Any}

    # Store metadata
    cls.__haystack_component__ = ComponentMeta(
        input_types=input_types,
        output_types=output_types,
        name=cls.__name__,
    )

    # Register component
    _COMPONENT_REGISTRY[cls.__name__] = cls

    return cls


def output_types(**types: Type) -> Callable:
    """
    Decorator to specify output types for a component's run method.

    Usage:
        @component
        class MyComponent:
            @component.output_types(documents=List[Document], count=int)
            def run(self, query: str) -> Dict[str, Any]:
                docs = [...]
                return {"documents": docs, "count": len(docs)}
    """

    def decorator(method: Callable) -> Callable:
        method._output_types = types
        return method

    return decorator


# Attach output_types to component decorator
component.output_types = output_types


@runtime_checkable
class ComponentProtocol(Protocol):
    """Protocol for Haystack components."""

    def run(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute the component."""
        ...


# ============================================================================
# Pipeline (Haystack 2.0 DAG-based Pipeline)
# ============================================================================


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    pass


class PipelineValidationError(PipelineError):
    """Raised when pipeline validation fails."""

    pass


class PipelineConnectionError(PipelineError):
    """Raised when connection between components is invalid."""

    pass


class PipelineRuntimeError(PipelineError):
    """Raised during pipeline execution."""

    pass


@dataclass
class Connection:
    """Represents a connection between two components."""

    sender: str
    sender_output: str
    receiver: str
    receiver_input: str


class Pipeline:
    """
    Haystack 2.0 compatible Pipeline for DAG-based component composition.

    Pipelines connect components in a directed acyclic graph (DAG), where
    outputs of one component flow as inputs to downstream components.

    Usage:
        pipe = Pipeline()
        pipe.add_component("retriever", retriever)
        pipe.add_component("reader", reader)
        pipe.connect("retriever.documents", "reader.documents")
        result = pipe.run({"retriever": {"query": "What is AI?"}})

    Features:
        - Type validation between connected components
        - Automatic topological sorting for execution order
        - Serialization/deserialization (dumps/loads)
        - Visualization support (draw method)
    """

    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a new Pipeline.

        Args:
            metadata: Optional pipeline metadata
        """
        self._components: Dict[str, Any] = {}
        self._connections: List[Connection] = []
        self._graph: Dict[str, Set[str]] = defaultdict(set)
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self.metadata = metadata or {}

    def add_component(self, name: str, instance: Any) -> None:
        """
        Add a component to the pipeline.

        Args:
            name: Unique name for this component instance
            instance: Component instance (must have a run method)

        Raises:
            ValueError: If name already exists or instance is invalid
        """
        if name in self._components:
            raise ValueError(f"Component '{name}' already exists in pipeline")

        if not hasattr(instance, "run") or not callable(instance.run):
            raise ValueError(f"Component must have a callable 'run' method")

        self._components[name] = instance
        self._graph[name]  # Initialize entry
        logger.debug(f"Added component '{name}' to pipeline")

    def connect(
        self,
        sender: str,
        receiver: str,
    ) -> None:
        """
        Connect two components.

        Supports both simple and detailed connection syntax:
        - Simple: pipe.connect("retriever", "reader")
        - Detailed: pipe.connect("retriever.documents", "reader.documents")

        Args:
            sender: Sender component name or "component.output"
            receiver: Receiver component name or "component.input"

        Raises:
            PipelineConnectionError: If connection is invalid
        """
        # Parse sender
        if "." in sender:
            sender_name, sender_output = sender.split(".", 1)
        else:
            sender_name = sender
            sender_output = self._get_default_sender_output(sender_name)

        # Parse receiver
        if "." in receiver:
            receiver_name, receiver_input = receiver.split(".", 1)
        else:
            receiver_name = receiver
            receiver_input = self._get_default_receiver_input(receiver_name)

        # Validate components exist
        if sender_name not in self._components:
            raise PipelineConnectionError(f"Sender component '{sender_name}' not found")
        if receiver_name not in self._components:
            raise PipelineConnectionError(
                f"Receiver component '{receiver_name}' not found"
            )

        # Validate ports and types when metadata is available
        self._validate_connection(sender_name, sender_output, receiver_name, receiver_input)

        # Check for cycles
        if self._would_create_cycle(sender_name, receiver_name):
            raise PipelineConnectionError(
                f"Connection from '{sender}' to '{receiver}' would create a cycle"
            )

        # Add connection
        connection = Connection(
            sender=sender_name,
            sender_output=sender_output,
            receiver=receiver_name,
            receiver_input=receiver_input,
        )
        self._connections.append(connection)
        self._graph[sender_name].add(receiver_name)
        self._reverse_graph[receiver_name].add(sender_name)

        logger.debug(f"Connected {sender} -> {receiver}")

    def _get_default_sender_output(self, component_name: str) -> str:
        """Resolve default sender output name for simple connection syntax."""
        component = self._components.get(component_name)
        meta = getattr(component, "__haystack_component__", None)

        if meta and meta.output_types:
            if "output" in meta.output_types:
                return "output"
            if len(meta.output_types) == 1:
                return next(iter(meta.output_types))
        return "output"

    def _get_default_receiver_input(self, component_name: str) -> str:
        """Resolve default receiver input name for simple connection syntax."""
        component = self._components.get(component_name)
        meta = getattr(component, "__haystack_component__", None)

        if meta and meta.input_types:
            if "input" in meta.input_types:
                return "input"
            if len(meta.input_types) == 1:
                return next(iter(meta.input_types))

        # Fall back to first explicit run parameter
        if component is not None:
            try:
                sig = inspect.signature(component.run)
                params = [
                    p
                    for p in sig.parameters.values()
                    if p.name != "self" and p.kind != inspect.Parameter.VAR_KEYWORD
                ]
                if len(params) == 1:
                    return params[0].name
            except (TypeError, ValueError):
                pass

        return "input"

    def _validate_connection(
        self,
        sender_name: str,
        sender_output: str,
        receiver_name: str,
        receiver_input: str,
    ) -> None:
        """Validate connection ports and basic type compatibility when declared."""
        sender = self._components[sender_name]
        receiver = self._components[receiver_name]
        sender_meta = getattr(sender, "__haystack_component__", None)
        receiver_meta = getattr(receiver, "__haystack_component__", None)

        sender_type: Optional[Type] = None
        receiver_type: Optional[Type] = None

        if sender_meta and sender_meta.output_types:
            if sender_output not in sender_meta.output_types:
                raise PipelineConnectionError(
                    f"Output '{sender_output}' not declared by component '{sender_name}'"
                )
            sender_type = sender_meta.output_types.get(sender_output)

        accepts_var_kwargs = False
        try:
            receiver_sig = inspect.signature(receiver.run)
            accepts_var_kwargs = any(
                p.kind == inspect.Parameter.VAR_KEYWORD
                for p in receiver_sig.parameters.values()
            )
        except (TypeError, ValueError):
            pass

        if receiver_meta and receiver_meta.input_types:
            if receiver_input not in receiver_meta.input_types and not accepts_var_kwargs:
                raise PipelineConnectionError(
                    f"Input '{receiver_input}' not declared by component '{receiver_name}'"
                )
            receiver_type = receiver_meta.input_types.get(receiver_input)

        if sender_type is not None and receiver_type is not None:
            if not self._is_type_compatible(sender_type, receiver_type):
                raise PipelineConnectionError(
                    f"Type mismatch: '{sender_name}.{sender_output}' ({sender_type}) "
                    f"cannot connect to '{receiver_name}.{receiver_input}' ({receiver_type})"
                )

    @staticmethod
    def _is_type_compatible(sender_type: Type, receiver_type: Type) -> bool:
        """Check relaxed compatibility for typing hints used by components."""
        if sender_type is Any or receiver_type is Any:
            return True
        if sender_type == receiver_type:
            return True

        sender_origin = getattr(sender_type, "__origin__", None)
        receiver_origin = getattr(receiver_type, "__origin__", None)
        if sender_origin and receiver_origin and sender_origin == receiver_origin:
            return True

        try:
            return issubclass(sender_type, receiver_type)
        except TypeError:
            return False

    def _would_create_cycle(self, sender: str, receiver: str) -> bool:
        """Check if adding an edge would create a cycle."""
        if sender == receiver:
            return True

        # BFS from receiver to check if we can reach sender
        visited = {receiver}
        queue = [receiver]

        while queue:
            current = queue.pop(0)
            for next_node in self._graph[current]:
                if next_node == sender:
                    return True
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append(next_node)

        return False

    def _topological_sort(self) -> List[str]:
        """Get components in execution order using Kahn's algorithm."""
        # Calculate in-degrees
        in_degree = {name: 0 for name in self._components}
        for connections in self._graph.values():
            for receiver in connections:
                in_degree[receiver] += 1

        # Start with nodes with no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            for neighbor in self._graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._components):
            raise PipelineValidationError("Pipeline contains a cycle")

        return result

    def run(
        self,
        data: Dict[str, Dict[str, Any]],
        include_outputs_from: Optional[Set[str]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute the pipeline.

        Args:
            data: Input data for each component. Format: {"component_name": {"param": value}}
            include_outputs_from: Optional set of component names to include in output

        Returns:
            Dictionary of outputs from each component

        Raises:
            PipelineRuntimeError: If execution fails

        Example:
            result = pipe.run({
                "retriever": {"query": "What is AI?"},
                "reader": {"top_k": 3}
            })
        """
        if not self._components:
            raise PipelineRuntimeError("Pipeline has no components")

        # Get execution order
        execution_order = self._topological_sort()

        # Track outputs from each component
        outputs: Dict[str, Dict[str, Any]] = {}

        # Execute components in order
        for component_name in execution_order:
            component = self._components[component_name]

            # Gather inputs for this component
            component_inputs = dict(data.get(component_name, {}))

            # Add outputs from upstream components based on connections
            for conn in self._connections:
                if conn.receiver == component_name:
                    sender_outputs = outputs.get(conn.sender, {})
                    if conn.sender_output in sender_outputs:
                        component_inputs[conn.receiver_input] = sender_outputs[
                            conn.sender_output
                        ]

            # Execute component
            try:
                result = component.run(**component_inputs)
                if not isinstance(result, dict):
                    result = {"output": result}
                outputs[component_name] = result
            except Exception as e:
                raise PipelineRuntimeError(
                    f"Component '{component_name}' failed: {e}"
                ) from e

        # Filter outputs if requested
        if include_outputs_from is not None:
            outputs = {k: v for k, v in outputs.items() if k in include_outputs_from}

        return outputs

    def get_component(self, name: str) -> Any:
        """Get a component by name."""
        if name not in self._components:
            raise KeyError(f"Component '{name}' not found in pipeline")
        return self._components[name]

    def get_component_names(self) -> List[str]:
        """Get all component names in execution order."""
        return self._topological_sort()

    def remove_component(self, name: str) -> None:
        """Remove a component and its connections."""
        if name not in self._components:
            raise KeyError(f"Component '{name}' not found")

        del self._components[name]
        self._connections = [
            c for c in self._connections if c.sender != name and c.receiver != name
        ]
        self._graph.pop(name, None)
        self._reverse_graph.pop(name, None)

        for connections in self._graph.values():
            connections.discard(name)
        for connections in self._reverse_graph.values():
            connections.discard(name)

    def walk(self) -> Iterator[Tuple[str, Any]]:
        """Iterate over components in execution order."""
        for name in self._topological_sort():
            yield name, self._components[name]

    def inputs(self, include_subcomponents: bool = False) -> Dict[str, Dict[str, Type]]:
        """Get input specifications for all components."""
        result = {}
        for name, component in self._components.items():
            if hasattr(component, "__haystack_component__"):
                meta = component.__haystack_component__
                result[name] = meta.input_types
            else:
                # Infer from run method signature
                sig = inspect.signature(component.run)
                result[name] = {
                    p.name: p.annotation
                    for p in sig.parameters.values()
                    if p.name != "self"
                }
        return result

    def outputs(
        self, include_subcomponents: bool = False
    ) -> Dict[str, Dict[str, Type]]:
        """Get output specifications for all components."""
        result = {}
        for name, component in self._components.items():
            if hasattr(component, "__haystack_component__"):
                meta = component.__haystack_component__
                result[name] = meta.output_types
            else:
                result[name] = {"output": Any}
        return result

    def draw(self, path: str = "pipeline.png") -> str:
        """
        Generate a visual representation of the pipeline.

        Args:
            path: Output path for the image

        Returns:
            Path to the generated image
        """
        try:
            import graphviz

            dot = graphviz.Digraph(comment="Pipeline")
            dot.attr(rankdir="LR")

            # Add nodes
            for name in self._components:
                dot.node(name, name, shape="box")

            # Add edges
            for conn in self._connections:
                label = f"{conn.sender_output} -> {conn.receiver_input}"
                dot.edge(conn.sender, conn.receiver, label=label)

            dot.render(path.replace(".png", ""), format="png", cleanup=True)
            return path
        except ImportError:
            logger.warning("graphviz not installed, cannot draw pipeline")
            return ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize pipeline to dictionary."""
        components_data = {}
        for name, component in self._components.items():
            comp_data = {
                "type": f"{component.__class__.__module__}.{component.__class__.__name__}",
            }
            # Serialize component-specific data if available
            if hasattr(component, "to_dict"):
                comp_data["init_parameters"] = component.to_dict()
            components_data[name] = comp_data

        connections_data = [
            {
                "sender": f"{c.sender}.{c.sender_output}",
                "receiver": f"{c.receiver}.{c.receiver_input}",
            }
            for c in self._connections
        ]

        return {
            "metadata": self.metadata,
            "components": components_data,
            "connections": connections_data,
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        callbacks: Optional[Dict[str, Callable]] = None,
    ) -> "Pipeline":
        """
        Deserialize pipeline from dictionary.

        Args:
            data: Serialized pipeline data
            callbacks: Optional callbacks for component instantiation

        Returns:
            Reconstructed Pipeline
        """
        pipe = cls(metadata=data.get("metadata", {}))
        callbacks = callbacks or {}

        components_data = data.get("components", {})
        for name, comp_data in components_data.items():
            component_type = comp_data.get("type")
            if not component_type:
                raise PipelineValidationError(
                    f"Component '{name}' is missing required field 'type'"
                )

            init_parameters = copy.deepcopy(comp_data.get("init_parameters", {}))
            if isinstance(init_parameters, dict):
                init_parameters.pop("type", None)

            # Prefer full path callback, then short class name callback.
            factory = callbacks.get(component_type)
            short_name = component_type.rsplit(".", 1)[-1]
            if factory is None:
                factory = callbacks.get(short_name)
            if factory is None:
                factory = _COMPONENT_REGISTRY.get(short_name)

            if factory is None:
                try:
                    module_name, class_name = component_type.rsplit(".", 1)
                    module = importlib.import_module(module_name)
                    factory = getattr(module, class_name)
                except (ImportError, AttributeError, ValueError) as exc:
                    raise PipelineValidationError(
                        f"Cannot resolve component type '{component_type}'"
                    ) from exc

            # Instantiate class/component
            if inspect.isclass(factory):
                instance = factory(**init_parameters)
            else:
                try:
                    instance = factory(**init_parameters)
                except TypeError:
                    instance = factory(init_parameters)

            pipe.add_component(name, instance)

        for conn in data.get("connections", []):
            sender = conn.get("sender")
            receiver = conn.get("receiver")
            if not sender or not receiver:
                raise PipelineValidationError("Invalid connection entry in pipeline data")
            pipe.connect(sender, receiver)

        return pipe

    def dumps(self) -> str:
        """Serialize pipeline to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def loads(cls, data: str) -> "Pipeline":
        """Deserialize pipeline from JSON string."""
        return cls.from_dict(json.loads(data))

    def __repr__(self) -> str:
        return f"Pipeline(components={list(self._components.keys())})"


# ============================================================================
# Document Stores (Haystack 2.0 compatible)
# ============================================================================


class DocumentStoreProtocol(Protocol):
    """Protocol for Haystack document stores."""

    def write_documents(
        self, documents: List[Document], policy: str = "skip"
    ) -> int: ...

    def filter_documents(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> List[Document]: ...

    def delete_documents(self, document_ids: List[str]) -> None: ...

    def count_documents(self) -> int: ...


class InMemoryDocumentStore:
    """
    Haystack 2.0 compatible in-memory document store.

    Wraps Agentic Brain's InMemoryDocumentStore with Haystack API.

    Usage:
        store = InMemoryDocumentStore()
        store.write_documents([Document(content="Hello")])
        docs = store.filter_documents()
    """

    def __init__(
        self,
        bm25_tokenization_regex: str = r"(?u)\b\w\w+\b",
        bm25_algorithm: str = "BM25L",
        bm25_parameters: Optional[Dict[str, float]] = None,
        embedding_similarity_function: str = "cosine",
    ):
        """
        Initialize the document store.

        Args:
            bm25_tokenization_regex: Regex for BM25 tokenization
            bm25_algorithm: BM25 variant to use
            bm25_parameters: BM25 parameters (k1, b, delta)
            embedding_similarity_function: Similarity function for embeddings
        """
        self._store = AgenticInMemoryStore()
        self._documents: Dict[str, Document] = {}
        self._embeddings: Dict[str, List[float]] = {}

        self.bm25_tokenization_regex = bm25_tokenization_regex
        self.bm25_algorithm = bm25_algorithm
        self.bm25_parameters = bm25_parameters or {"k1": 1.5, "b": 0.75, "delta": 0.5}
        self.embedding_similarity_function = embedding_similarity_function

        # BM25 index
        self._bm25_index: Optional[Any] = None
        self._doc_ids_list: List[str] = []

    def write_documents(
        self,
        documents: List[Document],
        policy: str = "skip",
    ) -> int:
        """
        Write documents to the store.

        Args:
            documents: List of documents to write
            policy: Duplicate handling policy ("skip", "overwrite", "fail")

        Returns:
            Number of documents written
        """
        written = 0
        for doc in documents:
            doc_id = doc.id or hashlib.sha256(doc.content.encode()).hexdigest()[:16]

            if doc_id in self._documents:
                if policy == "skip":
                    continue
                elif policy == "fail":
                    raise ValueError(f"Document {doc_id} already exists")
                # overwrite falls through

            self._documents[doc_id] = doc
            if doc.embedding is not None:
                self._embeddings[doc_id] = doc.embedding

            # Also add to underlying store
            self._store.add(doc.content, doc.meta, doc_id)
            written += 1

        # Rebuild BM25 index
        self._rebuild_bm25_index()

        return written

    def _rebuild_bm25_index(self) -> None:
        """Rebuild the BM25 index."""
        self._doc_ids_list = list(self._documents.keys())
        # BM25 index would be built here if rank_bm25 is available

    def filter_documents(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """
        Filter documents by metadata.

        Args:
            filters: Filter conditions in Haystack format

        Returns:
            List of matching documents
        """
        if filters is None:
            return list(self._documents.values())

        result = []
        for doc in self._documents.values():
            if self._matches_filters(doc, filters):
                result.append(doc)
        return result

    def _matches_filters(self, doc: Document, filters: Dict[str, Any]) -> bool:
        """Check if document matches filters."""
        # Handle Haystack filter format
        operator = filters.get("operator", "AND")
        conditions = filters.get("conditions", [])

        if not conditions:
            # Simple key-value filter
            for key, value in filters.items():
                if key in ("operator", "conditions"):
                    continue
                if doc.meta.get(key) != value:
                    return False
            return True

        # Complex filter
        results = []
        for condition in conditions:
            field = condition.get("field", "")
            op = condition.get("operator", "==")
            value = condition.get("value")

            # Get field value from document
            if field.startswith("meta."):
                doc_value = doc.meta.get(field[5:])
            elif field == "content":
                doc_value = doc.content
            elif field == "id":
                doc_value = doc.id
            else:
                doc_value = doc.meta.get(field)

            # Apply operator
            if op == "==" or op == "eq":
                results.append(doc_value == value)
            elif op == "!=" or op == "ne":
                results.append(doc_value != value)
            elif op == ">" or op == "gt":
                results.append(doc_value > value if doc_value else False)
            elif op == ">=" or op == "gte":
                results.append(doc_value >= value if doc_value else False)
            elif op == "<" or op == "lt":
                results.append(doc_value < value if doc_value else False)
            elif op == "<=" or op == "lte":
                results.append(doc_value <= value if doc_value else False)
            elif op == "in":
                results.append(doc_value in value if value else False)
            elif op == "not in":
                results.append(doc_value not in value if value else True)
            elif op == "contains":
                results.append(value in doc_value if doc_value else False)

        if operator == "AND":
            return all(results)
        elif operator == "OR":
            return any(results)
        elif operator == "NOT":
            return not any(results)
        return False

    def delete_documents(self, document_ids: List[str]) -> None:
        """Delete documents by ID."""
        for doc_id in document_ids:
            self._documents.pop(doc_id, None)
            self._embeddings.pop(doc_id, None)
            self._store.delete(doc_id)
        self._rebuild_bm25_index()

    def count_documents(self) -> int:
        """Count total documents."""
        return len(self._documents)

    def embedding_retrieval(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: bool = True,
        return_embedding: bool = False,
    ) -> List[Document]:
        """
        Retrieve documents by embedding similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters
            scale_score: Whether to scale scores to 0-1
            return_embedding: Whether to include embeddings in results

        Returns:
            List of documents sorted by similarity
        """
        candidates = self.filter_documents(filters)

        # Calculate similarities
        scored_docs = []
        for doc in candidates:
            doc_embedding = self._embeddings.get(doc.id or "")
            if doc_embedding is None:
                continue

            if self.embedding_similarity_function == "cosine":
                score = self._cosine_similarity(query_embedding, doc_embedding)
            elif self.embedding_similarity_function == "dot_product":
                score = self._dot_product(query_embedding, doc_embedding)
            else:
                score = self._cosine_similarity(query_embedding, doc_embedding)

            result_doc = Document(
                content=doc.content,
                id=doc.id,
                meta=doc.meta,
                embedding=doc_embedding if return_embedding else None,
                score=score,
            )
            scored_docs.append(result_doc)

        # Sort and return top_k
        scored_docs.sort(key=lambda x: x.score or 0, reverse=True)
        return scored_docs[:top_k]

    def bm25_retrieval(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: bool = True,
    ) -> List[Document]:
        """
        Retrieve documents using BM25 algorithm.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            scale_score: Whether to scale scores

        Returns:
            List of documents sorted by BM25 score
        """
        candidates = self.filter_documents(filters)
        if not candidates:
            return []

        # Tokenize query
        query_tokens = re.findall(self.bm25_tokenization_regex, query.lower())

        # Simple TF-IDF like scoring
        scored_docs = []
        for doc in candidates:
            doc_tokens = re.findall(self.bm25_tokenization_regex, doc.content.lower())
            score = sum(
                doc_tokens.count(token) / (len(doc_tokens) + 1)
                for token in query_tokens
            )

            result_doc = Document(
                content=doc.content,
                id=doc.id,
                meta=doc.meta,
                score=score,
            )
            scored_docs.append(result_doc)

        scored_docs.sort(key=lambda x: x.score or 0, reverse=True)
        return scored_docs[:top_k]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _dot_product(a: List[float], b: List[float]) -> float:
        """Calculate dot product."""
        return sum(x * y for x, y in zip(a, b))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize store configuration."""
        return {
            "type": "InMemoryDocumentStore",
            "bm25_tokenization_regex": self.bm25_tokenization_regex,
            "bm25_algorithm": self.bm25_algorithm,
            "bm25_parameters": self.bm25_parameters,
            "embedding_similarity_function": self.embedding_similarity_function,
        }


class Neo4jDocumentStore:
    """
    Haystack 2.0 compatible Neo4j document store.

    Connects to Agentic Brain's Neo4j backend for vector similarity search.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: str = "neo4j",
        password: Optional[str] = None,
        database: str = "neo4j",
        index_name: str = "document_embeddings",
        node_label: str = "Document",
        embedding_property: str = "embedding",
        text_property: str = "content",
        embedding_dimension: int = 384,
    ):
        """
        Initialize Neo4j document store.

        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password
            database: Database name
            index_name: Vector index name
            node_label: Label for document nodes
            embedding_property: Property name for embeddings
            text_property: Property name for text content
            embedding_dimension: Dimension of embedding vectors
        """
        import os

        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = username
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.database = database
        self.index_name = index_name
        self.node_label = node_label
        self.embedding_property = embedding_property
        self.text_property = text_property
        self.embedding_dimension = embedding_dimension

        self._retriever: Optional[Retriever] = None

    def _get_retriever(self) -> Retriever:
        """Get or create the retriever."""
        if self._retriever is None:
            self._retriever = Retriever(
                neo4j_uri=self.uri,
                neo4j_user=self.username,
                neo4j_password=self.password,
                sources=[self.node_label],
            )
        return self._retriever

    def write_documents(
        self,
        documents: List[Document],
        policy: str = "skip",
    ) -> int:
        """Write documents to Neo4j."""
        retriever = self._get_retriever()
        driver = retriever._get_driver()
        written = 0

        with driver.session(database=self.database) as session:
            for doc in documents:
                doc_id = doc.id or hashlib.sha256(doc.content.encode()).hexdigest()[:16]

                # Check if exists
                result = session.run(
                    f"MATCH (n:{self.node_label} {{id: $id}}) RETURN n",
                    id=doc_id,
                )
                exists = result.single() is not None

                if exists and policy == "skip":
                    continue
                elif exists and policy == "fail":
                    raise ValueError(f"Document {doc_id} already exists")

                # Write document
                query = f"""
                MERGE (n:{self.node_label} {{id: $id}})
                SET n.{self.text_property} = $content,
                    n.meta = $meta
                """
                params = {
                    "id": doc_id,
                    "content": doc.content,
                    "meta": json.dumps(doc.meta),
                }

                if doc.embedding is not None:
                    query = f"""
                    MERGE (n:{self.node_label} {{id: $id}})
                    SET n.{self.text_property} = $content,
                        n.{self.embedding_property} = $embedding,
                        n.meta = $meta
                    """
                    params["embedding"] = doc.embedding

                session.run(query, **params)
                written += 1

        return written

    def filter_documents(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Filter documents from Neo4j."""
        retriever = self._get_retriever()
        driver = retriever._get_driver()

        with driver.session(database=self.database) as session:
            query = f"MATCH (n:{self.node_label}) RETURN n LIMIT 1000"
            result = session.run(query)

            documents = []
            for record in result:
                node = record["n"]
                doc = Document(
                    content=node.get(self.text_property, ""),
                    id=node.get("id"),
                    meta=json.loads(node.get("meta", "{}")),
                    embedding=node.get(self.embedding_property),
                )
                if filters is None or self._matches_neo4j_filters(doc, filters):
                    documents.append(doc)

            return documents

    def _matches_neo4j_filters(self, doc: Document, filters: Dict[str, Any]) -> bool:
        """Check if document matches filters."""
        for key, value in filters.items():
            if key in ("operator", "conditions"):
                continue
            if doc.meta.get(key) != value:
                return False
        return True

    def delete_documents(self, document_ids: List[str]) -> None:
        """Delete documents from Neo4j."""
        retriever = self._get_retriever()
        driver = retriever._get_driver()

        with driver.session(database=self.database) as session:
            session.run(
                f"MATCH (n:{self.node_label}) WHERE n.id IN $ids DETACH DELETE n",
                ids=document_ids,
            )

    def count_documents(self) -> int:
        """Count documents in Neo4j."""
        retriever = self._get_retriever()
        driver = retriever._get_driver()

        with driver.session(database=self.database) as session:
            result = session.run(f"MATCH (n:{self.node_label}) RETURN count(n) as count")
            return result.single()["count"]

    def close(self) -> None:
        """Close the connection."""
        if self._retriever:
            self._retriever.close()
            self._retriever = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize store configuration."""
        return {
            "type": "Neo4jDocumentStore",
            "uri": self.uri,
            "username": self.username,
            "database": self.database,
            "index_name": self.index_name,
            "node_label": self.node_label,
        }


# ============================================================================
# Retrievers (Haystack 2.0 compatible)
# ============================================================================


@component
class EmbeddingRetriever:
    """
    Haystack 2.0 compatible embedding retriever.

    Retrieves documents using embedding similarity from a document store.

    Usage:
        retriever = EmbeddingRetriever(
            document_store=store,
            top_k=10,
        )
        docs = retriever.run(query_embedding=[0.1, 0.2, ...])["documents"]
    """

    def __init__(
        self,
        document_store: InMemoryDocumentStore,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: bool = True,
        return_embedding: bool = False,
    ):
        """
        Initialize the retriever.

        Args:
            document_store: Document store to retrieve from
            top_k: Number of documents to retrieve
            filters: Default metadata filters
            scale_score: Whether to scale scores
            return_embedding: Whether to return embeddings
        """
        self.document_store = document_store
        self.top_k = top_k
        self.filters = filters
        self.scale_score = scale_score
        self.return_embedding = return_embedding

    @component.output_types(documents=List[Document])
    def run(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: Optional[bool] = None,
        return_embedding: Optional[bool] = None,
    ) -> Dict[str, List[Document]]:
        """
        Retrieve documents by embedding similarity.

        Args:
            query_embedding: Query embedding vector
            top_k: Override default top_k
            filters: Override default filters
            scale_score: Override default scale_score
            return_embedding: Override default return_embedding

        Returns:
            Dictionary with "documents" key containing results
        """
        documents = self.document_store.embedding_retrieval(
            query_embedding=query_embedding,
            top_k=top_k or self.top_k,
            filters=filters or self.filters,
            scale_score=scale_score if scale_score is not None else self.scale_score,
            return_embedding=(
                return_embedding
                if return_embedding is not None
                else self.return_embedding
            ),
        )
        return {"documents": documents}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize retriever configuration."""
        return {
            "type": "EmbeddingRetriever",
            "top_k": self.top_k,
            "scale_score": self.scale_score,
            "return_embedding": self.return_embedding,
        }


@component
class BM25Retriever:
    """
    Haystack 2.0 compatible BM25 retriever.

    Retrieves documents using BM25 keyword matching.
    """

    def __init__(
        self,
        document_store: InMemoryDocumentStore,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: bool = True,
    ):
        """
        Initialize the retriever.

        Args:
            document_store: Document store to retrieve from
            top_k: Number of documents to retrieve
            filters: Default metadata filters
            scale_score: Whether to scale scores
        """
        self.document_store = document_store
        self.top_k = top_k
        self.filters = filters
        self.scale_score = scale_score

    @component.output_types(documents=List[Document])
    def run(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        scale_score: Optional[bool] = None,
    ) -> Dict[str, List[Document]]:
        """
        Retrieve documents using BM25.

        Args:
            query: Search query text
            top_k: Override default top_k
            filters: Override default filters
            scale_score: Override default scale_score

        Returns:
            Dictionary with "documents" key containing results
        """
        documents = self.document_store.bm25_retrieval(
            query=query,
            top_k=top_k or self.top_k,
            filters=filters or self.filters,
            scale_score=scale_score if scale_score is not None else self.scale_score,
        )
        return {"documents": documents}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize retriever configuration."""
        return {
            "type": "BM25Retriever",
            "top_k": self.top_k,
            "scale_score": self.scale_score,
        }


@component
class HybridRetriever:
    """
    Haystack 2.0 compatible hybrid retriever.

    Combines embedding and BM25 retrieval with Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        document_store: InMemoryDocumentStore,
        top_k: int = 10,
        embedding_weight: float = 0.5,
        bm25_weight: float = 0.5,
        rrf_k: int = 60,
    ):
        """
        Initialize the hybrid retriever.

        Args:
            document_store: Document store to retrieve from
            top_k: Number of documents to retrieve
            embedding_weight: Weight for embedding results
            bm25_weight: Weight for BM25 results
            rrf_k: RRF constant (typically 60)
        """
        self.document_store = document_store
        self.top_k = top_k
        self.embedding_weight = embedding_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k

    @component.output_types(documents=List[Document])
    def run(
        self,
        query: str,
        query_embedding: List[float],
        top_k: Optional[int] = None,
    ) -> Dict[str, List[Document]]:
        """
        Retrieve documents using hybrid approach.

        Args:
            query: Text query for BM25
            query_embedding: Embedding for vector search
            top_k: Override default top_k

        Returns:
            Dictionary with "documents" key containing fused results
        """
        k = top_k or self.top_k

        # Get both result sets
        embedding_docs = self.document_store.embedding_retrieval(
            query_embedding=query_embedding,
            top_k=k * 2,
        )
        bm25_docs = self.document_store.bm25_retrieval(
            query=query,
            top_k=k * 2,
        )

        # Build RRF scores
        rrf_scores: Dict[str, float] = {}

        for rank, doc in enumerate(embedding_docs):
            doc_id = doc.id or ""
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + self.embedding_weight / (
                self.rrf_k + rank + 1
            )

        for rank, doc in enumerate(bm25_docs):
            doc_id = doc.id or ""
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + self.bm25_weight / (
                self.rrf_k + rank + 1
            )

        # Get documents with scores
        doc_map = {doc.id: doc for doc in embedding_docs + bm25_docs if doc.id}

        result = []
        for doc_id, score in sorted(rrf_scores.items(), key=lambda x: -x[1])[:k]:
            if doc_id in doc_map:
                doc = doc_map[doc_id]
                result.append(
                    Document(
                        content=doc.content,
                        id=doc.id,
                        meta=doc.meta,
                        score=score,
                    )
                )

        return {"documents": result}


# ============================================================================
# Readers (Haystack 2.0 compatible)
# ============================================================================


@component
class ExtractiveReader:
    """
    Haystack 2.0 compatible extractive reader.

    Extracts answer spans from documents.
    """

    def __init__(
        self,
        model: str = "deepset/roberta-base-squad2",
        top_k: int = 3,
        max_seq_len: int = 384,
        doc_stride: int = 128,
        no_answer: bool = True,
    ):
        """
        Initialize the extractive reader.

        Args:
            model: Model name or path
            top_k: Number of answers per document
            max_seq_len: Maximum sequence length
            doc_stride: Stride for splitting long documents
            no_answer: Whether to include "no answer" option
        """
        self.model = model
        self.top_k = top_k
        self.max_seq_len = max_seq_len
        self.doc_stride = doc_stride
        self.no_answer = no_answer

    @component.output_types(answers=List[Dict[str, Any]])
    def run(
        self,
        query: str,
        documents: List[Document],
        top_k: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract answers from documents.

        Args:
            query: Question to answer
            documents: Documents to search
            top_k: Override default top_k

        Returns:
            Dictionary with "answers" key containing extracted answers
        """
        k = top_k or self.top_k
        query_lower = query.lower()

        # Simple extractive reading (pattern matching)
        answers = []
        for doc in documents:
            content = doc.content
            sentences = re.split(r"[.!?]+", content)

            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # Score based on query term overlap
                score = sum(
                    1 for word in query_lower.split() if word in sentence.lower()
                ) / max(len(query_lower.split()), 1)

                if score > 0:
                    answers.append(
                        {
                            "answer": sentence,
                            "score": min(score, 1.0),
                            "document": doc.to_dict(),
                            "context": content[
                                max(0, content.find(sentence) - 50) : content.find(
                                    sentence
                                )
                                + len(sentence)
                                + 50
                            ],
                        }
                    )

        # Sort by score and return top_k
        answers.sort(key=lambda x: x["score"], reverse=True)

        if self.no_answer and (not answers or answers[0]["score"] < 0.3):
            answers.insert(
                0, {"answer": "No answer found", "score": 0.0, "context": ""}
            )

        return {"answers": answers[:k]}


@component
class GenerativeReader:
    """
    Haystack 2.0 compatible generative reader.

    Generates answers using an LLM based on retrieved context.
    """

    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        prompt_template: Optional[str] = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the generative reader.

        Args:
            model: LLM model name
            prompt_template: Template for generating prompts
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            api_key: API key for LLM service
        """
        self.model = model
        self.prompt_template = prompt_template or (
            "Answer the following question based on the context provided.\n\n"
            "Context:\n{context}\n\n"
            "Question: {query}\n\n"
            "Answer:"
        )
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_key = api_key

    @component.output_types(answer=str, meta=Dict[str, Any])
    def run(
        self,
        query: str,
        documents: List[Document],
    ) -> Dict[str, Any]:
        """
        Generate an answer using LLM.

        Args:
            query: Question to answer
            documents: Context documents

        Returns:
            Dictionary with "answer" and "meta" keys
        """
        # Build context from documents
        context = "\n\n".join(
            f"[{i + 1}] {doc.content}" for i, doc in enumerate(documents)
        )

        # Build prompt
        prompt = self.prompt_template.format(context=context, query=query)

        # In production, this would call the actual LLM
        # For compatibility layer, return a placeholder
        answer = f"Based on {len(documents)} documents, the answer to '{query}' would be generated here."

        return {
            "answer": answer,
            "meta": {
                "model": self.model,
                "documents_used": len(documents),
                "prompt_length": len(prompt),
            },
        }


# ============================================================================
# Prompt Builder (Haystack 2.0 compatible)
# ============================================================================


@component
class PromptBuilder:
    """
    Haystack 2.0 compatible prompt builder.

    Constructs prompts from templates using Jinja2 syntax.
    """

    def __init__(
        self,
        template: str,
        required_variables: Optional[List[str]] = None,
    ):
        """
        Initialize the prompt builder.

        Args:
            template: Jinja2-style template string
            required_variables: List of required template variables
        """
        self.template = template
        self.required_variables = required_variables or []

        # Extract variables from template
        self._template_variables = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", template))
        self._template_variables.update(re.findall(r"\{(\w+)\}", template))

    @component.output_types(prompt=str)
    def run(self, **kwargs: Any) -> Dict[str, str]:
        """
        Build a prompt from the template.

        Args:
            **kwargs: Variables to fill in the template

        Returns:
            Dictionary with "prompt" key containing the rendered prompt
        """
        # Check required variables
        missing = set(self.required_variables) - set(kwargs.keys())
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        # Simple template rendering
        prompt = self.template

        # Handle documents specially
        if "documents" in kwargs:
            docs = kwargs["documents"]
            if isinstance(docs, list):
                doc_text = "\n\n".join(
                    f"Document {i + 1}:\n{d.content if hasattr(d, 'content') else str(d)}"
                    for i, d in enumerate(docs)
                )
                kwargs["documents"] = doc_text

        # Replace Jinja2-style variables
        for key, value in kwargs.items():
            # Handle both {{ var }} and { var }
            prompt = re.sub(r"\{\{\s*" + key + r"\s*\}\}", str(value), prompt)
            prompt = prompt.replace("{" + key + "}", str(value))

        return {"prompt": prompt}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize prompt builder configuration."""
        return {
            "type": "PromptBuilder",
            "template": self.template,
            "required_variables": self.required_variables,
        }


# ============================================================================
# Embedders (Haystack 2.0 compatible)
# ============================================================================


@component
class SentenceTransformersTextEmbedder:
    """
    Haystack 2.0 compatible text embedder using SentenceTransformers.

    Wraps Agentic Brain's embedding provider.
    """

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        prefix: str = "",
        suffix: str = "",
        batch_size: int = 32,
        normalize_embeddings: bool = True,
    ):
        """
        Initialize the text embedder.

        Args:
            model: Model name
            device: Device to use (auto-detected if None)
            prefix: Prefix to add to texts
            suffix: Suffix to add to texts
            batch_size: Batch size for embedding
            normalize_embeddings: Whether to normalize embeddings
        """
        self.model = model
        self.device = device
        self.prefix = prefix
        self.suffix = suffix
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings

        self._embedder: Optional[EmbeddingProvider] = None

    def _get_embedder(self) -> EmbeddingProvider:
        """Get or create the embedding provider."""
        if self._embedder is None:
            self._embedder = get_embeddings(provider="sentence_transformers")
        return self._embedder

    @component.output_types(embedding=List[float], meta=Dict[str, Any])
    def run(self, text: str) -> Dict[str, Any]:
        """
        Embed a single text.

        Args:
            text: Text to embed

        Returns:
            Dictionary with "embedding" and "meta" keys
        """
        embedder = self._get_embedder()
        text = f"{self.prefix}{text}{self.suffix}"
        embedding = embedder.embed(text)

        if self.normalize_embeddings:
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]

        return {
            "embedding": embedding,
            "meta": {"model": self.model, "device": self.device},
        }


@component
class SentenceTransformersDocumentEmbedder:
    """
    Haystack 2.0 compatible document embedder.

    Embeds documents and stores embeddings in their embedding field.
    """

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        batch_size: int = 32,
        progress_bar: bool = True,
        meta_fields_to_embed: Optional[List[str]] = None,
        embedding_separator: str = "\n",
    ):
        """
        Initialize the document embedder.

        Args:
            model: Model name
            device: Device to use
            batch_size: Batch size for embedding
            progress_bar: Whether to show progress bar
            meta_fields_to_embed: Metadata fields to include in embedding
            embedding_separator: Separator for concatenating fields
        """
        self.model = model
        self.device = device
        self.batch_size = batch_size
        self.progress_bar = progress_bar
        self.meta_fields_to_embed = meta_fields_to_embed or []
        self.embedding_separator = embedding_separator

        self._embedder: Optional[EmbeddingProvider] = None

    def _get_embedder(self) -> EmbeddingProvider:
        """Get or create the embedding provider."""
        if self._embedder is None:
            self._embedder = get_embeddings(provider="sentence_transformers")
        return self._embedder

    @component.output_types(documents=List[Document], meta=Dict[str, Any])
    def run(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Embed documents.

        Args:
            documents: Documents to embed

        Returns:
            Dictionary with embedded documents and metadata
        """
        embedder = self._get_embedder()
        result_docs = []

        for doc in documents:
            # Build text to embed
            parts = [doc.content]
            for field in self.meta_fields_to_embed:
                if field in doc.meta:
                    parts.append(str(doc.meta[field]))
            text = self.embedding_separator.join(parts)

            embedding = embedder.embed(text)

            result_doc = Document(
                content=doc.content,
                id=doc.id,
                meta=doc.meta,
                embedding=embedding,
                score=doc.score,
            )
            result_docs.append(result_doc)

        return {
            "documents": result_docs,
            "meta": {"model": self.model, "documents_count": len(documents)},
        }


# ============================================================================
# Writers (Haystack 2.0 compatible)
# ============================================================================


class DuplicatePolicy(Enum):
    """Policy for handling duplicate documents."""

    NONE = "none"
    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"


@component
class DocumentWriter:
    """
    Haystack 2.0 compatible document writer.

    Writes documents to a document store.
    """

    def __init__(
        self,
        document_store: InMemoryDocumentStore,
        policy: DuplicatePolicy = DuplicatePolicy.SKIP,
    ):
        """
        Initialize the document writer.

        Args:
            document_store: Target document store
            policy: Duplicate handling policy
        """
        self.document_store = document_store
        self.policy = policy

    @component.output_types(documents_written=int)
    def run(
        self,
        documents: List[Document],
        policy: Optional[DuplicatePolicy] = None,
    ) -> Dict[str, int]:
        """
        Write documents to the store.

        Args:
            documents: Documents to write
            policy: Override default policy

        Returns:
            Dictionary with count of documents written
        """
        policy_to_use = policy or self.policy
        written = self.document_store.write_documents(
            documents=documents,
            policy=policy_to_use.value if isinstance(policy_to_use, DuplicatePolicy) else policy_to_use,
        )
        return {"documents_written": written}


# ============================================================================
# Converters (Haystack 2.0 compatible)
# ============================================================================


@component
class TextFileToDocument:
    """Convert text files to Documents."""

    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding

    @component.output_types(documents=List[Document])
    def run(self, sources: List[Union[str, ByteStream]]) -> Dict[str, List[Document]]:
        """Convert sources to documents."""
        documents = []
        for source in sources:
            if isinstance(source, str):
                from pathlib import Path

                path = Path(source)
                content = path.read_text(encoding=self.encoding)
                documents.append(
                    Document(content=content, meta={"source": str(path)})
                )
            elif isinstance(source, ByteStream):
                content = source.to_string(self.encoding)
                documents.append(Document(content=content, meta=source.meta))
        return {"documents": documents}


@component
class DocumentJoiner:
    """Join multiple document lists into one."""

    def __init__(
        self,
        join_mode: str = "concatenate",
        top_k: Optional[int] = None,
        sort_by_score: bool = True,
    ):
        self.join_mode = join_mode
        self.top_k = top_k
        self.sort_by_score = sort_by_score

    @component.output_types(documents=List[Document])
    def run(self, documents: List[List[Document]]) -> Dict[str, List[Document]]:
        """Join document lists."""
        all_docs = []
        seen_ids: Set[str] = set()

        for doc_list in documents:
            for doc in doc_list:
                doc_id = doc.id or ""
                if self.join_mode == "concatenate" or doc_id not in seen_ids:
                    all_docs.append(doc)
                    seen_ids.add(doc_id)

        if self.sort_by_score:
            all_docs.sort(key=lambda x: x.score or 0, reverse=True)

        if self.top_k:
            all_docs = all_docs[: self.top_k]

        return {"documents": all_docs}


@component
class DocumentSplitter:
    """Split documents into smaller chunks."""

    def __init__(
        self,
        split_by: str = "sentence",
        split_length: int = 5,
        split_overlap: int = 0,
    ):
        self.split_by = split_by
        self.split_length = split_length
        self.split_overlap = split_overlap

    @component.output_types(documents=List[Document])
    def run(self, documents: List[Document]) -> Dict[str, List[Document]]:
        """Split documents."""
        result = []

        for doc in documents:
            if self.split_by == "sentence":
                units = re.split(r"(?<=[.!?])\s+", doc.content)
            elif self.split_by == "word":
                units = doc.content.split()
            elif self.split_by == "passage":
                units = doc.content.split("\n\n")
            else:
                units = [doc.content]

            # Create chunks
            for i in range(0, len(units), self.split_length - self.split_overlap):
                chunk_units = units[i : i + self.split_length]
                if not chunk_units:
                    continue

                separator = " " if self.split_by == "word" else " "
                chunk_content = separator.join(chunk_units)

                result.append(
                    Document(
                        content=chunk_content,
                        meta={
                            **doc.meta,
                            "split_id": i,
                            "split_idx_start": i,
                            "source_id": doc.id,
                        },
                    )
                )

        return {"documents": result}


# ============================================================================
# Routers (Haystack 2.0 compatible)
# ============================================================================


@component
class FileTypeRouter:
    """Route files by their type."""

    def __init__(self, mime_types: List[str]):
        self.mime_types = mime_types

    @component.output_types(
        text=List[ByteStream],
        pdf=List[ByteStream],
        other=List[ByteStream],
    )
    def run(self, sources: List[ByteStream]) -> Dict[str, List[ByteStream]]:
        """Route sources by MIME type."""
        result: Dict[str, List[ByteStream]] = {
            "text": [],
            "pdf": [],
            "other": [],
        }

        for source in sources:
            if "text" in source.mime_type:
                result["text"].append(source)
            elif "pdf" in source.mime_type:
                result["pdf"].append(source)
            else:
                result["other"].append(source)

        return result


@component
class MetadataRouter:
    """Route documents by metadata."""

    def __init__(self, rules: Dict[str, str]):
        """
        Initialize router.

        Args:
            rules: Dict mapping output names to filter conditions
        """
        self.rules = rules

    @component.output_types(documents=Dict[str, List[Document]])
    def run(self, documents: List[Document]) -> Dict[str, List[Document]]:
        """Route documents by metadata."""
        result: Dict[str, List[Document]] = {key: [] for key in self.rules}
        result["unmatched"] = []

        for doc in documents:
            matched = False
            for key, condition in self.rules.items():
                # Simple condition parsing: "field == value"
                if "==" in condition:
                    field, value = condition.split("==")
                    field = field.strip()
                    value = value.strip().strip("'\"")
                    if doc.meta.get(field) == value:
                        result[key].append(doc)
                        matched = True
                        break

            if not matched:
                result["unmatched"].append(doc)

        return result


# ============================================================================
# Utility Functions
# ============================================================================


def document_to_haystack(doc: AgenticDocument) -> Document:
    """Convert Agentic Brain Document to Haystack Document."""
    return Document.from_agentic_document(doc)


def haystack_to_document(doc: Document) -> AgenticDocument:
    """Convert Haystack Document to Agentic Brain Document."""
    return doc.to_agentic_document()


def chunk_to_haystack(chunk: RetrievedChunk) -> Document:
    """Convert RetrievedChunk to Haystack Document."""
    return Document.from_retrieved_chunk(chunk)


# ============================================================================
# Pre-built Pipeline Templates
# ============================================================================


def create_rag_pipeline(
    document_store: Optional[InMemoryDocumentStore] = None,
    embedder_model: str = "all-MiniLM-L6-v2",
    prompt_template: Optional[str] = None,
) -> Pipeline:
    """
    Create a standard RAG pipeline.

    Args:
        document_store: Document store (created if None)
        embedder_model: Model for embeddings
        prompt_template: Custom prompt template

    Returns:
        Configured Pipeline ready for use
    """
    if document_store is None:
        document_store = InMemoryDocumentStore()

    if prompt_template is None:
        prompt_template = """Answer the question based on the provided context.

Context:
{documents}

Question: {query}

Answer:"""

    pipe = Pipeline(metadata={"name": "RAG Pipeline", "version": "1.0"})

    # Add components
    pipe.add_component("text_embedder", SentenceTransformersTextEmbedder(model=embedder_model))
    pipe.add_component("retriever", EmbeddingRetriever(document_store=document_store))
    pipe.add_component("prompt_builder", PromptBuilder(template=prompt_template))

    # Connect components
    pipe.connect("text_embedder.embedding", "retriever.query_embedding")
    pipe.connect("retriever.documents", "prompt_builder.documents")

    return pipe


def create_indexing_pipeline(
    document_store: Optional[InMemoryDocumentStore] = None,
    embedder_model: str = "all-MiniLM-L6-v2",
) -> Pipeline:
    """
    Create a document indexing pipeline.

    Args:
        document_store: Target document store
        embedder_model: Model for embeddings

    Returns:
        Configured Pipeline for indexing
    """
    if document_store is None:
        document_store = InMemoryDocumentStore()

    pipe = Pipeline(metadata={"name": "Indexing Pipeline", "version": "1.0"})

    pipe.add_component("splitter", DocumentSplitter(split_by="sentence", split_length=5))
    pipe.add_component("embedder", SentenceTransformersDocumentEmbedder(model=embedder_model))
    pipe.add_component("writer", DocumentWriter(document_store=document_store))

    pipe.connect("splitter.documents", "embedder.documents")
    pipe.connect("embedder.documents", "writer.documents")

    return pipe


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Core
    "Document",
    "ByteStream",
    "Pipeline",
    "component",
    # Exceptions
    "PipelineError",
    "PipelineValidationError",
    "PipelineConnectionError",
    "PipelineRuntimeError",
    # Document Stores
    "InMemoryDocumentStore",
    "Neo4jDocumentStore",
    # Retrievers
    "EmbeddingRetriever",
    "BM25Retriever",
    "HybridRetriever",
    # Readers
    "ExtractiveReader",
    "GenerativeReader",
    # Builders
    "PromptBuilder",
    # Embedders
    "SentenceTransformersTextEmbedder",
    "SentenceTransformersDocumentEmbedder",
    # Writers
    "DocumentWriter",
    "DuplicatePolicy",
    # Converters
    "TextFileToDocument",
    "DocumentJoiner",
    "DocumentSplitter",
    # Routers
    "FileTypeRouter",
    "MetadataRouter",
    # Utilities
    "document_to_haystack",
    "haystack_to_document",
    "chunk_to_haystack",
    # Pipeline Templates
    "create_rag_pipeline",
    "create_indexing_pipeline",
]
