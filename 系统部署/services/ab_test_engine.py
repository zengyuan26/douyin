"""
A/B测试引擎

用于测试不同均衡器设置的实际效果对比

功能：
- 记录不同均衡器配置的脚本版本
- 追踪发布后的效果数据（播放量、点赞、评论、转发）
- 计算各配置的胜出方案
- 提供优化建议
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import hashlib

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """效果指标类型"""
    PLAYS = "plays"           # 播放量
    LIKES = "likes"          # 点赞
    COMMENTS = "comments"     # 评论
    SHARES = "shares"        # 转发
    COMPLETION = "completion" # 完播率
    FOLLOW = "follow"         # 关注


@dataclass
class BalanceConfig:
    """均衡器配置"""
    info_density: float = 0.6      # 信息密度 30-100%
    question_suspense: float = 0.5 # 问题悬念 30-100%
    emotion_fluctuation: float = 0.6  # 情绪波动 30-100%
    interaction_freq: float = 0.5  # 互动频率 30-100%
    reward_distribution: float = 0.6  # 奖励分布 30-100%
    difficulty_progression: float = 0.6  # 难度递进 30-100%

    def to_dict(self) -> Dict[str, float]:
        return {
            "信息密度": self.info_density,
            "问题悬念": self.question_suspense,
            "情绪波动": self.emotion_fluctuation,
            "互动频率": self.interaction_freq,
            "奖励分布": self.reward_distribution,
            "难度递进": self.difficulty_progression
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "BalanceConfig":
        return cls(
            info_density=data.get("信息密度", 0.6),
            question_suspense=data.get("问题悬念", 0.5),
            emotion_fluctuation=data.get("情绪波动", 0.6),
            interaction_freq=data.get("互动频率", 0.5),
            reward_distribution=data.get("奖励分布", 0.6),
            difficulty_progression=data.get("难度递进", 0.6)
        )

    def get_hash(self) -> str:
        """获取配置的唯一哈希"""
        config_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()[:8]


@dataclass
class EffectMetrics:
    """效果指标"""
    plays: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    completion_rate: float = 0.0  # 完播率 0-1
    follow: int = 0
    cpm: float = 0.0  # 每千次播放成本（可选）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plays": self.plays,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "completion_rate": self.completion_rate,
            "follow": self.follow
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EffectMetrics":
        return cls(
            plays=data.get("plays", 0),
            likes=data.get("likes", 0),
            comments=data.get("comments", 0),
            shares=data.get("shares", 0),
            completion_rate=data.get("completion_rate", 0.0),
            follow=data.get("follow", 0)
        )


@dataclass
class ABTestVariant:
    """A/B测试变体"""
    variant_id: str
    script_id: str  # 关联的脚本ID
    config: BalanceConfig
    metrics: EffectMetrics
    status: str = "running"  # running, completed, paused
    created_at: str = ""
    published_at: Optional[str] = None
    completed_at: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "script_id": self.script_id,
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "status": self.status,
            "created_at": self.created_at,
            "published_at": self.published_at,
            "completed_at": self.completed_at,
            "notes": self.notes
        }


@dataclass
class ABTestResult:
    """A/B测试结果"""
    test_id: str
    variants: List[ABTestVariant]
    winner_id: Optional[str]
    confidence: float  # 置信度 0-1
    metrics_summary: Dict[str, Any]
    recommendations: List[str]
    created_at: str
    completed_at: Optional[str] = None


class ABTestEngine:
    """A/B测试引擎"""

    # 指标权重（用于计算综合得分）
    METRIC_WEIGHTS = {
        MetricType.PLAYS: 0.15,
        MetricType.LIKES: 0.25,
        MetricType.COMMENTS: 0.20,
        MetricType.SHARES: 0.15,
        MetricType.COMPLETION: 0.15,
        MetricType.FOLLOW: 0.10
    }

    # 最小样本量（用于统计显著性）
    MIN_SAMPLE_SIZE = 100

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.95

    def __init__(self):
        self._tests: Dict[str, ABTestResult] = {}
        self._config_cache: Dict[str, List[ABTestVariant]] = {}

    def create_test(
        self,
        test_id: str,
        variants: List[Dict[str, Any]]
    ) -> ABTestResult:
        """
        创建A/B测试

        Args:
            test_id: 测试ID
            variants: 变体列表，每个包含：
                - variant_id: 变体ID
                - script_id: 脚本ID
                - config: 均衡器配置

        Returns:
            ABTestResult: 测试结果
        """
        now = datetime.now().isoformat()

        ab_variants = []
        for v in variants:
            config = BalanceConfig.from_dict(v.get("config", {}))
            variant = ABTestVariant(
                variant_id=v["variant_id"],
                script_id=v["script_id"],
                config=config,
                metrics=EffectMetrics(),
                status="running",
                created_at=now
            )
            ab_variants.append(variant)

        result = ABTestResult(
            test_id=test_id,
            variants=ab_variants,
            winner_id=None,
            confidence=0.0,
            metrics_summary={},
            recommendations=[],
            created_at=now
        )

        self._tests[test_id] = result

        # 缓存配置
        for v in ab_variants:
            config_hash = v.config.get_hash()
            if config_hash not in self._config_cache:
                self._config_cache[config_hash] = []
            self._config_cache[config_hash].append(v)

        logger.info(f"Created A/B test: {test_id} with {len(variants)} variants")
        return result

    def update_metrics(
        self,
        test_id: str,
        variant_id: str,
        metrics: Dict[str, Any]
    ):
        """
        更新变体效果指标

        Args:
            test_id: 测试ID
            variant_id: 变体ID
            metrics: 效果指标
        """
        if test_id not in self._tests:
            logger.warning(f"Test not found: {test_id}")
            return

        result = self._tests[test_id]
        variant = next((v for v in result.variants if v.variant_id == variant_id), None)

        if not variant:
            logger.warning(f"Variant not found: {variant_id}")
            return

        # 更新指标
        variant.metrics = EffectMetrics.from_dict(metrics)

        logger.info(f"Updated metrics for {variant_id}: {metrics}")

    def complete_variant(
        self,
        test_id: str,
        variant_id: str
    ):
        """标记变体完成"""
        if test_id not in self._tests:
            return

        result = self._tests[test_id]
        variant = next((v for v in result.variants if v.variant_id == variant_id), None)

        if variant:
            variant.status = "completed"
            variant.completed_at = datetime.now().isoformat()

    def analyze_results(self, test_id: str) -> ABTestResult:
        """
        分析测试结果

        Args:
            test_id: 测试ID

        Returns:
            ABTestResult: 分析后的结果
        """
        if test_id not in self._tests:
            raise ValueError(f"Test not found: {test_id}")

        result = self._tests[test_id]

        # 计算每个变体的综合得分
        variant_scores = []
        for variant in result.variants:
            if variant.metrics.plays == 0:
                continue

            score = self._calculate_composite_score(variant.metrics)
            variant_scores.append({
                "variant_id": variant.variant_id,
                "score": score,
                "metrics": variant.metrics
            })

        # 找出胜出者
        if variant_scores:
            # 按得分排序
            variant_scores.sort(key=lambda x: x["score"], reverse=True)

            winner = variant_scores[0]
            result.winner_id = winner["variant_id"]

            # 计算置信度（简化的统计方法）
            if len(variant_scores) > 1:
                score_diff = variant_scores[0]["score"] - variant_scores[1]["score"]
                # 样本量越大，差异越容易显著
                sample_factor = min(result.variants[0].metrics.plays / 1000, 1.0)
                result.confidence = min(0.5 + score_diff * 0.5 * sample_factor, 0.99)
            else:
                result.confidence = 1.0

            # 生成建议
            result.recommendations = self._generate_recommendations(
                variant_scores,
                result.variants
            )

        # 计算指标汇总
        result.metrics_summary = self._calculate_summary(variant_scores)

        result.completed_at = datetime.now().isoformat()

        return result

    def _calculate_composite_score(self, metrics: EffectMetrics) -> float:
        """计算综合得分"""
        score = 0.0

        # 标准化各指标（基于播放量的相对值）
        total_interactions = metrics.likes + metrics.comments + metrics.shares
        interaction_rate = total_interactions / max(metrics.plays, 1)

        # 各指标得分
        score += self.METRIC_WEIGHTS[MetricType.PLAYS] * min(metrics.plays / 10000, 1.0) * 100
        score += self.METRIC_WEIGHTS[MetricType.LIKES] * min(metrics.likes / 1000, 1.0) * 100
        score += self.METRIC_WEIGHTS[MetricType.COMMENTS] * min(metrics.comments / 100, 1.0) * 100
        score += self.METRIC_WEIGHTS[MetricType.SHARES] * min(metrics.shares / 50, 1.0) * 100
        score += self.METRIC_WEIGHTS[MetricType.COMPLETION] * metrics.completion_rate * 100
        score += self.METRIC_WEIGHTS[MetricType.FOLLOW] * min(metrics.follow / 100, 1.0) * 100

        return score

    def _generate_recommendations(
        self,
        variant_scores: List[Dict],
        variants: List[ABTestVariant]
    ) -> List[str]:
        """生成优化建议"""
        recommendations = []

        if not variant_scores:
            return ["数据不足，无法生成建议"]

        winner = variant_scores[0]
        winner_variant = next(v for v in variants if v.variant_id == winner["variant_id"])

        # 赢家配置建议
        recommendations.append(
            f"推荐使用均衡器配置（胜出变体: {winner['variant_id']}）："
        )
        for param, value in winner_variant.config.to_dict().items():
            recommendations.append(f"  - {param}: {value:.0%}")

        # 分析各项指标
        if len(variant_scores) > 1:
            loser = variant_scores[-1]
            loser_variant = next(v for v in variants if v.variant_id == loser["variant_id"])

            # 找出差异最大的参数
            param_diffs = []
            for param in winner_variant.config.to_dict():
                w_val = winner_variant.config.to_dict()[param]
                l_val = loser_variant.config.to_dict()[param]
                diff = abs(w_val - l_val)
                param_diffs.append((param, w_val, l_val, diff))

            # 按差异排序
            param_diffs.sort(key=lambda x: x[3], reverse=True)

            if param_diffs and param_diffs[0][3] > 0.1:
                param, w, l, d = param_diffs[0]
                recommendations.append(
                    f"\n关键差异参数：{param} "
                    f"(胜出:{w:.0%} vs 落后:{l:.0%})，"
                    f"建议提升至 {w:.0%}"
                )

        return recommendations

    def _calculate_summary(
        self,
        variant_scores: List[Dict]
    ) -> Dict[str, Any]:
        """计算指标汇总"""
        if not variant_scores:
            return {}

        summary = {
            "total_variants": len(variant_scores),
            "best_score": variant_scores[0]["score"],
            "worst_score": variant_scores[-1]["score"],
            "score_range": variant_scores[0]["score"] - variant_scores[-1]["score"],
            "variants": []
        }

        for vs in variant_scores:
            summary["variants"].append({
                "variant_id": vs["variant_id"],
                "score": round(vs["score"], 2),
                "metrics": vs["metrics"].to_dict()
            })

        return summary

    def get_test(self, test_id: str) -> Optional[ABTestResult]:
        """获取测试"""
        return self._tests.get(test_id)

    def list_tests(self) -> List[Dict[str, Any]]:
        """列出所有测试"""
        return [
            {
                "test_id": t.test_id,
                "created_at": t.created_at,
                "variants_count": len(t.variants),
                "winner_id": t.winner_id,
                "confidence": round(t.confidence, 2),
                "status": "completed" if t.completed_at else "running"
            }
            for t in self._tests.values()
        ]

    def find_similar_config(self, config: BalanceConfig) -> List[ABTestVariant]:
        """查找相似配置的历史测试结果"""
        config_hash = config.get_hash()

        # 精确匹配
        if config_hash in self._config_cache:
            return self._config_cache[config_hash]

        # 模糊匹配（参数差异小于20%）
        similar = []
        for cached_variants in self._config_cache.values():
            if not cached_variants:
                continue

            cached_config = cached_variants[0].config
            diff = self._calculate_config_diff(config, cached_config)

            if diff < 0.2:
                similar.extend(cached_variants)

        return similar

    def _calculate_config_diff(self, config1: BalanceConfig, config2: BalanceConfig) -> float:
        """计算两个配置的差异度"""
        d1 = config1.to_dict()
        d2 = config2.to_dict()

        total_diff = 0
        for key in d1:
            total_diff += abs(d1[key] - d2[key])

        return total_diff / len(d1)

    def suggest_config_adjustment(
        self,
        current_config: BalanceConfig,
        target_metric: MetricType,
        current_metrics: EffectMetrics
    ) -> Dict[str, Any]:
        """
        基于效果数据建议配置调整

        Args:
            current_config: 当前配置
            target_metric: 目标提升的指标
            current_metrics: 当前效果指标

        Returns:
            dict: 调整建议
        """
        suggestions = []

        # 基于目标指标分析需要调整的参数
        if target_metric == MetricType.PLAYS:
            # 提升播放量 -> 强化前3秒钩子
            suggestions.append({
                "parameter": "问题悬念",
                "current": current_config.question_suspense,
                "suggested": min(current_config.question_suspense + 0.1, 1.0),
                "reason": "强悬念钩子提升点击率"
            })
            suggestions.append({
                "parameter": "奖励分布",
                "current": current_config.reward_distribution,
                "suggested": min(current_config.reward_distribution + 0.15, 1.0),
                "reason": "前密后疏提升完播率"
            })

        elif target_metric == MetricType.COMPLETION:
            # 提升完播率 -> 优化奖励分布和难度递进
            suggestions.append({
                "parameter": "奖励分布",
                "current": current_config.reward_distribution,
                "suggested": min(current_config.reward_distribution + 0.2, 1.0),
                "reason": "前密后疏提升完播"
            })
            suggestions.append({
                "parameter": "难度递进",
                "current": current_config.difficulty_progression,
                "suggested": min(current_config.difficulty_progression + 0.1, 1.0),
                "reason": "层层递进维持观看兴趣"
            })

        elif target_metric == MetricType.LIKES:
            # 提升点赞 -> 强化情绪波动和互动引导
            suggestions.append({
                "parameter": "情绪波动",
                "current": current_config.emotion_fluctuation,
                "suggested": min(current_config.emotion_fluctuation + 0.15, 1.0),
                "reason": "情绪共鸣促进点赞"
            })
            suggestions.append({
                "parameter": "互动频率",
                "current": current_config.interaction_freq,
                "suggested": min(current_config.interaction_freq + 0.1, 1.0),
                "reason": "互动引导增加参与感"
            })

        elif target_metric == MetricType.COMMENTS:
            # 提升评论 -> 强化问题悬念和互动频率
            suggestions.append({
                "parameter": "问题悬念",
                "current": current_config.question_suspense,
                "suggested": min(current_config.question_suspense + 0.2, 1.0),
                "reason": "悬念引发讨论"
            })
            suggestions.append({
                "parameter": "互动频率",
                "current": current_config.interaction_freq,
                "suggested": min(current_config.interaction_freq + 0.15, 1.0),
                "reason": "直接引导评论"
            })

        elif target_metric == MetricType.SHARES:
            # 提升转发 -> 强化价值感和情绪共鸣
            suggestions.append({
                "parameter": "信息密度",
                "current": current_config.info_density,
                "suggested": min(current_config.info_density + 0.15, 1.0),
                "reason": "高价值内容促进转发"
            })
            suggestions.append({
                "parameter": "情绪波动",
                "current": current_config.emotion_fluctuation,
                "suggested": min(current_config.emotion_fluctuation + 0.1, 1.0),
                "reason": "情绪触动驱动分享"
            })

        return {
            "target_metric": target_metric.value,
            "current_metrics": current_metrics.to_dict(),
            "adjustments": suggestions
        }


# =============================================================================
# 便捷函数
# =============================================================================

def create_ab_test(
    test_id: str,
    configs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    创建A/B测试的便捷函数

    Args:
        test_id: 测试ID
        configs: 配置列表

    Returns:
        dict: 测试结果
    """
    engine = ABTestEngine()
    result = engine.create_test(test_id, configs)
    return result.to_dict() if hasattr(result, 'to_dict') else {
        "test_id": result.test_id,
        "variants": [v.to_dict() for v in result.variants],
        "created_at": result.created_at
    }


def analyze_ab_test(test_id: str) -> Dict[str, Any]:
    """分析A/B测试结果"""
    engine = ABTestEngine()
    # 实际使用时应该从数据库加载测试数据
    # 这里返回示例结构
    return {
        "test_id": test_id,
        "winner_id": "variant_a",
        "confidence": 0.85,
        "recommendations": [
            "推荐使用均衡器配置：信息密度70%, 问题悬念60%"
        ]
    }


def suggest_config(
    config: Dict[str, float],
    target_metric: str,
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """
    建议配置调整

    Args:
        config: 当前配置
        target_metric: 目标指标
        metrics: 当前效果指标

    Returns:
        dict: 调整建议
    """
    engine = ABTestEngine()
    balance_config = BalanceConfig.from_dict(config)

    try:
        metric_type = MetricType(target_metric)
        effect_metrics = EffectMetrics.from_dict(metrics)

        return engine.suggest_config_adjustment(
            balance_config,
            metric_type,
            effect_metrics
        )
    except ValueError:
        return {"error": f"Unknown metric: {target_metric}"}
