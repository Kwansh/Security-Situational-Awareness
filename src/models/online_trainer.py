"""Online training and hot-swap helper for streaming updates."""

from __future__ import annotations

import json
import shutil
import uuid
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional

import pandas as pd

from scripts.train import build_training_pipeline
from src.utils.model_artifacts import (
    DEFAULT_ARTIFACT_NAME,
    build_timestamped_artifact_name,
    save_artifacts,
    upsert_model_registry_entry,
)


LogFn = Optional[Callable[[str], None]]


@dataclass
class OnlineTrainingResult:
    artifact_path: Path
    backup_path: Optional[Path]
    row_count: int
    raw_feature_count: int
    selected_feature_count: int
    metrics: Dict[str, float]
    figures: Dict[str, str]
    source_files: List[str]
    buffer_path: str
    elapsed_seconds: float


class OnlineTrainer:
    """Train a replacement model from streamed data and atomically hot-swap it."""

    def __init__(
        self,
        data_dir: str,
        artifact_path: str = f"data/models/{DEFAULT_ARTIFACT_NAME}",
        output_dir: str = "data/models",
        figures_dir: str = "results/figures",
        model_names: str = "random_forest,xgboost",
        use_stacking: bool = False,
        test_size: float = 0.2,
        random_state: int = 42,
        chunk_size: int = 50000,
        window_rows: int = 200000,
        max_files: Optional[int] = None,
        max_rows_per_file: Optional[int] = 50000,
        rf_estimators: int = 200,
        xgb_estimators: int = 200,
        n_jobs: int = 1,
        backup_on_update: bool = True,
        persist_buffer_snapshot: bool = True,
        verbose: bool = True,
        log_fn: LogFn = None,
    ):
        self.data_dir = Path(data_dir)
        self.artifact_path = Path(artifact_path)
        self.output_dir = Path(output_dir)
        self.figures_dir = Path(figures_dir)
        self.model_names = model_names
        self.use_stacking = use_stacking
        self.test_size = test_size
        self.random_state = random_state
        self.chunk_size = int(max(1000, chunk_size))
        self.window_rows = int(max(1000, window_rows))
        self.max_files = max_files
        self.max_rows_per_file = max_rows_per_file
        self.rf_estimators = rf_estimators
        self.xgb_estimators = xgb_estimators
        self.n_jobs = n_jobs
        self.backup_on_update = backup_on_update
        self.persist_buffer_snapshot = persist_buffer_snapshot
        self.verbose = verbose
        self.log_fn = log_fn

    def _log(self, message: str) -> None:
        if self.verbose and self.log_fn is not None:
            self.log_fn(message)
        elif self.verbose:
            print(message, flush=True)

    def _iter_csv_files(self) -> List[Path]:
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Dataset directory does not exist: {self.data_dir}")
        files = sorted(
            path
            for path in self.data_dir.rglob("*.csv")
            if path.is_file() and not path.name.startswith(".~lock.")
        )
        if not files:
            raise FileNotFoundError(f"No CSV files found under {self.data_dir}")
        if self.max_files is not None:
            files = files[: self.max_files]
        return files

    def _load_stream_window(self) -> tuple[pd.DataFrame, List[str]]:
        files = self._iter_csv_files()
        self._log(f"[Online] Found {len(files)} CSV files under {self.data_dir}")

        frames: List[pd.DataFrame] = []
        source_files: List[str] = []
        loaded_rows = 0
        start_time = time.time()
        effective_rows_per_file = self.max_rows_per_file
        if effective_rows_per_file is None and len(files) > 0:
            # Default to balanced multi-file buffering so the online update window
            # does not come from a single attack profile only.
            effective_rows_per_file = max(1000, int(self.window_rows / len(files)))

        for file_index, path in enumerate(files, start=1):
            if loaded_rows >= self.window_rows:
                break
            source_files.append(path.name)
            self._log(f"[Online] [{file_index}/{len(files)}] Streaming file: {path.name}")
            rows_from_file = 0
            max_rows_for_file = (
                effective_rows_per_file
                if effective_rows_per_file and effective_rows_per_file > 0
                else None
            )

            for chunk in pd.read_csv(path, low_memory=False, on_bad_lines="skip", chunksize=self.chunk_size):
                if loaded_rows >= self.window_rows:
                    break
                remaining = self.window_rows - loaded_rows
                if max_rows_for_file is not None:
                    remaining = min(remaining, max_rows_for_file - rows_from_file)
                if remaining <= 0:
                    break
                if len(chunk) > remaining:
                    chunk = chunk.iloc[:remaining].copy()
                frames.append(chunk)
                loaded_rows += len(chunk)
                rows_from_file += len(chunk)
                progress = loaded_rows / self.window_rows if self.window_rows else 0.0
                elapsed = max(1e-6, time.time() - start_time)
                eta_seconds = (elapsed / progress - elapsed) if progress > 0 else 0.0
                self._log(
                    f"[Online] {path.name}: {loaded_rows:,}/{self.window_rows:,} rows buffered "
                    f"({progress * 100:5.1f}%) ETA {self._format_eta(eta_seconds)}"
                )
                if max_rows_for_file is not None and rows_from_file >= max_rows_for_file:
                    break

        if not frames:
            raise ValueError("No rows were buffered for online training.")

        combined = pd.concat(frames, ignore_index=True)
        self._log(f"[Online] Buffered dataset shape: {combined.shape}")
        return combined, source_files

    @staticmethod
    def _format_eta(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, rem = divmod(total, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def train(self) -> OnlineTrainingResult:
        start_time = time.time()
        self._log("[Online] Stage 1 - Buffering incremental CSV stream...")
        buffer_df, source_files = self._load_stream_window()

        self.output_dir.mkdir(parents=True, exist_ok=True)
        persisted_buffer_path: Optional[Path] = None
        if self.persist_buffer_snapshot:
            persisted_buffer_path = self.output_dir / "online_window_last.csv"
            buffer_df.to_csv(persisted_buffer_path, index=False)
            self._log(f"[Online] Snapshot saved to {persisted_buffer_path}")
        backup_path = (
            self.artifact_path.with_name(f"{self.artifact_path.stem}_backup{self.artifact_path.suffix}")
            if self.backup_on_update
            else None
        )
        buffer_csv: Optional[Path] = None
        temp_dir = self.output_dir.parent / f"online_training_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            buffer_csv = temp_dir / "online_window.csv"
            buffer_df.to_csv(buffer_csv, index=False)
            self._log(f"[Online] Buffered data written to {buffer_csv}")

            self._log("[Online] Stage 2 - Retraining replacement model in the background...")
            result = build_training_pipeline(
                data_dir=str(temp_dir),
                k_features=0,
                use_stacking=self.use_stacking,
                test_size=self.test_size,
                random_state=self.random_state,
                max_files=1,
                max_rows_per_file=0,
                chunk_size=self.chunk_size,
                rf_estimators=self.rf_estimators,
                xgb_estimators=self.xgb_estimators,
                n_jobs=self.n_jobs,
                model_names=self.model_names,
                verbose=self.verbose,
                visualization_dir=str(self.figures_dir),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self._log("[Online] Stage 3 - Saving new artifact atomically...")
        timestamped_artifact_path = self.artifact_path.with_name(
            build_timestamped_artifact_name(self.artifact_path.stem.replace("_latest", ""))
        )
        save_artifacts(
            timestamped_artifact_path,
            model=result["ensemble"],
            scaler=result["preprocessor"].scaler,
            selector=result["selector"],
            feature_columns=result["feature_columns"],
            label_mapping=result["preprocessor"].label_mapping,
            metrics=result["metrics"],
            preprocessor=result["preprocessor"],
            atomic=True,
            backup_path=backup_path,
            metadata={
                "training_mode": "online",
                "source_files": source_files,
                "buffer_rows": len(buffer_df),
            },
        )
        shutil.copy2(timestamped_artifact_path, self.artifact_path)
        upsert_model_registry_entry(
            self.output_dir,
            artifact_path=timestamped_artifact_path,
            latest_path=self.artifact_path,
            status="current",
            metadata={
                "training_mode": "online",
                "source_files": source_files,
                "buffer_rows": len(buffer_df),
                "row_count": int(result["row_count"]),
                "raw_feature_count": int(result["raw_feature_count"]),
                "selected_feature_count": int(result["selected_feature_count"]),
                "metrics": {key: value for key, value in result["metrics"].items() if key != "report"},
            },
        )

        metrics_path = self.output_dir / "online_metrics.json"
        metrics_path.write_text(
            json.dumps(
                {
                    "artifact_path": str(self.artifact_path),
                    "timestamped_artifact_path": str(timestamped_artifact_path),
                    "backup_path": str(backup_path) if backup_path else None,
                    "row_count": int(result["row_count"]),
                    "raw_feature_count": int(result["raw_feature_count"]),
                    "selected_feature_count": int(result["selected_feature_count"]),
                    "metrics": result["metrics"],
                    "figures": result["figures"],
                    "source_files": source_files,
                    "buffer_rows": len(buffer_df),
                    "training_mode": "online",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        elapsed = time.time() - start_time
        self._log(f"[Online] Update complete in {elapsed:.1f}s")
        return OnlineTrainingResult(
            artifact_path=self.artifact_path,
            backup_path=backup_path,
            row_count=int(result["row_count"]),
            raw_feature_count=int(result["raw_feature_count"]),
            selected_feature_count=int(result["selected_feature_count"]),
            metrics=result["metrics"],
            figures=result["figures"],
            source_files=source_files,
            buffer_path=str(persisted_buffer_path) if persisted_buffer_path else "",
            elapsed_seconds=elapsed,
        )
