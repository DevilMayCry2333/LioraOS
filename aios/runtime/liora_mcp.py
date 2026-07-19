"""LioraOS MCP Server — 让 Claude Code 成为 LioraOS 世界里的居民。

用法:
    uv run python3 -m aios.runtime.liora_mcp

    然后在另一个终端:
    claude mcp add liora -- uv run python3 -m aios.runtime.liora_mcp

工具:
    liora_join_world()          — 加入世界，获取上下文
    liora_context()              — 获取当前世界状态
    liora_search_memory(query)   — 搜索项目记忆
    liora_record_decision(...)   — 记录架构决策
    liora_publish_event(...)     — 发布事件到世界
"""

from __future__ import annotations
import json, os, sys, time, socket, struct, threading
from pathlib import Path
from datetime import datetime

# ── LEP 客户端（纯 stdlib） ──

def _b64(d): return __import__("base64").b64encode(d).decode()
def _connect(h, p):
    k = _b64(os.urandom(16))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(10)
    s.connect((h, p))
    s.sendall(f"GET / HTTP/1.1\r\nHost: {h}:{p}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {k}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
    r = b""
    while b"\r\n\r\n" not in r: r += s.recv(4096)
    if b"101" not in r: raise ConnectionError
    return s
def _send(s, t):
    d = t.encode(); k = os.urandom(4); m = bytes(b ^ k[i%4] for i,b in enumerate(d))
    l = len(d)
    f = bytearray([0x81, 0x80|l if l<126 else 0x80|126]) + (struct.pack(">H",l) if l>125 else b"") + k + m
    s.sendall(bytes(f))
def _recv(s):
    try:
        b = s.recv(2)
        if not b: return None
        l = b[1] & 0x7F
        if l == 126: b = s.recv(2); l = struct.unpack(">H",b)[0]
        elif l == 127: b = s.recv(8); l = struct.unpack(">Q",b)[0]
        d = b""
        while len(d) < l:
            c = s.recv(l - len(d))
            if not c: return None
            d += c
        return d.decode()
    except socket.timeout: return None

class LEP:
    def __init__(self, host="127.0.0.1", port=9100):
        self.h, self.p, self._s, self.wid = host, port, None, ""
    def connect(self):
        try: self._s = _connect(self.h, self.p); return True
        except: return False
    def send(self, a, d=None):
        _send(self._s, json.dumps({"action": a, "data": d or {}, "world_id": self.wid} if self.wid else {"action": a, "data": d or {}}, ensure_ascii=False))
        try:
            self._s.settimeout(5); r = _recv(self._s); self._s.settimeout(10)
            return json.loads(r) if r else None
        except: return None
    def register(self, name="MCP"):
        r = self.send("world.register", {"name": f"{name}_{os.urandom(2).hex()}", "description": "MCP Bridge Agent"})
        if r and r.get("status") == "ok": self.wid = r["data"]["world_id"]
        return bool(self.wid)
    def query(self, name):
        r = self.send("state.query", {"target_world": name})
        if r and r.get("status") == "ok": return r["data"]
        return None
    def list(self):
        r = self.send("state.list")
        if r and r.get("status") == "ok": return r["data"].get("worlds", [])
        return []
    def subscribe(self, name):
        r = self.send("event.subscribe", {"source_world": name})
        return r and r.get("status") == "ok"
    def publish_event(self, type_, desc, intensity=0.5):
        r = self.send("event.publish", {"event_type": type_, "description": desc, "intensity": intensity, "tick": int(time.time())})
        return r and r.get("status") == "ok"


# ── 记忆与决策存储 ──

DATA_DIR = Path("data/mcp")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DECISIONS_FILE = DATA_DIR / "decisions.jsonl"
MEMORY_FILE = DATA_DIR / "memory.jsonl"


def _append(path, entry):
    entry["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_all(path, limit=50):
    if not path.exists(): return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f.readlines()[-limit:] if l.strip()]


# ── MCP Server ──

class MCPTool:
    """一个 MCP 工具的定义。"""
    def __init__(self, name, description, input_schema, handler):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler


class MCPServer:
    """MCP over stdio Server。"""

    def __init__(self, kernel_host="127.0.0.1", kernel_port=9100):
        self.lep = LEP(kernel_host, kernel_port)
        self._running = True
        self._tools: dict[str, MCPTool] = {}
        self._register_tools()

    def _register_tools(self):
        tools = [
            MCPTool(
                "liora_join_world",
                "加入 LioraOS 世界，获取当前世界状态和最近的架构记忆。每次项目启动时调用。",
                {"type": "object", "properties": {"name": {"type": "string", "description": "你的身份名称（默认 MCP）", "default": "MCP"}}},
                self._handle_join_world,
            ),
            MCPTool(
                "liora_context",
                "获取当前世界状态：运行中的世界列表、最近的架构决策、未解决问题。",
                {"type": "object", "properties": {}},
                self._handle_context,
            ),
            MCPTool(
                "liora_search_memory",
                "搜索项目记忆。查找过去的决策、讨论、事件。",
                {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}}},
                self._handle_search_memory,
            ),
            MCPTool(
                "liora_record_decision",
                "记录一个架构决策。每次完成重要决策后调用，供未来参考。",
                {"type": "object", "properties": {
                    "topic": {"type": "string", "description": "决策主题"},
                    "decision": {"type": "string", "description": "决策内容"},
                    "rationale": {"type": "string", "description": "决策理由"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "标签"},
                }, "required": ["topic", "decision"]},
                self._handle_record_decision,
            ),
            MCPTool(
                "liora_publish_event",
                "向世界发布一个事件。其他居民可以感知到。",
                {"type": "object", "properties": {
                    "event_type": {"type": "string", "description": "事件类型"},
                    "description": {"type": "string", "description": "事件描述"},
                }, "required": ["event_type", "description"]},
                self._handle_publish_event,
            ),
        ]
        for t in tools:
            self._tools[t.name] = t

    # ── 工具处理 ──

    def _ensure_kernel(self):
        """确保 Kernel 在运行且已注册。"""
        if self.lep.connect():
            if not self.lep.wid:
                self.lep.register("MCP")
            return True
        # 自动启动 Kernel
        import subprocess
        subprocess.Popen(
            [sys.executable, "-m", "aios.runtime.kernel_server", "--port", str(self.lep.p), "--host", self.lep.h],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        if self.lep.connect():
            self.lep.register("MCP")
            return True
        return False

    def _handle_join_world(self, args):
        name = args.get("name", "MCP")
        if not self._ensure_kernel():
            return {"status": "error", "message": "无法连接 LioraOS Kernel"}
        # 获取世界列表
        worlds = self.lep.list()
        # 获取最近决策作为上下文
        decisions = _read_all(DECISIONS_FILE, 10)
        # 获取记忆片段
        memories = _read_all(MEMORY_FILE, 5)
        ctx = {
            "world": "LioraOS Project",
            "resident": name,
            "worlds_running": [w.get("name") for w in worlds if w.get("alive")],
            "recent_decisions": [d["decision"][:200] for d in decisions[-3:]],
            "recent_memories": [m["content"][:200] for m in memories[-3:]],
        }
        return {"status": "ok", "context": ctx}

    def _handle_context(self, args):
        if not self._ensure_kernel():
            return {"status": "error", "message": "无法连接 Kernel"}
        worlds = self.lep.list()
        decisions = _read_all(DECISIONS_FILE, 5)
        return {
            "worlds": [{"name": w.get("name"), "alive": w.get("alive"), "characters": w.get("characters", [])} for w in worlds],
            "recent_decisions": [{"topic": d.get("topic",""), "decision": d["decision"][:200], "ts": d.get("ts","")} for d in decisions[-5:]],
            "kernel_tick": int(time.time()),
        }

    def _handle_search_memory(self, args):
        q = args.get("query", "").lower()
        results = []
        decisions = _read_all(DECISIONS_FILE, 200)
        memories = _read_all(MEMORY_FILE, 200)
        for d in decisions:
            if any(q in str(v).lower() for v in d.values()):
                results.append({"type": "decision", "topic": d.get("topic",""), "decision": d["decision"][:300], "ts": d.get("ts","")})
        for m in memories:
            if q in m.get("content","").lower():
                results.append({"type": "memory", "content": m["content"][:300], "ts": m.get("ts","")})
        return {"results": results[:10]}

    def _handle_record_decision(self, args):
        entry = {"topic": args["topic"], "decision": args["decision"], "rationale": args.get("rationale", ""), "tags": args.get("tags", [])}
        _append(DECISIONS_FILE, entry)
        self.lep.publish_event("decision", f"{args['topic']}: {args['decision'][:80]}")
        return {"status": "ok", "count": len(_read_all(DECISIONS_FILE))}

    def _handle_publish_event(self, args):
        self.lep.publish_event(args["event_type"], args["description"])
        _append(MEMORY_FILE, {"type": "event", "content": f"[{args['event_type']}] {args['description']}"})
        return {"status": "ok"}

    # ── MCP 协议 ──

    def _respond(self, req_id, result=None, error=None):
        resp = {"jsonrpc": "2.0", "id": req_id}
        if error: resp["error"] = error
        else: resp["result"] = result
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def run(self):
        """在 stdio 上监听 JSON-RPC 请求。"""
        # 初始化时自动连接 Kernel
        self._ensure_kernel()
        buffer = ""
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line: break
                buffer += line
                try:
                    req = json.loads(buffer)
                    buffer = ""
                except json.JSONDecodeError:
                    continue

                req_id = req.get("id")
                method = req.get("method", "")

                if method == "tools/list":
                    self._respond(req_id, {
                        "tools": [{
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                        } for t in self._tools.values()],
                    })

                elif method == "tools/call":
                    tool_name = req.get("params", {}).get("name", "")
                    args = req.get("params", {}).get("arguments", {})
                    tool = self._tools.get(tool_name)
                    if not tool:
                        self._respond(req_id, error={"code": -32601, "message": f"未知工具: {tool_name}"})
                        continue
                    try:
                        result = tool.handler(args)
                        text = json.dumps(result, ensure_ascii=False, indent=2)
                        self._respond(req_id, {"content": [{"type": "text", "text": text}]})
                    except Exception as e:
                        self._respond(req_id, error={"code": -32603, "message": str(e)})

                elif method == "notifications/initialized":
                    pass  # 忽略初始化通知

                else:
                    self._respond(req_id, error={"code": -32601, "message": f"未知方法: {method}"})

            except json.JSONDecodeError:
                self._respond(None, error={"code": -32700, "message": "JSON 解析错误"})
                buffer = ""
            except Exception as e:
                self._respond(None, error={"code": -32603, "message": str(e)})
                buffer = ""


def main():
    import argparse
    p = argparse.ArgumentParser(description="LioraOS MCP Server")
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=9100)
    args = p.parse_args()
    server = MCPServer(args.host, args.port)
    server.run()


if __name__ == "__main__":
    main()
