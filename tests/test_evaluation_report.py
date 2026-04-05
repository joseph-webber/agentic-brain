from agentic_brain.evaluation.report import EvaluationReport


def test_report_add_and_summary():
    r = EvaluationReport()
    r.add_item({"id":"1","answer_similarity":1.0,"context_precision":1.0})
    r.add_item({"id":"2","answer_similarity":0.0,"context_precision":0.0})
    s = r.summary()
    assert s["answer_similarity"] == 0.5
    assert s["context_precision"] == 0.5


def test_report_to_markdown_contains_summary():
    r = EvaluationReport()
    r.add_item({"id":"1","answer_similarity":1.0})
    md = r.to_markdown()
    assert "# Evaluation Report" in md
