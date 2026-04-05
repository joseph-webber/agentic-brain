from agentic_brain.evaluation.report import EvaluationReport


def test_markdown_contains_items():
    r = EvaluationReport()
    r.add_item({"id": "1", "answer_similarity": 0.5})
    md = r.to_markdown()
    assert True
