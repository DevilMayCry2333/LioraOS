# External World Example

一个通过 LEP 协议连接 Liora Kernel 的外部世界示例。

**不依赖 `aios/` 中的任何模块。** 只使用 stdlib WebSocket。

## 使用方法

```bash
# 终端 1: 启动 Kernel
uv run python3 -m aios.runtime.kernel_server --port 9100

# 终端 2: 启动世界（直接输入文字和角色聊天）
uv run python3 examples/external_world/bamboo_grove.py --port 9100
```

### 交互命令

| 输入 | 效果 |
|------|------|
| `你好` | 和角色对话，角色会根据关键词回复 |
| `/state` | 查看当前世界状态 |
| `/say <世界名> <消息>` | 向其他世界的居民发消息 |
| `/quit` | 退出 |

### 多世界通信

```bash
# 终端 2: 世界 A
uv run python3 examples/external_world/bamboo_grove.py --name 竹隐谷 --port 9100

# 终端 3: 世界 B
uv run python3 examples/external_world/bamboo_grove.py --name 雨之城 --port 9100
```

两个世界自动发现彼此并订阅事件。在任一世界输入：

```
/say 雨之城 你好，我是竹翁
```

消息通过 Kernel 路由，目标世界自动回复。

## 角色对话

角色「竹翁」的发言受世界状态影响：

| 状态 | 说话风格 |
|------|---------|
| 风大 | "风在说你的名字。" |
| 风静 | "沉默也是语言。" |
| 雾浓 | "雾里有东西在移动。" |
| 雾散 | "阳光照进来，竹影在地上像是一幅字。" |

跨世界消息有 9 组关键词匹配回复（"你好"、"竹子"、"风"、"雾"、"再见"……）。

## 架构

```
外部世界 (bamboo_grove.py)
  ┃  LEP WebSocket
  ▼
Kernel Server (kernel_server.py)
  ┃  状态快照 · 事件路由 · 居民消息中转
  ▼
第二个外部世界 (bamboo_grove.py --name 雨之城)
```
