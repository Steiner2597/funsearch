"""Tests for observability features."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from experiments.failure_taxonomy import FailureAnalyzer, FailureType
from experiments.metrics import GenerationMetrics, MetricsCollector


class TestGenerationMetrics:
    def test_metrics_serialization(self):
        metrics = GenerationMetrics(
            generation=1,
            best_score_cheap=10.5,
            avg_score_cheap=12.3,
            best_score_full=9.8,
            avg_score_full=11.2,
            n_generated=50,
            n_deduped=5,
            n_failed=3,
            failure_breakdown={"timeout": 2, "syntax_error": 1},
            eval_time_ms=1500.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        data = metrics.to_dict()
        assert data['generation'] == 1
        assert data['best_score_cheap'] == 10.5
        assert 'timestamp' in data


class TestMetricsCollector:
    def test_record_and_export_jsonl(self):
        collector = MetricsCollector()
        
        metrics1 = GenerationMetrics(
            generation=0, best_score_cheap=15.0, avg_score_cheap=18.0,
            best_score_full=None, avg_score_full=None,
            n_generated=10, n_deduped=0, n_failed=0,
            failure_breakdown={}, eval_time_ms=500.0,
            timestamp=datetime.now(timezone.utc)
        )
        metrics2 = GenerationMetrics(
            generation=1, best_score_cheap=12.0, avg_score_cheap=16.0,
            best_score_full=11.5, avg_score_full=15.0,
            n_generated=10, n_deduped=1, n_failed=1,
            failure_breakdown={"timeout": 1}, eval_time_ms=800.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        collector.record_generation(metrics1)
        collector.record_generation(metrics2)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "metrics.jsonl"
            collector.export_jsonl(jsonl_path)
            
            assert jsonl_path.exists()
            lines = jsonl_path.read_text().strip().split('\n')
            assert len(lines) == 2
            
            data1 = json.loads(lines[0])
            assert data1['generation'] == 0
            assert data1['best_score_cheap'] == 15.0
    
    def test_export_csv(self):
        collector = MetricsCollector()
        
        metrics = GenerationMetrics(
            generation=0, best_score_cheap=15.0, avg_score_cheap=18.0,
            best_score_full=None, avg_score_full=None,
            n_generated=10, n_deduped=0, n_failed=0,
            failure_breakdown={}, eval_time_ms=500.0,
            timestamp=datetime.now(timezone.utc)
        )
        collector.record_generation(metrics)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "metrics.csv"
            collector.export_csv(csv_path)
            
            assert csv_path.exists()
            content = csv_path.read_text()
            assert 'generation' in content
            assert 'best_score_cheap' in content


class TestFailureAnalyzer:
    def test_classify_timeout(self):
        analyzer = FailureAnalyzer()
        assert analyzer.classify_error("Execution timed out") == FailureType.TIMEOUT
    
    def test_classify_import_blocked(self):
        analyzer = FailureAnalyzer()
        assert analyzer.classify_error("Import blocked: socket") == FailureType.IMPORT_BLOCKED
    
    def test_classify_syntax_error(self):
        analyzer = FailureAnalyzer()
        assert analyzer.classify_error("SyntaxError: invalid syntax") == FailureType.SYNTAX_ERROR
    
    def test_record_and_get_stats(self):
        analyzer = FailureAnalyzer()
        analyzer.record_failure("Execution timed out")
        analyzer.record_failure("Execution timed out")
        analyzer.record_failure("SyntaxError: invalid syntax")
        
        stats = analyzer.get_failure_stats()
        assert stats[FailureType.TIMEOUT] == 2
        assert stats[FailureType.SYNTAX_ERROR] == 1
    
    def test_get_top_failures(self):
        analyzer = FailureAnalyzer()
        analyzer.record_failure("timeout")
        analyzer.record_failure("timeout")
        analyzer.record_failure("timeout")
        analyzer.record_failure("syntax error")
        
        top = analyzer.get_top_failures(n=2)
        assert len(top) == 2
        assert top[0][0] == "timeout"
        assert top[0][1] == 3


class TestPlotting:
    def test_plot_generation_skipped_if_no_matplotlib(self):
        pytest.importorskip("matplotlib")
        
        from experiments.plotting import PlotGenerator
        
        plotter = PlotGenerator()
        
        metrics_data = [
            {'generation': 0, 'best_score_cheap': 15.0, 'avg_score_cheap': 18.0,
             'best_score_full': None, 'avg_score_full': None},
            {'generation': 1, 'best_score_cheap': 12.0, 'avg_score_cheap': 16.0,
             'best_score_full': 11.5, 'avg_score_full': 15.0},
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            plot_path = Path(tmpdir) / "evolution.png"
            plotter.plot_evolution_curve(metrics_data, plot_path)
            
            assert plot_path.exists()
            assert plot_path.stat().st_size > 0
