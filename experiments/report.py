import json
import base64
from pathlib import Path
from datetime import datetime
import yaml

class ReportGenerator:
    def __init__(self, metrics_path: Path, plots_dir: Path, config: dict):
        self.metrics_path = Path(metrics_path)
        self.plots_dir = Path(plots_dir)
        self.config = config
        self.metrics = self._load_metrics()
        self.kpis = self._calculate_kpis()

    def _load_metrics(self) -> list[dict]:
        metrics = []
        if self.metrics_path.exists():
            with open(self.metrics_path, "r") as f:
                for line in f:
                    if line.strip():
                        metrics.append(json.loads(line))
        return metrics

    def _calculate_kpis(self) -> dict:
        if not self.metrics:
            return {}

        best_scores = [m["overall"]["best_score"] for m in self.metrics if m["overall"]["best_score"] is not None]
        best_score = max(best_scores) if best_scores else None
        
        # Time to best (generation where best score was first achieved)
        time_to_best = None
        if best_score is not None:
            for m in self.metrics:
                if m["overall"]["best_score"] == best_score:
                    time_to_best = m["generation"]
                    break

        last_metric = self.metrics[-1] if self.metrics else {}
        if "dedup" in last_metric and isinstance(last_metric["dedup"], dict):
            total_dedup_skipped = last_metric["dedup"].get("skipped_total", 0)
        else:
            total_dedup_skipped = last_metric.get("dedup_skipped_total", 0)
        num_islands = self.config.get("num_islands", 1)
        population_size = self.config.get("population_size", 1)
        total_generations = len(self.metrics)
        total_candidates_attempted = total_generations * num_islands * population_size
        
        unique_rate = 1.0 - (total_dedup_skipped / total_candidates_attempted) if total_candidates_attempted > 0 else 1.0

        # Final diversity (using overall count as a proxy for population size/diversity)
        final_diversity = self.metrics[-1]["overall"]["count"] if self.metrics else 0

        return {
            "best_score": best_score,
            "unique_rate": unique_rate,
            "time_to_best": time_to_best,
            "final_diversity": final_diversity,
            "total_dedup_skipped": total_dedup_skipped,
            "total_candidates_attempted": total_candidates_attempted
        }

    def generate_markdown(self, output_path: Path) -> None:
        output_path = Path(output_path)
        
        # Run Summary
        run_id = self.config.get("run_id", "N/A")
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task = self.config.get("task_name", self.config.get("task", "N/A"))
        dataset = self.config.get("dataset", "N/A")

        # Evolution Analysis
        start_score = self.metrics[0].get("overall", {}).get("best_score", "N/A") if self.metrics else "N/A"
        end_score = self.metrics[-1].get("overall", {}).get("best_score", "N/A") if self.metrics else "N/A"

        # Per-Island Performance
        island_rows = []
        if self.metrics:
            last_gen = self.metrics[-1]
            for island_id, data in last_gen.get("islands", {}).items():
                best = data.get('best_score')
                avg = data.get('avg_score')
                best_str = f"{best:.4f}" if best is not None else "N/A"
                avg_str = f"{avg:.4f}" if avg is not None else "N/A"
                island_rows.append(f"| {island_id} | {best_str} | {avg_str} | {data.get('count', 0)} |")

        # Deduplication Statistics
        dedup_skipped = self.kpis.get("total_dedup_skipped", 0)
        total_attempted = self.kpis.get("total_candidates_attempted", 0)
        dedup_percent = (dedup_skipped / total_attempted * 100) if total_attempted > 0 else 0

        improvement = "N/A"
        if isinstance(start_score, (int, float)) and isinstance(end_score, (int, float)):
            improvement = f"{end_score - start_score:.4f}"

        island_table = "\n".join(island_rows)
        
        md_content = f"""# FunSearch Experiment Report

## Run Summary
- **Run ID:** {run_id}
- **Date:** {date}
- **Task:** {task}
- **Dataset:** {dataset}

## Key Performance Indicators
| Metric | Value | Note |
|--------|-------|------|
| Best Score | {self.kpis.get('best_score', 'N/A')} | Higher = better (negated bins) |
| Unique Rate | {self.kpis.get('unique_rate', 0):.2%} | |
| Generations to Best | {self.kpis.get('time_to_best', 'N/A')} | |
| Final Diversity | {self.kpis.get('final_diversity', 0)} | |

## Evolution Analysis
- **Starting Best Score:** {start_score}
- **Ending Best Score:** {end_score}
- **Improvement:** {improvement}

## Per-Island Performance
| Island ID | Best Score | Avg Score | Count |
|-----------|------------|-----------|-------|
{island_table}

## Deduplication Statistics
- **Total Candidates Attempted:** {total_attempted}
- **Duplicates Skipped:** {dedup_skipped}
- **Deduplication Efficiency:** {dedup_percent:.2f}%

## Configuration
```yaml
{yaml.dump(self.config, default_flow_style=False)}
```
"""
        output_path.write_text(md_content)

    def generate_html(self, output_path: Path) -> None:
        output_path = Path(output_path)
        
        # Embed images as base64
        embedded_images = []
        if self.plots_dir.exists():
            # Sort to ensure consistent order (e.g. evolution first)
            plot_files = sorted(list(self.plots_dir.glob("*.png")))
            for plot_file in plot_files:
                with open(plot_file, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    title = plot_file.stem.replace("_", " ").title()
                    embedded_images.append(f'<div class="plot-card"><h3>{title}</h3><img src="data:image/png;base64,{encoded}" alt="{plot_file.name}"></div>')

        # Run Summary
        run_id = self.config.get("run_id", "N/A")
        date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task = self.config.get("task_name", self.config.get("task", "N/A"))
        dataset = self.config.get("dataset", "N/A")

        # Evolution Analysis
        start_score = self.metrics[0].get("overall", {}).get("best_score", "N/A") if self.metrics else "N/A"
        end_score = self.metrics[-1].get("overall", {}).get("best_score", "N/A") if self.metrics else "N/A"
        
        improvement = "N/A"
        if isinstance(start_score, (int, float)) and isinstance(end_score, (int, float)):
            improvement = f"{end_score - start_score:.4f}"

        # Per-Island Performance
        island_rows = []
        if self.metrics:
            last_gen = self.metrics[-1]
            for island_id, data in last_gen.get("islands", {}).items():
                best = data.get('best_score')
                avg = data.get('avg_score')
                best_str = f"{best:.4f}" if best is not None else "N/A"
                avg_str = f"{avg:.4f}" if avg is not None else "N/A"
                island_rows.append(f"<tr><td>{island_id}</td><td>{best_str}</td><td>{avg_str}</td><td>{data.get('count', 0)}</td></tr>")

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FunSearch Experiment Report - {run_id}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; padding: 20px; background-color: #f4f7f6; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        section {{ background: white; padding: 25px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #eee; padding: 12px; text-align: left; }}
        th {{ background-color: #f8f9fa; color: #2c3e50; font-weight: 600; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        .config {{ background-color: #2c3e50; color: #ecf0f1; padding: 20px; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; font-size: 14px; line-height: 1.4; }}
        .plot-card {{ margin-bottom: 30px; text-align: center; }}
        img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 5px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
        .kpi-container {{ display: flex; flex-wrap: wrap; gap: 20px; margin-bottom: 10px; }}
        .kpi-card {{ flex: 1; min-width: 200px; background: #fff; border-top: 4px solid #3498db; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); text-align: center; }}
        .kpi-value {{ font-size: 28px; font-weight: bold; color: #2c3e50; margin-top: 10px; }}
        .kpi-label {{ font-size: 12px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; }}
        .summary-list {{ list-style: none; padding: 0; }}
        .summary-list li {{ margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #eee; }}
        .summary-list li:last-child {{ border-bottom: none; }}
        .summary-list strong {{ color: #2c3e50; width: 120px; display: inline-block; }}
    </style>
</head>
<body>
    <header style="margin-bottom: 40px; text-align: center;">
        <h1>FunSearch Experiment Report</h1>
        <p style="color: #7f8c8d;">Generated on {date}</p>
    </header>
    
    <section>
        <h2>Run Summary</h2>
        <ul class="summary-list">
            <li><strong>Run ID:</strong> {run_id}</li>
            <li><strong>Task:</strong> {task}</li>
            <li><strong>Dataset:</strong> {dataset}</li>
        </ul>
    </section>

    <section style="background: transparent; box-shadow: none; padding: 0;">
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Best Score</div>
                <div class="kpi-value">{self.kpis.get('best_score', 'N/A')}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Unique Rate</div>
                <div class="kpi-value">{self.kpis.get('unique_rate', 0):.2%}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Generations to Best</div>
                <div class="kpi-value">{self.kpis.get('time_to_best', 'N/A')}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Final Diversity</div>
                <div class="kpi-value">{self.kpis.get('final_diversity', 0)}</div>
            </div>
        </div>
    </section>

    <section>
        <h2>Evolution Analysis</h2>
        <div style="display: flex; justify-content: space-between; text-align: center;">
            <div style="flex: 1;">
                <div class="kpi-label">Starting Best</div>
                <div style="font-size: 20px; font-weight: 600;">{start_score}</div>
            </div>
            <div style="flex: 1; border-left: 1px solid #eee; border-right: 1px solid #eee;">
                <div class="kpi-label">Ending Best</div>
                <div style="font-size: 20px; font-weight: 600;">{end_score}</div>
            </div>
            <div style="flex: 1;">
                <div class="kpi-label">Improvement</div>
                <div style="font-size: 20px; font-weight: 600; color: #27ae60;">{improvement}</div>
            </div>
        </div>
    </section>

    <section>
        <h2>Per-Island Performance</h2>
        <table>
            <thead>
                <tr>
                    <th>Island ID</th>
                    <th>Best Score</th>
                    <th>Avg Score</th>
                    <th>Count</th>
                </tr>
            </thead>
            <tbody>
                {"".join(island_rows)}
            </tbody>
        </table>
    </section>

    <section>
        <h2>Visualizations</h2>
        {"".join(embedded_images) if embedded_images else "<p>No plots available.</p>"}
    </section>

    <section>
        <h2>Configuration</h2>
        <pre class="config">{yaml.dump(self.config, default_flow_style=False)}</pre>
    </section>
</body>
</html>
"""
        output_path.write_text(html_content)
