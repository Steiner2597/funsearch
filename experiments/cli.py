"""CLI interface for running experiments."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from experiments.config import load_config
from experiments.runner import ExperimentRunner
from experiments.artifacts import ArtifactManager

from experiments.report import ReportGenerator
from experiments.compare import RunComparator
import yaml

app = typer.Typer(help="FunSearch Experiment CLI")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run ID to generate report for"),
    artifact_dir: str = typer.Option("artifacts", help="Artifacts directory"),
) -> None:
    """Generate Markdown and HTML reports for a run."""
    run_dir = Path(artifact_dir) / run_id
    
    if not run_dir.exists():
        typer.secho(f"❌ Run not found: {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    metrics_path = run_dir / "metrics.jsonl"
    plots_dir = run_dir / "plots"
    config_path = run_dir / "config.yaml"
    
    if not metrics_path.exists():
        typer.secho(f"❌ Metrics not found for run: {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    if not config_path.exists():
        typer.secho(f"❌ Config not found for run: {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
        
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    generator = ReportGenerator(metrics_path, plots_dir, config)
    
    md_path = run_dir / "report.md"
    html_path = run_dir / "report.html"
    
    generator.generate_markdown(md_path)
    generator.generate_html(html_path)
    
    typer.secho(f"✅ Reports generated successfully!", fg=typer.colors.GREEN)
    typer.echo(f"   Markdown: {md_path}")
    typer.echo(f"   HTML:     {html_path}")


@app.command()
def run(
    config_path: str = typer.Argument(..., help="Path to experiment YAML config"),
    variant: str = typer.Option(
        "both",
        "--variant",
        help="A/B variant to run (A, B, or both)",
        case_sensitive=False,
    ),
) -> None:
    """Run a complete experiment from config file."""
    if variant.lower() not in ["a", "b", "both"]:
        typer.secho(f"❌ Invalid variant: {variant}. Must be A, B, or both.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
        
    try:
        config = load_config(config_path)
        config.variant = variant.lower()
        runner = ExperimentRunner(config)
        summary = runner.run()
        
        if summary.get("status") == "completed":
            typer.secho("\n✅ Experiment completed successfully!", fg=typer.colors.GREEN)
        else:
            typer.secho("\n⚠️  Experiment incomplete", fg=typer.colors.YELLOW)
        
    except FileNotFoundError as e:
        typer.secho(f"❌ Config file not found: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except ValueError as e:
        typer.secho(f"❌ Invalid config: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"❌ Experiment failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command()
def export_best(
    run_id: str = typer.Argument(..., help="Run ID to export best candidate from"),
    artifact_dir: str = typer.Option("artifacts", help="Artifacts directory"),
) -> None:
    """Export the best candidate from a completed run."""
    run_dir = Path(artifact_dir) / run_id
    
    if not run_dir.exists():
        typer.secho(f"❌ Run not found: {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    best_candidate_path = run_dir / "best_candidate.py"
    
    if not best_candidate_path.exists():
        typer.secho(f"❌ No best candidate found for run: {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    typer.secho(f"✅ Best candidate location:", fg=typer.colors.GREEN)
    typer.echo(f"   {best_candidate_path}")
    
    with open(best_candidate_path, "r") as f:
        content = f.read()
    
    typer.echo("\n" + "=" * 80)
    typer.echo(content)
    typer.echo("=" * 80)


@app.command()
def list_runs(
    artifact_dir: str = typer.Option("artifacts", help="Artifacts directory"),
) -> None:
    """List all experiment runs in artifacts directory."""
    artifacts_path = Path(artifact_dir)
    
    if not artifacts_path.exists():
        typer.secho(f"❌ Artifacts directory not found: {artifact_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    run_dirs = [d for d in artifacts_path.iterdir() if d.is_dir()]
    
    if not run_dirs:
        typer.secho("No runs found.", fg=typer.colors.YELLOW)
        return
    
    typer.secho(f"\n📁 Found {len(run_dirs)} run(s):\n", fg=typer.colors.BLUE)
    
    for run_dir in sorted(run_dirs):
        run_id = run_dir.name
        
        config_path = run_dir / "config.yaml"
        metrics_path = run_dir / "metrics.jsonl"
        best_path = run_dir / "best_candidate.py"
        
        has_config = "✓" if config_path.exists() else "✗"
        has_metrics = "✓" if metrics_path.exists() else "✗"
        has_best = "✓" if best_path.exists() else "✗"
        
        num_generations = 0
        if metrics_path.exists():
            with open(metrics_path, "r") as f:
                num_generations = sum(1 for _ in f)
        
        typer.echo(f"  {run_id}")
        typer.echo(f"    Config: {has_config} | Metrics: {has_metrics} | Best: {has_best} | Generations: {num_generations}")


@app.command()
def resume(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
    artifact_dir: str = typer.Option("artifacts", help="Artifacts directory"),
) -> None:
    """Resume an interrupted experiment run (optional feature)."""
    typer.secho("⚠️  Resume functionality not yet implemented", fg=typer.colors.YELLOW)
    typer.echo(f"   Run ID: {run_id}")
    typer.echo(f"   Artifacts: {artifact_dir}")
    raise typer.Exit(1)


@app.command()
def compare(
    run_ids: list[str] = typer.Argument(..., help="Run IDs to compare"),
    artifact_dir: str = typer.Option("artifacts", help="Artifacts directory"),
    output_dir: str = typer.Option(".", help="Output directory for comparison files"),
) -> None:
    """Compare multiple experiment runs."""
    artifacts_path = Path(artifact_dir)
    
    if not artifacts_path.exists():
        typer.secho(f"❌ Artifacts directory not found: {artifact_dir}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    if len(run_ids) < 2:
        typer.secho("❌ At least 2 run IDs are required for comparison", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    typer.secho(f"\n📊 Comparing {len(run_ids)} runs...\n", fg=typer.colors.BLUE)
    
    comparator = RunComparator(artifacts_path)
    comparison = comparator.compare(run_ids)
    
    if not comparison.get("runs"):
        typer.secho("❌ No valid runs found to compare", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    md_path = output_path / "compare.md"
    csv_path = output_path / "compare.csv"
    
    comparator.export_markdown(comparison, md_path)
    comparator.export_csv(comparison, csv_path)
    
    typer.secho("✅ Comparison completed successfully!", fg=typer.colors.GREEN)
    typer.echo(f"   Markdown: {md_path}")
    typer.echo(f"   CSV:      {csv_path}")
    
    warnings = comparison.get("warnings", [])
    if warnings:
        typer.secho("\n⚠️  Warnings:", fg=typer.colors.YELLOW)
        for warning in warnings:
            typer.echo(f"   - {warning}")
    
    runs = comparison.get("runs", [])
    if runs:
        typer.secho(f"\n📈 Summary:", fg=typer.colors.BLUE)
        best_score_winner = comparison.get("best_score_winner")
        for run in runs:
            winner_marker = " 🏆" if run["run_id"] == best_score_winner else ""
            typer.echo(
                f"   {run['run_id']}{winner_marker}: "
                f"Best={run['best_score']:.2f}, "
                f"Unique={run['unique_rate']:.1%}, "
                f"TTB={run['time_to_best']}"
            )


if __name__ == "__main__":
    app()
