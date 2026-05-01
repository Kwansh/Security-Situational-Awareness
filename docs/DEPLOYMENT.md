# Docker 部署指南（当前代码版本）

## 一键启动（推荐）

```bash
docker compose up -d --build
```

该命令会同时启动两个服务：
- `api`：FastAPI 服务（8000）
- `detector`：持续读取 `data/ingest/*.csv` 并调用 `/predict`

## 服务结构

- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)
- 健康检查：[http://localhost:8000/health](http://localhost:8000/health)

## 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看 API 日志
docker compose logs -f api

# 查看 detector 日志
docker compose logs -f detector

# 停止并移除容器
docker compose down
```

## 目录挂载

`docker-compose.yml` 已配置：
- `./data:/app/data`
- `./results:/app/results`

请确保主机目录存在：
- `data/ingest`
- `data/models/model_artifacts.pkl`

## 本地非 Docker 启动（双进程）

请在两个终端分别执行。

终端 1（API）：
```powershell
python run_api.py --host 0.0.0.0 --port 8000 --no-reload
```

终端 2（detector）：
```powershell
python scripts/continuous_detector.py `
  --watch-dir data/ingest `
  --api-base http://127.0.0.1:8000 `
  --poll-interval 0.5 `
  --poll-jitter-ratio 0.4 `
  --max-rows-per-cycle 50 `
  --process-existing `
  --traffic-mode burst `
  --dispatch-interval 0.02 `
  --dispatch-jitter-ratio 0.8 `
  --burst-size-min 3 `
  --burst-size-max 18 `
  --burst-pause-min 0.1 `
  --burst-pause-max 1.2
```

注意：不要把 `python run_api.py ...` 接在 `--dispatch-jitter-ratio` 后面同一行，否则会被解析成参数字符串并报错。
