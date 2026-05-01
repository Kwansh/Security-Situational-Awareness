#!/usr/bin/env python3
"""Extract standard/full/hybrid features from CSV files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

import joblib
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.feature_extractor import FeatureExtractor


def collect_csv_files(input_dir: Path) -> List[Path]:
    files = sorted(path for path in input_dir.rglob("*.csv") if path.is_file())
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {input_dir}")
    return files


def infer_label_from_filename(filename: str) -> str:
    name = filename.lower()
    if "syn" in name:
        return "syn_flood"
    if "udplag" in name:
        return "udplag_flood"
    if "udp" in name:
        return "udp_flood"
    if "ldap" in name:
        return "ldap_flood"
    if "mssql" in name:
        return "mssql_flood"
    if "netbios" in name:
        return "netbios_flood"
    if "portmap" in name:
        return "portmap_flood"
    if "dns" in name:
        return "dns_flood"
    if "ntp" in name:
        return "ntp_flood"
    return "normal"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract features from CICFlowMeter CSV files.")
    parser.add_argument("--input", "-i", default="data/raw", help="Input CSV directory")
    parser.add_argument("--output", "-o", default="data/processed/features.pkl", help="Output PKL path")
    parser.add_argument("--mode", choices=["standard", "full", "hybrid"], default="standard", help="Feature mode")
    parser.add_argument("--window-seconds", type=int, default=1, help="Time window size in seconds")
    parser.add_argument("--max-rows", type=int, default=50000, help="Max rows per CSV file, 0 means full file")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)
    max_rows = None if args.max_rows <= 0 else args.max_rows

    extractor = FeatureExtractor(mode=args.mode, window_seconds=args.window_seconds)
    csv_files = collect_csv_files(input_dir)

    feature_frames: List[pd.DataFrame] = []
    labels: List[str] = []

    for csv_file in csv_files:
        frame = pd.read_csv(csv_file, low_memory=False, nrows=max_rows)
        features, columns = extractor.extract(frame)
        if features.empty:
            continue

        label = infer_label_from_filename(csv_file.name)
        feature_frames.append(features)
        labels.extend([label] * len(features))

    if not feature_frames:
        raise RuntimeError("No valid features were extracted.")

    combined = pd.concat(feature_frames, ignore_index=True)
    label_names = sorted(set(labels))
    label_mapping = {name: idx for idx, name in enumerate(label_names)}
    y = np.asarray([label_mapping[name] for name in labels], dtype=int)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "X": combined.values,
            "y": y,
            "feature_names": list(combined.columns),
            "mode": args.mode,
            "window_seconds": args.window_seconds,
            "label_mapping": label_mapping,
            "rows": int(len(combined)),
            "files": [str(path) for path in csv_files],
        },
        output_path,
    )

    print(
        json.dumps(
            {
                "output": str(output_path),
                "mode": args.mode,
                "rows": int(len(combined)),
                "features": int(combined.shape[1]),
                "labels": label_mapping,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
