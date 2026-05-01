"""Helpers for attaching LLM-generated reports to API responses."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Mapping

LLM_REPORT_TIMEOUT_SECONDS = float(os.getenv("LLM_REPORT_TIMEOUT_SECONDS", "15.0"))
LLM_REPORT_FALLBACK = (
    "1. 状态提示：AI 辅助分析当前不可用（可能是网络超时）。\n"
    "2. 处置建议：请参考上方基础规则检测结果进行排查。"
)
LLM_REPORT_FAST_MODE = "已跳过大模型分析（快速模式）。"


async def build_llm_report(result_data: Mapping[str, Any], is_passive: bool) -> str:
    """Run the LLM explanation in a worker thread with a hard timeout."""
    from llm_analysis_agent.llm_agent import llm_explain_agent

    payload = dict(result_data)
    report = await asyncio.wait_for(
        asyncio.to_thread(llm_explain_agent, payload, is_passive),
        timeout=LLM_REPORT_TIMEOUT_SECONDS,
    )
    if not isinstance(report, str):
        raise TypeError("LLM report must be a string.")
    report = report.strip()
    if not report:
        raise ValueError("LLM report is empty.")
    return report
