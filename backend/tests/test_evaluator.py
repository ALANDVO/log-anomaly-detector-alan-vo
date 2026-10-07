import pytest
from app.services.evaluator import ModelEvaluator, BENCHMARK_DATASET
from app.core.database import init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_evaluator_benchmark_metrics():
    res = ModelEvaluator.run_benchmark()
    assert res.sample_count == len(BENCHMARK_DATASET)
    assert 0.0 <= res.precision <= 1.0
    assert 0.0 <= res.recall <= 1.0
    assert 0.0 <= res.f1_score <= 1.0
    assert res.true_positives + res.false_positives + res.true_negatives + res.false_negatives == res.sample_count
    assert res.latency_ms_per_item > 0
    assert len(res.limitations) >= 3

def test_benchmark_dataset_integrity():
    for item in BENCHMARK_DATASET:
        assert "id" in item
        assert "service" in item
        assert "level" in item
        assert "message" in item
        assert isinstance(item["is_ground_truth_anomaly"], bool)
        assert "category" in item
