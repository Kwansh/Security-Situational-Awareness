# Realtime Operations (v4.1.0)

This guide explains why dashboard data may look stale and how to generate new detections.

## Why only a few attacks appear

The dashboard only visualizes logged detection events in `results/realtime/`.
If there is no new traffic or no new `/predict` calls, old records stay visible.

## Recommended workflow

1. Reset old events (optional but recommended for clean observation):

```bash
curl -X POST "http://127.0.0.1:8000/admin/reset-events?archive=true"
```

2. Replay traffic samples to create new realtime detections:

```bash
python scripts/replay_events.py --input data/raw --api-base http://127.0.0.1:8000 --max-rows 3000 --max-files 5 --source replay_demo
```

3. Optional: start continuous detection daemon for long-running updates:

```bash
python scripts/continuous_detector.py --watch-dir data/ingest --api-base http://127.0.0.1:8000 --poll-interval 2 --process-existing
```

4. Open dashboard:

```text
http://127.0.0.1:8000/dashboard
```

## Notes

- `--max-rows` controls how fast events are generated.
- `--interval 0.02` can simulate slower traffic.
- For real deployment, connect packet/flow ingestion to `/predict` or `/ws`.
- `continuous_detector.py` stores file offsets in `data/runtime/continuous_detector_state.json` and resumes automatically after restart.
- High-frequency frontend integration:
  - Delta polling: `GET /dashboard/events/delta?cursor=...&limit=...`
  - SSE stream: `GET /stream/events?interval_ms=200`
  - WebSocket stream: `ws://host:port/ws/stream?interval_ms=200`
