#!/usr/bin/env python3
"""Continuous detection daemon: watch CSV files and push new rows to /predict."""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class FileCursor:
    offset: int = 0
    header: List[str] = field(default_factory=list)


class ContinuousDetector:
    def __init__(
        self,
        watch_dir: str,
        api_base: str,
        state_file: str,
        pattern: str = "*.csv",
        poll_interval: float = 2.0,
        source: str = "continuous_detector",
        timeout: float = 10.0,
        max_rows_per_cycle: int = 2000,
        process_existing: bool = False,
        traffic_mode: str = "uniform",
        dispatch_interval: float = 0.0,
        dispatch_jitter_ratio: float = 0.0,
        burst_size_min: int = 5,
        burst_size_max: int = 20,
        burst_pause_min: float = 0.2,
        burst_pause_max: float = 1.5,
        poll_jitter_ratio: float = 0.0,
        verbose: bool = True,
    ) -> None:
        self.watch_dir = Path(watch_dir)
        self.api_base = api_base.rstrip("/")
        self.predict_url = f"{self.api_base}/predict"
        self.state_file = Path(state_file)
        self.pattern = pattern
        self.poll_interval = max(0.2, float(poll_interval))
        self.source = source
        self.timeout = max(1.0, float(timeout))
        self.max_rows_per_cycle = max(1, int(max_rows_per_cycle))
        self.process_existing = process_existing
        self.traffic_mode = str(traffic_mode).strip().lower()
        if self.traffic_mode not in {"uniform", "jitter", "burst"}:
            raise ValueError(f"Unsupported traffic_mode: {traffic_mode}")
        self.dispatch_interval = max(0.0, float(dispatch_interval))
        self.dispatch_jitter_ratio = max(0.0, float(dispatch_jitter_ratio))
        self.burst_size_min = max(1, int(burst_size_min))
        self.burst_size_max = max(self.burst_size_min, int(burst_size_max))
        self.burst_pause_min = max(0.0, float(burst_pause_min))
        self.burst_pause_max = max(self.burst_pause_min, float(burst_pause_max))
        self.poll_jitter_ratio = max(0.0, float(poll_jitter_ratio))
        self.verbose = verbose

        self.state: Dict[str, FileCursor] = {}
        self.sent_total = 0
        self.error_total = 0
        self._burst_remaining = 0

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        files = raw.get("files", {})
        for path_str, payload in files.items():
            self.state[path_str] = FileCursor(
                offset=int(payload.get("offset", 0)),
                header=list(payload.get("header", [])),
            )
        self.sent_total = int(raw.get("sent_total", 0))
        self.error_total = int(raw.get("error_total", 0))

    def _save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "files": {
                path: {"offset": cursor.offset, "header": cursor.header}
                for path, cursor in self.state.items()
            },
            "sent_total": self.sent_total,
            "error_total": self.error_total,
            "updated_at": time.time(),
        }
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def _iter_files(self) -> List[Path]:
        if not self.watch_dir.exists():
            return []
        files = sorted(path for path in self.watch_dir.rglob(self.pattern) if path.is_file())
        return files

    @staticmethod
    def _read_complete_line(handle) -> Optional[str]:
        pos = handle.tell()
        line = handle.readline()
        if not line:
            return None
        # Skip incomplete tail line while writer is still appending.
        if not line.endswith("\n"):
            handle.seek(pos)
            return None
        return line

    def _post_predict(self, record: Dict[str, object]) -> bool:
        payload = {"record": record, "source": self.source}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.predict_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as resp:
                if 200 <= int(resp.status) < 300:
                    return True
            return False
        except (HTTPError, URLError, TimeoutError, ValueError):
            return False

    def _process_file(self, path: Path) -> int:
        key = str(path.resolve())
        cursor = self.state.get(key, FileCursor())

        if not path.exists():
            return 0

        processed = 0
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            if cursor.offset > 0:
                handle.seek(cursor.offset)

            if not cursor.header:
                header_line = self._read_complete_line(handle)
                if not header_line:
                    return 0
                cursor.header = next(csv.reader([header_line.strip()]), [])
                if not cursor.header:
                    return 0

                if not self.process_existing and cursor.offset == 0:
                    # New file: only start from future appended rows.
                    handle.seek(0, 2)
                    cursor.offset = handle.tell()
                    self.state[key] = cursor
                    return 0

            while processed < self.max_rows_per_cycle:
                line = self._read_complete_line(handle)
                if line is None:
                    break
                row = next(csv.DictReader(StringIO(line), fieldnames=cursor.header))
                cleaned = {}
                for k, v in row.items():
                    if v is None or v == "":
                        continue
                    cleaned[str(k)] = v
                if not cleaned:
                    continue

                if self._post_predict(cleaned):
                    self.sent_total += 1
                else:
                    self.error_total += 1
                processed += 1
                self._sleep_after_dispatch()

            cursor.offset = handle.tell()
            self.state[key] = cursor
        return processed

    def _sleep_after_dispatch(self) -> None:
        if self.traffic_mode == "uniform":
            if self.dispatch_interval > 0:
                time.sleep(self.dispatch_interval)
            return

        if self.traffic_mode == "jitter":
            if self.dispatch_interval <= 0:
                return
            ratio = self.dispatch_jitter_ratio
            low = max(0.0, self.dispatch_interval * (1.0 - ratio))
            high = self.dispatch_interval * (1.0 + ratio)
            time.sleep(random.uniform(low, high))
            return

        # Burst mode: send rows in chunks, then pause.
        if self._burst_remaining <= 0:
            self._burst_remaining = random.randint(self.burst_size_min, self.burst_size_max)
        self._burst_remaining -= 1

        if self.dispatch_interval > 0:
            ratio = self.dispatch_jitter_ratio
            low = max(0.0, self.dispatch_interval * (1.0 - ratio))
            high = self.dispatch_interval * (1.0 + ratio)
            time.sleep(random.uniform(low, high))

        if self._burst_remaining <= 0:
            time.sleep(random.uniform(self.burst_pause_min, self.burst_pause_max))

    def _sleep_between_cycles(self) -> None:
        if self.poll_jitter_ratio <= 0:
            time.sleep(self.poll_interval)
            return
        low = max(0.05, self.poll_interval * (1.0 - self.poll_jitter_ratio))
        high = max(low, self.poll_interval * (1.0 + self.poll_jitter_ratio))
        time.sleep(random.uniform(low, high))

    def run(self) -> None:
        self._load_state()
        self._log(f"[Daemon] watch_dir={self.watch_dir}")
        self._log(f"[Daemon] predict_url={self.predict_url}")
        self._log(f"[Daemon] process_existing={self.process_existing}")
        self._log(
            "[Daemon] traffic_mode="
            f"{self.traffic_mode} dispatch_interval={self.dispatch_interval}s "
            f"dispatch_jitter_ratio={self.dispatch_jitter_ratio} poll_jitter_ratio={self.poll_jitter_ratio}"
        )
        if self.traffic_mode == "burst":
            self._log(
                "[Daemon] burst="
                f"{self.burst_size_min}-{self.burst_size_max} rows "
                f"pause={self.burst_pause_min}-{self.burst_pause_max}s"
            )
        self._log("[Daemon] started. Press Ctrl+C to stop.")

        while True:
            cycle_rows = 0
            for path in self._iter_files():
                try:
                    cycle_rows += self._process_file(path)
                except Exception as exc:
                    self.error_total += 1
                    self._log(f"[Daemon] file processing failed: {path} | {exc}")
            self._save_state()
            if cycle_rows > 0:
                self._log(
                    f"[Daemon] cycle_rows={cycle_rows} sent_total={self.sent_total} errors={self.error_total}"
                )
            self._sleep_between_cycles()


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch CSV directory and continuously call /predict.")
    parser.add_argument("--watch-dir", type=str, default="data/ingest", help="Directory to watch for CSV files.")
    parser.add_argument("--api-base", type=str, default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument(
        "--state-file",
        type=str,
        default="data/runtime/continuous_detector_state.json",
        help="State file for per-file offsets.",
    )
    parser.add_argument("--pattern", type=str, default="*.csv", help="File glob pattern.")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument("--source", type=str, default="continuous_detector", help="Event source name.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--max-rows-per-cycle",
        type=int,
        default=2000,
        help="Max rows per file processed each polling cycle.",
    )
    parser.add_argument(
        "--process-existing",
        action="store_true",
        help="Process existing historical rows of new files on first seen.",
    )
    parser.add_argument(
        "--traffic-mode",
        type=str,
        default="uniform",
        choices=["uniform", "jitter", "burst"],
        help="Dispatch timing mode: uniform/fixed, jittered, or bursty.",
    )
    parser.add_argument(
        "--dispatch-interval",
        type=float,
        default=0.0,
        help="Base delay (seconds) after each dispatched row.",
    )
    parser.add_argument(
        "--dispatch-jitter-ratio",
        type=float,
        default=0.0,
        help="For jitter/burst mode, delay variation ratio around dispatch-interval (e.g. 0.5 = +/-50%%).",
    )
    parser.add_argument(
        "--burst-size-min",
        type=int,
        default=5,
        help="Burst mode: minimum rows per burst.",
    )
    parser.add_argument(
        "--burst-size-max",
        type=int,
        default=20,
        help="Burst mode: maximum rows per burst.",
    )
    parser.add_argument(
        "--burst-pause-min",
        type=float,
        default=0.2,
        help="Burst mode: minimum pause (seconds) between bursts.",
    )
    parser.add_argument(
        "--burst-pause-max",
        type=float,
        default=1.5,
        help="Burst mode: maximum pause (seconds) between bursts.",
    )
    parser.add_argument(
        "--poll-jitter-ratio",
        type=float,
        default=0.0,
        help="Polling cycle interval variation ratio (e.g. 0.3 = +/-30%%).",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable daemon logs.")
    args = parser.parse_args()

    daemon = ContinuousDetector(
        watch_dir=args.watch_dir,
        api_base=args.api_base,
        state_file=args.state_file,
        pattern=args.pattern,
        poll_interval=args.poll_interval,
        source=args.source,
        timeout=args.timeout,
        max_rows_per_cycle=args.max_rows_per_cycle,
        process_existing=args.process_existing,
        traffic_mode=args.traffic_mode,
        dispatch_interval=args.dispatch_interval,
        dispatch_jitter_ratio=args.dispatch_jitter_ratio,
        burst_size_min=args.burst_size_min,
        burst_size_max=args.burst_size_max,
        burst_pause_min=args.burst_pause_min,
        burst_pause_max=args.burst_pause_max,
        poll_jitter_ratio=args.poll_jitter_ratio,
        verbose=not args.quiet,
    )
    daemon.run()


if __name__ == "__main__":
    main()
