# LEP/1.0 — Liora Existence Protocol

> 版本: 1.0-draft · 2026-07-17
>
> LEP 是外部世界与 Liora Kernel 之间的唯一通信协议。
> 任何实现了 LEP 的进程都可以作为 LioraOS 的世界运行。
> Kernel 不导入世界代码。世界不导入 Kernel 内部模块。

---

## 设计原则

1. **协议即边界** — Kernel 和世界之间只通过 LEP 通信，没有其他耦合
2. **传输无关** — 协议定义在 JSON 消息层，底层可以是 WebSocket、UDP、HTTP、IPC
3. **世界无状态连接** — Kernel 不假设世界的持久性，世界可以随时断开重连
4. **Kernel 是路由器** — 世界之间不直接通信，所有消息经过 Kernel 路由
5. **世界拥有自己的状态** — Kernel 不存储世界的演化逻辑，只存储世界的最新状态快照

---

## 传输层

### WebSocket（默认）

- 端口: 9100
- 端点: `ws://<host>:9100/`
- 帧类型: 文本帧（Text Frame）
- 消息编码: UTF-8 JSON

### 连接生命周期

```
客户端                              LEP Kernel
  │                                     │
  │──── WebSocket Handshake ──────────→  │
  │←─── 101 Switching Protocols ────────│
  │                                     │
  │──── {"action": "world.register"} ──→│
  │←─── {"status": "ok", ...} ──────────│
  │                                     │
  │──── {"action": "world.heartbeat"} → │  (每 30s)
  │←─── {"status": "ok"} ───────────────│
  │                                     │
  │──── {"action": "state.publish"} ──→ │  (每 tick)
  │←─── {"action": "tick"} ←────────────│  (每 tick)
  │                                     │
  │──── {"action": "world.disconnect"}→ │
  │←─── {"status": "ok"} ───────────────│
  │                                     │
  │──── WebSocket Close ──────────────→  │
```

---

## 消息格式

### 请求（客户端 → Kernel）

```json
{
  "action": "<action_name>",
  "world_id": "<assigned_by_kernel>",
  "data": { ... }
}
```

### 响应（Kernel → 客户端）

```json
{
  "status": "ok" | "error",
  "action": "<action_name>",
  "data": { ... },
  "error": { "code": "...", "message": "..." }
}
```

### 推送（Kernel → 客户端，无对应请求）

```json
{
  "action": "<action_name>",
  "data": { ... }
}
```

---

## 动作参考

### world.register

世界连接后第一个动作。注册到 Kernel 并获取 world_id。

**请求:**
```json
{
  "action": "world.register",
  "data": {
    "name": "echo_valley",
    "description": "一片被雾气笼罩的竹林",
    "state_variables": {
      "wind": 0.3,
      "fog": 0.5,
      "hum": 0.2
    },
    "characters": ["竹翁", "青鸦"]
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "world.register",
  "data": {
    "world_id": "wld_a1b2c3d4",
    "tick": 0,
    "interval": 15.0
  }
}
```

---

### world.heartbeat

存活检测。Kernel 超过 90 秒未收到 heart beat 则认为世界已断开。

**请求:**
```json
{
  "action": "world.heartbeat",
  "world_id": "wld_a1b2c3d4",
  "data": {}
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "world.heartbeat",
  "data": {}
}
```

---

### state.publish

世界将当前状态同步到 Kernel。Kernel 不验证状态，只存储最新快照供其他世界查询。

**请求:**
```json
{
  "action": "state.publish",
  "world_id": "wld_a1b2c3d4",
  "data": {
    "tick": 42,
    "state": {
      "wind": 0.45,
      "fog": 0.32,
      "hum": 0.67
    }
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "state.publish",
  "data": {}
}
```

---

### state.query

查询其他世界的当前状态快照。

**请求:**
```json
{
  "action": "state.query",
  "world_id": "wld_a1b2c3d4",
  "data": {
    "target_world": "night_city"
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "state.query",
  "data": {
    "world": "night_city",
    "tick": 73,
    "state": {
      "corporate_grip": 0.6,
      "street_heat": 0.4
    }
  }
}
```

---

### state.list

列出所有已注册的世界。

