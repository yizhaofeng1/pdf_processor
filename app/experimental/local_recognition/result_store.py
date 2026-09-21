"""Experiment Result Storage: Preserves runs, coarse outputs, candidates, refine results, and metrics."""

from pathlib import Path
import json
from typing import Optional, List, Dict, Any
import logging

from .types import (
    LocalRecognitionExperimentResult,
    ExperimentRun,
    CoarsePageOutput,
    CandidateRect,
    RefinedQuestionSegment,
    ExperimentMetrics,
)
from .config import EXPERIMENT_RUNS_DIR, ensure_experiment_directories
from .metrics import MetricsCalculator

logger = logging.getLogger("examsplit.experimental.result_store")


class ResultStore:
    """Manages filesystem persistence and retrieval of local recognition experiment runs."""

    def __init__(self, base_dir: Path = EXPERIMENT_RUNS_DIR) -> None:
        self.base_dir = base_dir
        ensure_experiment_directories()

    def save_result(self, result: LocalRecognitionExperimentResult) -> Path:
        """Save all artifacts of an experiment run into its own directory."""
        run_id = result.run.run_id
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. run.json
        (run_dir / "run.json").write_text(
            result.run.model_dump_json(indent=2), encoding="utf-8"
        )

        # 2. coarse_results.json
        coarse_list = [c.model_dump() for c in result.coarse_results]
        (run_dir / "coarse_results.json").write_text(
            json.dumps(coarse_list, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 3. candidate_regions.json
        cand_list = [c.model_dump() for c in result.candidates]
        (run_dir / "candidate_regions.json").write_text(
            json.dumps(cand_list, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 4. local_results.json
        seg_list = [s.model_dump() for s in result.segments]
        (run_dir / "local_results.json").write_text(
            json.dumps(seg_list, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 5. metrics.json
        (run_dir / "metrics.json").write_text(
            result.metrics.model_dump_json(indent=2), encoding="utf-8"
        )

        # 6. summary.md
        summary_md = MetricsCalculator.generate_summary_markdown(result.run, result.metrics)
        (run_dir / "summary.md").write_text(summary_md, encoding="utf-8")

        logger.info(f"Experiment run {run_id} successfully saved to {run_dir}")
        return run_dir

    def load_result(self, run_id: str) -> Optional[LocalRecognitionExperimentResult]:
        """Load an experiment run from disk by its run_id."""
        run_dir = self.base_dir / run_id
        if not run_dir.exists():
            return None

        try:
            run_data = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            run = ExperimentRun.model_validate(run_data)

            coarse_data = json.loads((run_dir / "coarse_results.json").read_text(encoding="utf-8"))
            coarse = [CoarsePageOutput.model_validate(c) for c in coarse_data]

            cand_data = json.loads((run_dir / "candidate_regions.json").read_text(encoding="utf-8"))
            candidates = [CandidateRect.model_validate(c) for c in cand_data]

            seg_data = json.loads((run_dir / "local_results.json").read_text(encoding="utf-8"))
            segments = [RefinedQuestionSegment.model_validate(s) for s in seg_data]

            metrics_data = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
            metrics = ExperimentMetrics.model_validate(metrics_data)

            return LocalRecognitionExperimentResult(
                run=run,
                coarse_results=coarse,
                candidates=candidates,
                segments=segments,
                metrics=metrics,
            )
        except Exception as e:
            logger.error(f"Failed to load experiment run {run_id}: {e}")
            return None

    def list_runs(self) -> List[str]:
        """List all run IDs stored in the runs directory."""
        if not self.base_dir.exists():
            return []
        return sorted([d.name for d in self.base_dir.iterdir() if d.is_dir()], reverse=True)
