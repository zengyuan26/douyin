"""
短视频脚本评分服务

基于方案设计的评分体系：
- 情绪评分 (30%): 情绪词密度、情绪转折、情绪峰值位置
- 节奏评分 (30%): 前3秒钩子强度、奖励点分布、难度递进曲线
- 互动评分 (40%): 问句密度、CTA出现次数、互动引导

评分范围: 0-100分
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TrustSourceType(Enum):
    """信任来源类型"""
    KNOWLEDGE = "knowledge"      # 知识型
    PERSONA = "persona"         # 人设型
    INSTITUTION = "institution" # 机构型
    PRODUCT = "product"         # 产品型


@dataclass
class ScoreDimension:
    """评分维度"""
    name: str
    score: float
    weight: float
    details: Dict[str, float]
    suggestion: str = ""


@dataclass
class ScriptScoreReport:
    """脚本评分报告"""
    total_score: float
    grade: str
    passed: bool
    dimensions: List[ScoreDimension]
    suggestions: List[str]
    emotion_score: float
    rhythm_score: float
    interaction_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_score": round(self.total_score, 1),
            "grade": self.grade,
            "passed": self.passed,
            "dimensions": [
                {
                    "name": d.name,
                    "score": round(d.score, 1),
                    "weight": d.weight,
                    "details": {k: round(v, 1) for k, v in d.details.items()},
                    "suggestion": d.suggestion
                }
                for d in self.dimensions
            ],
            "suggestions": self.suggestions,
            "emotion_score": round(self.emotion_score, 1),
            "rhythm_score": round(self.rhythm_score, 1),
            "interaction_score": round(self.interaction_score, 1)
        }


# =============================================================================
# 情绪词典
# =============================================================================
EMOTION_WORDS = {
    # 强正面情绪
    "强正面": [
        "太棒了", "绝了", "牛", "惊艳", "震撼", "狂喜", "激动", "兴奋",
        "爆哭", "笑死", "笑喷", "哭死", "爱了", "绝了", "YYDS", "神仙",
        "天花板", "无敌", "完美", "满分", "超赞", "强推", "必买", "疯狂"
    ],
    # 正面情绪
    "正面": [
        "开心", "高兴", "快乐", "幸福", "满足", "期待", "放心", "温暖",
        "感动", "治愈", "舒适", "轻松", "自在", "美好", "享受", "舒服",
        "赞", "好", "不错", "喜欢", "推荐", "种草", "值得", "划算"
    ],
    # 强负面情绪
    "强负面": [
        "崩溃", "绝望", "窒息", "无语", "气死", "扎心", "暴击", "泪目",
        "哭死", "心痛", "心碎", "扎心了", "太难了", "救命", "要命", "疯"
    ],
    # 负面情绪
    "负面": [
        "难过", "失望", "后悔", "焦虑", "担心", "害怕", "遗憾", "无奈",
        "郁闷", "烦躁", "纠结", "难受", "坑", "翻车", "踩雷", "差"
    ],
    # 疑问情绪
    "疑问": [
        "为什么", "怎么", "如何", "是不是", "会不会", "能不能",
        "真的吗", "竟然", "居然", "没想到", "想不到", "震惊"
    ],
    # 惊讶情绪
    "惊讶": [
        "惊", "居然", "竟然", "万万没想到", "没想到", "不可思议",
        "难以置信", "震惊", "吓人", "恐怖", "可怕", "夸张"
    ]
}

# 情绪词权重
EMOTION_WEIGHTS = {
    "强正面": 2.0,
    "正面": 1.0,
    "强负面": 1.5,
    "负面": 0.8,
    "疑问": 1.2,
    "惊讶": 1.5
}

# =============================================================================
# 钩子关键词
# =============================================================================
HOOK_KEYWORDS = {
    "痛点": ["崩溃", "扎心", "太难了", "救命", "有人跟我一样", "困扰", "问题", "烦恼"],
    "悬念": ["最后", "结果", "没想到", "竟然", "揭秘", "真相", "秘密", "内幕"],
    "冲突": ["但是", "然而", "其实", "偏偏", "竟然", "居然", "对比", "反差"],
    "反差": ["别人", "以为", "以为", "原来", "竟然", "差距", "区别", "不同"],
    "数字": ["3个", "5个", "7个", "10个", "1招", "3步", "秘诀", "技巧"],
    "金句": ["记住", "一定要", "千万别", "最重要", "关键", "核心", "本质"]
}

# =============================================================================
# 互动关键词
# =============================================================================
INTERACTION_KEYWORDS = {
    "问句": ["吗", "？", "是不是", "会不会", "有没有", "你", "你们", "你呢"],
    "cta": ["关注", "点赞", "评论", "收藏", "转发", "私信", "联系我们", "点击"],
    "引导": ["来说说", "聊聊", "你们觉得", "评论区", "告诉我", "一起"]
}


class ScriptScorer:
    """短视频脚本评分器"""

    # 评分权重配置
    WEIGHTS = {
        "emotion": 0.30,
        "rhythm": 0.30,
        "interaction": 0.40
    }

    # 及格分数线（按信任来源类型）
    PASS_THRESHOLDS = {
        TrustSourceType.KNOWLEDGE: 75,
        TrustSourceType.PERSONA: 70,
        TrustSourceType.INSTITUTION: 75,
        TrustSourceType.PRODUCT: 70
    }

    # 评分等级
    GRADES = [
        (95, "S", "神级"),
        (90, "A+", "优秀"),
        (85, "A", "良好"),
        (80, "B+", "较好"),
        (70, "B", "一般"),
        (60, "C", "及格"),
        (0, "D", "不及格")
    ]

    def __init__(self):
        self.emotion_patterns = self._compile_emotion_patterns()

    def _compile_emotion_patterns(self) -> Dict[str, re.Pattern]:
        """编译情绪词正则表达式"""
        patterns = {}
        for category, words in EMOTION_WORDS.items():
            # 转义特殊字符并用|连接
            escaped_words = [re.escape(w) for w in words]
            pattern_str = "|".join(escaped_words)
            patterns[category] = re.compile(pattern_str)
        return patterns

    def score(
        self,
        script: Dict[str, Any],
        trust_source: TrustSourceType = TrustSourceType.KNOWLEDGE
    ) -> ScriptScoreReport:
        """
        对短视频脚本进行评分

        Args:
            script: 脚本数据，包含以下字段：
                - title: 标题
                - opening: 开场钩子
                - scenes: 分镜列表
                - duration: 时长（秒）
                - narration: 口播文案
            trust_source: 信任来源类型，影响评分权重

        Returns:
            ScriptScoreReport: 评分报告
        """
        # 合并所有文本内容
        all_text = self._extract_text(script)

        # 各维度评分
        emotion_result = self._score_emotion(all_text, script)
        rhythm_result = self._score_rhythm(all_text, script)
        interaction_result = self._score_interaction(all_text, script)

        # 计算总分
        total_score = (
            emotion_result["score"] * self.WEIGHTS["emotion"] +
            rhythm_result["score"] * self.WEIGHTS["rhythm"] +
            interaction_result["score"] * self.WEIGHTS["interaction"]
        )

        # 确定等级
        grade, grade_label = self._get_grade(total_score)

        # 获取及格线
        threshold = self.PASS_THRESHOLDS.get(trust_source, 75)
        passed = total_score >= threshold

        # 收集建议
        suggestions = []
        suggestions.extend(emotion_result.get("suggestions", []))
        suggestions.extend(rhythm_result.get("suggestions", []))
        suggestions.extend(interaction_result.get("suggestions", []))

        # 构建报告
        dimensions = [
            ScoreDimension(
                name="情绪评分",
                score=emotion_result["score"],
                weight=self.WEIGHTS["emotion"],
                details=emotion_result.get("details", {}),
                suggestion="; ".join(emotion_result.get("suggestions", [])) if emotion_result.get("suggestions") else ""
            ),
            ScoreDimension(
                name="节奏评分",
                score=rhythm_result["score"],
                weight=self.WEIGHTS["rhythm"],
                details=rhythm_result.get("details", {}),
                suggestion="; ".join(rhythm_result.get("suggestions", [])) if rhythm_result.get("suggestions") else ""
            ),
            ScoreDimension(
                name="互动评分",
                score=interaction_result["score"],
                weight=self.WEIGHTS["interaction"],
                details=interaction_result.get("details", {}),
                suggestion="; ".join(interaction_result.get("suggestions", [])) if interaction_result.get("suggestions") else ""
            )
        ]

        return ScriptScoreReport(
            total_score=total_score,
            grade=f"{grade}({grade_label})",
            passed=passed,
            dimensions=dimensions,
            suggestions=suggestions,
            emotion_score=emotion_result["score"],
            rhythm_score=rhythm_result["score"],
            interaction_score=interaction_result["score"]
        )

    def _extract_text(self, script: Dict[str, Any]) -> str:
        """提取脚本中的所有文本内容"""
        texts = []

        # 标题
        if script.get("title"):
            texts.append(script["title"])

        # 开场
        if script.get("opening"):
            texts.append(script["opening"])

        # 分镜口播
        scenes = script.get("scenes", [])
        for scene in scenes:
            if scene.get("narration"):
                texts.append(scene["narration"])
            if scene.get("subtitle_text"):
                texts.append(scene["subtitle_text"])

        # 完整口播
        if script.get("narration"):
            texts.append(script["narration"])

        return " ".join(texts)

    def _score_emotion(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        情绪评分 (30%)

        包含三个子维度：
        - 情绪词密度 (10%): 情绪词出现频率
        - 情绪转折次数 (10%): 正负情绪交替次数
        - 情绪峰值位置 (10%): 前10秒是否有强情绪
        """
        result = {
            "score": 0.0,
            "details": {},
            "suggestions": []
        }

        if not text:
            result["suggestions"].append("脚本内容为空，无法评估情绪")
            return result

        # 1. 情绪词密度评分
        emotion_density = self._calc_emotion_density(text)
        result["details"]["情绪词密度"] = emotion_density

        # 2. 情绪转折次数
        emotion_shifts = self._calc_emotion_shifts(text, script)
        result["details"]["情绪转折次数"] = emotion_shifts

        # 3. 情绪峰值位置（前3秒/前10秒）
        peak_position = self._calc_peak_position(text, script)
        result["details"]["情绪峰值位置"] = peak_position

        # 计算子维度得分
        density_score = min(emotion_density * 100, 100)  # 密度转分数
        shift_score = min(emotion_shifts * 20, 100)  # 转折转分数
        peak_score = peak_position * 100  # 位置直接是0-100

        # 加权平均
        sub_score = density_score * 0.4 + shift_score * 0.3 + peak_score * 0.3
        result["score"] = sub_score

        # 生成建议
        if density_score < 50:
            result["suggestions"].append("情绪词密度偏低，建议增加情绪表达")
        if shift_score < 30:
            result["suggestions"].append("情绪转折较少，建议增加情绪波动")
        if peak_score < 50:
            result["suggestions"].append("开场情绪不够强烈，建议强化前3秒钩子")

        return result

    def _calc_emotion_density(self, text: str) -> float:
        """计算情绪词密度（每100字情绪词数）"""
        total_words = len(text)
        if total_words == 0:
            return 0.0

        emotion_count = 0
        for category, pattern in self.emotion_patterns.items():
            matches = pattern.findall(text)
            emotion_count += len(matches) * EMOTION_WEIGHTS.get(category, 1.0)

        # 返回每100字的加权情绪词数
        return (emotion_count / total_words) * 100

    def _calc_emotion_shifts(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> int:
        """
        计算情绪转折次数

        定义：正面→负面 或 负面→正面的交替
        """
        # 获取分镜/段落的情绪标签
        scenes = script.get("scenes", [])
        if not scenes:
            # 没有分镜信息，基于全文情绪分析
            return self._infer_emotion_shifts(text)

        # 基于分镜情感标签计算转折
        shifts = 0
        prev_is_positive = None

        for scene in scenes:
            emotion = scene.get("emotion_stage", "")
            # 判断是否正面
            is_positive = any(
                kw in emotion for kw in ["高", "正面", "兴奋", "高潮", "峰值"]
            )
            is_negative = any(
                kw in emotion for kw in ["低", "负面", "压抑", "平静", "铺垫"]
            )

            if prev_is_positive is not None:
                if is_positive != prev_is_positive:
                    shifts += 1

            prev_is_positive = is_positive

        return max(shifts, 0)

    def _infer_emotion_shifts(self, text: str) -> int:
        """基于文本推断情绪转折次数"""
        segments = text.split("。")
        shifts = 0
        prev_positive = None

        for segment in segments[:10]:  # 只看前10句
            pos_count = len(self.emotion_patterns["正面"].findall(segment)) + \
                        len(self.emotion_patterns["强正面"].findall(segment))
            neg_count = len(self.emotion_patterns["负面"].findall(segment)) + \
                        len(self.emotion_patterns["强负面"].findall(segment))

            is_positive = pos_count > neg_count

            if prev_positive is not None and is_positive != prev_positive:
                shifts += 1

            prev_positive = is_positive

        return shifts

    def _calc_peak_position(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> float:
        """
        计算情绪峰值位置

        返回值：0-1
        - 1.0: 峰值在前3秒（最佳）
        - 0.7: 峰值在前10秒
        - 0.4: 峰值在中间
        - 0.0: 峰值在结尾
        """
        # 尝试从开场提取情绪强度
        opening = script.get("opening", "")
        scenes = script.get("scenes", [])

        # 如果有开场，分析开场情绪
        if opening:
            strong_emotion = (
                len(self.emotion_patterns["强正面"].findall(opening)) +
                len(self.emotion_patterns["强负面"].findall(opening)) +
                len(self.emotion_patterns["惊讶"].findall(opening))
            )
            if strong_emotion >= 2:
                return 1.0
            elif strong_emotion >= 1:
                return 0.7

        # 分析第一分镜
        if scenes and len(scenes) > 0:
            first_scene = scenes[0]
            narration = first_scene.get("narration", "")
            if narration:
                strong_emotion = (
                    len(self.emotion_patterns["强正面"].findall(narration)) +
                    len(self.emotion_patterns["强负面"].findall(narration))
                )
                if strong_emotion >= 2:
                    return 1.0
                elif strong_emotion >= 1:
                    return 0.7

        # 检查是否有钩子关键词
        hook_count = 0
        for category, keywords in HOOK_KEYWORDS.items():
            for kw in keywords:
                if kw in text[:100]:  # 前100字
                    hook_count += 1

        if hook_count >= 3:
            return 0.8
        elif hook_count >= 1:
            return 0.5

        return 0.3

    def _score_rhythm(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        节奏评分 (30%)

        包含三个子维度：
        - 前3秒钩子强度 (15%): 开场是否够吸引人
        - 奖励点分布 (10%): 奖励点是否符合"前密后疏"
        - 难度递进曲线 (5%): 内容难度是否递增
        """
        result = {
            "score": 0.0,
            "details": {},
            "suggestions": []
        }

        if not text:
            result["suggestions"].append("脚本内容为空，无法评估节奏")
            return result

        # 1. 前3秒钩子强度
        hook_strength = self._calc_hook_strength(text, script)
        result["details"]["前3秒钩子强度"] = hook_strength

        # 2. 奖励点分布
        reward_distribution = self._calc_reward_distribution(text, script)
        result["details"]["奖励点分布"] = reward_distribution

        # 3. 难度递进曲线
        difficulty_progression = self._calc_difficulty_progression(script)
        result["details"]["难度递进曲线"] = difficulty_progression

        # 加权平均
        hook_score = hook_strength * 100
        reward_score = reward_distribution * 100
        difficulty_score = difficulty_progression * 100

        sub_score = hook_score * 0.5 + reward_score * 0.3 + difficulty_score * 0.2
        result["score"] = sub_score

        # 生成建议
        if hook_score < 50:
            result["suggestions"].append("前3秒钩子不够强，建议使用痛点/悬念/反差开头")
        if reward_score < 50:
            result["suggestions"].append("奖励点分布不合理，建议前密后疏")
        if difficulty_score < 50:
            result["suggestions"].append("内容难度递进不明显，建议层层递进")

        return result

    def _calc_hook_strength(self, text: str, script: Dict[str, Any]) -> float:
        """
        计算前3秒钩子强度

        检查开场是否有：
        - 痛点钩子
        - 悬念钩子
        - 冲突/反差钩子
        - 强情绪词
        """
        # 获取开场文本（前100字）
        opening = script.get("opening", "")
        scenes = script.get("scenes", [])

        hook_text = opening
        if not hook_text and scenes:
            hook_text = scenes[0].get("narration", "")[:100]
        if not hook_text:
            hook_text = text[:100]

        score = 0.0

        # 检查钩子类型
        hook_types = 0

        # 痛点钩子
        pain_keywords = ["崩溃", "扎心", "太难了", "有人跟我一样", "困扰", "问题", "烦恼"]
        if any(kw in hook_text for kw in pain_keywords):
            score += 0.3
            hook_types += 1

        # 悬念钩子
        suspense_keywords = ["最后", "结果", "没想到", "竟然", "揭秘", "真相"]
        if any(kw in hook_text for kw in suspense_keywords):
            score += 0.3
            hook_types += 1

        # 反差钩子
        contrast_keywords = ["但是", "其实", "原来", "竟然", "差距", "别人"]
        if any(kw in hook_text for kw in contrast_keywords):
            score += 0.2
            hook_types += 1

        # 强情绪
        strong_emotion = (
            len(self.emotion_patterns["强正面"].findall(hook_text)) +
            len(self.emotion_patterns["强负面"].findall(hook_text)) +
            len(self.emotion_patterns["惊讶"].findall(hook_text))
        )
        if strong_emotion >= 2:
            score += 0.2
            hook_types += 1

        # 综合得分
        return min(score, 1.0)

    def _calc_reward_distribution(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> float:
        """
        计算奖励点分布

        奖励点包括：
        - 知识干货点
        - 情感共鸣点
        - 金句/观点

        分布评分：
        - 前密后疏（符合规律）: 1.0
        - 均匀分布: 0.6
        - 后密前疏: 0.3
        """
        scenes = script.get("scenes", [])
        if not scenes:
            # 无分镜信息，默认均匀
            return 0.6

        # 分析每段的长度
        total_scenes = len(scenes)
        if total_scenes <= 1:
            return 0.5

        # 提取每段的"奖励点"数量
        reward_points = []
        for i, scene in enumerate(scenes):
            narration = scene.get("narration", "")
            scene_text = narration or ""

            # 计算该段的奖励点
            points = 0

            # 知识干货
            knowledge_keywords = ["技巧", "方法", "秘诀", "关键", "重点", "注意"]
            points += sum(1 for kw in knowledge_keywords if kw in scene_text)

            # 情感共鸣
            emotion_count = sum(
                len(pattern.findall(scene_text))
                for pattern in self.emotion_patterns.values()
            )
            points += min(emotion_count, 3)

            # 金句
            golden_keywords = ["记住", "一定要", "最重要", "核心", "本质"]
            points += sum(1 for kw in golden_keywords if kw in scene_text)

            reward_points.append(points)

        # 判断分布类型
        # 前10秒（前3段）vs 后面的奖励点比例
        early_reward = sum(reward_points[:min(3, len(reward_points))])
        total_reward = sum(reward_points)

        if total_reward == 0:
            return 0.5

        early_ratio = early_reward / total_reward

        if early_ratio >= 0.6:
            return 1.0  # 前密后疏
        elif early_ratio >= 0.4:
            return 0.7  # 适度前密
        elif early_ratio >= 0.25:
            return 0.5  # 均匀分布
        else:
            return 0.3  # 后密前疏（不好）

    def _calc_difficulty_progression(self, script: Dict[str, Any]) -> float:
        """
        计算难度递进曲线

        检查分镜/段落的难度是否递增
        """
        scenes = script.get("scenes", [])
        if not scenes or len(scenes) <= 1:
            return 0.5

        # 分析每段的复杂度
        complexities = []
        for scene in scenes:
            narration = scene.get("narration", "")

            # 复杂度指标：句子长度、专业词汇数量
            sentences = narration.split("。")
            avg_sentence_len = sum(len(s) for s in sentences) / max(len(sentences), 1)

            # 专业词汇（简化判断：超过平均长度的词）
            words = narration.split()
            professional_ratio = sum(1 for w in words if len(w) >= 6) / max(len(words), 1)

            complexity = avg_sentence_len * 0.5 + professional_ratio * 100 * 0.5
            complexities.append(complexity)

        # 检查是否递增
        increases = sum(
            1 for i in range(1, len(complexities))
            if complexities[i] >= complexities[i-1]
        )

        progression_ratio = increases / max(len(complexities) - 1, 1)

        return min(progression_ratio, 1.0)

    def _score_interaction(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        互动评分 (40%)

        包含三个子维度：
        - 问句密度 (15%): 问句出现频率
        - CTA出现次数 (10%): 行动号召次数
        - 互动引导 (15%): 引导评论/讨论
        """
        result = {
            "score": 0.0,
            "details": {},
            "suggestions": []
        }

        if not text:
            result["suggestions"].append("脚本内容为空，无法评估互动")
            return result

        # 1. 问句密度
        question_density = self._calc_question_density(text)
        result["details"]["问句密度"] = question_density

        # 2. CTA出现次数
        cta_count = self._calc_cta_count(text, script)
        result["details"]["CTA出现次数"] = cta_count

        # 3. 互动引导
        interaction_guidance = self._calc_interaction_guidance(text, script)
        result["details"]["互动引导"] = interaction_guidance

        # 计算子维度得分
        question_score = min(question_density * 50, 100)  # 每50字1问句为满分
        cta_score = min(cta_count * 25, 100)  # 4次CTA为满分
        guidance_score = interaction_guidance * 100

        sub_score = question_score * 0.35 + cta_score * 0.25 + guidance_score * 0.4
        result["score"] = sub_score

        # 生成建议
        if question_score < 40:
            result["suggestions"].append("问句太少，建议每20-30秒设置一个问句")
        if cta_score < 30:
            result["suggestions"].append("CTA不足，建议至少出现2次行动号召")
        if guidance_score < 50:
            result["suggestions"].append("互动引导不够，建议引导评论/讨论")

        return result

    def _calc_question_density(self, text: str) -> float:
        """计算问句密度（每100字问句数）"""
        total_words = len(text)
        if total_words == 0:
            return 0.0

        # 统计问号数量
        question_count = text.count("？") + text.count("?")

        # 统计问句关键词
        question_keywords = ["吗", "是不是", "会不会", "有没有", "为什么", "怎么"]
        keyword_count = sum(text.count(kw) for kw in question_keywords)

        total_questions = question_count + keyword_count

        # 返回每100字的问句数
        return (total_questions / total_words) * 100

    def _calc_cta_count(self, text: str, script: Dict[str, Any]) -> int:
        """计算CTA出现次数"""
        cta_keywords = [
            "关注", "点赞", "评论", "收藏", "转发", "私信",
            "联系我们", "点击", "链接", "评论区", "留言",
            "点我", "扫码", "下单", "购买", "咨询"
        ]

        count = 0
        for kw in cta_keywords:
            count += text.count(kw)

        return min(count, 4)  # 最多计4次

    def _calc_interaction_guidance(
        self,
        text: str,
        script: Dict[str, Any]
    ) -> float:
        """计算互动引导程度"""
        guidance_keywords = [
            "来说说", "聊聊", "你们觉得", "评论区", "告诉我",
            "一起", "大家", "你们", "你呢", "有没有", "是不是"
        ]

        scenes = script.get("scenes", [])
        total_scenes = max(len(scenes), 1)

        # 统计引导出现的分镜数
        guided_scenes = 0
        for scene in scenes:
            narration = scene.get("narration", "")
            if any(kw in narration for kw in guidance_keywords):
                guided_scenes += 1

        # 如果没有分镜信息，基于全文判断
        if not scenes:
            guidance_count = sum(text.count(kw) for kw in guidance_keywords)
            if guidance_count >= 3:
                return 1.0
            elif guidance_count >= 1:
                return 0.6
            else:
                return 0.3

        # 基于分镜数计算比例
        return guided_scenes / total_scenes

    def _get_grade(self, score: float) -> tuple:
        """根据分数获取等级"""
        for threshold, grade, label in self.GRADES:
            if score >= threshold:
                return grade, label
        return "D", "不及格"

    def get_threshold(self, trust_source: TrustSourceType) -> int:
        """获取指定信任来源类型的及格分数线"""
        return self.PASS_THRESHOLDS.get(trust_source, 75)


# =============================================================================
# 便捷函数
# =============================================================================
def score_script(
    script: Dict[str, Any],
    trust_source: TrustSourceType = TrustSourceType.KNOWLEDGE
) -> Dict[str, Any]:
    """
    对短视频脚本进行评分的便捷函数

    Args:
        script: 脚本数据
        trust_source: 信任来源类型

    Returns:
        dict: 评分报告（字典格式）
    """
    scorer = ScriptScorer()
    report = scorer.score(script, trust_source)
    return report.to_dict()


def get_score_summary(report: Dict[str, Any]) -> str:
    """生成评分摘要文本"""
    total = report.get("total_score", 0)
    grade = report.get("grade", "")
    passed = report.get("passed", False)

    status = "通过" if passed else "未通过"
    emotion = report.get("emotion_score", 0)
    rhythm = report.get("rhythm_score", 0)
    interaction = report.get("interaction_score", 0)

    summary = f"""脚本评分报告
============
总分: {total:.1f} ({grade}) - {status}
情绪评分: {emotion:.1f}/100 (权重30%)
节奏评分: {rhythm:.1f}/100 (权重30%)
互动评分: {interaction:.1f}/100 (权重40%)

"""

    suggestions = report.get("suggestions", [])
    if suggestions:
        summary += "优化建议:\n"
        for i, s in enumerate(suggestions, 1):
            summary += f"  {i}. {s}\n"

    return summary
