#!/usr/bin/env python3
"""Replay CSV records to API /predict for realtime dashboard event generation."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
import math
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd


def iter_csv_files(input_path: Path, max_files: int | None = None) -> List[Path]:
    if input_path.is_file():
        files = [input_path]
    else:
        files = sorted(
            path for path in input_path.rglob("*.csv") if path.is_file() and not path.name.startswith(".~lock.")
        )
    if max_files is not None:
        files = files[: max(0, int(max_files))]
    return files


def sanitize_record(record: Dict[str, object]) -> Dict[str, object]:
    cleaned: Dict[str, object] = {}
    for key, value in record.items():
        if pd.isna(value):
            continue
        if hasattr(value, "item"):
            try:
                value = value.item()
            except Exception:
                pass
        cleaned[str(key)] = value
    return cleaned


def post_predict(predict_url: str, payload: Dict[str, object], timeout: float) -> Dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        predict_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        content = response.read().decode("utf-8")
        return json.loads(content)


def replay_rows(
    files: Iterable[Path],
    predict_url: str,
    source: str,
    chunk_size: int,
    max_rows: int | None,
    per_file_limit: int | None,
    interval: float,
    timeout: float,
) -> Dict[str, object]:
    total = 0
    attack_total = 0
    errors = 0
    labels = Counter()
    per_file_counts = Counter()

    start = time.time()
    for file_path in files:
        if per_file_limit is not None and per_file_counts[file_path.name] >= per_file_limit:
            continue
        for chunk in pd.read_csv(file_path, low_memory=False, on_bad_lines="skip", chunksize=chunk_size):
            for _, row in chunk.iterrows():
                if max_rows is not None and total >= max_rows:
                    elapsed = time.time() - start
                    return {
                        "total": total,
                        "attack_total": attack_total,
                        "errors": errors,
                        "labels": dict(labels),
                        "elapsed_seconds": round(elapsed, 2),
                    }
                if per_file_limit is not None and per_file_counts[file_path.name] >= per_file_limit:
                    break
                payload = {"record": sanitize_record(row.to_dict()), "source": source}
                try:
                    result = post_predict(predict_url, payload, timeout=timeout)
                    total += 1
                    per_file_counts[file_path.name] += 1
                    label = str(result.get("prediction_label", "unknown"))
                    labels[label] += 1
                    if bool(result.get("is_attack", False)):
                        attack_total += 1
                except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                    errors += 1
                    if errors <= 5:
                        print(f"[Replay] request failed: {exc}", flush=True)
                if interval > 0:
                    time.sleep(interval)
                if total > 0 and total % 100 == 0:
                    print(
                        f"[Replay] sent={total:,} attacks={attack_total:,} errors={errors:,}",
                        flush=True,
                    )
            if per_file_limit is not None and per_file_counts[file_path.name] >= per_file_limit:
                break

    elapsed = time.time() - start
    return {
        "total": total,
        "attack_total": attack_total,
        "errors": errors,
        "labels": dict(labels),
        "per_file_counts": dict(per_file_counts),
        "elapsed_seconds": round(elapsed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay CSV data to API /predict for realtime dashboard updates.")
    parser.add_argument("--input", type=str, default="data/raw", help="CSV file or directory.")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--source", type=str, default="replay", help="Source tag attached to events.")
    parser.add_argument("--max-files", type=int, default=None, help="Optional max CSV file count.")
    parser.add_argument("--max-rows", type=int, default=2000, help="Optional max records to replay.")
    parser.add_argument("--chunk-size", type=int, default=500, help="CSV read chunk size.")
    parser.add_argument("--balanced", dest="balanced", action="store_true", help="Replay balanced rows across files (default).")
    parser.add_argument("--no-balanced", dest="balanced", action="store_false", help="Replay sequentially from first files.")
    parser.set_defaults(balanced=True)
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between requests.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    files = iter_csv_files(input_path, max_files=args.max_files)
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {input_path}")

    predict_url = f"{args.api_base.rstrip('/')}/predict"
    print(f"[Replay] target={predict_url}", flush=True)
    print(f"[Replay] files={len(files)} max_rows={args.max_rows}", flush=True)
    per_file_limit = None
    if args.balanced and args.max_rows is not None and args.max_rows > 0:
        per_file_limit = max(1, int(math.ceil(args.max_rows / max(1, len(files)))))
        print(f"[Replay] balanced mode on: per_file_limit={per_file_limit}", flush=True)

    summary = replay_rows(
        files=files,
        predict_url=predict_url,
        source=args.source,
        chunk_size=max(1, int(args.chunk_size)),
        max_rows=None if args.max_rows is None or args.max_rows <= 0 else int(args.max_rows),
        per_file_limit=per_file_limit,
        interval=max(0.0, float(args.interval)),
        timeout=max(1.0, float(args.timeout)),
    )
    summary["dashboard_url"] = f"{args.api_base.rstrip('/')}/dashboard"
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
