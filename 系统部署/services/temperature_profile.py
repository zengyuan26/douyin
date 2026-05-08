"""
温度档案生成器

基于内容评分结果，生成温度档案并提供优化建议
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TemperatureProfile:
    """温度档案"""
    persona_type: str = ''
    target_elements: List[str] = field(default_factory=list)
    dimension_scores: Dict[str, int] = field(default_factory=dict)
    total_score: int = 0
    grade: str = 'D'
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    optimization_priority: List[str] = field(default_factory=list)


class TemperatureProfileGenerator:
    """
    温度档案生成器

    功能：
    1. 基于评分结果生成温度档案
    2. 分析温度优势和劣势
    3. 生成优化建议
    4. 确定优化优先级
    """

    # 温度维度名称映射
    DIMENSION_NAMES = {
        '标题温度': 'title_temperature',
        '开篇温度': 'opener_temperature',
        '内容温度': 'content_temperature',
        '情感连接': 'emotional_connection',
        '行动温度': 'action_temperature'
    }

    # 维度优化建议模板
    OPTIMIZATION_SUGGESTIONS = {
        '标题温度': [
            '增加情绪词：{emotion_word}',
            '添加数字钩子：{number}个技巧/步骤/方法',
            '使用疑问句引发好奇',
            '增加"你"增强代入感'
        ],
        '开篇温度': [
            '开篇30字内直接给答案',
            '增加情绪词引发共鸣',
            '使用"你"增加代入感',
            '添加情绪阶段设计'
        ],
        '内容温度': [
            '强化人设关键词：{persona_keywords}',
            '覆盖三要素：{elements}',
            '增加情感递进',
            '使用口语化表达'
        ],
        '情感连接': [
            '增加"你"的使用频率',
            '增加情感词密度',
            '使用共情句式',
            '添加温暖收尾'
        ],
        '行动温度': [
            '增强CTA情感强度',
            '添加紧迫感词汇',
            '明确具体行动',
            '使用强CTA词'
        ]
    }

    # 优化优先级分组
    OPTIMIZATION_GROUPS = {
        'A': {
            'name': '开篇组',
            'priority': 1,
            'items': ['开篇温度'],
        },
        'B': {
            'name': '骨架组',
            'priority': 2,
            'items': ['标题温度', '情感连接'],
        },
        'C': {
            'name': '转化组',
            'priority': 3,
            'items': ['内容温度', '行动温度'],
        }
    }

    def __init__(self):
        pass

    def generate_profile(
        self,
        content: Dict,
        persona_type: str = '陪伴者',
        target_elements: List[str] = None,
        temperature_scores: Dict[str, int] = None
    ) -> TemperatureProfile:
        """
        生成温度档案

        Args:
            content: 内容数据
            persona_type: 人设类型
            target_elements: 三要素组合
            temperature_scores: 温度评分结果（可选）

        Returns:
            TemperatureProfile: 温度档案
        """
        if target_elements is None:
            target_elements = ['有用', '有共鸣']

        # 分析优势和劣势
        strengths, weaknesses = self._analyze_strengths_weaknesses(
            temperature_scores or {}
        )

        # 生成优化建议
        suggestions = self._generate_suggestions(
            weaknesses,
            persona_type,
            target_elements
        )

        # 确定优化优先级
        priority = self._determine_optimization_priority(weaknesses)

        # 计算总分
        total_score = sum(temperature_scores.values()) if temperature_scores else 0

        # 确定等级
        grade = self._calculate_grade(total_score)

        return TemperatureProfile(
            persona_type=persona_type,
            target_elements=target_elements,
            dimension_scores=temperature_scores or {},
            total_score=total_score,
            grade=grade,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            optimization_priority=priority
        )

    def generate_from_scores(
        self,
        temperature_score_result: Dict
    ) -> TemperatureProfile:
        """
        从温度评分结果生成档案

        Args:
            temperature_score_result: temperature_scorer.score() 返回的结果

        Returns:
            TemperatureProfile: 温度档案
        """
        # 提取profile
        profile_data = temperature_score_result.get('profile', {})

        # 提取维度分数
        dimension_scores = {}
        for item in temperature_score_result.get('items', []):
            dimension_scores[item['name']] = item['score']

        # 分析优势和劣势
        strengths, weaknesses = self._analyze_strengths_weaknesses(dimension_scores)

        # 生成优化建议
        suggestions = self._generate_suggestions(
            weaknesses,
            profile_data.get('persona_type', '陪伴者'),
            profile_data.get('target_elements', ['有用', '有共鸣'])
        )

        # 确定优化优先级
        priority = self._determine_optimization_priority(weaknesses)

        # 构建档案
        return TemperatureProfile(
            persona_type=profile_data.get('persona_type', '陪伴者'),
            target_elements=profile_data.get('target_elements', ['有用', '有共鸣']),
            dimension_scores=dimension_scores,
            total_score=temperature_score_result.get('total_score', 0),
            grade=temperature_score_result.get('grade', 'D'),
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            optimization_priority=priority
        )

    def _analyze_strengths_weaknesses(
        self,
        dimension_scores: Dict[str, int]
    ) -> tuple:
        """分析优势和劣势"""
        strengths = []
        weaknesses = []

        for dimension, score in dimension_scores.items():
            if score >= 8:
                strengths.append(dimension)
            elif score < 6:
                weaknesses.append(dimension)

        return strengths, weaknesses

    def _generate_suggestions(
        self,
        weaknesses: List[str],
        persona_type: str,
        target_elements: List[str]
    ) -> List[str]:
        """生成优化建议"""
        suggestions = []

        for dimension in weaknesses:
            dimension_suggestions = self.OPTIMIZATION_SUGGESTIONS.get(dimension, [])

            for suggestion in dimension_suggestions[:2]:  # 每个维度最多2条建议
                # 替换模板变量
                formatted = suggestion.format(
                    emotion_word='扎心、破防、绝了',
                    number='5',
                    persona_keywords='焦虑、迷茫、担心',
                    elements=', '.join(target_elements)
                )
                suggestions.append(f"【{dimension}】{formatted}")

        return suggestions

    def _determine_optimization_priority(self, weaknesses: List[str]) -> List[str]:
        """确定优化优先级"""
        priority_order = []

        for group_key, group_info in sorted(
            self.OPTIMIZATION_GROUPS.items(),
            key=lambda x: x[1]['priority']
        ):
            for item in group_info['items']:
                if item in weaknesses:
                    priority_order.append(item)

        # 添加不在弱点列表中的维度
        all_dims = ['开篇温度', '标题温度', '情感连接', '内容温度', '行动温度']
        for dim in all_dims:
            if dim not in priority_order:
                priority_order.append(dim)

        return priority_order

    def _calculate_grade(self, score: int) -> str:
        """计算等级"""
        if score >= 45:
            return 'A'
        elif score >= 40:
            return 'B'
        elif score >= 30:
            return 'C'
        else:
            return 'D'

    def to_dict(self, profile: TemperatureProfile) -> Dict:
        """将档案转换为字典"""
        return {
            'persona_type': profile.persona_type,
            'target_elements': profile.target_elements,
            'dimension_scores': profile.dimension_scores,
            'total_score': profile.total_score,
            'grade': profile.grade,
            'strengths': profile.strengths,
            'weaknesses': profile.weaknesses,
            'suggestions': profile.suggestions,
            'optimization_priority': profile.optimization_priority
        }


class TemperatureOptimizer:
    """
    温度优化器

    基于温度档案，生成优化后的内容建议
    """

    def __init__(self):
        self.generator = TemperatureProfileGenerator()

    def optimize(
        self,
        content: Dict,
        temperature_scores: Dict[str, int],
        persona_type: str = '陪伴者',
        target_elements: List[str] = None
    ) -> Dict:
        """
        优化内容建议

        Args:
            content: 原始内容
            temperature_scores: 温度评分
            persona_type: 人设类型
            target_elements: 三要素组合

        Returns:
            Dict: 包含优化建议和优先级
        """
        if target_elements is None:
            target_elements = ['有用', '有共鸣']

        # 生成档案
        profile = self.generator.generate_profile(
            content=content,
            persona_type=persona_type,
            target_elements=target_elements,
            temperature_scores=temperature_scores
        )

        # 生成具体优化建议
        optimizations = self._generate_optimizations(
            content=content,
            profile=profile
        )

        return {
            'profile': self.generator.to_dict(profile),
            'optimizations': optimizations,
            'priority_order': profile.optimization_priority
        }

    def _generate_optimizations(
        self,
        content: Dict,
        profile: TemperatureProfile
    ) -> List[Dict]:
        """生成具体优化建议"""
        optimizations = []

        # 按优先级处理每个维度
        for dimension in profile.optimization_priority:
            score = profile.dimension_scores.get(dimension, 0)

            if score >= 8:
                continue  # 已达标，无需优化

            opt = {
                'dimension': dimension,
                'current_score': score,
                'target_score': 8,
                'suggestions': [],
                'priority': self._get_dimension_priority(dimension)
            }

            # 根据维度生成具体建议
            if dimension == '标题温度':
                opt['suggestions'] = self._optimize_title(content)
            elif dimension == '开篇温度':
                opt['suggestions'] = self._optimize_opener(content)
            elif dimension == '内容温度':
                opt['suggestions'] = self._optimize_content(content, profile.persona_type)
            elif dimension == '情感连接':
                opt['suggestions'] = self._optimize_emotional_connection(content)
            elif dimension == '行动温度':
                opt['suggestions'] = self._optimize_action(content)

            optimizations.append(opt)

        return optimizations

    def _optimize_title(self, content: Dict) -> List[str]:
        """优化标题建议"""
        title = content.get('title', '')
        suggestions = []

        if not title:
            suggestions.append('请添加有温度的标题')
            return suggestions

        # 检查情绪词
        emotion_words = ['扎心', '破防', '绝了', '笑死', '哭死']
        has_emotion = any(word in title for word in emotion_words)
        if not has_emotion:
            suggestions.append(f'建议添加情绪词：{", ".join(emotion_words[:3])}')

        # 检查疑问句
        has_question = any(q in title for q in ['吗', '怎么', '如何', '为什么'])
        if not has_question:
            suggestions.append('建议添加疑问句引发好奇')

        # 检查数字
        import re
        if not re.search(r'\d+', title):
            suggestions.append('建议添加数字钩子（如：3个技巧、5个方法）')

        # 检查"你"
        if '你' not in title:
            suggestions.append('建议使用"你"增强代入感')

        return suggestions

    def _optimize_opener(self, content: Dict) -> List[str]:
        """优化开篇建议"""
        slides = content.get('slides', [])
        suggestions = []

        if not slides:
            suggestions.append('请添加内容')
            return suggestions

        first_slide = slides[0]
        opener = first_slide.get('big_slogan', '') + ' ' + first_slide.get('main_title', '')

        if len(opener) > 30:
            suggestions.append('开篇建议≤30字直接给答案')

        # 检查情绪词
        emotion_words = ['扎心', '破防', '绝了', '笑死', '哭死']
        has_emotion = any(word in opener for word in emotion_words)
        if not has_emotion:
            suggestions.append('开篇建议添加情绪词引发共鸣')

        # 检查"你"
        if '你' not in opener:
            suggestions.append('开篇建议使用"你"增加代入感')

        return suggestions

    def _optimize_content(self, content: Dict, persona_type: str) -> List[str]:
        """优化内容建议"""
        suggestions = []

        # 人设关键词建议
        persona_keywords = {
            '陪伴者': ['焦虑', '迷茫', '担心', '崩溃', '扎心', '破防'],
            '教导者': ['干货', '技巧', '秘诀', '方法', '指南', '攻略'],
            '崇拜者': ['种草', '强推', '绝了', '太牛了', '惊艳', '宝藏'],
            '陪衬者': ['笑死', '哈哈', '太真实', '我也有过', '社死'],
            '搞笑者': ['笑死', '绝了', '炸裂', '破防', '离谱', '反转']
        }

        keywords = persona_keywords.get(persona_type, [])
        suggestions.append(f'建议使用{persona_type}人设关键词：{", ".join(keywords[:4])}')

        # 三要素建议
        suggestions.append('建议覆盖三要素：有趣/有用/有共鸣')

        return suggestions

    def _optimize_emotional_connection(self, content: Dict) -> List[str]:
        """优化情感连接建议"""
        suggestions = []

        suggestions.append('建议增加"你"的使用频率（≥3次）')
        suggestions.append('建议增加情感词密度：扎心、破防、绝了、笑死')

        return suggestions

    def _optimize_action(self, content: Dict) -> List[str]:
        """优化行动温度建议"""
        cta = content.get('cta', '')
        suggestions = []

        if not cta:
            suggestions.append('请添加行动号召')
            return suggestions

        # 检查强CTA词
        strong_words = ['收藏', '转发', '关注', '私信', '赶紧', '强烈']
        has_strong = any(word in cta for word in strong_words)
        if not has_strong:
            suggestions.append('建议使用强CTA词：赶紧、强烈、求求')

        # 检查具体行动
        has_action = any(word in cta for word in ['私信', '评论', '关注', '点击'])
        if not has_action:
            suggestions.append('CTA需要包含具体行动：私信、评论、关注等')

        return suggestions

    def _get_dimension_priority(self, dimension: str) -> int:
        """获取维度优先级"""
        priorities = {
            '开篇温度': 1,
            '标题温度': 2,
            '情感连接': 2,
            '内容温度': 3,
            '行动温度': 3
        }
        return priorities.get(dimension, 4)


# 全局实例
temperature_profile_generator = TemperatureProfileGenerator()
temperature_optimizer = TemperatureOptimizer()


def generate_temperature_profile(
    content: Dict,
    persona_type: str = '陪伴者',
    target_elements: List[str] = None,
    temperature_scores: Dict[str, int] = None
) -> Dict:
    """
    便捷函数：生成温度档案

    使用方法：
        from services.temperature_profile import generate_temperature_profile

        profile = generate_temperature_profile(
            content=content_data,
            persona_type='陪伴者',
            target_elements=['有用', '有共鸣'],
            temperature_scores={'标题温度': 8, '开篇温度': 7, ...}
        )
    """
    generator = TemperatureProfileGenerator()
    profile = generator.generate_profile(
        content=content,
        persona_type=persona_type,
        target_elements=target_elements,
        temperature_scores=temperature_scores
    )
    return generator.to_dict(profile)


def optimize_temperature(
    content: Dict,
    temperature_scores: Dict[str, int],
    persona_type: str = '陪伴者',
    target_elements: List[str] = None
) -> Dict:
    """
    便捷函数：优化温度建议

    使用方法：
        from services.temperature_profile import optimize_temperature

        result = optimize_temperature(
            content=content_data,
            temperature_scores={'标题温度': 6, ...},
            persona_type='陪伴者',
            target_elements=['有用', '有共鸣']
        )
    """
    optimizer = TemperatureOptimizer()
    return optimizer.optimize(
        content=content,
        temperature_scores=temperature_scores,
        persona_type=persona_type,
        target_elements=target_elements
    )
