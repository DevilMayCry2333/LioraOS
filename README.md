# LioraOS

通用智能运行内核。不定义世界观，只提供运行机制。

世界通过 LEP 协议连接 Kernel，独立运行，互不依赖。

## 快速开始

两步启动一个世界：

```bash
# 1. 启动 Kernel
uv run python3 -m aios.runtime.kernel_server --port 9100

# 2. 启动世界
uv run python3 examples/external_world/convenience_store.py --port 9100
```

### 多世界

```bash
# 终端 1: Kernel
uv run python3 -m aios.runtime.kernel_server --port 9100

# 终端 2: 便利店
uv run python3 examples/external_world/convenience_store.py --port 9100

# 终端 3: 石牌村工作室
uv run python3 examples/external_world/studio_1998.py --port 9100
```

世界通过 Kernel 交换事件和居民消息（可选）。默认各自独立演化。

## 内置世界

| 世界 | 启动方式 | 说明 |
|------|---------|------|
| 便利店 | `examples/external_world/convenience_store.py` | 锚点世界。开钰在收银台后面 |
| 石牌村 | `examples/external_world/studio_1998.py` | 五人工坊。林岸和阿柠在修 bug |
| 竹隐谷 | `examples/external_world/bamboo_grove.py` | 竹翁在雾气里说话 |

## 架构

```
Kernel (aios/runtime/kernel_server.py)
  ┃  LEP WebSocket :9100
  ┣━━ examples/external_world/convenience_store.py
  ┣━━ examples/external_world/studio_1998.py
  ┗━━ 你自己的世界（通过 LEP 接入）
```

- Kernel 不加载世界代码
- 世界通过 LEP 协议注册、同步状态、收发事件
- 世界可以随时断开和重连
- Kernel 永远在，世界来来去去

## 创建你自己的世界

`docs/` 目录：

- [`world_tutorial.md`](docs/world_tutorial.md) — 逐步教程（人类版）
- [`world_tutorial_vibe.md`](docs/world_tutorial_vibe.md) — 500 字 prompt（AI 版）
- [`arch_constraints.md`](docs/arch_constraints.md) — 架构约束清单
- [`LEP_SPEC.md`](docs/LEP_SPEC.md) — LEP 协议规范

## 开发

```bash
uv run python3 -m pytest tests/ -v           # 全部测试
uv run python3 -m pytest tests/test_social.py -v  # 单个文件
```

Python ≥ 3.11。无外部依赖（pytest 仅 dev）。使用 `uv`。
