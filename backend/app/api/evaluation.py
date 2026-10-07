from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Request

from app.core.security import get_current_user, require_role, verify_csrf
from app.models.schemas import BenchmarkResultResponse
from app.services.evaluator import ModelEvaluator, BENCHMARK_DATASET
from app.services.audit import AuditService

router = APIRouter(prefix="/api/evaluation", tags=["ML Evaluation"])

@router.get("/benchmark", response_model=BenchmarkResultResponse)
async def get_or_run_benchmark(user: dict = Depends(get_current_user)):
    """Executes the reproducible benchmark evaluation and returns precision, recall, F1, and baseline metrics."""
    return ModelEvaluator.run_benchmark()

@router.post("/benchmark", response_model=BenchmarkResultResponse)
async def run_benchmark_action(
    request: Request,
    user: dict = Depends(require_role("analyst")),
    _csrf: None = Depends(verify_csrf)
):
    """
    Explicitly triggers the benchmark pipeline on the labeled ground-truth dataset.
    Audited mutation requiring analyst role.
    """
    res = ModelEvaluator.run_benchmark()

    AuditService.record(
        user_id=user["id"],
        username=user["username"],
        action="run_ml_benchmark",
        entity_type="evaluation_run",
        entity_id=res.run_id,
        ip_address=request.client.host if request.client else "127.0.0.1",
        details=f"F1 score: {res.f1_score:.4f} (baseline: {res.baseline_f1:.4f})"
    )

    return res

@router.get("/dataset")
async def get_dataset_info(user: dict = Depends(get_current_user)):
    """Returns dataset provenance, distribution, and sample schema."""
    anomalies = sum(1 for item in BENCHMARK_DATASET if item["is_ground_truth_anomaly"])
    normals = len(BENCHMARK_DATASET) - anomalies
    categories = list(set(item["category"] for item in BENCHMARK_DATASET))

    return {
        "dataset_name": "CloudMicroservice-Benchmark-v1",
        "description": "Curated distributed system and cloud microservice log traces with verified ground-truth labels.",
        "sample_count": len(BENCHMARK_DATASET),
        "ground_truth_anomalies": anomalies,
        "ground_truth_nominal": normals,
        "categories": categories,
        "samples": BENCHMARK_DATASET[:10]
    }
