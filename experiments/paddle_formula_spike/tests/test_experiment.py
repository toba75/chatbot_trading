from experiments.paddle_formula_spike.experiment import assess_prediction


def test_assess_prediction_requires_tokens_and_structure() -> None:
    record = {
        "source_tokens": ["x", "2"],
        "source_signature": ["x", "<sup>", "2", "</sup>"],
    }

    assert assess_prediction(record, "x^{2}")["paddle_exact"] is True
    assert assess_prediction(record, "x_{2}")["paddle_exact"] is False


def test_assess_prediction_rejects_an_invalid_candidate() -> None:
    record = {"source_tokens": ["x"], "source_signature": ["x"]}

    result = assess_prediction(record, "\\unknowncommand{x}")

    assert result["paddle_exact"] is False
