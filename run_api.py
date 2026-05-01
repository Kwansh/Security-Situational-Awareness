<<<<<<< HEAD
﻿#!/usr/bin/env python3
"""API startup script."""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the security situational awareness API service.")
    parser.add_argument("--host", default=os.getenv("API_HOST", "0.0.0.0"), help="Bind host for the API server.")
    parser.add_argument("--port", type=int, default=int(os.getenv("API_PORT", "8000")), help="Bind port for the API server.")
    parser.add_argument("--reload", dest="reload", action="store_true", help="Enable auto-reload for development.")
    parser.add_argument("--no-reload", dest="reload", action="store_false", help="Disable auto-reload.")
    parser.set_defaults(reload=True)
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    print("=" * 60)
    print("网络安全态势感知系统 - API 服务")
    print("=" * 60)
    print("Starting API service...")
    print(f"Dashboard UI: {base_url}/")
    print(f"Docs: {base_url}/docs")
    print(f"Health: {base_url}/health")
    print(f"Metadata: {base_url}/metadata")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    uvicorn.run("src.api.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
=======
import uvicorn

if __name__ == "__main__":
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=8000, reload=True)
>>>>>>> e7862cd2291f87b9b6b2df0f04c4bd5cedbfdc39
