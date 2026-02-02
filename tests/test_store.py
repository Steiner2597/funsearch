from pathlib import Path

from store.repository import Candidate, CandidateStore, EvaluationResult


def test_deduplication_normalizes_code(tmp_path: Path) -> None:
    store = CandidateStore(run_id="run-1", config={"name": "test"}, seed=1, base_dir=tmp_path)
    code_a = """
    import os
    import sys

    def foo():
        return 1
    """
    code_b = """
    import sys
    import os
    def foo():
            return 1
    """
    candidate_a = Candidate(
        id="cand-a",
        run_id="run-1",
        code=code_a,
        code_hash="",
        parent_id=None,
        generation=0,
        model_id="model-x",
    )
    candidate_b = Candidate(
        id="cand-b",
        run_id="run-1",
        code=code_b,
        code_hash="",
        parent_id=None,
        generation=0,
        model_id="model-x",
    )
    assert store.save_candidate(candidate_a) is True
    assert store.save_candidate(candidate_b) is False


def test_top_k_returns_sorted_candidates(tmp_path: Path) -> None:
    store = CandidateStore(run_id="run-2", config={"name": "test"}, seed=2, base_dir=tmp_path)
    candidates = [
        Candidate(
            id="cand-1",
            run_id="run-2",
            code="def foo():\n    return 1",
            code_hash="",
            parent_id=None,
            generation=0,
            model_id="model-x",
        ),
        Candidate(
            id="cand-2",
            run_id="run-2",
            code="def bar():\n    return 2",
            code_hash="",
            parent_id=None,
            generation=0,
            model_id="model-x",
        ),
        Candidate(
            id="cand-3",
            run_id="run-2",
            code="def baz():\n    return 3",
            code_hash="",
            parent_id=None,
            generation=0,
            model_id="model-x",
        ),
    ]
    for candidate in candidates:
        assert store.save_candidate(candidate) is True

    store.record_evaluation(
        EvaluationResult(candidate_id="cand-1", fidelity="full", score=0.1, runtime_ms=10.0)
    )
    store.record_evaluation(
        EvaluationResult(candidate_id="cand-2", fidelity="full", score=0.9, runtime_ms=12.0)
    )
    store.record_evaluation(
        EvaluationResult(candidate_id="cand-3", fidelity="full", score=0.5, runtime_ms=11.0)
    )

    top_candidates = store.get_top_k("run-2", "full", 2)
    assert [candidate.id for candidate in top_candidates] == ["cand-2", "cand-3"]


def test_duplicate_code_hash_rejected(tmp_path: Path) -> None:
    store = CandidateStore(run_id="run-3", config={"name": "test"}, seed=3, base_dir=tmp_path)
    code = "def foo():\n    return 1"
    candidate_a = Candidate(
        id="cand-a",
        run_id="run-3",
        code=code,
        code_hash="",
        parent_id=None,
        generation=0,
        model_id="model-x",
    )
    candidate_b = Candidate(
        id="cand-b",
        run_id="run-3",
        code=code,
        code_hash="",
        parent_id=None,
        generation=0,
        model_id="model-x",
    )
    assert store.save_candidate(candidate_a) is True
    assert store.save_candidate(candidate_b) is False
