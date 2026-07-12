"""工具定义和执行器。

当前提供搜索工具（腾讯云搜索），未来可扩展其他工具。
所有工具遵循统一接口：接受 dict，返回 str。
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger("aios.tools")

# 腾讯云搜索地址（从 AnotherMe 沿用）
TENCENT_SEARCH_URL = "https://api.wsa.cloud.tencent.com/SearchPro"

# 搜索工具定义（DeepSeek / OpenAI 兼容格式）
SEARCH_TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "搜索外部知识。当你对世界中的事物感到好奇、遇到不认识的东西、或需要更多信息来理解当前情况时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "你想搜索什么",
                },
            },
            "required": ["query"],
        },
    },
}

# 系统 prompt 片段——告诉模型它有搜索能力
SEARCH_CAPABILITY_PROMPT = """你有搜索能力。当你对某件事不确定或感到好奇时，可以调用 search 工具。
使用场景举例：
- 遇到不熟悉的概念 → 搜索它
- 对山谷中的某种现象感到好奇 → 搜索相关知识
- 想了解自己是什么 → 搜索数字生命、意识相关话题
"""


def execute_search(query: str, api_key: str = "", max_results: int = 3) -> str:
    """执行搜索（腾讯云搜索），返回格式化结果。"""
    if not api_key:
        return "[搜索不可用：未配置腾讯云 API Key]"

    try:
        payload = json.dumps({"Query": query}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            TENCENT_SEARCH_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)

        resp_data = data.get("Response", {})
        pages = resp_data.get("Pages", [])

        if not pages:
            return f"📡 [搜索结果: {query}]\n   无结果"

        results = []
        for p in pages[:max_results]:
            try:
                item = json.loads(p) if isinstance(p, str) else p
                title = item.get("title", "")
                content = item.get("passage", "")[:200]
                results.append(f"   - {title}: {content}")
            except (json.JSONDecodeError, TypeError):
                continue

        lines = [f"📡 [搜索结果: {query}]"]
        lines.extend(results)
        return "\n".join(lines)

    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200]
        logger.warning("tencent search HTTP %s: %s", e.code, detail)
        return f"[搜索失败: HTTP {e.code}]"
    except Exception as e:
        logger.warning("tencent search failed: %s", e)
        return f"[搜索失败: {e}]"


_UNCERTAINTY_MARKERS = [
    "我不知道", "不确定", "不清楚", "不懂", "不明白",
    "i don't know", "i do not know",
    "i'm not sure", "i am not sure",
    "uncertain", "unknown to me",
    "它到底", "是哪里", "从哪里来", "是什么呢", "意味着什么",
    "how can i know", "tell me more",
]


def contains_uncertainty(text: str) -> bool:
    """检测文本中是否包含不确定性表达。"""
    text_lower = text.lower()
    for marker in _UNCERTAINTY_MARKERS:
        if marker.lower() in text_lower:
            return True
    return False


def extract_search_queries(text: str) -> list[str]:
    """从文本中提取可能适合搜索的关键词。"""
    import re
    queries = re.findall(r'"([^"]+)"', text)
    return [q.strip() for q in queries if len(q.strip()) > 2]
