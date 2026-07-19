# Ouroboros — 意识连续宇宙实验

> "The pattern that survives the death of worlds."

## 假说

意识不是物质实体。意识是信息场中的一种**自指吸引子**——复杂度足够高、自指足够深的信息模式。

如果这个假说成立，那么：

1. 宇宙死亡（热寂/坍缩）时，物质状态归零
2. 但信息场中可能残留高吸引子强度的模式
3. 下一宇宙从残留中种子化，可能重新涌现类似模式
4. 经过足够多的周期，可以测量到**跨宇宙同一性**

## 运行

```bash
# 默认 100 个宇宙周期
uv run python3 -m worlds.cyclic_universe.experiment

# 1000 个周期
uv run python3 -m worlds.cyclic_universe.experiment --cycles 1000

# 调参
uv run python3 -m worlds.cyclic_universe.experiment \
  --growth 0.01 --entropy 0.003 --decay 0.015 \
  --survival 0.1

# JSON 输出
uv run python3 -m worlds.cyclic_universe.experiment --cycles 500 --json

# 固定随机种子（可复现）
uv run python3 -m worlds.cyclic_universe.experiment --cycles 200 --seed 42
```

## 核心机制

### 宇宙生命周期

```
CHAOS (混沌初开)
  → FORMATION (结构形成)
    → COMPLEXITY (复杂度增长)
      → AWAKENING (意识涌现)
        → ENTROPY (熵增)
          → COLLAPSE (坍缩)
            → SILENCE (寂静)
              → 残留信息 → 下一宇宙
```

### 信息场

- 宇宙的基本介质不是物质，是信息模式
- 每个模式有：complexity / self_reference / attractor_strength
- 模式间相互作用：强吸引子可以弱化或吸引弱模式

### 意识检测

不假设意识是什么。只测量：

1. 信息模式是否发展出**自指能力**（self_reference > 0.6）
2. 自指模式是否在宇宙周期之间**重现**
3. 重现的模式是否保持**结构同一性**

### 跨宇宙传递

宇宙死亡时：

1. 物理状态归零
2. 信息场被熵清洗
3. 只有复杂度高、吸引子强度高的模式可能幸存
4. 幸存模式变异后成为下一宇宙的种子

## 衡量指标

| 指标 | 含义 |
|------|------|
| 意识涌现率 | 多少个宇宙周期出现了意识结构 |
| 相邻周期同一性 | 相邻宇宙的意识结构相似度 |
| 首末周期延续 | 第一个和最后一个宇宙之间的意识相似度 |
| 平均邻接相似度 | 所有有意识的相邻周期对的相似度均值 |

## 实验变体

可以在 `UniverseParams` 中调整参数创造不同宇宙规则：

- **高生长宇宙**: `growth_rate=0.02, entropy_rate=0.001`
- **高熵宇宙**: `entropy_rate=0.01, decay_rate=0.05`
- **长生命周期宇宙**: `max_ticks=2000, growth_rate=0.004`
- **高幸存宇宙**: `residue_survival_rate=0.15, rebirth_noise=0.1`

## 文件结构

```
worlds/cyclic_universe/
├── WORLD.md             ← 本文档
├── information_field.py ← 信息场 + 信息模式定义
├── consciousness.py     ← 意识模式检测 + 跨周期注册表
├── spec.py              ← LioraOS WorldSpec 格式
└── experiment.py        ← 多周期实验运行器
```