**请求:**
```json
{
  "action": "state.list",
  "data": {}
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "state.list",
  "data": {
    "worlds": [
      {"world_id": "wld_a1b2c3d4", "name": "echo_valley", "characters": ["竹翁", "青鸦"], "tick": 42},
      {"world_id": "wld_e5f6g7h8", "name": "night_city", "characters": ["V", "Judy"], "tick": 73}
    ]
  }
}
```

---

### event.publish

世界发布一个事件，Kernel 路由给所有订阅了该世界事件的其他世界。

**请求:**
```json
{
  "action": "event.publish",
  "world_id": "wld_a1b2c3d4",
  "data": {
    "event_type": "wind_gust",
    "description": "一阵强风穿过竹林",
    "intensity": 0.7,
    "effect": {"wind": 0.1}
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "event.publish",
  "data": {
    "event_id": "evt_001"
  }
}
```

---

### event.subscribe

订阅来自特定世界的事件。Kernel 将事件推送给订阅者。

**请求:**
```json
{
  "action": "event.subscribe",
  "world_id": "wld_a1b2c3d4",
  "data": {
    "source_world": "night_city"
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "event.subscribe",
  "data": {}
}
```

**推送格式（事件到达时 Kernel → 订阅者）：**
```json
{
  "action": "event",
  "data": {
    "source_world": "night_city",
    "event_id": "evt_001",
    "event_type": "data_breach",
    "description": "网络攻击导致数据泄露",
    "intensity": 0.6
  }
}
```

---

### resident.message

向其他世界的居民发送消息。Kernel 路由到目标世界的连接。

**请求:**
```json
{
  "action": "resident.message",
  "world_id": "wld_a1b2c3d4",
  "data": {
    "from": "竹翁",
    "to": "V",
    "target_world": "night_city",
    "content": "风在说你的名字。"
  }
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "resident.message",
  "data": {
    "delivered": true
  }
}
```

---

### world.disconnect

优雅断开连接。

**请求:**
```json
{
  "action": "world.disconnect",
  "world_id": "wld_a1b2c3d4",
  "data": {}
}
```

**响应:**
```json
{
  "status": "ok",
  "action": "world.disconnect",
  "data": {}
}
```

---

### tick（服务端推送）

Kernel 周期性向所有已注册世界推送 tick 信号。世界收到后应执行自己的演化逻辑并通过 `state.publish` 返回新状态。

```json
{
  "action": "tick",
  "data": {
    "tick": 42,
    "timestamp": "2026-07-17T12:00:00"
  }
}
```

---

### world.event（服务端推送）

Kernel 向世界推送其他世界的事件（基于订阅）。

```json
{
  "action": "world.event",
  "data": {
    "source_world": "night_city",
    "event_type": "data_breach",
    "description": "荒坂集团的数据库被入侵",
    "intensity": 0.6
  }
}
```

---

### resident.incoming（服务端推送）

Kernel 向世界推送来自其他世界居民的跨世界消息。

```json
{
  "action": "resident.incoming",
  "data": {
    "from": "竹翁",
    "source_world": "echo_valley",
    "content": "风在说你的名字。"
  }
}
```

---

## 错误码

| code | HTTP 类比 | 说明 |
|------|-----------|------|
| `UNKNOWN_ACTION` | 404 | 动作不存在 |
| `MISSING_WORLD_ID` | 401 | 需要 world_id 但未提供 |
| `WORLD_NOT_FOUND` | 404 | world_id 未注册或已断开 |
| `INVALID_STATE` | 422 | 状态格式无效 |
| `DUPLICATE_WORLD` | 409 | 同名世界已注册 |
| `RATE_LIMITED` | 429 | 消息频率过高 |
| `INTERNAL_ERROR` | 500 | Kernel 内部错误 |

---

## 传输无关性

LEP 消息格式与传输层解耦。同一组 action 可以跑在任何传输上：

| 传输 | 场景 | 实现位置 |
|------|------|---------|
| WebSocket | 外部世界 / 浏览器 | `gateway.py` |
| UDP (ANIP) | 节点间广播 | `anip_udp.py` |
| Unix Socket | 本地 IPC | 待实现 |
| HTTP POST | 无状态触发 | 待实现 |
| QUIC | 低延迟跨网络 | 待实现 |

传输层只需要保证：**一个 JSON 消息发出去，对方能收到完整的 JSON 字符串。**
