# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Tests for DSPy compatibility utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

from agentic_brain.rag import dspy_compat as dspy


class TestFieldDescriptors:
    def test_input_field_default_prefix(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField(desc="Question")
            answer = dspy.OutputField(desc="Answer")

        assert Sig._input_fields["question"].prefix == "Question:"

    def test_output_field_default_prefix(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        assert Sig._output_fields["answer"].prefix == "Answer:"

    def test_field_custom_prefix(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField(prefix="Q>")
            answer = dspy.OutputField(prefix="A>")

        assert Sig._input_fields["question"].prefix == "Q>"
        assert Sig._output_fields["answer"].prefix == "A>"


class TestSignature:
    def test_signature_inherits_fields(self) -> None:
        class Base(dspy.Signature):
            context = dspy.InputField()

        class Derived(Base):
            question = dspy.InputField()
            answer = dspy.OutputField()

        assert "context" in Derived._input_fields
        assert "question" in Derived._input_fields
        assert "answer" in Derived._output_fields

    def test_signature_unknown_field_raises(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        with pytest.raises(ValueError, match="Unknown field"):
            Sig(unknown="oops")

    def test_signature_default_values_applied(self) -> None:
        class Sig(dspy.Signature):
            topic = dspy.InputField(required=False, default="general")
            answer = dspy.OutputField()

        sig = Sig()
        assert sig.topic == "general"

    def test_signature_missing_required_fields_raises(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        with pytest.raises(ValueError, match="Missing required fields"):
            Sig()

    def test_signature_format_prompt_list(self) -> None:
        class Sig(dspy.Signature):
            items = dspy.InputField(format="list")
            answer = dspy.OutputField()

        sig = Sig(items=["alpha", "beta"])
        prompt = sig.format_prompt()
        assert "- alpha" in prompt
        assert "- beta" in prompt

    def test_signature_format_prompt_json(self) -> None:
        class Sig(dspy.Signature):
            payload = dspy.InputField(format="json")
            answer = dspy.OutputField()

        sig = Sig(payload={"key": "value"})
        prompt = sig.format_prompt()
        assert '"key": "value"' in prompt


class TestPrediction:
    def test_prediction_attribute_access(self) -> None:
        prediction = dspy.Prediction(answer="yes")
        assert prediction.answer == "yes"

    def test_prediction_completions(self) -> None:
        prediction = dspy.Prediction(answer="yes")
        assert prediction.completions == [{"answer": "yes"}]

    def test_prediction_trace(self) -> None:
        prediction = dspy.Prediction(answer="yes")
        prediction.add_trace("step", {"ok": True})
        assert prediction._trace[0]["step"] == "step"


class TestModule:
    def test_named_submodules(self) -> None:
        class Child(dspy.Module):
            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return dspy.Prediction(output="child")

        class Parent(dspy.Module):
            def __init__(self) -> None:
                super().__init__()
                self.child = Child()

            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return self.child()

        module = Parent()
        names = [name for name, _ in module.named_submodules()]
        assert "child" in names

    def test_parameters_include_submodule(self) -> None:
        class Child(dspy.Module):
            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return dspy.Prediction(output="child")

        class Parent(dspy.Module):
            def __init__(self) -> None:
                super().__init__()
                self.child = Child()

            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return self.child()

        module = Parent()
        module.child.set_parameter("temp", 0.3)
        params = module.parameters()
        assert params["child.temp"] == 0.3


class TestRetrieve:
    def test_retrieve_without_retriever(self) -> None:
        retrieve = dspy.Retrieve(retriever=None)
        result = retrieve("question")
        assert result.passages == []
        assert result.scores == []

    def test_retrieve_search_dict_results(self) -> None:
        class Retriever:
            def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
                return [
                    {"content": f"{query}-1", "score": 0.9, "meta": "a"},
                    {"content": f"{query}-2", "score": 0.8, "meta": "b"},
                ]

        retrieve = dspy.Retrieve(retriever=Retriever(), k=2)
        result = retrieve("q")
        assert result.passages == ["q-1", "q-2"]
        assert result.scores == [0.9, 0.8]
        assert result.metadata[0]["meta"] == "a"

    def test_retrieve_search_object_results(self) -> None:
        @dataclass
        class Chunk:
            content: str
            score: float
            metadata: Dict[str, Any]

        class Retriever:
            def search(self, query: str, top_k: int = 5) -> List[Chunk]:
                return [Chunk(content=query, score=0.5, metadata={"id": 1})]

        retrieve = dspy.Retrieve(retriever=Retriever(), k=1)
        result = retrieve("q")
        assert result.passages == ["q"]
        assert result.metadata[0]["id"] == 1

    def test_retrieve_retrieve_results(self) -> None:
        @dataclass
        class Hit:
            content: str
            score: float
            metadata: Dict[str, Any]

        class Retriever:
            def retrieve(self, query: str, top_k: int = 5) -> List[Hit]:
                return [Hit(content="hit", score=1.0, metadata={"rank": 1})]

        retrieve = dspy.Retrieve(retriever=Retriever(), k=1)
        result = retrieve("q")
        assert result.passages == ["hit"]
        assert result.metadata[0]["rank"] == 1

    def test_retrieve_callable_string_results(self) -> None:
        def retriever(query: str, k: int = 5) -> List[str]:
            return [f"{query}-a", f"{query}-b"]

        retrieve = dspy.Retrieve(retriever=retriever, k=2)
        result = retrieve("q")
        assert result.passages == ["q-a", "q-b"]

    def test_retrieve_callable_dict_results(self) -> None:
        def retriever(query: str, k: int = 5) -> List[Dict[str, Any]]:
            return [{"text": f"{query}-a", "score": 0.6}]

        retrieve = dspy.Retrieve(retriever=retriever, k=1)
        result = retrieve("q")
        assert result.passages == ["q-a"]
        assert result.scores == [0.6]

    def test_retrieve_async_search(self) -> None:
        class Retriever:
            def __init__(self) -> None:
                self.last_strategy = None
                self.last_top_k = None

            async def search(self, query: str, top_k: int = 5, strategy: Any = None) -> List[Dict[str, Any]]:
                self.last_strategy = strategy
                self.last_top_k = top_k
                return [{"content": query, "score": 0.7}]

        retriever = Retriever()
        retrieve = dspy.Retrieve(retriever=retriever, k=1, strategy="hybrid")
        result = retrieve("async")
        assert result.passages == ["async"]
        assert retriever.last_top_k == 1
        assert retriever.last_strategy is not None


class TestChainOfThought:
    def test_chain_of_thought_parses_reasoning(self) -> None:
        class Sig(dspy.Signature):
            context = dspy.InputField()
            question = dspy.InputField()
            answer = dspy.OutputField()

        responses = {
            "Answer:": "Reasoning: Think it through.\nAnswer: 42",
        }
        lm = dspy.MockLLM(responses=responses)
        cot = dspy.ChainOfThought(Sig, lm=lm)
        result = cot(context="ctx", question="q")
        assert result.reasoning == "Think it through."
        assert result.answer == "42"

    def test_chain_of_thought_no_lm(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        cot = dspy.ChainOfThought(Sig, lm=None)
        result = cot(question="q")
        assert "No LM configured" in result.answer

    def test_chain_of_thought_parses_json_output(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField(format="json")

        responses = {
            "Answer:": "Reasoning: ok\nAnswer: {\"items\": [\"a\"]}",
        }
        lm = dspy.MockLLM(responses=responses)
        cot = dspy.ChainOfThought(Sig, lm=lm)
        result = cot(question="q")
        assert result.answer == {"items": ["a"]}


class TestReAct:
    def test_extract_thought(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        react = dspy.ReAct(Sig)
        thought = react._extract_thought("Thought: hello\nAction: Finish[done]")
        assert thought == "hello"

    def test_extract_action(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        react = dspy.ReAct(Sig)
        action = react._extract_action("Action: Search[python]")
        assert action is not None
        assert action.type == dspy.ActionType.SEARCH
        assert action.input == "python"

    def test_react_executes_tool_and_finishes(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        class SequenceLLM:
            def __init__(self, responses: List[str]) -> None:
                self._responses = iter(responses)

            def generate(self, prompt: str, **kwargs: Any) -> str:
                return next(self._responses)

        def search_tool(query: str) -> str:
            return "Guido van Rossum"

        lm = SequenceLLM(
            [
                "Thought: need info\nAction: Search[python]",
                "Thought: done\nAction: Finish[Guido]",
            ]
        )
        react = dspy.ReAct(Sig, tools={"Search": search_tool}, lm=lm)
        result = react(question="Who invented Python?")
        assert result.answer == "Guido"
        assert result.trace.actions[0].output == "Guido van Rossum"

    def test_react_tool_error(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        responses = {
            "Begin!": "Thought: try tool\nAction: Search[data]",
            "Observation:": "Thought: done\nAction: Finish[ok]",
        }
        lm = dspy.MockLLM(responses=responses)

        def search_tool(_: str) -> str:
            raise ValueError("boom")

        react = dspy.ReAct(Sig, tools={"Search": search_tool}, lm=lm)
        result = react(question="q")
        assert result.trace.observations[0].startswith("Error:")

    def test_react_unknown_tool(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        react = dspy.ReAct(Sig, tools={})
        action = dspy.Action(type=dspy.ActionType.SEARCH, input="x")
        assert react._execute_action(action) == "Unknown tool: Search"


class TestUtilities:
    def test_make_signature(self) -> None:
        Sig = dspy.make_signature(
            "Answer questions",
            {"question": "The question"},
            {"answer": "The answer"},
        )
        assert issubclass(Sig, dspy.Signature)
        assert "question" in Sig._input_fields

    def test_compile_module_bootstrap(self) -> None:
        class Dummy(dspy.Module):
            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return dspy.Prediction(answer="ok")

        module = Dummy()
        trainset = [
            {"inputs": {"question": "q"}, "expected": {"answer": "ok"}},
        ]
        compiled = dspy.compile_module(module, trainset=trainset)
        assert compiled._compiled is True
        assert "demos" in compiled.parameters()

    def test_evaluate_accuracy(self) -> None:
        class Sig(dspy.Signature):
            question = dspy.InputField()
            answer = dspy.OutputField()

        class Echo(dspy.Module):
            def forward(self, **kwargs: Any) -> dspy.Prediction:
                return dspy.Prediction(answer=kwargs.get("question"))

        dataset = [
            {"inputs": {"question": "hi"}, "expected": {"answer": "hi"}},
        ]
        evaluator = dspy.Evaluate(devset=dataset, metric=dspy.exact_match, display_progress=False)
        results = evaluator(Echo())
        assert results.accuracy == 1.0
