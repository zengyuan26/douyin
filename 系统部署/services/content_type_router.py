"""
内容类型智能路由服务

功能：
1. 增强画像分析 - 提取影响内容类型的因素
2. 智能路由 - 根据选题+画像推荐最佳内容类型
3. 多版本生成支持 - 图文/短视频/长文

分析维度：
- 选题因素：类型、关键词、内容方向
- 画像因素：年龄、职业、决策周期、消费能力、内容偏好
- 业务因素：产品复杂度、展示需求、决策门槛
"""

import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime


class ContentTypeRouter:
    """
    内容类型智能路由器

    分析维度权重：
    1. 选题类型 → 基础内容类型倾向
    2. 画像年龄 → 媒介偏好（短视频/图文）
    3. 画像职业 → 内容深度偏好
    4. 画像决策周期 → 内容紧迫程度
    5. 画像消费能力 → 转化型vs种草型
    6. 画像内容偏好 → 直接匹配
    7. 业务复杂度 → 内容形式复杂度
    8. 选题关键词 → 微调
    """

    # ==================== 选题类型 → 内容类型基础分 ====================
    TOPIC_TYPE_BASE_SCORES = {
        # 图文优先（展示型内容）
        'graphic_priority': {
            '避坑指南': {'graphic': 0.95, 'short_video': 0.6, 'long_text': 0.5},
            '对比选型': {'graphic': 0.95, 'short_video': 0.7, 'long_text': 0.6},
            '选购指南': {'graphic': 0.95, 'short_video': 0.65, 'long_text': 0.7},
            '数字清单': {'graphic': 0.95, 'short_video': 0.5, 'long_text': 0.6},
            '步骤流程': {'graphic': 0.95, 'short_video': 0.7, 'long_text': 0.5},
        },
        # 短视频优先（故事型内容）
        'video_priority': {
            '痛点解决': {'graphic': 0.7, 'short_video': 0.9, 'long_text': 0.5},
            '经验分享': {'graphic': 0.6, 'short_video': 0.95, 'long_text': 0.6},
            '情感故事': {'graphic': 0.5, 'short_video': 0.95, 'long_text': 0.7},
            '场景演示': {'graphic': 0.7, 'short_video': 0.95, 'long_text': 0.4},
            '效果展示': {'graphic': 0.7, 'short_video': 0.95, 'long_text': 0.5},
        },
        # 长文优先（深度型内容）
        'longtext_priority': {
            '知识科普': {'graphic': 0.7, 'short_video': 0.65, 'long_text': 0.95},
            '原因分析': {'graphic': 0.7, 'short_video': 0.6, 'long_text': 0.95},
            '行业揭秘': {'graphic': 0.75, 'short_video': 0.7, 'long_text': 0.95},
            '深度测评': {'graphic': 0.8, 'short_video': 0.6, 'long_text': 0.95},
            '数据解读': {'graphic': 0.8, 'short_video': 0.55, 'long_text': 0.95},
        },
        # 通用型（三种皆可）
        'neutral': {
            '决策安心': {'graphic': 0.8, 'short_video': 0.8, 'long_text': 0.7},
            '效果验证': {'graphic': 0.85, 'short_video': 0.85, 'long_text': 0.7},
            '实操技巧': {'graphic': 0.85, 'short_video': 0.8, 'long_text': 0.6},
            '节日营销': {'graphic': 0.8, 'short_video': 0.9, 'long_text': 0.5},
            '季节营销': {'graphic': 0.8, 'short_video': 0.85, 'long_text': 0.5},
        }
    }

    # ==================== 画像维度 → 权重调整 ====================
    PORTRAIT_WEIGHTS = {
        # 年龄段 → 媒介偏好
        'age': {
            '18-25岁': {'short_video': 0.15, 'graphic': 0.05, 'long_text': -0.1},
            '25-35岁': {'short_video': 0.1, 'graphic': 0.05, 'long_text': 0.0},
            '35-45岁': {'short_video': 0.0, 'graphic': 0.1, 'long_text': 0.05},
            '45-55岁': {'short_video': -0.1, 'graphic': 0.15, 'long_text': 0.1},
            '55岁以上': {'short_video': -0.15, 'graphic': 0.2, 'long_text': 0.15},
        },
        # 职业 → 内容深度偏好
        'occupation': {
            '学生': {'short_video': 0.15, 'long_text': -0.05, 'graphic': 0.0},
            '白领/职场': {'short_video': 0.1, 'long_text': 0.05, 'graphic': 0.0},
            '自由职业': {'short_video': 0.1, 'long_text': 0.0, 'graphic': 0.05},
            '企业主/管理者': {'long_text': 0.15, 'graphic': 0.1, 'short_video': -0.05},
            '家长/宝妈': {'short_video': 0.1, 'graphic': 0.1, 'long_text': 0.0},
            '退休人员': {'graphic': 0.15, 'long_text': 0.1, 'short_video': -0.1},
        },
        # 决策周期 → 内容紧迫程度（短决策→快内容，长决策→深度内容）
        'decision_cycle': {
            '即时决策': {'short_video': 0.15, 'graphic': 0.1, 'long_text': -0.1},
            '短期决策(1-7天)': {'short_video': 0.1, 'graphic': 0.1, 'long_text': 0.0},
            '中期决策(1-3月)': {'graphic': 0.1, 'long_text': 0.1, 'short_video': 0.0},
            '长期决策(3月+)': {'long_text': 0.15, 'graphic': 0.1, 'short_video': -0.1},
        },
        # 消费能力 → 转化型vs种草型
        'spending_level': {
            '高消费': {'graphic': 0.1, 'long_text': 0.1, 'short_video': 0.0},
            '中消费': {'graphic': 0.05, 'long_text': 0.05, 'short_video': 0.05},
            '性价比优先': {'graphic': 0.1, 'short_video': 0.05, 'long_text': -0.05},
            '价格敏感': {'graphic': 0.1, 'short_video': 0.05, 'long_text': -0.05},
        },
        # 内容偏好 → 直接匹配
        'content_preference': {
            '短视频': {'short_video': 0.2, 'graphic': -0.05, 'long_text': -0.1},
            '图文': {'graphic': 0.2, 'short_video': -0.05, 'long_text': 0.0},
            '长文': {'long_text': 0.2, 'graphic': 0.05, 'short_video': -0.1},
            '深度内容': {'long_text': 0.15, 'graphic': 0.05, 'short_video': -0.05},
            '轻松娱乐': {'short_video': 0.15, 'graphic': 0.0, 'long_text': -0.1},
        }
    }

    # ==================== 业务维度 → 权重调整 ====================
    BUSINESS_WEIGHTS = {
        # 产品复杂度 → 内容形式复杂度
        'complexity': {
            '简单标准化': {'graphic': 0.1, 'short_video': 0.05, 'long_text': -0.1},
            '中等复杂度': {'graphic': 0.1, 'short_video': 0.0, 'long_text': 0.05},
            '高复杂度': {'long_text': 0.15, 'graphic': 0.05, 'short_video': -0.1},
            '专业服务': {'long_text': 0.2, 'graphic': 0.0, 'short_video': -0.15},
        },
        # 展示需求 → 是否需要视觉演示
        'visual_needs': {
            '需要展示效果': {'short_video': 0.2, 'graphic': 0.1, 'long_text': -0.1},
            '需要对比展示': {'graphic': 0.2, 'short_video': 0.1, 'long_text': 0.0},
            '需要步骤演示': {'short_video': 0.15, 'graphic': 0.15, 'long_text': 0.0},
            '纯文字说明': {'long_text': 0.15, 'graphic': 0.0, 'short_video': -0.15},
        },
        # 决策门槛 → 转化型内容比例
        'decision_threshold': {
            '低门槛(尝鲜型)': {'short_video': 0.15, 'graphic': 0.05, 'long_text': -0.1},
            '中门槛(考虑型)': {'graphic': 0.1, 'short_video': 0.05, 'long_text': 0.05},
            '高门槛(决策型)': {'long_text': 0.15, 'graphic': 0.1, 'short_video': -0.1},
        },
        # 内容方向
        'content_direction': {
            '种草型': {'short_video': 0.1, 'graphic': 0.1, 'long_text': 0.0},
            '转化型': {'graphic': 0.1, 'short_video': 0.0, 'long_text': 0.1},
            '品牌型': {'long_text': 0.1, 'graphic': 0.1, 'short_video': 0.05},
        }
    }

    # ==================== 标题关键词 → 微调 ====================
    TITLE_KEYWORD_WEIGHTS = {
        'steps': {'keywords': ['步骤', '教程', '指南', '方法', '清单', '攻略'], 'adjustments': {'graphic': 0.15, 'short_video': 0.1, 'long_text': 0.0}},
        'deep': {'keywords': ['揭秘', '真相', '原理', '深度', '内幕', '全面'], 'adjustments': {'long_text': 0.15, 'graphic': 0.05, 'short_video': -0.1}},
        'emotional': {'keywords': ['分享', '我的', '故事', '真实', '经历', '亲测'], 'adjustments': {'short_video': 0.15, 'graphic': 0.0, 'long_text': 0.05}},
        'comparison': {'keywords': ['对比', '区别', '哪个好', '选哪个', '比较'], 'adjustments': {'graphic': 0.2, 'short_video': 0.05, 'long_text': 0.05}},
        'hot': {'keywords': ['爆款', '必看', '火了', '赶紧', '限时'], 'adjustments': {'short_video': 0.2, 'graphic': -0.1, 'long_text': -0.15}},
        'data': {'keywords': ['数据', '统计', '研究', '报告', '发现'], 'adjustments': {'long_text': 0.15, 'graphic': 0.1, 'short_video': -0.05}},
        'warning': {'keywords': ['避坑', '陷阱', '骗局', '千万别', '注意'], 'adjustments': {'graphic': 0.15, 'short_video': 0.1, 'long_text': 0.0}},
        'seasonal': {'keywords': ['高考', '中考', '开学', '毕业', '假期'], 'adjustments': {'short_video': 0.1, 'graphic': 0.1, 'long_text': 0.0}},
    }

    # ==================== 内容类型详情 ====================
    CONTENT_TYPES = {
        'graphic': {
            'name': '图文',
            'icon': '🖼️',
            'description': '适合展示对比、步骤、清单类内容，用户可快速浏览和收藏',
            'platforms': ['小红书', '微博', '今日头条'],
            'best_for': ['避坑指南', '对比选型', '选购指南', '数字清单', '步骤流程'],
            'features': ['信息密度高', '便于收藏', '制作成本低', '适合深度用户'],
            'typical_length': '5-8张图，每图≤100字'
        },
        'short_video': {
            'name': '短视频',
            'icon': '🎬',
            'description': '适合故事讲述、场景演示、真人出镜，内容生动直观',
            'platforms': ['抖音', '快手', '视频号', 'B站'],
            'best_for': ['痛点解决', '经验分享', '情感故事', '场景演示', '效果展示'],
            'features': ['传播速度快', '互动性强', '适合年轻用户', '情感连接深'],
            'typical_length': '30秒-3分钟'
        },
        'long_text': {
            'name': '长文',
            'icon': '📝',
            'description': '适合深度分析、专业知识讲解，需要用户静下心来阅读',
            'platforms': ['微信公众号', '知乎', '今日头条'],
            'best_for': ['知识科普', '原因分析', '行业揭秘', '深度测评', '数据解读'],
            'features': ['权威性强', '信任度高', '适合高决策门槛', '长尾流量大'],
            'typical_length': '2000-5000字'
        }
    }

    # ==================== 选题类型映射 ====================
    TOPIC_TYPE_MAPPING = {
        # 直接匹配
        '避坑指南': 'graphic_priority',
        '对比选型': 'graphic_priority',
        '选购指南': 'graphic_priority',
        '数字清单': 'graphic_priority',
        '痛点解决': 'video_priority',
        '经验分享': 'video_priority',
        '情感故事': 'video_priority',
        '知识科普': 'longtext_priority',
        '原因分析': 'longtext_priority',
        '行业揭秘': 'longtext_priority',
        '决策安心': 'neutral',
        '效果验证': 'neutral',
        '实操技巧': 'neutral',
        # 新增类型映射
        '场景演示': 'video_priority',
        '效果展示': 'video_priority',
        '深度测评': 'longtext_priority',
        '数据解读': 'longtext_priority',
        '节日营销': 'neutral',
        '季节营销': 'neutral',
    }

    def __init__(self):
        pass

    def analyze_portrait(self, portrait: Dict) -> Dict[str, Any]:
        """
        从画像中提取影响内容类型的因素

        Args:
            portrait: 用户画像数据

        Returns:
            分析结果，包含各维度提取结果
        """
        result = {
            'age': self._extract_age(preview.get('age', portrait.get('年龄段', ''))),
            'occupation': self._extract_occupation(preview.get('occupation', portrait.get('职业', ''))),
            'decision_cycle': self._extract_decision_cycle(portrait),
            'spending_level': self._extract_spending_level(portrait),
            'content_preference': self._extract_content_preference(portrait),
            'summary': []
        }

        # 生成摘要
        if result['age']:
            result['summary'].append(f"年龄段：{result['age']}")
        if result['occupation']:
            result['summary'].append(f"职业：{result['occupation']}")
        if result['decision_cycle']:
            result['summary'].append(f"决策周期：{result['decision_cycle']}")
        if result['spending_level']:
            result['summary'].append(f"消费能力：{result['spending_level']}")
        if result['content_preference']:
            result['summary'].append(f"内容偏好：{result['content_preference']}")

        return result

    def _extract_age(self, age_str: str) -> Optional[str]:
        """提取年龄段"""
        age_patterns = [
            (r'18.*?25', '18-25岁'),
            (r'20.*?30', '25-35岁'),
            (r'25.*?35', '25-35岁'),
            (r'30.*?40', '35-45岁'),
            (r'35.*?45', '35-45岁'),
            (r'40.*?50', '45-55岁'),
            (r'45.*?55', '45-55岁'),
            (r'5[5-9].*?|60.*?', '55岁以上'),
        ]
        for pattern, label in age_patterns:
            if re.search(pattern, age_str):
                return label
        return None

    def _extract_occupation(self, occ_str: str) -> Optional[str]:
        """提取职业类型"""
        occ_lower = occ_str.lower()
        if any(kw in occ_lower for kw in ['学生', '大学生', '研究生']):
            return '学生'
        if any(kw in occ_lower for kw in ['白领', '职场', '上班', '职员', '员工']):
            return '白领/职场'
        if any(kw in occ_lower for kw in ['自由职业', '个体', '创业', '自媒体']):
            return '自由职业'
        if any(kw in occ_lower for kw in ['企业主', '老板', '管理者', '经理', '总监', 'CEO']):
            return '企业主/管理者'
        if any(kw in occ_lower for kw in ['家长', '宝妈', '宝爸', '妈妈', '爸爸', '家庭主妇']):
            return '家长/宝妈'
        if any(kw in occ_lower for kw in ['退休', '老年人', '养老']):
            return '退休人员'
        return None

    def _extract_decision_cycle(self, portrait: Dict) -> Optional[str]:
        """提取决策周期"""
        # 从画像描述中推断
        desc = str(portrait)
        if any(kw in desc for kw in ['急需', '紧急', '马上', '立刻']):
            return '即时决策'
        if any(kw in desc for kw in ['最近', '近期', '考虑', '打算']):
            return '短期决策(1-7天)'
        if any(kw in desc for kw in ['慢慢选', '不急', '观望', '了解']):
            return '中期决策(1-3月)'
        if any(kw in desc for kw in ['长期', '规划', '未来']):
            return '长期决策(3月+)'
        return None

    def _extract_spending_level(self, portrait: Dict) -> Optional[str]:
        """提取消费能力"""
        desc = str(portrait)
        if any(kw in desc for kw in ['高端', '品质', '不在乎钱', '进口', ' luxury']):
            return '高消费'
        if any(kw in desc for kw in ['性价比', '划算', '实用', '便宜', '优惠']):
            return '性价比优先'
        if any(kw in desc for kw in ['价格敏感', '省钱', '折扣', '便宜']):
            return '价格敏感'
        return '中消费'

    def _extract_content_preference(self, portrait: Dict) -> Optional[str]:
        """提取内容偏好"""
        desc = str(portrait)
        if any(kw in desc for kw in ['喜欢视频', '看视频', '刷抖音', '短视频']):
            return '短视频'
        if any(kw in desc for kw in ['喜欢图文', '看图片', '收藏']):
            return '图文'
        if any(kw in desc for kw in ['喜欢长文', '深度', '专业']):
            return '长文'
        if any(kw in desc for kw in ['轻松', '娱乐', '有趣']):
            return '轻松娱乐'
        return None

    def route(self, topic: Dict, portrait: Dict = None, business_info: Dict = None) -> Dict[str, Any]:
        """
        智能路由：根据选题+画像推荐最佳内容类型

        Args:
            topic: 选题信息 {title, type, keywords, content_direction}
            portrait: 用户画像
            business_info: 业务信息 {complexity, visual_needs, decision_threshold}

        Returns:
            {
                "primary": {"type": "graphic", "score": 0.95, "reasons": [...]},
                "secondary": {"type": "short_video", "score": 0.75},
                "all_scores": {"graphic": 0.95, "short_video": 0.75, "long_text": 0.5},
                "recommendations": {...}
            }
        """
        # 1. 初始化分数
        scores = {
            'graphic': 0.5,
            'short_video': 0.5,
            'long_text': 0.5
        }
        reasons = []

        # 2. 基于选题类型打基础分
        topic_type = topic.get('type', topic.get('type_key', '决策安心'))
        topic_category = self.TOPIC_TYPE_MAPPING.get(topic_type, 'neutral')

        if topic_category in self.TOPIC_TYPE_BASE_SCORES:
            base_scores = self.TOPIC_TYPE_BASE_SCORES[topic_category].get(topic_type, {'graphic': 0.7, 'short_video': 0.7, 'long_text': 0.7})
            for content_type, score in base_scores.items():
                scores[content_type] = score
            reasons.append(f"选题「{topic_type}」类型适合{self.CONTENT_TYPES[max(scores, key=scores.get)]['name']}")

        # 3. 基于画像调整
        if portrait:
            portrait_analysis = self.analyze_portrait(portrait)
            adjustments = self._get_portrait_adjustments(portrait_analysis)
            for content_type, adj in adjustments.items():
                scores[content_type] = max(0.1, min(1.0, scores.get(content_type, 0.5) + adj))

        # 4. 基于业务信息调整
        if business_info:
            biz_adjustments = self._get_business_adjustments(business_info)
            for content_type, adj in biz_adjustments.items():
                scores[content_type] = max(0.1, min(1.0, scores.get(content_type, 0.5) + adj))

        # 5. 基于标题关键词微调
        title = topic.get('title', '')
        keyword_adjustments = self._get_keyword_adjustments(title)
        for content_type, adj in keyword_adjustments.items():
            scores[content_type] = max(0.1, min(1.0, scores.get(content_type, 0.5) + adj))

        # 6. 排序获取推荐
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_types[0][0]
        secondary_type = sorted_types[1][0] if len(sorted_types) > 1 else None
        tertiary_type = sorted_types[2][0] if len(sorted_types) > 2 else None

        # 7. 生成推荐详情
        result = {
            'primary': {
                'type': primary_type,
                'score': round(scores[primary_type], 2),
                'name': self.CONTENT_TYPES[primary_type]['name'],
                'icon': self.CONTENT_TYPES[primary_type]['icon'],
                'description': self.CONTENT_TYPES[primary_type]['description'],
                'reasons': reasons,
                'platforms': self.CONTENT_TYPES[primary_type]['platforms'],
                'features': self.CONTENT_TYPES[primary_type]['features'],
                'typical_length': self.CONTENT_TYPES[primary_type]['typical_length']
            },
            'secondary': {
                'type': secondary_type,
                'score': round(scores[secondary_type], 2),
                'name': self.CONTENT_TYPES[secondary_type]['name'],
                'icon': self.CONTENT_TYPES[secondary_type]['icon'],
                'platforms': self.CONTENT_TYPES[secondary_type]['platforms']
            } if secondary_type else None,
            'tertiary': {
                'type': tertiary_type,
                'score': round(scores[tertiary_type], 2),
                'name': self.CONTENT_TYPES[tertiary_type]['name'],
                'icon': self.CONTENT_TYPES[tertiary_type]['icon']
            } if tertiary_type else None,
            'all_scores': {k: round(v, 2) for k, v in scores.items()},
            'content_types': self.CONTENT_TYPES,
            'topic_analysis': {
                'type': topic_type,
                'category': topic_category,
                'title_keywords': self._extract_title_keywords(title)
            }
        }

        # 如果有画像分析，也返回
        if portrait:
            result['portrait_analysis'] = self.analyze_portrait(portrait)

        return result

    def _get_portrait_adjustments(self, analysis: Dict) -> Dict[str, float]:
        """从画像分析中获取权重调整"""
        adjustments = {}

        # 年龄
        age = analysis.get('age')
        if age and age in self.PORTRAIT_WEIGHTS['age']:
            for ct, adj in self.PORTRAIT_WEIGHTS['age'][age].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 职业
        occ = analysis.get('occupation')
        if occ and occ in self.PORTRAIT_WEIGHTS['occupation']:
            for ct, adj in self.PORTRAIT_WEIGHTS['occupation'][occ].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 决策周期
        dc = analysis.get('decision_cycle')
        if dc and dc in self.PORTRAIT_WEIGHTS['decision_cycle']:
            for ct, adj in self.PORTRAIT_WEIGHTS['decision_cycle'][dc].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 消费能力
        sl = analysis.get('spending_level')
        if sl and sl in self.PORTRAIT_WEIGHTS['spending_level']:
            for ct, adj in self.PORTRAIT_WEIGHTS['spending_level'][sl].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 内容偏好
        cp = analysis.get('content_preference')
        if cp and cp in self.PORTRAIT_WEIGHTS['content_preference']:
            for ct, adj in self.PORTRAIT_WEIGHTS['content_preference'][cp].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        return adjustments

    def _get_business_adjustments(self, business_info: Dict) -> Dict[str, float]:
        """从业务信息中获取权重调整"""
        adjustments = {}

        # 产品复杂度
        complexity = business_info.get('complexity', '')
        if complexity in self.BUSINESS_WEIGHTS['complexity']:
            for ct, adj in self.BUSINESS_WEIGHTS['complexity'][complexity].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 展示需求
        visual = business_info.get('visual_needs', '')
        if visual in self.BUSINESS_WEIGHTS['visual_needs']:
            for ct, adj in self.BUSINESS_WEIGHTS['visual_needs'][visual].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 决策门槛
        threshold = business_info.get('decision_threshold', '')
        if threshold in self.BUSINESS_WEIGHTS['decision_threshold']:
            for ct, adj in self.BUSINESS_WEIGHTS['decision_threshold'][threshold].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        # 内容方向
        direction = business_info.get('content_direction', '')
        if direction in self.BUSINESS_WEIGHTS['content_direction']:
            for ct, adj in self.BUSINESS_WEIGHTS['content_direction'][direction].items():
                adjustments[ct] = adjustments.get(ct, 0) + adj

        return adjustments

    def _get_keyword_adjustments(self, title: str) -> Dict[str, float]:
        """从标题关键词中获取权重调整"""
        adjustments = {}
        title_lower = title.lower()

        for category, config in self.TITLE_KEYWORD_WEIGHTS.items():
            for keyword in config['keywords']:
                if keyword in title_lower:
                    for ct, adj in config['adjustments'].items():
                        adjustments[ct] = adjustments.get(ct, 0) + adj
                    break

        return adjustments

    def _extract_title_keywords(self, title: str) -> List[str]:
        """提取标题中的关键词"""
        keywords = []
        title_lower = title.lower()

        for category, config in self.TITLE_KEYWORD_WEIGHTS.items():
            for keyword in config['keywords']:
                if keyword in title_lower:
                    keywords.append(keyword)

        return list(set(keywords))


# 全局实例
content_type_router = ContentTypeRouter()
