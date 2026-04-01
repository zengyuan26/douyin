"""
内容类型推荐服务

基于选题推荐最适合的内容类型（图文/长文/短视频）
"""

import json
from typing import Dict, List, Optional


class ContentTypeRecommender:
    """内容类型推荐器"""
    
    # 选题类型 -> 内容类型 基础分
    TOPIC_TYPE_SCORES = {
        'graphic': {
            '问题诊断': 0.9,
            '解决方案': 0.8,
            '经验分享': 0.7,
            '避坑指南': 0.95,
            '知识科普': 0.85,
        },
        'long_text': {
            '知识科普': 0.9,
            '解决方案': 0.7,
            '经验分享': 0.6,
        },
        'short_video': {
            '问题诊断': 0.7,
            '解决方案': 0.9,
            '经验分享': 0.95,
            '避坑指南': 0.6,
            '知识科普': 0.75,
        }
    }
    
    # 额外权重因子
    EXTRA_WEIGHTS = {
        'is_hot_topic': {
            'short_video': 0.2,
            'graphic': -0.1,
            'long_text': -0.15
        },
        'is_professional': {
            'long_text': 0.15,
            'graphic': 0.05,
            'short_video': -0.1
        },
        'is_comparison': {
            'graphic': 0.2,
            'short_video': 0.1,
            'long_text': -0.05
        },
        'target_age_young': {
            'short_video': 0.15,
            'graphic': 0.05,
            'long_text': -0.1
        },
        'target_age_old': {
            'graphic': 0.1,
            'long_text': 0.05,
            'short_video': -0.1
        },
        'is_local_service': {
            'graphic': 0.15,
            'short_video': 0.1,
            'long_text': 0.0
        },
        'is_emotional': {
            'short_video': 0.15,
            'graphic': 0.0,
            'long_text': 0.0
        },
        'has_steps': {
            'graphic': 0.15,
            'short_video': 0.1,
            'long_text': 0.05
        }
    }
    
    # 内容类型描述
    CONTENT_TYPE_INFO = {
        'graphic': {
            'name': '图文',
            'description': '适合展示对比、步骤、清单类内容，用户可快速浏览和收藏',
            'best_for': ['避坑指南', '问题诊断', '解决方案步骤'],
            'platform': ['小红书', '微博', '微信公众号']
        },
        'long_text': {
            'name': '长文',
            'description': '适合深度分析、专业知识讲解，需要用户静下心来阅读',
            'best_for': ['知识科普', '深度分析', '专业测评'],
            'platform': ['微信公众号', '知乎', '头条号']
        },
        'short_video': {
            'name': '短视频',
            'description': '适合故事讲述、场景演示、真人出镜，内容生动直观',
            'best_for': ['经验分享', '解决方案演示', '情感共鸣'],
            'platform': ['抖音', '快手', '视频号', 'B站']
        }
    }
    
    @classmethod
    def recommend(cls, topic: Dict, portrait: Dict = None,
                business_info: Dict = None) -> Dict:
        """
        推荐内容类型
        
        Args:
            topic: 选题信息
                {
                    "title": "选题标题",
                    "type": "避坑指南"
                }
            portrait: 用户画像（可选）
                {
                    "age_range": "25-35岁",
                    "occupation": "白领"
                }
            business_info: 业务信息（可选）
                {
                    "is_hot_topic": false,
                    "is_professional": true,
                    "is_comparison": true
                }
        
        Returns:
            推荐结果
            {
                "primary": {
                    "type": "graphic",
                    "score": 0.95,
                    "reasons": ["选题类型为避坑指南，适合图文"]
                },
                "secondary": {
                    "type": "short_video",
                    "score": 0.65
                },
                "all_scores": {...},
                "info": {...}
            }
        """
        topic_type = topic.get('type', '问题诊断')
        topic_title = topic.get('title', '')
        
        # 初始化分数
        scores = {
            'graphic': 0.5,
            'long_text': 0.5,
            'short_video': 0.5
        }
        
        # 1. 基于选题类型打分
        if topic_type in cls.TOPIC_TYPE_SCORES.get('graphic', {}):
            scores['graphic'] = cls.TOPIC_TYPE_SCORES['graphic'][topic_type]
        if topic_type in cls.TOPIC_TYPE_SCORES.get('long_text', {}):
            scores['long_text'] = cls.TOPIC_TYPE_SCORES['long_text'][topic_type]
        if topic_type in cls.TOPIC_TYPE_SCORES.get('short_video', {}):
            scores['short_video'] = cls.TOPIC_TYPE_SCORES['short_video'][topic_type]
        
        # 2. 基于业务信息调整
        if business_info:
            if business_info.get('is_hot_topic'):
                scores['short_video'] += cls.EXTRA_WEIGHTS['is_hot_topic']['short_video']
                scores['graphic'] += cls.EXTRA_WEIGHTS['is_hot_topic']['graphic']
            
            if business_info.get('is_professional'):
                scores['long_text'] += cls.EXTRA_WEIGHTS['is_professional']['long_text']
            
            if business_info.get('is_comparison'):
                scores['graphic'] += cls.EXTRA_WEIGHTS['is_comparison']['graphic']
            
            if business_info.get('is_local_service'):
                scores['graphic'] += cls.EXTRA_WEIGHTS['is_local_service']['graphic']
            
            if business_info.get('is_emotional'):
                scores['short_video'] += cls.EXTRA_WEIGHTS['is_emotional']['short_video']
        
        # 3. 基于画像调整
        if portrait:
            age_range = portrait.get('age_range', '')
            occupation = portrait.get('occupation', '').lower()
            
            # 年龄判断
            if '18' in age_range or '20' in age_range or '25' in age_range:
                scores['short_video'] += cls.EXTRA_WEIGHTS['target_age_young']['short_video']
            elif '45' in age_range or '50' in age_range or '55' in age_range:
                scores['graphic'] += cls.EXTRA_WEIGHTS['target_age_old']['graphic']
            
            # 白领/职场人更偏好短视频
            if any(kw in occupation for kw in ['白领', '职场', 'office', 'manager']):
                scores['short_video'] += 0.05
        
        # 4. 基于标题关键词微调
        title_lower = topic_title.lower()
        if any(kw in title_lower for kw in ['步骤', '教程', '指南', '方法', '清单']):
            scores['graphic'] += cls.EXTRA_WEIGHTS['has_steps']['graphic']
        if any(kw in title_lower for kw in ['揭秘', '真相', '为什么', '原理', '深度']):
            scores['long_text'] += 0.1
        if any(kw in title_lower for kw in ['分享', '我的', '故事', '真实']):
            scores['short_video'] += 0.1
        
        # 限制分数范围
        for k in scores:
            scores[k] = max(0.1, min(1.0, scores[k]))
        
        # 排序获取推荐
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = sorted_types[0][0]
        secondary_type = sorted_types[1][0] if len(sorted_types) > 1 else None
        
        # 生成推荐理由
        reasons = []
        reasons.append(f"选题类型为「{topic_type}」")
        if scores['graphic'] > scores['short_video'] and scores['graphic'] > scores['long_text']:
            reasons.append(f"「{topic_type}」类内容适合图文展示")
        elif scores['short_video'] > scores['graphic'] and scores['short_video'] > scores['long_text']:
            reasons.append(f"「{topic_type}」类内容适合短视频呈现")
        elif scores['long_text'] > scores['graphic'] and scores['long_text'] > scores['short_video']:
            reasons.append(f"「{topic_type}」类内容适合长文深度讲解")
        
        return {
            'primary': {
                'type': primary_type,
                'score': round(scores[primary_type], 2),
                'name': cls.CONTENT_TYPE_INFO[primary_type]['name'],
                'description': cls.CONTENT_TYPE_INFO[primary_type]['description'],
                'reasons': reasons,
                'best_platforms': cls.CONTENT_TYPE_INFO[primary_type]['platform']
            },
            'secondary': {
                'type': secondary_type,
                'score': round(scores[secondary_type], 2) if secondary_type else None,
                'name': cls.CONTENT_TYPE_INFO[secondary_type]['name'] if secondary_type else None
            } if secondary_type else None,
            'all_scores': {k: round(v, 2) for k, v in scores.items()},
            'content_types': cls.CONTENT_TYPE_INFO
        }
    
    @classmethod
    def get_content_type_info(cls, content_type: str) -> Optional[Dict]:
        """获取内容类型详细信息"""
        return cls.CONTENT_TYPE_INFO.get(content_type)


# 全局实例
content_type_recommender = ContentTypeRecommender()
