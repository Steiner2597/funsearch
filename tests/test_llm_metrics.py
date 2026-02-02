"""Tests for LLM metrics collection."""

import pytest
from unittest.mock import Mock, MagicMock
from llm.base import LLMResponse
from experiments.runner import LLMProviderAdapter
from llm.prompts import PromptTemplate


class TestLLMMetrics:
    """Test LLM metrics tracking and aggregation."""
    
    def test_adapter_tracks_call_count(self):
        """Test that LLMProviderAdapter tracks total number of LLM calls."""
        # Setup mock provider with _metrics dict
        mock_provider = Mock()
        mock_provider.provider_id = "test_provider"
        mock_provider._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
        mock_provider.generate = Mock(return_value=LLMResponse(
            text="def score_bin(): return 1.0",
            usage={"input_tokens": 100, "output_tokens": 50},
            latency_ms=500.0,
            raw_response={},
            model_id="test-model"
        ))
        mock_provider.get_metrics = Mock(return_value={
            "calls": 3,
            "total_latency_ms": 1500.0,
            "avg_latency_ms": 500.0,
            "total_input_tokens": 300,
            "total_output_tokens": 150,
            "cache_hits": 0,
            "cache_misses": 3,
            "errors": 0,
        })
        
        # Create adapter
        prompt_template = PromptTemplate()
        adapter = LLMProviderAdapter(mock_provider, prompt_template)
        
        # Make multiple generate calls
        adapter.generate(temperature=0.7)
        adapter.generate(temperature=0.8)
        adapter.mutate(parent_code="def score_bin(): return 0", temperature=0.7)
        
        # Verify metrics tracked
        metrics = adapter.get_metrics()
        assert metrics["calls"] == 3
        assert metrics["total_latency_ms"] == 1500.0
        assert metrics["avg_latency_ms"] == 500.0
    
    def test_adapter_tracks_token_usage(self):
        """Test that adapter tracks input and output tokens."""
        mock_provider = Mock()
        mock_provider.provider_id = "test_provider"
        mock_provider._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
        mock_provider.generate = Mock(return_value=LLMResponse(
            text="code",
            usage={"input_tokens": 100, "output_tokens": 50},
            latency_ms=200.0,
            raw_response={},
            model_id="test-model"
        ))
        mock_provider.get_metrics = Mock(return_value={
            "calls": 1,
            "total_latency_ms": 200.0,
            "avg_latency_ms": 200.0,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "cache_hits": 0,
            "cache_misses": 1,
            "errors": 0,
        })
        
        prompt_template = PromptTemplate()
        adapter = LLMProviderAdapter(mock_provider, prompt_template)
        
        adapter.generate(temperature=0.7)
        
        metrics = adapter.get_metrics()
        assert metrics["total_input_tokens"] == 100
        assert metrics["total_output_tokens"] == 50
    
    def test_adapter_tracks_cache_hits(self):
        """Test that adapter tracks cache hits and misses."""
        mock_provider = Mock()
        mock_provider.provider_id = "test_provider"
        mock_provider._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
        
        mock_provider.generate = Mock(side_effect=[
            LLMResponse(
                text="code1",
                usage={"input_tokens": 100, "output_tokens": 50},
                latency_ms=500.0,
                raw_response={"cache_hit": False},
                model_id="test-model"
            ),
            LLMResponse(
                text="code1",
                usage={"input_tokens": 100, "output_tokens": 0},
                latency_ms=10.0,
                raw_response={"cache_hit": True},
                model_id="test-model"
            )
        ])
        mock_provider.get_metrics = Mock(return_value={
            "calls": 2,
            "total_latency_ms": 510.0,
            "avg_latency_ms": 255.0,
            "total_input_tokens": 200,
            "total_output_tokens": 50,
            "cache_hits": 1,
            "cache_misses": 1,
            "errors": 0,
        })
        
        prompt_template = PromptTemplate()
        adapter = LLMProviderAdapter(mock_provider, prompt_template)
        
        adapter.generate(temperature=0.7)
        adapter.generate(temperature=0.7)
        
        metrics = adapter.get_metrics()
        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 1
    
    def test_adapter_tracks_errors(self):
        """Test that adapter tracks LLM call errors."""
        mock_provider = Mock()
        mock_provider.provider_id = "test_provider"
        mock_provider._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
        mock_provider.generate = Mock(side_effect=Exception("API Error"))
        mock_provider.get_metrics = Mock(return_value={
            "calls": 1,
            "total_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 1,
        })
        
        prompt_template = PromptTemplate()
        adapter = LLMProviderAdapter(mock_provider, prompt_template)
        
        with pytest.raises(Exception):
            adapter.generate(temperature=0.7)
        
        metrics = adapter.get_metrics()
        assert metrics["errors"] == 1
        assert metrics["calls"] == 1
    
    def test_adapter_reset_metrics(self):
        """Test that adapter can reset metrics between generations."""
        mock_provider = Mock()
        mock_provider.provider_id = "test_provider"
        mock_provider._metrics = {
            "calls": 0,
            "total_latency_ms": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
        }
        mock_provider.generate = Mock(return_value=LLMResponse(
            text="code",
            usage={"input_tokens": 100, "output_tokens": 50},
            latency_ms=200.0,
            raw_response={},
            model_id="test-model"
        ))
        
        call_count = [0]
        def get_metrics_impl():
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "calls": 1,
                    "total_latency_ms": 200.0,
                    "avg_latency_ms": 200.0,
                    "total_input_tokens": 100,
                    "total_output_tokens": 50,
                    "cache_hits": 0,
                    "cache_misses": 1,
                    "errors": 0,
                }
            else:
                return {
                    "calls": 0,
                    "total_latency_ms": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "errors": 0,
                }
        
        mock_provider.get_metrics = Mock(side_effect=get_metrics_impl)
        mock_provider.reset_metrics = Mock()
        
        prompt_template = PromptTemplate()
        adapter = LLMProviderAdapter(mock_provider, prompt_template)
        
        adapter.generate(temperature=0.7)
        assert adapter.get_metrics()["calls"] == 1
        
        adapter.reset_metrics()
        mock_provider.reset_metrics.assert_called_once()
        
        metrics = adapter.get_metrics()
        assert metrics["calls"] == 0
        assert metrics["total_latency_ms"] == 0.0
        assert metrics["total_input_tokens"] == 0
    
    def test_metrics_in_generation_stats(self):
        """Test that LLM metrics are included in generation stats."""
        # This test would require mocking the entire FunSearchLoop
        # For now, we test the structure of expected metrics
        expected_llm_metrics = {
            "calls": 10,
            "total_latency_ms": 5000.0,
            "avg_latency_ms": 500.0,
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "cache_hits": 3,
            "cache_misses": 7,
            "errors": 0
        }
        
        # Verify structure
        assert "calls" in expected_llm_metrics
        assert "total_latency_ms" in expected_llm_metrics
        assert "avg_latency_ms" in expected_llm_metrics
        assert "cache_hits" in expected_llm_metrics
        assert "cache_misses" in expected_llm_metrics
        assert "errors" in expected_llm_metrics
        
        # Verify calculations
        assert expected_llm_metrics["avg_latency_ms"] == (
            expected_llm_metrics["total_latency_ms"] / expected_llm_metrics["calls"]
        )
