import importlib.util
from pathlib import Path

import pytest

from funsearch_core.schemas import LLMProviderConfig
from llm.cache import LLMCache
from llm.providers import FakeProvider, OpenAIProvider, create_provider
from llm.prompts import NoveltyPromptTemplate, PromptTemplate, get_prompt_template
from llm.retry import RetryPolicy


# --- Prompt Template Tests ---


def test_prompt_template_generate_fresh() -> None:
    """Test that PromptTemplate.generate_fresh_candidate returns expected content."""
    template = PromptTemplate()
    prompt = template.generate_fresh_candidate()

    assert "score_bin" in prompt
    assert "bin packing" in prompt.lower()
    assert "```python" in prompt


def test_prompt_template_mutate() -> None:
    """Test that PromptTemplate.mutate_candidate includes parent code."""
    template = PromptTemplate()
    parent_code = "def score_bin(item_size, remaining_capacity, bin_index, step):\n    return remaining_capacity"
    prompt = template.mutate_candidate(parent_code)

    assert "score_bin" in prompt
    assert "remaining_capacity" in prompt
    assert "Mutate" in prompt or "mutate" in prompt.lower()


def test_prompt_template_refine() -> None:
    """Test that PromptTemplate.refine_candidate handles multiple candidates and failures."""
    template = PromptTemplate()
    codes = [
        "def score_bin(item_size, remaining_capacity, bin_index, step): return 1.0",
        "def score_bin(item_size, remaining_capacity, bin_index, step): return 2.0",
    ]
    failures = ["Fails on large items", "Too slow"]
    prompt = template.refine_candidate(codes, failures)

    assert "Candidate 1" in prompt
    assert "Candidate 2" in prompt
    assert "Fails on large items" in prompt
    assert "Too slow" in prompt


def test_novelty_prompt_template_emphasizes_creativity() -> None:
    """Test that NoveltyPromptTemplate includes novelty-focused language."""
    template = NoveltyPromptTemplate()
    prompt = template.generate_fresh_candidate()

    # Should contain novelty-focused keywords
    assert any(
        keyword in prompt.upper()
        for keyword in ["CREATIVE", "UNCONVENTIONAL", "NOVEL", "UNUSUAL"]
    )
    assert "score_bin" in prompt


def test_novelty_prompt_template_mutate_is_radical() -> None:
    """Test that NoveltyPromptTemplate.mutate emphasizes radical changes."""
    template = NoveltyPromptTemplate()
    parent_code = "def score_bin(item_size, remaining_capacity, bin_index, step): return 1.0"
    prompt = template.mutate_candidate(parent_code)

    # Should emphasize radical transformation
    assert any(
        keyword in prompt.lower()
        for keyword in ["radical", "completely different", "unconventional"]
    )


def test_get_prompt_template_default() -> None:
    """Test that get_prompt_template returns PromptTemplate by default."""
    template = get_prompt_template()
    assert isinstance(template, PromptTemplate)
    assert not isinstance(template, NoveltyPromptTemplate)


def test_get_prompt_template_variant_a() -> None:
    """Test that get_prompt_template('A') returns standard PromptTemplate."""
    template = get_prompt_template("A")
    assert isinstance(template, PromptTemplate)
    assert not isinstance(template, NoveltyPromptTemplate)


def test_get_prompt_template_variant_b() -> None:
    """Test that get_prompt_template('B') returns NoveltyPromptTemplate."""
    template = get_prompt_template("B")
    assert isinstance(template, NoveltyPromptTemplate)


def test_get_prompt_template_none() -> None:
    """Test that get_prompt_template(None) returns standard PromptTemplate."""
    template = get_prompt_template(None)
    assert isinstance(template, PromptTemplate)
    assert not isinstance(template, NoveltyPromptTemplate)


# --- Provider Tests ---


def test_fake_provider_returns_deterministic_response() -> None:
    provider = FakeProvider(provider_id="fake-1", model_name="fake-model")
    response_a = provider.generate("prompt", temperature=0.3, max_tokens=64)
    response_b = provider.generate("prompt", temperature=0.3, max_tokens=64)

    assert response_a.text == response_b.text
    assert response_a.model_id == "fake-model"
    assert response_a.usage["prompt_tokens"] > 0


def test_cache_hit_returns_same_response_without_api_call(tmp_path: Path) -> None:
    cache = LLMCache(run_id="run-1", base_dir=tmp_path)
    provider = FakeProvider(provider_id="fake-1")
    prompt = "cache prompt"

    response_a = cache.get_or_generate(provider, prompt, temperature=0.2, max_tokens=32)
    assert provider.call_count == 1

    response_b = cache.get_or_generate(provider, prompt, temperature=0.2, max_tokens=32)
    assert provider.call_count == 1
    assert response_a.text == response_b.text


def test_provider_selection_by_config() -> None:
    fake_config = LLMProviderConfig(
        provider_id="fake-1",
        provider_type="fake",
        model_name="fake-model",
    )
    provider = create_provider(fake_config)
    assert isinstance(provider, FakeProvider)

    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai package not installed")

    openai_config = LLMProviderConfig(
        provider_id="openai-1",
        provider_type="openai",
        model_name="gpt-4o-mini",
        api_key="test-key",
    )
    openai_provider = create_provider(openai_config)
    assert isinstance(openai_provider, OpenAIProvider)


def test_retry_policy_retries_on_timeout() -> None:
    attempts = {"count": 0}

    def flaky_call() -> str:
        if attempts["count"] < 2:
            attempts["count"] += 1
            raise TimeoutError("timeout")
        return "ok"

    policy = RetryPolicy(max_retries=3, sleep_fn=lambda _: None)
    assert policy.execute(flaky_call) == "ok"
    assert attempts["count"] == 2
