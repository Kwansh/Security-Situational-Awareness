#!/usr/bin/env python3
"""Replay a mixed set of benign and attack samples to /predict for demo/testing."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
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


def sanitize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
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


def post_predict(predict_url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
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


def detect_label_column(frame: pd.DataFrame) -> str | None:
    for candidate in ("Label", "label", "Class", "class", "attack", "Attack", "target", "Target", "y", "Y"):
        if candidate in frame.columns:
            return candidate
    return None


def infer_file_label(file_path: Path) -> str:
    name = file_path.stem.lower()
    if "benign" in name or "normal" in name:
        return "BENIGN"
    if "syn" in name:
        return "SYN"
    if "udp" in name:
        return "UDP"
    if "dns" in name:
        return "DNS"
    if "ntp" in name:
        return "NTP"
    if "ldap" in name:
        return "LDAP"
    if "mssql" in name:
        return "MSSQL"
    if "netbios" in name:
        return "NetBIOS"
    if "portmap" in name:
        return "Portmap"
    return file_path.stem


def collect_candidates(
    files: Iterable[Path],
    *,
    chunk_size: int,
    rows_per_file: int,
    max_rows: int | None,
    seed: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    file_list = list(files)
    mixed_rows: List[Dict[str, Any]] = []

    total_files = len(file_list)
    for file_index, file_path in enumerate(file_list, start=1):
        selected: List[Dict[str, Any]] = []
        label_hint = infer_file_label(file_path)
        label_column = None

        for chunk in pd.read_csv(file_path, low_memory=False, on_bad_lines="skip", chunksize=chunk_size):
            if label_column is None:
                label_column = detect_label_column(chunk)
            if label_column and label_column in chunk.columns:
                # Keep the label column inside the record so /predict can drop or reuse it.
                pass

            chunk = chunk.sample(frac=1.0, random_state=rng.randint(0, 1_000_000_000))
            for _, row in chunk.iterrows():
                if len(selected) >= rows_per_file:
                    break

                record = sanitize_record(row.to_dict())
                record.setdefault("Label", record.get(label_column) if label_column else label_hint)
                record.setdefault("source_file", file_path.name)
                selected.append(record)

            if len(selected) >= rows_per_file:
                break

        if selected:
            mixed_rows.extend(selected)
        print(f"[Load] {file_index}/{total_files} {file_path.name}: {len(selected)} rows", flush=True)

        if max_rows is not None and len(mixed_rows) >= max_rows:
            break

    rng.shuffle(mixed_rows)
    if max_rows is not None and max_rows > 0:
        mixed_rows = mixed_rows[:max_rows]
    return mixed_rows


def replay_rows(
    rows: Iterable[Dict[str, Any]],
    predict_url: str,
    source: str,
    interval: float,
    timeout: float,
) -> Dict[str, Any]:
    total = 0
    attack_total = 0
    errors = 0
    labels = Counter()
    sources = Counter()
    label_groups = Counter()

    start = time.time()
    for row in rows:
        payload = {"record": row, "source": source}
        try:
            result = post_predict(predict_url, payload, timeout=timeout)
            total += 1
            label = str(result.get("prediction_label", "unknown"))
            labels[label] += 1
            if bool(result.get("is_attack", False)):
                attack_total += 1
            sources[str(row.get("source_file", "unknown"))] += 1
            label_groups[str(row.get("Label", row.get("label", "unknown")))] += 1

            if total <= 5 or total % 50 == 0:
                print(
                    f"[Replay] #{total} label={row.get('Label', row.get('label', 'unknown'))} "
                    f"pred={result.get('prediction_label')} attack={result.get('is_attack')} "
                    f"conf={float(result.get('confidence', 0.0)):.4f}",
                    flush=True,
                )
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors += 1
            if errors <= 5:
                print(f"[Replay] request failed: {exc}", flush=True)

        if interval > 0:
            time.sleep(interval)

    elapsed = time.time() - start
    return {
        "total": total,
        "attack_total": attack_total,
        "errors": errors,
        "prediction_labels": dict(labels),
        "input_labels": dict(label_groups),
        "per_file_sent": dict(sources),
        "elapsed_seconds": round(elapsed, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay mixed benign and attack CSV rows to API /predict.")
    parser.add_argument("--input", type=str, default="data/raw", help="CSV file or directory.")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--source", type=str, default="mixed_replay", help="Source tag attached to events.")
    parser.add_argument("--max-files", type=int, default=None, help="Optional max CSV file count.")
    parser.add_argument("--rows-per-file", type=int, default=200, help="Rows to sample from each file.")
    parser.add_argument("--max-rows", type=int, default=2000, help="Global cap on replayed rows.")
    parser.add_argument("--chunk-size", type=int, default=5000, help="CSV read chunk size.")
    parser.add_argument("--interval", type=float, default=0.0, help="Seconds between requests.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    files = iter_csv_files(input_path, max_files=args.max_files)
    if not files:
        raise FileNotFoundError(f"No CSV files found under: {input_path}")

    predict_url = f"{args.api_base.rstrip('/')}/predict"
    print(f"[Replay] target={predict_url}", flush=True)
    print(f"[Replay] files={len(files)} rows_per_file={args.rows_per_file} max_rows={args.max_rows}", flush=True)

    rows = collect_candidates(
        files,
        chunk_size=max(1, int(args.chunk_size)),
        rows_per_file=max(1, int(args.rows_per_file)),
        max_rows=None if args.max_rows is None or args.max_rows <= 0 else int(args.max_rows),
        seed=int(args.seed),
    )
    if not rows:
        raise RuntimeError("No rows were collected for replay.")

    print(f"[Replay] collected={len(rows)} mixed rows", flush=True)

    summary = replay_rows(
        rows,
        predict_url=predict_url,
        source=args.source,
        interval=max(0.0, float(args.interval)),
        timeout=max(1.0, float(args.timeout)),
    )
    summary["dashboard_url"] = f"{args.api_base.rstrip('/')}/dashboard"
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
