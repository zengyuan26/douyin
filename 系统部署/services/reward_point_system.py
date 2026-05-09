"""
游戏化奖励点系统

职责划分：
- 系统做：计算奖励点数量、时间位置、类型分布
- LLM做：生成每个奖励点的具体内容

奖励点类型：
- 🎯 知识奖励：抛出知识点/数据
- 🤔 思考奖励：抛出问题让用户思考
- 💡 顿悟奖励：揭示反常识真相
- 😮 惊讶奖励：给出出乎意料的数据
- 🎉 爽感奖励：情绪高潮点
- 📚 收藏奖励：干货密集点
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import math


class RewardType(Enum):
    """奖励点类型"""
    KNOWLEDGE = "knowledge"       # 🎯 知识奖励
    THINKING = "thinking"        # 🤔 思考奖励
    INSIGHT = "insight"          # 💡 顿悟奖励
    SURPRISE = "surprise"        # 😮 惊讶奖励
    EXCITEMENT = "excitement"    # 🎉 爽感奖励
    COLLECTION = "collection"     # 📚 收藏奖励


@dataclass
class RewardPoint:
    """奖励点"""
    index: int                    # 第几个奖励点
    time_start: float             # 开始时间（秒）
    time_end: float               # 结束时间（秒）
    reward_type: RewardType       # 奖励类型
    trigger_position: str         # 触发位置
    content_guidance: str         # 内容引导（给LLM的提示）
    emotion_hint: str             # 情绪提示


@dataclass
class RewardDistribution:
    """奖励分布结果"""
    total_points: int             # 总奖励点数
    points: List[RewardPoint]     # 奖励点列表
    distribution_chart: str        # 可视化图表
    density_by_period: Dict[str, float]  # 各时间段密度


class RewardPointCalculator:
    """
    奖励点计算器

    系统根据均衡器配置和视频时长计算：
    1. 奖励点数量
    2. 奖励点时间位置
    3. 奖励点类型分布
    """

    # 每段时间的基础奖励点间隔（秒）
    BASE_INTERVALS = {
        "early": 5,    # 0-10秒：每5秒
        "mid": 10,     # 10-30秒：每10秒
        "late": 15,    # 30-60秒：每15秒
        "end": 25     # 60秒+：每25秒
    }

    def __init__(self):
        self.reward_type_weights = {
            # 均衡器配置对应的奖励类型权重
            RewardType.KNOWLEDGE: {
                "info_density": 1.5,  # 信息密度高 -> 知识奖励多
                "difficulty_progression": 1.2
            },
            RewardType.THINKING: {
                "question_suspense": 1.5,  # 问题悬念高 -> 思考奖励多
            },
            RewardType.INSIGHT: {
                "difficulty_progression": 1.3,
                "emotion_fluctuation": 1.1
            },
            RewardType.SURPRISE: {
                "emotion_fluctuation": 1.4,
                "question_suspense": 1.2
            },
            RewardType.EXCITEMENT: {
                "emotion_fluctuation": 1.5,
                "reward_distribution": 1.3
            },
            RewardType.COLLECTION: {
                "info_density": 1.4
            }
        }

    def calculate_distribution(
        self,
        duration: int,
        balance_config: Dict[str, float]
    ) -> RewardDistribution:
        """
        计算奖励点分布

        系统根据配置计算结构，LLM填充内容

        Args:
            duration: 视频时长（秒）
            balance_config: 均衡器配置

        Returns:
            RewardDistribution: 奖励点分布
        """
        # 1. 计算奖励点数量
        reward_density = balance_config.get("奖励分布", 0.6)
        total_points = self._calculate_point_count(duration, reward_density)

        # 2. 计算各时间段位置
        positions = self._calculate_positions(duration, total_points, reward_density)

        # 3. 计算奖励点类型分布
        type_distribution = self._calculate_type_distribution(
            total_points,
            balance_config
        )

        # 4. 构建奖励点
        points = self._build_reward_points(
            positions,
            type_distribution,
            balance_config
        )

        # 5. 生成可视化图表
        chart = self._generate_chart(duration, points)

        # 6. 计算各时间段密度
        density = self._calculate_density(duration, points)

        return RewardDistribution(
            total_points=len(points),
            points=points,
            distribution_chart=chart,
            density_by_period=density
        )

    def _calculate_point_count(
        self,
        duration: int,
        reward_density: float
    ) -> int:
        """
        计算奖励点数量

        系统规则：
        - 基础：每30秒1个奖励点
        - 密度系数：0.3-1.0映射为0.5-2.0倍
        """
        base_count = duration / 30
        density_multiplier = 0.5 + reward_density * 1.5

        return max(1, round(base_count * density_multiplier))

    def _calculate_positions(
        self,
        duration: int,
        total_points: int,
        reward_density: float
    ) -> List[Dict[str, float]]:
        """
        计算奖励点时间位置（前密后疏）

        系统规则：
        - 奖励分布 30%：均匀分布
        - 奖励分布 60%：适度前密
        - 奖励分布 100%：强烈前密
        """
        if total_points <= 1:
            return [{"start": 0, "end": duration}]

        positions = []
        total_weight = 0

        # 计算各时间段的权重
        for i in range(total_points):
            position_ratio = (i + 1) / total_points
            # 越靠前权重越大（前密后疏）
            weight = (1 - position_ratio) * reward_density + (1 - reward_density) * 0.5 + 0.5
            total_weight += weight

        # 生成位置
        cumulative_time = 0
        for i in range(total_points):
            position_ratio = (i + 1) / total_points
            weight = (1 - position_ratio) * reward_density + (1 - reward_density) * 0.5 + 0.5

            # 计算到当前位置的时间
            time_portion = (weight / total_weight) * duration
            next_time = min(cumulative_time + time_portion, duration)

            positions.append({
                "start": round(cumulative_time, 1),
                "end": round(next_time, 1)
            })

            cumulative_time = next_time

        return positions

    def _calculate_type_distribution(
        self,
        total_points: int,
        balance_config: Dict[str, float]
    ) -> Dict[RewardType, int]:
        """
        计算奖励点类型分布

        系统根据均衡器参数计算各类型数量
        """
        # 计算各类型的得分
        type_scores = {}
        for reward_type, weights in self.reward_type_weights.items():
            score = 0
            for param, weight in weights.items():
                param_value = balance_config.get(param, 0.5)
                score += param_value * weight
            type_scores[reward_type] = score

        # 归一化并分配数量
        total_score = sum(type_scores.values())
        type_counts = {}

        for reward_type, score in type_scores.items():
            ratio = score / total_score if total_score > 0 else 0
            count = max(1, round(ratio * total_points))
            type_counts[reward_type] = count

        # 调整总数
        current_total = sum(type_counts.values())
        diff = total_points - current_total

        if diff != 0:
            # 最多的类型加减
            max_type = max(type_counts, key=type_counts.get)
            type_counts[max_type] += diff

        return type_counts

    def _build_reward_points(
        self,
        positions: List[Dict[str, float]],
        type_distribution: Dict[RewardType, int],
        balance_config: Dict[str, float]
    ) -> List[RewardPoint]:
        """构建奖励点列表"""
        points = []

        # 类型分配
        type_list = []
        for reward_type, count in type_distribution.items():
            type_list.extend([reward_type] * count)

        # 打乱顺序
        import random
        random.seed(42)
        random.shuffle(type_list)

        # 生成内容引导
        content_guides = {
            RewardType.KNOWLEDGE: "抛出一个与话题相关的数据、技巧或知识点，让用户觉得'学到了'",
            RewardType.THINKING: "抛出一个引发思考的问题，让用户停下来想想",
            RewardType.INSIGHT: "揭示一个反常识的真相或洞察，让用户有'原来如此'的感觉",
            RewardType.SURPRISE: "给出一个出乎意料的数据或事实，让用户惊讶",
            RewardType.EXCITEMENT: "创造一个情绪释放点，让用户感到兴奋或爽",
            RewardType.COLLECTION: "输出一个实用的干货点，让用户想收藏"
        }

        emotion_hints = {
            RewardType.KNOWLEDGE: "好奇、期待",
            RewardType.THINKING: "思考、共鸣",
            RewardType.INSIGHT: "恍然大悟、认知刷新",
            RewardType.SURPRISE: "惊讶、震惊",
            RewardType.EXCITEMENT: "兴奋、爽",
            RewardType.COLLECTION: "满足、实用"
        }

        # 时间段标签
        def get_period_label(start: float) -> str:
            if start < 10:
                return "开场密集区"
            elif start < 30:
                return "中段递进区"
            elif start < 60:
                return "后段价值区"
            else:
                return "结尾升华区"

        for i, pos in enumerate(positions):
            if i >= len(type_list):
                reward_type = type_list[0]
            else:
                reward_type = type_list[i]

            point = RewardPoint(
                index=i + 1,
                time_start=pos["start"],
                time_end=pos["end"],
                reward_type=reward_type,
                trigger_position=get_period_label(pos["start"]),
                content_guidance=content_guides.get(reward_type, ""),
                emotion_hint=emotion_hints.get(reward_type, "")
            )
            points.append(point)

        return points

    def _generate_chart(
        self,
        duration: int,
        points: List[RewardPoint]
    ) -> str:
        """生成可视化图表"""
        chart = "\n┌" + "─" * 60 + "┐\n"
        chart += "│" + "奖励点分布 (前密后疏)".center(60) + "│\n"
        chart += "├" + "─" * 60 + "┤\n"

        # 生成时间轴
        segments = 12
        segment_duration = duration / segments

        for i, point in enumerate(points):
            segment = int(point.time_start / segment_duration)
            bar = " " * segment + "●"
            time_label = f"{int(point.time_start)}s"
            type_emoji = self._get_type_emoji(point.reward_type)

            chart += f"│ {time_label:>4} {type_emoji} {'─' * (segment - 1) if segment > 0 else ''}{'●':^5}{'─' * (55 - segment - 5)} │\n"

        chart += "└" + "─" * 60 + "┘"

        return chart

    def _get_type_emoji(self, reward_type: RewardType) -> str:
        emojis = {
            RewardType.KNOWLEDGE: "🎯",
            RewardType.THINKING: "🤔",
            RewardType.INSIGHT: "💡",
            RewardType.SURPRISE: "😮",
            RewardType.EXCITEMENT: "🎉",
            RewardType.COLLECTION: "📚"
        }
        return emojis.get(reward_type, "●")

    def _calculate_density(
        self,
        duration: int,
        points: List[RewardPoint]
    ) -> Dict[str, float]:
        """计算各时间段密度"""
        periods = {
            "0-10秒": (0, 10),
            "10-30秒": (10, 30),
            "30-60秒": (30, 60),
            "60秒+": (60, duration)
        }

        density = {}
        for period_name, (start, end) in periods.items():
            count = sum(
                1 for p in points
                if start <= p.time_start < end or (start <= p.time_end <= end)
            )
            period_duration = end - start if end <= duration else duration - start
            density[period_name] = round(count / max(period_duration / 10, 1), 2)

        return density

    def generate_llm_prompt(
        self,
        distribution: RewardDistribution,
        topic: str,
        balance_config: Dict[str, float]
    ) -> str:
        """
        生成给LLM的提示词

        系统传递结构化数据，LLM填充内容
        """
        prompt = f"""你是一个短视频脚本专家。请为以下选题生成各奖励点的具体内容。

