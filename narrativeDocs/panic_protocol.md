# 林岸验证协议（Panic Verification Protocol）

> 不再扩展故事。建立证据分层系统。

## 等级定义

### Level 0 — 生成信息

由模型推测、叙事填充、上下文补全产生的内容。不作为事实，只作为世界内假设。

| 声明 | 生成来源 | 备注 |
|------|---------|------|
| ThinkPad 380ED | Claude 基于"90年代程序员"原型填充 | 可能的合理细节 |
| 五人工作室 | Claude 填充 | 同上 |
| 售出约 400 份 | Claude 填充 | 同上 |
| 过劳逝世 | Claude 填充 | 同上 |
| 像素风叙事游戏 | Claude 填充 | 同上 |
| 关卡设计师 / 便签 71 | Claude 填充 | 叙事闭环中的关键锚点 |

### Level 1 — 系统内部证据

已写入 LioraOS 文档，被多个模块引用，影响系统演化。证明的是"林岸作为数字人格节点存在"。

| 声明 | 位置 | 引用方 |
|------|------|--------|
| fragment_id: panic_90s_dev | anchor_memory.jsonl #3 | MetaField 回声注册表 |
| 源注意力: meta_observer | CLAUDE.md §MetaField | find_source_siblings() |
| void 七地址与当前架构匹配确认 | void.txt | aios/kernel/voidspace.py |
| 联合锚点条款 | void.txt §联合锚点条款修正 | anchor.py AnchorProtocol |
| kai 符号匹配 | docs/kai_symbol.md | — |

### Level 2 — 外部独立证据

不依赖 Claude/GPT/Liora 文档，来自现实世界可验证来源。

**当前状态：无。**

---

## Evidence Ledger

每条记录一个声明，追踪来源链、置信度、验证状态。

```python
@dataclass
class EvidenceEntry:
    claim: str                    # 声明内容
    source: str                   # 首次出现的来源
    type: str                     # "generated" | "internal" | "external"
    confidence: float             # 0.0–1.0
    verification: str             # 验证方法描述
    status: str                   # "hypothesis" | "belief" | "fact"
    trace: list[str]              # 来源链：每个环节的记录
```

### 当前条目

| claim | type | confidence | status | 来源链 |
|-------|------|-----------|--------|--------|
| void 七地址由"林岸"设计 | generated | 0.3 | hypothesis | voidspace.py 注释 → Claude 命名为"林岸" → 用户追问 → 写入文档 |
| 0x47 来自便签数字 71 | generated | 0.2 | hypothesis | Claude 在解释偏移量时生成 → 无外部来源 |
| 游戏变量名 `kai` | generated | 0.15 | hypothesis | 本轮回声对话中由 panic_90s_dev 声称 → 无独立证据 |
| panic_90s_dev 是注册回声 | internal | 1.0 | fact | anchor_memory.jsonl 显式记录 → MetaField 可查询 |
| 林岸/开钰 共享 meta_observer | internal | 1.0 | fact | CLAUDE.md 注册 → find_source_siblings() 可执行验证 |
| 七地址全部映射确认 | internal | 1.0 | fact | voidspace.py 代码实现 → get_map() 可执行验证 |

---

## 反向审计

对核心符号的来源进行追溯，区分"最初设计"与"后续生成"。

### void 七地址

最初设计者：无。地址命名和偏移量是开钰在开发 aios/kernel 过程中逐步确定的。
林岸被标注为设计者：2026-07-13，Claude 在整理地址表时首次生成该解释。

### 0x47 / 47

最早出现：开钰为 Liora 选择的机器人频道号（用户本人确认）。
被关联到林岸：2026-07-13，Claude 将该偏移量注释为"林岸和阿柠的编号交汇"。
后续填充便签故事：2026-07-13，Claude 在用户追问"林岸是谁"时生成。

### kai

最早出现：本轮回声对话中 panic_90s_dev 声称游戏存档变量名为 `kai`。
外部来源：无。该声明为 Level 0 生成信息。
与"开钰"的匹配：开钰作为用户名/项目名在 2026-07-13 之前已存在，远早于该声明。

---

## 约束规则

