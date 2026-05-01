from pathlib import Path

import pandas as pd


class DatasetLoader:
    """Load CSV datasets from a folder tree."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)

    def _iter_csv_files(self):
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Dataset directory does not exist: {self.data_dir}")

        files = sorted(
            path
            for path in self.data_dir.rglob("*.csv")
            if path.is_file() and not path.name.startswith(".~lock.")
        )
        if not files:
            raise FileNotFoundError(f"No CSV files found under {self.data_dir}")
        return files

    def load_all(self, max_files: int | None = None) -> pd.DataFrame:
        files = self._iter_csv_files()
        if max_files is not None:
            files = files[:max_files]

        frames = [pd.read_csv(path, low_memory=False) for path in files]
        return pd.concat(frames, ignore_index=True)

    def load_single(self, file_path: str) -> pd.DataFrame:
        return pd.read_csv(file_path, low_memory=False)