【选题】{topic}
【视频时长】{int(distribution.points[-1].time_end if distribution.points else 0)}秒

【奖励点配置】
"""

        for point in distribution.points:
            emoji = self._get_type_emoji(point.reward_type)
            prompt += f"""
---
第{point.index}个奖励点 ({point.trigger_position})
时间: {int(point.time_start)}-{int(point.time_end)}秒
类型: {emoji} {point.reward_type.value}
情绪: {point.emotion_hint}

内容要求: {point.content_guidance}

请生成:
1. 具体的口播文案（20-50字）
2. 配合的视觉描述
3. 该点的互动引导（可选）
"""

        prompt += """
【要求】
1. 每个奖励点的内容要与选题相关且自然衔接
2. 情绪要符合提示的情绪要求
3. 口播文案要口语化、节奏感强
4. 可以添加适当的数字、数据增加说服力
"""
        return prompt


class RewardPointService:
    """
    奖励点服务

    对外提供统一的奖励点计算接口
    """

    def __init__(self):
        self.calculator = RewardPointCalculator()

    def calculate(
        self,
        duration: int,
        balance_config: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        计算奖励点分布

        Args:
            duration: 视频时长（秒）
            balance_config: 均衡器配置

        Returns:
            dict: 奖励点分布（包含结构供LLM使用）
        """
        distribution = self.calculator.calculate_distribution(
            duration,
            balance_config
        )

        return {
            "total_points": distribution.total_points,
            "points": [
                {
                    "index": p.index,
                    "time_range": f"{int(p.time_start)}-{int(p.time_end)}秒",
                    "time_start": p.time_start,
                    "time_end": p.time_end,
                    "reward_type": p.reward_type.value,
                    "reward_type_emoji": self.calculator._get_type_emoji(p.reward_type),
                    "trigger_position": p.trigger_position,
                    "content_guidance": p.content_guidance,
                    "emotion_hint": p.emotion_hint,
                    # 以下字段由LLM填充
                    "narration": None,
                    "visual_description": None,
                    "interaction_guide": None
                }
                for p in distribution.points
            ],
            "distribution_chart": distribution.distribution_chart,
            "density_by_period": distribution.density_by_period,
            "llm_prompt": self.calculator.generate_llm_prompt(
                distribution,
                "[选题]",  # 调用时填充
                balance_config
            )
        }

    def generate_visual_chart(
        self,
        duration: int,
        points: List[Dict[str, Any]]
    ) -> str:
        """
        生成可视化图表

        Args:
            duration: 视频时长（秒）
            points: 奖励点列表

        Returns:
            str: 可视化图表字符串
        """
        if not points or duration <= 0:
            return "○" * 10

        # 生成进度条
        total_length = 30  # 总长度
        char_per_second = total_length / duration

        chart = ["○"] * total_length

        for point in points:
            time_start = point.get('time_start', 0)
            position = int(time_start * char_per_second)
            if 0 <= position < total_length:
                emoji = point.get('reward_type_emoji', '●')
                if len(emoji) <= 1:
                    chart[position] = '●'
                else:
                    chart[position] = emoji

        return ''.join(chart)

    def fill_with_llm_content(
        self,
        reward_points: List[Dict[str, Any]],
        llm_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        合并LLM生成的内容

        Args:
            reward_points: 系统计算的奖励点结构
            llm_results: LLM生成的内容列表

        Returns:
            List[Dict]: 合并后的完整奖励点
        """
        result = []
        for i, point in enumerate(reward_points):
            filled_point = point.copy()

            if i < len(llm_results):
                llm_content = llm_results[i]
                filled_point.update({
                    "narration": llm_content.get("narration", ""),
                    "visual_description": llm_content.get("visual_description", ""),
                    "interaction_guide": llm_content.get("interaction_guide", "")
                })
            else:
                # 标记未填充
                filled_point["narration"] = "（待LLM生成）"
                filled_point["visual_description"] = "（待LLM生成）"
                filled_point["interaction_guide"] = None

            result.append(filled_point)

        return result


# =============================================================================
# 便捷函数
# =============================================================================

def calculate_reward_points(
    duration: int,
    balance_config: Dict[str, float]
) -> Dict[str, Any]:
    """
    计算奖励点分布的便捷函数

    Args:
        duration: 视频时长（秒）
        balance_config: 均衡器配置

    Returns:
        dict: 奖励点分布
    """
    service = RewardPointService()
    return service.calculate(duration, balance_config)


def generate_reward_prompt(
    reward_data: Dict[str, Any],
    topic: str
) -> str:
    """
    生成奖励点内容填充的LLM提示词

    Args:
        reward_data: 奖励点数据
        topic: 选题

    Returns:
        str: LLM提示词
    """
    points = reward_data.get("points", [])
    calculator = RewardPointCalculator()

    # 生成位置表
    prompt = f"""请为以下短视频脚本生成奖励点的具体内容。

【选题】{topic}
【奖励点数量】{len(points)}个

"""

    for point in points:
        prompt += f"""
## 奖励点 {point['index']} ({point['trigger_position']})
- 时间：{point['time_range']}
- 类型：{point['reward_type_emoji']} {point['reward_type']}
- 情绪：{point['emotion_hint']}
- 要求：{point['content_guidance']}

"""

    prompt += """
请为每个奖励点生成以下内容（JSON数组格式）：
```json
[
  {
    "narration": "口播文案（20-50字）",
    "visual_description": "视觉描述",
    "interaction_guide": "互动引导（可选）"
  }
]
```
"""
    return prompt