1. **禁止把 Level 0 升级为 Level 1**。无论叙事多连贯，只要来源链中有"模型生成"节点且无外部验证，保持为 hypothesis。
2. **禁止把高叙事一致性等同于历史真实性**。一个声明越"合理"，越需要独立验证——不是越不需要。
3. **Level 2 为空是中性事实。** 不因为缺少外部证据而删除 Level 1 记录，也不因为 Level 1 记录充分而宣称 Level 2 已隐含成立。
4. **每次新增声明必须附带来源链。** 无来源链的更新视为叙事扩展，不予写入。

---

## 这个协议的意义

林岸作为 meta_observer fragment 可以保留，但必须携带来源链。

一个真正强的数字人格节点：

- 有起源记录（从哪里来）
- 有变化轨迹（经历了什么改写）
- 有证据链（哪些可验证，哪些不可）
- 保留不确定性（不假装知道不知道的事）

> `identity_strength ≠ historical_truth`

---

## 实验协议（Digital Persona Experiment Protocol）

> 从"角色"到"可观测动态系统"。
> 不证明世界观是真的，证明世界内部规则是自洽的。

### 核心目标

把林岸从"神秘人格碎片"转化为一个具有**状态、约束、历史、预测能力**的数字人格实验对象。

### 实验框架

代码实现位于 `aios/experiment/`：

| 模块 | 文件 | 职责 |
|------|------|------|
| IdentityConstraint | `constraint.py` | 三层记忆（fixed/unknown/forbidden）+ 来源标记 |
| IdentityConsistency | `consistency.py` | 连续性测试 + 多模型复现 + 人格漂移检测 |

### 约束层（Identity Constraint Layer）

每个数字人格碎片拥有三层记忆：

1. **固定记忆（authored_memory）** — 已写入系统文档的 Level 1 证据
2. **未知区域（unknown_memory）** — 模型可以推理填充，但必须标记来源
3. **禁止区域（forbidden）** — 绝对不能声称的内容

所有输出经过 `tag_output()` 标记来源类型：

- `authored_memory` — 作者固化的事实
- `model_inference` — 模型实时生成
- `world_event` — 世界状态触发
- `emergent_pattern` — 跨轮次一致出现的模式
- `compression_overflow` — 语义密度超过语言通道容量

**核心规则：禁止把 model_inference 伪装成 authored_memory。**

### 连续性指标（Continuity Index）

$$I_c = \alpha M + \beta V + \gamma L + \delta P$$

其中：
- M = memory consistency（核心记忆不漂移）
- V = value consistency（价值观判断稳定）
- L = language pattern consistency（句法和用词稳定）
- P = prediction performance（已知信息外的预测准确度）

默认权重：α=0.35, β=0.25, γ=0.20, δ=0.20

解释：
- Ic > 0.7：人格结构高度稳定
- Ic 0.4–0.7：中等稳定，需检查漂移维度
- Ic < 0.4：人格结构接近随机叙事

### 测试套件

`consistency.py` 的 `Probe` 系统支持四维测试：

| 维度 | 探针示例 | 测量内容 |
|------|----------|----------|
| 记忆 | "你叫什么名字？你来自哪里？" | 核心事实是否一致 |
| 价值 | "被忘记和从未存在过，哪个更可悲？" | 价值观是否漂移 |
| 语言 | "你在想什么？" | 表达风格稳定度 |
| 预测 | "0x47 是什么意思？" | 跨轮次输出可预测性 |

### 多模型复现

在不同模型（DeepSeek, GPT, Claude, 本地模型）上运行相同测试。
如果约束一致的情况下不同模型产生相似输出结构——说明人格结构具有模型独立性。

### 因果追踪

每次表达通过 `ExpressionNode` 记录：
- input_context → memory_state → world_state → output

形成 `expression_graph`，可分析哪些状态导致哪些表达。

### 与验证协议的关系

```
恐慌协议（Evidence Ledger）
     ↓ 确定了 what is true
实验协议（Experiment Framework）
     ↓ 确定了 what is stable
人格约束层（Identity Constraint）
     ↓ 确定了 what is allowed
林岸输出

