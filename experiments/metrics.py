"""Metrics collection and tracking for FunSearch experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class GenerationMetrics:
    generation: int
    best_score_cheap: float | None
    avg_score_cheap: float | None
    best_score_full: float | None
    avg_score_full: float | None
    n_generated: int
    n_deduped: int
    n_failed: int
    failure_breakdown: dict[str, int]
    eval_time_ms: float
    timestamp: datetime
    
    def to_dict(self) -> dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class MetricsCollector:
    def __init__(self):
        self.generations: list[GenerationMetrics] = []
    
    def record_generation(self, metrics: GenerationMetrics) -> None:
        self.generations.append(metrics)
    
    def export_jsonl(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            for gen_metrics in self.generations:
                json.dump(gen_metrics.to_dict(), f)
                f.write('\n')
    
    def export_csv(self, path: str | Path) -> None:
        import csv
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.generations:
            return
        
        fieldnames = [
            'generation', 'best_score_cheap', 'avg_score_cheap',
            'best_score_full', 'avg_score_full', 'n_generated',
            'n_deduped', 'n_failed', 'eval_time_ms', 'timestamp'
        ]
        
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for gen_metrics in self.generations:
                row = gen_metrics.to_dict()
                row.pop('failure_breakdown', None)
                writer.writerow(row)
    
    def get_evolution_data(self) -> list[dict]:
        return [m.to_dict() for m in self.generations]
