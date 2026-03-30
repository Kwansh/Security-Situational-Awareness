from pathlib import Path

import pandas as pd

from scripts.train import build_training_pipeline
from src.model_artifacts import load_artifacts, save_artifacts


def build_sample_frame():
    rows = []
    for index in range(40):
        label = "BENIGN" if index % 2 == 0 else "Syn"
        rows.append(
            {
                "Flow ID": f"flow-{index}",
                "Source IP": "192.168.0.1",
                "Destination IP": "10.0.0.1",
                "Timestamp": "2018-11-03 11:36:28",
                "Flow Duration": 1000 + index,
                "Total Fwd Packets": 10 + index,
                "Total Backward Packets": 3 + (index % 5),
                "Flow Bytes/s": 5.0 + index,
                "Label": label,
            }
        )
    return pd.DataFrame(rows)


def make_workspace(root: Path, name: str) -> Path:
    workspace = root / ".test_runs" / name
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def test_training_pipeline_saves_artifacts():
    tmp_path = make_workspace(Path.cwd(), "pipeline")
    data_dir = tmp_path / "raw"
    data_dir.mkdir(exist_ok=True)
    build_sample_frame().iloc[:20].to_csv(data_dir / "part1.csv", index=False)
    build_sample_frame().iloc[20:].to_csv(data_dir / "part2.csv", index=False)

    result = build_training_pipeline(str(data_dir), k_features=3, use_stacking=False, test_size=0.25)

    artifact_path = tmp_path / "model_artifacts.pkl"
    save_artifacts(
        artifact_path,
        model=result["ensemble"],
        scaler=result["preprocessor"].scaler,
        selector=result["selector"],
        feature_columns=result["feature_columns"],
        label_mapping=result["preprocessor"].label_mapping,
        metrics=result["metrics"],
    )

    artifacts = load_artifacts(artifact_path)
    assert artifact_path.exists()
    assert len(artifacts["feature_columns"]) == 4
    assert "accuracy" in artifacts["metrics"]
