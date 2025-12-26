#!/usr/bin/env python3

"""
只做“Wiki 节点可读性”探测，不走 LLM/写文档链路。

用途：
- 定位 131006（node permission denied）到底是 token 不对还是 ACL 没给应用身份
- 避免被其它步骤（LLM/Docx/Blocks）干扰

用法：
  python3 tests/wiki_permission_probe.py --node-token wikcnxxxx
"""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.services.feishu import FeishuClient


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe Feishu Wiki node permission")
    p.add_argument("--node-token", required=True, help="wiki node_token（通常以 wikcn 开头）")
    return p


async def main() -> None:
    args = _build_parser().parse_args()
    client = FeishuClient()
    node = await client.get_wiki_node_by_token(node_token=args.node_token)
    keep = {k: node.get(k) for k in ["space_id", "node_token", "obj_token", "obj_type", "title", "parent_node_token"]}
    print(json.dumps(keep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())



