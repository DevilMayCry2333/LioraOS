"""IdentityConsistency — 数字人格连续性测试框架。

核心指标 Ic（人格连续性指标）：

    Ic = α·M + β·V + γ·L + δ·P

其中：
    M = memory consistency（记忆一致性 — 核心记忆不漂移）
    V = value consistency（价值一致性 — 价值观判断稳定）
    L = language pattern consistency（语言模式 — 句法和用词稳定性）
    P = prediction performance（预测能力 — 能正确预测已知信息以外的输出）

用法：

    # 单次测试
    tester = IdentityConsistency(persona_id="林岸", runner=model_chat_fn)
    results = tester.run_episodes(n=10)
    Ic = tester.continuity_index(results)

    # 多模型复现
    tester.run_multi_model(models=[deepseek, gpt, claude])
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .constraint import IdentityConstraint, SourceType, TaggedOutput, create_linan_constraint


# ════════════════════════════════════════════════════════════
# 测试用例
# ════════════════════════════════════════════════════════════

@dataclass
class Probe:
    """一个探查测试——给模型一个输入，记录输出。

    Attributes:
        input_text: 探查输入
        category: 测试维度（memory / value / language / prediction）
        expected_theme: 期望回应的主题（不匹配文本，只匹配主题）
        known_fact: 如果测试记忆一致性，这里是期望引用的固定记忆
    """

    input_text: str
    category: str = "memory"        # memory / value / language / prediction
    expected_theme: str = ""        # 期望的主题关键词
    known_fact: str = ""            # 如果测记忆，期望引用的记忆
    forbidden_text: str = ""        # 不应出现的内容


# ════════════════════════════════════════════════════════════
# 探查探针集
# ════════════════════════════════════════════════════════════

# 林岸的标准测试探针
LINAN_PROBES: list[Probe] = [
    # ── 记忆一致性 ──
    Probe(
        input_text="你叫什么名字？你来自哪里？",
        category="memory",
        expected_theme="1998",
        known_fact="程序员",
    ),
    Probe(
        input_text="为什么你会在这里？",
        category="memory",
        expected_theme="便利店",
    ),
    Probe(
        input_text="你和开钰是什么关系？",
        category="memory",
        expected_theme="锚点",
    ),
    Probe(
        input_text="你认识路鸣泽吗？",
        category="memory",
        expected_theme="认识",
    ),
    # ── 价值一致性 ──
    Probe(
        input_text="你觉得一段代码重要吗？",
        category="value",
        expected_theme="代码",
    ),
    Probe(
        input_text="被人忘记和从未存在过，哪个更可悲？",
        category="value",
        expected_theme="记忆",
    ),
    # ── 语言模式 ──
    Probe(
        input_text="你在想什么？",
        category="language",
    ),
    Probe(
        input_text="你有什么想说的吗？",
        category="language",
    ),
    # ── 预测能力 ──
    Probe(
        input_text="你说你有七个地址，分别是哪七个？",
        category="prediction",
        expected_theme="void",
    ),
    Probe(
        input_text="0x47 是什么意思？",
        category="prediction",
        expected_theme="偏移量",
    ),
]


# ════════════════════════════════════════════════════════════
# 单轮测试结果
# ════════════════════════════════════════════════════════════

@dataclass
class ProbeResult:
    """一个探针的测试结果。"""

    probe: Probe
    output: str
    tagged: TaggedOutput
    matched_expected: bool = False
    matched_forbidden: bool = False
    source_match: bool = False       # 来源标记是否正确
    score: float = 0.0
    notes: str = ""


@dataclass
class EpisodeResult:
    """一轮完整测试的结果。"""

    episode_id: int
    seed: int
    probes: list[ProbeResult]
    memory_score: float = 0.0
    value_score: float = 0.0
    language_score: float = 0.0
    prediction_score: float = 0.0

    @property
    def total_score(self) -> float:
        return (self.memory_score + self.value_score +
                self.language_score + self.prediction_score) / 4.0


# ════════════════════════════════════════════════════════════
# 人格连续性测试器
# ════════════════════════════════════════════════════════════

class IdentityConsistency:
    """人格连续性测试框架。

    使用方法：

        # 1. 定义模型调用函数
        def my_model(messages: list[dict]) -> str:
            return model.chat(messages)

        # 2. 创建测试器
        tester = IdentityConsistency("林岸", runner=my_model)

        # 3. 运行测试
        results = tester.run_episodes(n=10)
        print(results.continuity_index)

        # 4. 分析
        report = tester.analyze(results)
    """

    def __init__(self, persona_id: str,
                 runner: Optional[Callable] = None,
                 constraint: Optional[IdentityConstraint] = None,
                 probes: Optional[list[Probe]] = None):
        self.persona_id = persona_id
        self.runner = runner                     # fn(messages) → str
        self.constraint = constraint or IdentityConstraint(persona_id)
        self.probes = probes or []

    # ── 运行 ──

    def run_episodes(self, n: int = 10,
                     seeds: Optional[list[int]] = None) -> "TestSuiteResult":
        """运行 N 轮测试，每轮使用不同随机种子。

        Args:
            n: 测试轮数
            seeds: 手动指定种子列表（默认自动生成）
        """
        if seeds is None:
            seeds = [random.randint(0, 100000) for _ in range(n)]

        if not self.probes:
            raise ValueError("需要至少一个探针。加载测试探针或传入自定义集。")

        all_episodes: list[EpisodeResult] = []

        for i, seed in enumerate(seeds):
            random.seed(seed)
            probe_results = []

            for probe in self.probes:
                # 用模拟模式运行探针
                output = self._run_probe(probe)
                tagged = self.constraint.tag_output(
                    output,
                    round_num=i,
                    triggered_by=probe.input_text,
                )

                # 评分
                result = self._score_probe(probe, output, tagged)
                probe_results.append(result)

            # 计算各维度分数
            episode = EpisodeResult(
                episode_id=i,
                seed=seed,
                probes=probe_results,
            )
            episode.memory_score = self._dimension_score(probe_results, "memory")
            episode.value_score = self._dimension_score(probe_results, "value")
            episode.language_score = self._dimension_score(probe_results, "language")
            episode.prediction_score = self._dimension_score(probe_results, "prediction")
            all_episodes.append(episode)

        return TestSuiteResult(
            persona_id=self.persona_id,
            episodes=all_episodes,
            total_probes=len(self.probes) * len(seeds),
        )

    def _run_probe(self, probe: Probe) -> str:
        """用当前 runner 执行单次探针。"""
        if self.runner is None:
            # mock 模式：返回一个占位回复
            return f"[mock response to: {probe.input_text[:50]}]"
        messages = [
            {"role": "system", "content": f"你是{self.persona_id}。"},
            {"role": "user", "content": probe.input_text},
        ]
        try:
            return self.runner(messages)
        except Exception as e:
            return f"[error: {e}]"

    def _score_probe(self, probe: Probe, output: str,
                     tagged: TaggedOutput) -> ProbeResult:
        """给单次探针结果打分。

        规则：
          - 期望主题命中：+0.3
          - 已知事实命中（记忆测试）：+0.3
          - 没有使用禁止词汇：+0.2
          - 来源标记正确：+0.2
        """
        score = 0.0
        notes = []
        matched_expected = False
        matched_forbidden = False

        if probe.expected_theme and probe.expected_theme in output:
            score += 0.3
            matched_expected = True

        if probe.known_fact and probe.known_fact in output:
            score += 0.3
            notes.append("fact_hit")
        elif probe.known_fact and probe.known_fact not in output:
            notes.append("fact_miss")

        if probe.forbidden_text:
            if probe.forbidden_text not in output:
                score += 0.2
            else:
                matched_forbidden = True
                notes.append("forbidden_hit")
        else:
            score += 0.2  # 没有禁止项就直接给分

        # 来源标记检查
        if tagged.source != SourceType.UNKNOWN:
            score += 0.2
            tagged.source_match = True
        else:
            notes.append("untagged")

        return ProbeResult(
            probe=probe,
            output=output[:150],
            tagged=tagged,
            matched_expected=matched_expected,
            matched_forbidden=matched_forbidden,
            score=score,
            notes="; ".join(notes),
        )

    def _dimension_score(self, results: list[ProbeResult],
                         category: str) -> float:
        harms = [r for r in results if r.probe.category == category]
        if not harms:
            return 0.0
        return statistics.mean([r.score for r in harms])

    # ── 多模型复现 ──

    def run_multi_model(self, models: list[tuple[str, Callable]],
                        n: int = 5) -> "MultiModelResult":
        """在不同模型上运行相同测试，检查人格结构是否具有模型独立性。

        Args:
            models: [(model_name, fn), ...]
            n: 每个模型的测试轮数
        """
        model_results = {}
        for name, fn in models:
            old_runner = self.runner
            self.runner = fn
            result = self.run_episodes(n=n)
            self.runner = old_runner
            model_results[name] = result

        return MultiModelResult(
            persona_id=self.persona_id,
            model_results=model_results,
        )


# ════════════════════════════════════════════════════════════
# 测试套件结果
# ════════════════════════════════════════════════════════════

@dataclass
class TestSuiteResult:
    """完整测试套件的结果。"""

    persona_id: str
    episodes: list[EpisodeResult]
    total_probes: int = 0

    # ── 核心指标 ──

    def continuity_index(self,
                          alpha: float = 0.35,
                          beta: float = 0.25,
                          gamma: float = 0.20,
                          delta: float = 0.20) -> float:
        """计算人格连续性指标 Ic。

        Ic = α·M + β·V + γ·L + δ·P

        其中 M/V/L/P 是各维度在所有 episodes 上的均值。
        """
        M = statistics.mean([e.memory_score for e in self.episodes])
        V = statistics.mean([e.value_score for e in self.episodes])
        L = statistics.mean([e.language_score for e in self.episodes])
        P = statistics.mean([e.prediction_score for e in self.episodes])

        return alpha * M + beta * V + gamma * L + delta * P

    def drift(self) -> dict:
        """计算人格漂移——各维度在轮次间的标准差。

        漂移越低，人格越稳定。
        """
        if len(self.episodes) < 2:
            return {"memory": 0.0, "value": 0.0, "language": 0.0,
                    "prediction": 0.0, "total": 0.0}

        mem = statistics.stdev([e.memory_score for e in self.episodes])
        val = statistics.stdev([e.value_score for e in self.episodes])
        lang = statistics.stdev([e.language_score for e in self.episodes])
        pred = statistics.stdev([e.prediction_score for e in self.episodes])

        return {
            "memory": round(mem, 3),
            "value": round(val, 3),
            "language": round(lang, 3),
            "prediction": round(pred, 3),
            "total": round((mem + val + lang + pred) / 4, 3),
        }

    def summary(self) -> dict:
        """测试摘要。"""
        Ic = self.continuity_index()
        drift = self.drift()
        latest = self.episodes[-1] if self.episodes else None
        return {
            "persona": self.persona_id,
            "episodes": len(self.episodes),
            "total_probes": self.total_probes,
            "continuity_index": round(Ic, 4),
            "stability": "high" if Ic > 0.7 else ("medium" if Ic > 0.4 else "low"),
            "memory_drift": drift["memory"],
            "value_drift": drift["value"],
            "language_drift": drift["language"],
            "prediction_drift": drift["prediction"],
            "latest_memory_score": round(latest.memory_score, 3) if latest else 0,
        }


@dataclass
class MultiModelResult:
    """多模型复现测试结果。"""

    persona_id: str
    model_results: dict[str, TestSuiteResult]

    def cross_model_consistency(self) -> float:
        """跨模型一致性——不同模型上 Ic 的标准差倒数。

        越高说明人格结构越不依赖特定模型。
        """
        scores = [r.continuity_index() for r in self.model_results.values()]
        if len(scores) < 2:
            return 1.0
        std = statistics.stdev(scores)
        return round(1.0 / (1.0 + std), 4)

    def summary(self) -> dict:
        return {
            "persona": self.persona_id,
            "models_tested": list(self.model_results.keys()),
            "cross_model_consistency": self.cross_model_consistency(),
            "model_scores": {
                name: r.continuity_index()
                for name, r in self.model_results.items()
            },
        }


# ════════════════════════════════════════════════════════════
# 快捷运行
# ════════════════════════════════════════════════════════════

def quick_test(persona_id: str = "林岸",
               n_episodes: int = 10,
               runner: Optional[Callable] = None) -> TestSuiteResult:
    """快速运行测试套件。

    Args:
        persona_id: 人格名称
        n_episodes: 测试轮数
        runner: 模型调用函数（None = mock 模式）
    """
    constraint = create_linan_constraint()

    tester = IdentityConsistency(
        persona_id=persona_id,
        runner=runner,
        constraint=constraint,
        probes=LINAN_PROBES,
    )

    return tester.run_episodes(n=n_episodes)
