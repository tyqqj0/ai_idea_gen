#!/usr/bin/env python3

"""
手动向 /api/addon/process 发送请求的辅助脚本，便于本地调试飞书文档处理流程。

用法示例：
    python tests/manual_trigger.py \
        --doc-token LnTEwLXdrigzbzkLpEfczH4lnOc \
        --user-id test_user_001 \
        --trigger-source api_test
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Any, Dict

import httpx

DEFAULT_ENDPOINT = "http://127.0.0.1:8001/api/addon/process"
COMPLETE_STATUSES = {"succeeded", "failed"}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="触发 AI 文档处理接口并打印详细日志"
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"接口地址，默认 {DEFAULT_ENDPOINT}",
    )
    parser.add_argument("--doc-token", required=True, help="文档 doc_token")
    parser.add_argument(
        "--user-id",
        default="test_user",
        help="触发用户 open_id，可用测试值",
    )
    parser.add_argument(
        "--mode",
        default="idea_expand",
        choices=["idea_expand", "research"],
        help="处理模式",
    )
    parser.add_argument(
        "--trigger-source",
        default="manual_test",
        help="触发来源标记，便于排查日志",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="请求超时时间（秒）",
    )
    parser.add_argument(
        "--raw-body",
        help="直接以字符串发送原始请求体，调试序列化问题",
    )
    parser.add_argument(
        "--status-endpoint",
        help="查询任务状态的 URL，支持 {task_id} 占位符；默认同域 /addon/tasks/{task_id}",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="任务状态轮询间隔（秒）",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=180.0,
        help="任务状态最大等待时间（秒）",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="仅触发任务，不等待结果",
    )
    return parser


async def _post_json(
    client: httpx.AsyncClient,
    endpoint: str,
    payload: Dict[str, Any],
    *,
    raw_body: str | None = None,
) -> httpx.Response:
    if raw_body is not None:
        return await client.post(
            endpoint,
            data=raw_body,
            headers={"Content-Type": "application/json"},
        )
    return await client.post(endpoint, json=payload)


def _derive_status_url(
    process_endpoint: str, task_id: str, override: str | None
) -> str:
    if override:
        return override.format(task_id=task_id)
    sanitized = process_endpoint.rstrip("/")
    if sanitized.endswith("/process"):
        sanitized = sanitized.rsplit("/", 1)[0]
    return f"{sanitized}/tasks/{task_id}"


async def _poll_task_status(
    client: httpx.AsyncClient,
    status_url: str,
    *,
    interval: float,
    timeout: float,
) -> Dict[str, Any]:
    logging.info(
        "开始轮询任务状态 url=%s interval=%.1fs timeout=%.1fs",
        status_url,
        interval,
        timeout,
    )
    deadline = time.perf_counter() + timeout
    attempt = 0

    while True:
        attempt += 1
        try:
            response = await client.get(status_url)
        except httpx.HTTPError as exc:
            logging.warning("查询任务失败 attempt=%d: %s", attempt, exc)
        else:
            logging.info(
                "任务状态响应 attempt=%d status=%s", attempt, response.status_code
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    logging.warning("任务状态响应非 JSON：%s", response.text)
                else:
                    logging.info(
                        "当前任务状态: %(status)s, updated_at=%(updated_at)s",
                        data,
                    )
                    if data.get("status") in COMPLETE_STATUSES:
                        return data
            elif response.status_code == 404:
                logging.warning("任务尚未写入存储，继续重试…")

        if time.perf_counter() >= deadline:
            raise TimeoutError("轮询任务状态超时")

        await asyncio.sleep(interval)


async def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    payload = {
        "doc_token": args.doc_token,
        "user_id": args.user_id,
        "mode": args.mode,
        "trigger_source": args.trigger_source,
    }

    logging.info("请求地址: %s", args.endpoint)
    if args.raw_body is None:
        logging.info(
            "请求体(JSON):\n%s",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
    else:
        logging.info("使用原始请求体字符串:\n%s", args.raw_body)

    async with httpx.AsyncClient(timeout=args.timeout) as client:
        start = time.perf_counter()
        try:
            response = await _post_json(
                client,
                args.endpoint,
                payload,
                raw_body=args.raw_body,
            )
        except httpx.HTTPError as exc:
            logging.exception("请求失败: %s", exc)
            sys.exit(1)
        duration = time.perf_counter() - start

        logging.info("HTTP 状态: %s, 耗时: %.2fs", response.status_code, duration)
        logging.info("响应头: %s", dict(response.headers))

        try:
            data = response.json()
            logging.info(
                "响应体(JSON):\n%s",
                json.dumps(data, ensure_ascii=False, indent=2),
            )
        except ValueError:
            logging.error("响应体不是 JSON，无法解析任务 ID：%s", response.text)
            sys.exit(1)

        task_id = data.get("task_id")
        if not task_id:
            logging.error("响应中未找到 task_id，退出")
            sys.exit(1)

        if args.no_wait:
            logging.info("任务已创建 task_id=%s，不等待结果", task_id)
            return

        status_url = _derive_status_url(args.endpoint, task_id, args.status_endpoint)

        try:
            final_state = await _poll_task_status(
                client,
                status_url,
                interval=args.poll_interval,
                timeout=args.poll_timeout,
            )
        except TimeoutError as exc:
            logging.error("%s", exc)
            sys.exit(2)

        logging.info(
            "任务完成，最终状态: %s",
            json.dumps(final_state, ensure_ascii=False, indent=2),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(main())


