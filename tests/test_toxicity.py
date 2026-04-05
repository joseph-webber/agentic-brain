from agentic_brain.guardrails.toxicity import ToxicityDetector


def test_detect_toxic_word():
    t = ToxicityDetector()
    assert "idiot" in t.detect_toxicity("you are an idiot")


def test_is_toxic():
    t = ToxicityDetector()
    assert t.is_toxic("so stupid")


def test_sanitize_masks():
    t = ToxicityDetector()
    s = t.sanitize("you are an asshole")
    assert "asshole" not in s


def test_case_insensitive():
    t = ToxicityDetector()
    assert t.is_toxic("IDIoT")


def test_multiple_hits_unique():
    t = ToxicityDetector()
    hits = t.detect_toxicity("you are an idiot and an idiot")
    assert hits.count("idiot") == 1


def test_empty_text():
    t = ToxicityDetector()
    assert t.detect_toxicity("") == []
