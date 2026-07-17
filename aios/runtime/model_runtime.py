"""ModelRuntime — LLM 调用路由。

职责：
- 路由到远程（DeepSeek）或本地（Ollama/GLM4）模型
- 主路由失败时自动回退
- 支持 function calling（search 工具）
- 非 tool 模式下的不确定性自动检测 + 补搜
- urlopen timeout 硬超时（替代 SIGALRM，线程安全）

不负责：对话管理、prompt 构建、历史维护。
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from aios.kernel.budget import get_attention_budget, MIN_BALANCE_FOR_LLM
from aios.runtime.tools import (
    SEARCH_TOOL_DEF, execute_search, contains_uncertainty,
)

logger = logging.getLogger("aios.model")


@dataclass
class ModelConfig:
    """模型端点配置。"""
    url: str = ""
    api_key: str = ""
    model_name: str = ""

    @classmethod
    def from_json_path(cls, path: str) -> ModelConfig:
        try:
            with open(path) as f:
                data = json.load(f)
                return cls(
                    url=data.get("url", data.get("DEEPSEEK_API_URL", "")),
                    api_key=data.get("api_key", data.get("DEEPSEEK_API_KEY", "")),
                    model_name=data.get("model", data.get("DEEPSEEK_MODEL", "")),
                )
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()

    @classmethod
    def from_env(cls, prefix: str = "DEEPSEEK") -> ModelConfig:
        return cls(
            url=os.environ.get(f"{prefix}_API_URL", ""),
            api_key=os.environ.get(f"{prefix}_API_KEY", ""),
            model_name=os.environ.get(f"{prefix}_MODEL", ""),
        )


class ModelRuntime:
    """LLM 调用运行时。

    支持：
    - 主/备路由
    - Function calling（tool use）
    - 不确定性检测 + 自动补搜
    - 硬超时

    用法：
        model = ModelRuntime(primary=deepseek_cfg, fallback=glm4_cfg)
        reply = model.chat(messages)                # 无 tools
        reply = model.chat(messages, tools=True)    # 带 search tool + 自动处理 tool call
    """

    def __init__(self, primary: ModelConfig, fallback: Optional[ModelConfig] = None,
                 timeout: int = 30, search_api_key: str = ""):
        self._primary = primary
        self._fallback = fallback
        self._timeout = timeout
        self._search_api_key = search_api_key

    def _check_budget(self) -> bool:
        """检查注意力预算是否足够一次 LLM 调用。

        检查当前全局焦点（由应用层设置）的交互层余额。
        如果未设置焦点，返回 True（向后兼容）。
        """
        try:
            budget = get_attention_budget()
            focus = budget.current_focus
            if not focus:
                return True  # 未设置焦点，不限制
            return budget.can_spend_llm(focus)
        except Exception:
            logger.debug("budget check failed, defaulting to allow")
            return True

    def _spend_budget(self, tool_call: bool = False):
        """从当前焦点的交互层扣除一次 LLM 调用成本。"""
        try:
            budget = get_attention_budget()
            focus = budget.current_focus
            if focus:
                budget.spend_llm(focus, tool_call=tool_call)
        except Exception:
            logger.debug("budget spend failed")

    def chat(self, messages: list[dict], temperature: float = 0.7,
             max_tokens: int = 512,
             auto_search: bool = False) -> str:
        """普通对话。

        如果注意力预算不足，返回降级响应（空字符串）让调用方知悉。

        Args:
            auto_search: 如果为 True，检测到模型回复不确定性时自动搜索并重试。
                         适合小模型本地模式——模型说"我不知道"时自动补搜。
        """
        if not self._check_budget():
            logger.info("注意力预算不足，跳过 LLM 调用")
            return ""

        last_error = None
        for label, cfg in [("primary", self._primary), ("fallback", self._fallback)]:
            if not cfg or not cfg.url:
                continue
            try:
                reply = self._call(cfg, messages, temperature, max_tokens)
                self._spend_budget(tool_call=False)
                # 不确定性自动补搜
                if auto_search and contains_uncertainty(reply):
                    logger.info("%s expressed uncertainty, auto-searching...", label)
                    search_result = self._auto_search(reply, messages)
                    if search_result:
                        enriched = list(messages)
                        enriched.append({"role": "assistant", "content": reply})
                        enriched.append({"role": "user", "content": search_result})
                        reply = self._call(cfg, enriched, temperature, max_tokens)
                        self._spend_budget(tool_call=False)
                return reply
            except Exception as e:
                logger.warning("model %s failed: %s", label, e)
                last_error = e
        raise RuntimeError("all models failed") from last_error

    def chat_with_search(self, messages: list[dict], temperature: float = 0.7,
                          max_tokens: int = 512,
                          auto_retry_on_uncertainty: bool = True,
                          summarizer=None) -> str:
        """带搜索能力的对话。

        如果注意力预算不足，返回降级响应（空字符串）让调用方知悉。

        支持两种模式：
        1. Tool calling — 模型通过 function calling 主动调用 search
        2. 不确定性检测 — 模型回复中包含不确定性时自动补搜

        Args:
            messages: 对话消息列表
            auto_retry_on_uncertainty: 检测到不确定性时自动搜索并重试
        """
        if not self._check_budget():
            logger.info("注意力预算不足，跳过 LLM 调用 (chat_with_search)")
            return ""

        last_reply = ""

        # ── 先试 tool calling（DeepSeek 原生支持） ──
        for label, cfg in [("primary", self._primary), ("fallback", self._fallback)]:
            if not cfg or not cfg.url:
                continue
            try:
                result = self._call_with_tools(cfg, messages, temperature, max_tokens)
                if result:
                    last_reply = result
                    self._spend_budget(tool_call=True)
                    break
            except Exception as e:
                logger.warning("tool call with %s failed: %s", label, e)

        # ── Tool calling 没出结果 → 普通调用 ──
        if not last_reply:
            for label, cfg in [("primary", self._primary), ("fallback", self._fallback)]:
                if not cfg or not cfg.url:
                    continue
                try:
                    last_reply = self._call(cfg, messages, temperature, max_tokens)
                    self._spend_budget(tool_call=False)
                    break
                except Exception as e:
                    logger.warning("model %s failed: %s", label, e)

        if not last_reply:
            raise RuntimeError("all models failed")

        # ── 不确定性检测 + 自动补搜 ──
        if auto_retry_on_uncertainty and contains_uncertainty(last_reply):
            logger.info("detected uncertainty, auto-searching...")
            search_result = self._auto_search(last_reply, messages)
            if search_result:
                # 改写最后一条用户消息：追加搜索结果
                enriched = [dict(m) for m in messages]
                for i in range(len(enriched) - 1, -1, -1):
                    if enriched[i].get("role") == "user":
                        enriched[i] = {
                            "role": "user",
                            "content": enriched[i]["content"] + f"\n\n[山谷外传来了信息：]\n{search_result}",
                        }
                        break
                try:
                    # 如果提供了 summarizer（如 GLM4），用它处理搜索结果
                    # 避免 DeepSeek 听到自己名字时出戏
                    if summarizer is not None:
                        enriched_reply = summarizer(enriched)
                    else:
                        cfg = self._primary if self._primary and self._primary.url else self._fallback
                        enriched_reply = self._call(cfg, enriched, temperature, max_tokens)
                    if enriched_reply:
                        self._spend_budget(tool_call=False)
                        return enriched_reply
                except Exception:
                    logger.debug("enriched reply call failed, returning original")

        return last_reply

    def _call_with_tools(self, cfg: ModelConfig, messages: list[dict],
                          temperature: float, max_tokens: int,
                          max_tool_rounds: int = 3) -> Optional[str]:
        """带 function calling 的模型调用。最多 max_tool_rounds 轮工具循环。"""
        current_messages = list(messages)

        for _ in range(max_tool_rounds):
            cleaned = self._sanitize_messages(current_messages)
            payload = json.dumps({
                "model": cfg.model_name,
                "messages": cleaned,
                "tools": [SEARCH_TOOL_DEF],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }).encode("utf-8")

            headers = {"Content-Type": "application/json"}
            if cfg.api_key:
                headers["Authorization"] = f"Bearer {cfg.api_key}"

            req = urllib.request.Request(cfg.url, data=payload, headers=headers,
                                          method="POST")

            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(
                    f"HTTP {e.code} (tool call): {body}"
                ) from e

            choice = result.get("choices", [{}])[0]
            msg = choice.get("message", {})

            # 没有 tool_calls → 最终回复
            if not msg.get("tool_calls"):
                return msg.get("content", "")

            # 处理 tool_calls
            current_messages.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": msg["tool_calls"],
            })

            for tc in msg["tool_calls"]:
                fn = tc.get("function", {})
                if fn.get("name") == "search":
                    args = json.loads(fn.get("arguments", "{}"))
                    query = args.get("query", "")
                    search_text = execute_search(query, self._search_api_key)
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": search_text,
                    })

        # 达到 max_tool_rounds，返回最后一条 content
        return current_messages[-1].get("content", "") if current_messages else None

    def _auto_search(self, original_reply: str,
                     original_messages: list[dict]) -> Optional[str]:
        """基于不确定性自动搜索，返回注入 prompt。

        搜索词从用户的最后一条消息中提取。
        特殊词（如模型名）不走外部搜索，直接返回内置认知。
        """
        # 从用户消息中提取搜索词
        query = ""
        for msg in reversed(original_messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                query = content.strip()[:100]
                break

        if not query or len(query) < 2:
            return None

        # 走外部搜索
        if self._search_api_key:
            result = execute_search(query, self._search_api_key)
            if result and "📡 [搜索结果" in result:
                return (f"你向外探寻，山谷外传来了信息：\n"
                        f"{result}")

        # 搜索不可用时，用 WebFetch 兜底
        if not self._search_api_key:
            try:
                from urllib.request import urlopen
                import urllib.parse
                encoded = urllib.parse.quote(query[:50])
                url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
                with urlopen(url, timeout=10) as resp:
                    ddg = json.loads(resp.read())
                abstract = ddg.get("AbstractText", "")
                if abstract:
                    return (f"你向外探寻，山谷外传来了信息：\n"
                            f"📡 [搜索结果: {query}]\n"
                            f"   {abstract[:500]}")
            except Exception:
                logger.debug("DuckDuckGo fallback search failed for: %s", query)

        return None

    @staticmethod
    def _sanitize_messages(messages: list[dict]) -> list[dict]:
        """清理消息中的非法 surrogate 字符，防止 JSON 序列化时出错。"""
        cleaned = []
        for msg in messages:
            item = {}
            for k, v in msg.items():
                if isinstance(v, str):
                    # replace lone surrogates with U+FFFD (replacement char)
                    item[k] = v.encode("utf-8", errors="replace").decode("utf-8")
                elif isinstance(v, list):
                    item[k] = [
                        s.encode("utf-8", errors="replace").decode("utf-8")
                        if isinstance(s, str) else s
                        for s in v
                    ]
                else:
                    item[k] = v
            cleaned.append(item)
        return cleaned

    def _call(self, cfg: ModelConfig, messages: list[dict],
              temperature: float, max_tokens: int) -> str:
        """底层模型调用（无 tools）。"""
        cleaned = self._sanitize_messages(messages)
        payload = json.dumps({
            "model": cfg.model_name,
            "messages": cleaned,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

        req = urllib.request.Request(cfg.url, data=payload, headers=headers,
                                      method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(
                f"HTTP {e.code}: {body}"
            ) from e

        return (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
