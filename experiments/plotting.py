"""Visualization and plotting for FunSearch experiments."""

from __future__ import annotations

from pathlib import Path

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


class PlotGenerator:
    def __init__(self):
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib is required for plotting")
    
    def _set_style(self) -> None:
        style = 'seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'ggplot'
        plt.style.use(style)

    def _reset_style(self) -> None:
        plt.style.use('default')

    def plot_evolution_curve(self, metrics_data: list[dict], save_path: str | Path) -> None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._set_style()
        generations = [m['generation'] for m in metrics_data]
        
        best_scores = []
        avg_scores = []
        for m in metrics_data:
            if 'overall' in m:
                best_scores.append(m['overall'].get('best_score'))
                avg_scores.append(m['overall'].get('avg_score'))
            else:
                best_scores.append(m.get('best_score_cheap') or m.get('best_score'))
                avg_scores.append(m.get('avg_score_cheap') or m.get('avg_score'))
        
        plt.figure(figsize=(10, 6))
        
        if any(x is not None for x in best_scores):
            plt.plot(generations, best_scores, 'b-', label='Best Score', linewidth=2, marker='o')
        if any(x is not None for x in avg_scores):
            plt.plot(generations, avg_scores, 'g--', label='Avg Score', alpha=0.7, marker='s')
        
        plt.xlabel('Generation', fontsize=12)
        plt.ylabel('Score', fontsize=12)
        plt.title('FunSearch Evolution: Bin Packing', fontsize=14, fontweight='bold')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()
    
    def plot_failure_distribution(self, metrics_data: list[dict], save_path: str | Path) -> None:
        """Plot failure type distribution from metrics."""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._set_style()
        failure_totals: dict[str, int] = {}
        for m in metrics_data:
            failures = m.get('failures', {}) or m.get('failure_breakdown', {})
            for ftype, count in failures.items():
                failure_totals[ftype] = failure_totals.get(ftype, 0) + count
        
        if not failure_totals or sum(failure_totals.values()) == 0:
            self._reset_style()
            return
        
        labels = list(failure_totals.keys())
        sizes = list(failure_totals.values())
        
        plt.figure(figsize=(8, 6))
        cmap = plt.get_cmap('Set3')
        colors = cmap(range(len(labels)))
        plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
        plt.title('Failure Type Distribution', fontsize=14, fontweight='bold')
        plt.axis('equal')
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()
    
    def plot_diversity_over_time(self, diversity_data: list[dict], save_path: str | Path) -> None:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._set_style()
        generations = [d['generation'] for d in diversity_data]
        unique_sigs = [d['unique_signatures'] for d in diversity_data]
        
        plt.figure(figsize=(10, 6))
        plt.plot(generations, unique_sigs, 'g-', linewidth=2, marker='o')
        plt.xlabel('Generation', fontsize=12)
        plt.ylabel('Number of Unique Signatures', fontsize=12)
        plt.title('Population Diversity Over Time', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()

    def plot_dashboard(self, metrics_data: list[dict], save_path: str | Path) -> None:
        """Generate a multi-panel dashboard plot."""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        self._set_style()
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('FunSearch Experiment Dashboard', fontsize=18, fontweight='bold')

        generations = [m['generation'] for m in metrics_data]

        ax1 = axes[0, 0]
        best_scores = []
        avg_scores = []
        for m in metrics_data:
            if 'overall' in m:
                best_scores.append(m['overall'].get('best_score'))
                avg_scores.append(m['overall'].get('avg_score'))
            else:
                best_scores.append(m.get('best_score_cheap') or m.get('best_score'))
                avg_scores.append(m.get('avg_score_cheap') or m.get('avg_score'))

        if any(x is not None for x in best_scores):
            ax1.plot(generations, best_scores, 'b-', label='Best Score', linewidth=2, marker='o')
        if any(x is not None for x in avg_scores):
            ax1.plot(generations, avg_scores, 'g--', label='Avg Score', alpha=0.7, marker='s')
        ax1.set_title('Overall Score Evolution', fontsize=14)
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Score')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        ax2 = axes[0, 1]
        island_ids = set()
        for m in metrics_data:
            if 'islands' in m:
                island_ids.update(m['islands'].keys())
        
        for island_id in sorted(island_ids):
            island_best = [m.get('islands', {}).get(island_id, {}).get('best_score') for m in metrics_data]
            if any(x is not None for x in island_best):
                ax2.plot(generations, island_best, label=f'Island {island_id}', alpha=0.8)
        
        ax2.set_title('Per-Island Best Scores', fontsize=14)
        ax2.set_xlabel('Generation')
        ax2.set_ylabel('Best Score')
        if island_ids:
            ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='small')
        ax2.grid(True, alpha=0.3)

        ax3 = axes[1, 0]
        dedup_skipped = [m.get('dedup_skipped') or m.get('n_deduped') or 0 for m in metrics_data]
        candidates = [m.get('candidates_generated') or m.get('n_generated') or 0 for m in metrics_data]
        
        if any(c > 0 for c in candidates):
            unique_rate = []
            for d, c in zip(dedup_skipped, candidates):
                if c > 0:
                    unique_rate.append((c - d) / c * 100)
                else:
                    unique_rate.append(0)
            ax3.plot(generations, unique_rate, 'm-', label='Unique Rate (%)', marker='^')
            ax3.set_ylabel('Unique Rate (%)')
            ax3.set_ylim(0, 105)
        
        ax3.set_title('Deduplication Statistics', fontsize=14)
        ax3.set_xlabel('Generation')
        ax3.grid(True, alpha=0.3)

        ax4 = axes[1, 1]
        eval_times = [m.get('eval_time_ms') for m in metrics_data]
        if any(t is not None for t in eval_times):
            ax4.plot(generations, eval_times, 'r-x', label='Eval Time (ms)')
            ax4.set_ylabel('Time (ms)')
            ax4.set_title('Evaluation Timing', fontsize=14)
        else:
            if any(c > 0 for c in candidates):
                ax4.bar(generations, candidates, color='skyblue', alpha=0.7, label='Candidates')
                ax4.set_ylabel('Count')
                ax4.set_title('Candidates per Generation', fontsize=14)
        
        ax4.set_xlabel('Generation')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()

    def plot_per_island_evolution(self, metrics_data: list[dict], save_path: str | Path) -> None:
        """Plot best scores for each island."""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        self._set_style()
        generations = [m['generation'] for m in metrics_data]
        island_ids = set()
        for m in metrics_data:
            if 'islands' in m:
                island_ids.update(m['islands'].keys())

        plt.figure(figsize=(12, 7))
        for island_id in sorted(island_ids):
            island_best = [m.get('islands', {}).get(island_id, {}).get('best_score') for m in metrics_data]
            if any(x is not None for x in island_best):
                plt.plot(generations, island_best, label=f'Island {island_id}', linewidth=2)

        plt.title('Per-Island Best Score Evolution', fontsize=16, fontweight='bold')
        plt.xlabel('Generation', fontsize=12)
        plt.ylabel('Best Score', fontsize=12)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()

    def plot_dedup_stats(self, metrics_data: list[dict], save_path: str | Path) -> None:
        """Plot deduplication statistics."""
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        self._set_style()
        generations = [m['generation'] for m in metrics_data]
        
        dedup_skipped = []
        total_skipped = []
        for m in metrics_data:
            if "dedup" in m and isinstance(m["dedup"], dict):
                dedup_skipped.append(m["dedup"].get("skipped", 0))
                total_skipped.append(m["dedup"].get("skipped_total", 0))
            else:
                dedup_skipped.append(m.get('dedup_skipped') or m.get('n_deduped') or 0)
                total_skipped.append(m.get('dedup_skipped_total') or 0)

        plt.figure(figsize=(10, 6))
        plt.plot(generations, dedup_skipped, 'r-o', label='Skipped (this gen)', linewidth=2)
        plt.plot(generations, total_skipped, 'b--s', label='Total Skipped', alpha=0.6)

        plt.title('Deduplication Statistics Over Time', fontsize=14, fontweight='bold')
        plt.xlabel('Generation', fontsize=12)
        plt.ylabel('Count', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        self._reset_style()
