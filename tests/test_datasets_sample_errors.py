from agentic_brain.evaluation.datasets import Dataset
import pytest


def test_dataset_sample_too_many():
    ds = Dataset()
    with pytest.raises(ValueError):
        ds.sample(1)
