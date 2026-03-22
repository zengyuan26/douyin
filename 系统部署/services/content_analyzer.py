"""
公开内容生成平台 - 内容分析器

功能：
1. 标题分析评分
2. 标签优化
3. 内容结构分析
4. 爆款元素提取
"""

import re
import json
from typing import Dict, List, Optional, Any
from collections import Counter


class ContentAnalyzer:
    """内容分析器"""

    # 爆款标题关键词
    VIRAL_KEYWORDS = [
        '竟然', '原来', '难怪', '怪不得', '99%', '全网', '爆款',
        '必看', '收藏', '吐血', '良心', '干货', '揭秘', '曝光',
        '神', '绝了', '炸裂', '逆天', '王炸', '天花板', 'yyds'
    ]

    # 痛点关键词
    PAIN_POINT_KEYWORDS = [
        '坑', '难', '麻烦', '纠结', '烦恼', '困扰', '不懂',
        '不会', '不知道', '怎么选', '哪个好', '有什么区别',
        '怎么办', '如何避免', '千万别', '不要', '后悔', '踩雷'
    ]

    # 情感关键词
    EMOTION_KEYWORDS = [
        '感动', '泪目', '破防', '心酸', '扎心', '太难了',
        '羡慕', '嫉妒', '震惊', '惊呆了', 'OMG', '哇塞',
        '太牛了', '太强了', '服了', '爱了', '绝了'
    ]

    # 数字模式
    NUMBER_PATTERNS = [
        r'\d+个', r'\d+步', r'\d+招', r'\d+秘诀',
        r'\d+技巧', r'\d+方法', r'\d+分钟', r'\d+天',
        r'\d+小时', r'\d+年', r'第\d+'
    ]

    # 疑问词
    QUESTION_WORDS = [
        '为什么', '怎么', '如何', '什么', '哪个',
        '是不是', '能不能', '要不要', '该不该',
        '为什么', '为何', '干嘛', '怎么就'
    ]

    @classmethod
    def analyze_title(cls, title: str) -> Dict[str, Any]:
        """
        分析标题质量

        Args:
            title: 标题文本

        Returns:
            分析结果 {
                'score': int,           # 总分 0-100
                'viral_score': int,      # 爆款指数 0-30
                'emotion_score': int,    # 情感指数 0-30
                'structure_score': int,   # 结构指数 0-20
                'length_score': int,      # 长度指数 0-20
                'elements': [],          # 包含的元素
                'suggestions': []        # 优化建议
            }
        """
        if not title:
            return {
                'score': 0,
                'viral_score': 0,
                'emotion_score': 0,
                'structure_score': 0,
                'length_score': 0,
                'elements': [],
                'suggestions': ['标题不能为空']
            }

        elements = []
        suggestions = []
        viral_score = 0
        emotion_score = 0
        structure_score = 0
        length_score = 0

        # 1. 检查爆款元素
        for keyword in cls.VIRAL_KEYWORDS:
            if keyword in title:
                elements.append(f'爆款词: {keyword}')
                viral_score += 6

        # 2. 检查痛点元素
        for keyword in cls.PAIN_POINT_KEYWORDS:
            if keyword in title:
                elements.append(f'痛点词: {keyword}')
                viral_score += 5

        # 3. 检查情感元素
        for keyword in cls.EMOTION_KEYWORDS:
            if keyword in title:
                elements.append(f'情感词: {keyword}')
                emotion_score += 8

        # 4. 检查结构元素
        has_number = False
        for pattern in cls.NUMBER_PATTERNS:
            if re.search(pattern, title):
                has_number = True
                structure_score += 10
                elements.append('数字结构')
                break

        for question_word in cls.QUESTION_WORDS:
            if question_word in title:
                structure_score += 10
                elements.append(f'疑问结构: {question_word}')
                break

        # 5. 长度评分
        length = len(title)
        if 15 <= length <= 25:
            length_score = 20
        elif 10 <= length < 15 or 25 < length <= 35:
            length_score = 15
        elif 35 < length <= 45:
            length_score = 10
        else:
            suggestions.append(f'建议标题长度控制在15-25字，当前{length}字')
            length_score = 5

        # 计算总分
        total_score = min(100, viral_score + emotion_score + structure_score + length_score)

        # 添加建议
        if viral_score < 10:
            suggestions.append('建议添加爆款关键词，如"竟然、难怪、99%"等')
        if emotion_score < 10:
            suggestions.append('建议添加情感词，增加共鸣感')
        if structure_score == 0:
            suggestions.append('建议使用数字或疑问结构，如"3步教你..."或"为什么..."')
        if length_score < 15:
            suggestions.append('标题过长或过短，建议15-25字')

        return {
            'score': total_score,
            'viral_score': min(30, viral_score),
            'emotion_score': min(30, emotion_score),
            'structure_score': min(20, structure_score),
            'length_score': min(20, length_score),
            'length': length,
            'elements': elements,
            'suggestions': suggestions
        }

    @classmethod
    def optimize_tags(cls, tags: List[str], industry: str = None) -> Dict[str, Any]:
        """
        优化标签

        Args:
            tags: 原始标签列表
            industry: 行业

        Returns:
            优化结果
        """
        if not tags:
            return {
                'original': [],
                'optimized': [],
                'removed': [],
                'added': [],
                'score': 0
            }

        original_count = len(tags)
        optimized = []
        removed = []
        added = []
        score = 60

        for tag in tags:
            tag_clean = tag.strip().lstrip('#')

            # 检查格式
            if len(tag_clean) < 2:
                removed.append(tag)
                continue

            if len(tag_clean) > 10:
                removed.append(tag)
                continue

            optimized.append(f'#{tag_clean}')

        # 检查是否包含行业标签
        if industry:
            industry_found = any(industry in t for t in optimized)
            if not industry_found:
                added.append(f'#{industry}')
                optimized.append(f'#{industry}')
                score += 10

        # 添加通用标签
        if len(optimized) < 5:
            common_tags = ['好物推荐', '种草', '分享', '干货']
            for tag in common_tags:
                if f'#{tag}' not in optimized:
                    added.append(f'#{tag}')
                    optimized.append(f'#{tag}')
                    if len(optimized) >= 8:
                        break

        # 检查重复
        tag_texts = [t.lstrip('#') for t in optimized]
        duplicates = [t for t, c in Counter(tag_texts).items() if c > 1]
        if duplicates:
            score -= 10

        return {
            'original_count': original_count,
            'optimized': optimized[:10],  # 最多10个标签
            'removed': removed,
            'added': added,
            'score': max(0, score)
        }

    @classmethod
    def analyze_content_structure(cls, content: str) -> Dict[str, Any]:
        """
        分析内容结构

        Args:
            content: 内容文本

        Returns:
            结构分析结果
        """
        if not content:
            return {
                'has_intro': False,
                'has_body': False,
                'has_conclusion': False,
                'structure_type': 'unknown',
                'image_count': 0,
                'suggestions': []
            }

        suggestions = []

        # 检查是否有引导关注
        has_cta = any(word in content for word in ['关注', '点赞', '收藏', '评论', '转发'])

        # 检查是否有痛点引入
        has_pain_point = any(word in content for word in cls.PAIN_POINT_KEYWORDS)

        # 检查是否有解决方案
        has_solution = any(word in content for word in ['方法', '技巧', '秘诀', '教你', '如何', '攻略'])

        # 检查是否有总结
        has_summary = any(word in content for word in ['总之', '总结', '最后', '总之', '划重点'])

        # 提取图片数量（根据常见模式）
        image_count = len(re.findall(r'图\d+|图片\d+|第\d+张', content))

        # 判断结构类型
        if has_pain_point and has_solution:
            structure_type = 'problem_solution'
        elif has_cta:
            structure_type = 'marketing'
        elif '步骤' in content or '第' in content:
            structure_type = 'step_by_step'
        else:
            structure_type = 'general'

        # 生成建议
        if not has_pain_point:
            suggestions.append('建议添加痛点引入，引发共鸣')
        if not has_solution:
            suggestions.append('建议添加解决方案或方法论')
        if not has_cta:
            suggestions.append('建议添加行动号召，如"关注、收藏"等')
        if not has_summary:
            suggestions.append('建议添加总结或划重点')

        return {
            'has_intro': has_pain_point,
            'has_body': has_solution,
            'has_conclusion': has_summary,
            'has_cta': has_cta,
            'structure_type': structure_type,
            'image_count': image_count,
            'suggestions': suggestions
        }

    @classmethod
    def generate_image_suggestions(cls, topic: str, structure_type: str = 'problem_solution') -> List[Dict]:
        """
        生成图片内容建议

        Args:
            topic: 选题
            structure_type: 内容结构类型

        Returns:
            图片建议列表
        """
        base_suggestions = {
            'problem_solution': [
                {'index': 1, 'type': '封面', 'content': '痛点场景 + 吸引眼球的标题'},
                {'index': 2, 'type': '问题', 'content': '展示目标客户的困扰和痛点'},
                {'index': 3, 'type': '分析', 'content': '分析痛点产生的原因'},
                {'index': 4, 'type': '方案', 'content': '提供解决方案或产品推荐'},
                {'index': 5, 'type': '总结', 'content': '总结要点 + 行动号召'}
            ],
            'knowledge': [
                {'index': 1, 'type': '封面', 'content': '知识点标题 + 吸引配图'},
                {'index': 2, 'type': '引入', 'content': '知识点背景或重要性'},
                {'index': 3, 'type': '核心', 'content': '核心知识点讲解'},
                {'index': 4, 'type': '案例', 'content': '实际案例或应用场景'},
                {'index': 5, 'type': '总结', 'content': '要点回顾 + 实用建议'}
            ],
            'marketing': [
                {'index': 1, 'type': '封面', 'content': '产品/品牌 + 核心卖点'},
                {'index': 2, 'type': '卖点1', 'content': '第一个核心卖点'},
                {'index': 3, 'type': '卖点2', 'content': '第二个核心卖点'},
                {'index': 4, 'type': '卖点3', 'content': '第三个核心卖点'},
                {'index': 5, 'type': '号召', 'content': '购买引导 + 行动号召'}
            ],
            'story': [
                {'index': 1, 'type': '封面', 'content': '故事场景 + 悬念标题'},
                {'index': 2, 'type': '冲突', 'content': '遇到的困难或问题'},
                {'index': 3, 'type': '转折', 'content': '关键转折点'},
                {'index': 4, 'type': '高潮', 'content': '解决后的效果或收获'},
                {'index': 5, 'type': '感悟', 'content': '总结感悟 + 推荐'}
            ]
        }

        return base_suggestions.get(structure_type, base_suggestions['problem_solution'])

    @classmethod
    def analyze_and_improve(cls, content_data: Dict) -> Dict:
        """
        综合分析和改进内容

        Args:
            content_data: {
                'titles': [],
                'tags': [],
                'content': str
            }

        Returns:
            改进后的内容
        """
        result = {
            'titles_analysis': [],
            'best_title': None,
            'tags_analysis': None,
            'content_analysis': None,
            'image_suggestions': [],
            'overall_score': 0
        }

        # 分析标题
        title_scores = []
        for title in content_data.get('titles', []):
            analysis = cls.analyze_title(title)
            title_scores.append({
                'title': title,
                'analysis': analysis
            })
            result['titles_analysis'] = title_scores

        # 选择最佳标题
        if title_scores:
            title_scores.sort(key=lambda x: x['analysis']['score'], reverse=True)
            result['best_title'] = title_scores[0]

        # 分析标签
        result['tags_analysis'] = cls.optimize_tags(
            content_data.get('tags', []),
            content_data.get('industry')
        )

        # 分析内容结构
        result['content_analysis'] = cls.analyze_content_structure(
            content_data.get('content', '')
        )

        # 生成图片建议
        result['image_suggestions'] = cls.generate_image_suggestions(
            topic=content_data.get('topic', ''),
            structure_type=result['content_analysis']['structure_type']
        )

        # 计算总分
        title_best = result['best_title']['analysis']['score'] if result['best_title'] else 0
        tag_score = result['tags_analysis']['score']
        content_score = 50 if result['content_analysis']['has_body'] else 30
        result['overall_score'] = int((title_best + tag_score + content_score) / 3)

        return result


# 全局实例
content_analyzer = ContentAnalyzer()
