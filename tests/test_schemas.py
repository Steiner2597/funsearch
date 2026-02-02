from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from funsearch_core.schemas import Candidate, RunConfig


def test_candidate_create_and_serialize() -> None:
    candidate = Candidate(
        id="cand-1",
        code="def foo():\n    return 1",
        score=1.23,
        signature="sig-1",
        parent_id=None,
        generation=0,
        runtime_ms=12.3,
        error_type=None,
        model_id="model-x",
        eval_metadata={"fidelity": "cheap", "metric": 1},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    json_payload = candidate.to_json()
    restored = Candidate.from_json(json_payload)

    assert restored.to_dict() == candidate.to_dict()
    assert restored.created_at.tzinfo is not None
    assert restored.created_at.utcoffset() == timezone.utc.utcoffset(restored.created_at)


def test_runconfig_load_from_dict() -> None:
    data: dict[str, object] = {
        "run_id": "run-123",
        "seed": 42,
        "max_generations": 5,
        "population_size": 10,
        "num_islands": 2,
        "top_k_for_full_eval": 3,
        "generator_provider_id": "gen-llm",
        "refiner_provider_id": "refiner-llm",
        "task_name": "bin_packing",
    }

    config = RunConfig.from_dict(data)

    assert config.to_dict() == data


def test_candidate_generation_validation() -> None:
    with pytest.raises(ValidationError):
        _ = Candidate(
            id="cand-2",
            code="def bar():\n    return 2",
            score=None,
            signature="sig-2",
            parent_id=None,
            generation=-1,
            runtime_ms=None,
            error_type=None,
            model_id="model-y",
            eval_metadata={"fidelity": "cheap"},
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
