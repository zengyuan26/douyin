"""
长文内容生成服务

支持8种长文模板结构：
1. 知识科普型 - 专业内容深度讲解
2. 原因分析型 - 问题原因深度剖析
3. 行业揭秘型 - 行业内幕深度挖掘
4. 深度测评型 - 产品/服务深度对比
5. 经验分享型 - 个人经历深度复盘
6. 数据解读型 - 数据背后深度洞察
7. 选购指南型 - 决策全流程深度指导
8. 解决方案型 - 问题系统化深度解决
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from services.llm import get_llm_service


class LongTextGenerator:
    """长文内容生成器"""

    # 8种长文模板结构
    TEXT_TEMPLATES = [
        {
            'id': 'knowledge_article',
            'name': '知识科普型',
            'word_count': '2000-3000字',
            'reading_time': '5-8分钟',
            'desc': '专业内容趣味化讲解，建立专家形象',
            'sections': ['引言导入', '核心概念', '原理解释', '实际应用', '案例分析', '总结建议'],
            'best_for': ['知识科普', '原因分析'],
            'keywords': ['原理', '真相', '秘密', '科普', '解读'],
            'structure': '''
## 知识科普型模板结构

【引言导入】（200-300字）
- 热点引入或问题抛出
- 建立读者兴趣
- 引出核心内容

【核心概念】（300-400字）
- 定义核心概念
- 解释专业术语
- 铺垫基础知识

【原理解释】（400-500字）
- 深入分析原理
- 技术/科学依据
- 逻辑推导过程

【实际应用】（400-500字）
- 生活中的应用场景
- 常见误区纠正
- 实用技巧分享

【案例分析】（400-500字）
- 2-3个实际案例
- 成功/失败对比
- 经验教训总结

【总结建议】（200-300字）
- 核心要点回顾
- 行动建议
- 推荐阅读
'''
        },
        {
            'id': 'cause_analysis',
            'name': '原因分析型',
            'word_count': '2500-3500字',
            'reading_time': '6-9分钟',
            'desc': '问题原因深度剖析，找到症结所在',
            'sections': ['现象描述', '表层原因', '深层原因', '影响因素', '案例验证', '对策建议'],
            'best_for': ['原因分析', '知识科普'],
            'keywords': ['原因', '为什么', '分析', '揭秘', '背后'],
            'structure': '''
## 原因分析型模板结构

【现象描述】（200-300字）
- 描述常见现象
- 读者共鸣引入
- 引出问题

【表层原因】（400-500字）
- 表面可见的原因
- 大多数人看到的原因
- 浅层逻辑分析

【深层原因】（500-600字）
- 背后的深层逻辑
- 行业/社会因素
- 本质原因挖掘

【影响因素】（400-500字）
- 影响原因的多重因素
- 权重分析
- 交叉影响关系

【案例验证】（500-600字）
- 典型案例拆解
- 原因的实际体现
- 验证逻辑

【对策建议】（300-400字）
- 基于原因的建议
- 具体行动方案
- 预防措施
'''
        },
        {
            'id': 'industry_reveal',
            'name': '行业揭秘型',
            'word_count': '3000-4000字',
            'reading_time': '8-10分钟',
            'desc': '行业内幕深度挖掘，建立信任背书',
            'sections': ['行业背景', '潜规则揭秘', '内幕真相', '消费者误区', '正确认知', '选择建议'],
            'best_for': ['行业揭秘', '对比选型'],
            'keywords': ['内幕', '潜规则', '行业', '揭秘', '真相'],
            'structure': '''
## 行业揭秘型模板结构

【行业背景】（300-400字）
- 行业基本情况
- 市场规模/现状
- 行业特点概述

【潜规则揭秘】（500-600字）
- 行业内不为人知的规则
- 常见但少有人说的现象
- 灰色地带说明

【内幕真相】（500-600字）
- 商家不愿意告诉你的真相
- 成本/利润内幕
- 质量差异真相

【消费者误区】（400-500字）
- 大多数消费者的错误认知
- 被营销误导的观念
- 常见购买陷阱

【正确认知】（400-500字）
- 正确的判断标准
- 专业的选择方法
- 识别好产品的能力

【选择建议】（400-500字）
- 给读者的实用建议
- 具体操作指南
- 避坑清单
'''
        },
        {
            'id': 'deep_review',
            'name': '深度测评型',
            'word_count': '3000-4000字',
            'reading_time': '8-10分钟',
            'desc': '产品/服务多维度深度对比测评',
            'sections': ['测评背景', '测评维度', '产品A分析', '产品B分析', '多维对比', '综合结论'],
            'best_for': ['深度测评', '对比选型', '效果验证'],
            'keywords': ['测评', '对比', '评测', '横评', '深度'],
            'structure': '''
## 深度测评型模板结构

【测评背景】（200-300字）
- 测评初衷/缘起
- 测评目标说明
- 测评对象介绍

【测评维度】（400-500字）
- 确定测评维度
- 每维度评判标准
- 权重分配说明

【产品A分析】（500-600字）
- 产品A详细介绍
- 各维度表现分析
- 优缺点总结

【产品B分析】（500-600字）
- 产品B详细介绍
- 各维度表现分析
- 优缺点总结

【多维对比】（400-500字）
- 表格对比展示
- 各维度分项对比
- 关键差异分析

【综合结论】（400-500字）
- 适用人群分析
- 最终推荐建议
- 购买建议
'''
        },
        {
            'id': 'experience_share',
            'name': '经验分享型',
            'word_count': '2000-3000字',
            'reading_time': '5-8分钟',
            'desc': '个人经历深度复盘，情感共鸣+实用价值',
            'sections': ['背景介绍', '经历描述', '踩坑分享', '转折突破', '经验总结', '行动建议'],
            'best_for': ['经验分享', '情感故事'],
            'keywords': ['经历', '分享', '故事', '我的', '真实'],
            'structure': '''
## 经验分享型模板结构

【背景介绍】（200-300字）
- 个人情况说明
- 背景铺垫
- 读者关联建立

【经历描述】（400-500字）
- 详细经历过程
- 时间线梳理
- 关键节点说明

【踩坑分享】（400-500字）
- 遇到的困难/坑
- 当时的想法
- 付出代价说明

【转折突破】（400-500字）
- 转折点是什么
- 如何找到出路
- 关键突破时刻

【经验总结】（400-500字）
- 核心经验提炼
- 方法论沉淀
- 可复用的方法

【行动建议】（300-400字）
- 给读者的建议
- 具体行动步骤
- 鼓励话语
'''
        },
        {
            'id': 'data_insight',
            'name': '数据解读型',
            'word_count': '2500-3500字',
            'reading_time': '6-9分钟',
            'desc': '数据背后深度洞察，专业权威输出',
            'sections': ['数据来源', '数据概览', '关键发现', '深度解读', '趋势预测', '应用建议'],
            'best_for': ['数据解读', '原因分析'],
            'keywords': ['数据', '研究', '报告', '发现', '统计'],
            'structure': '''
## 数据解读型模板结构

【数据来源】（200-300字）
- 数据来源说明
- 数据可靠性说明
- 样本/时间范围

【数据概览】（400-500字）
- 整体数据展示
- 基本发现
- 数据可视化

【关键发现】（500-600字）
- 3-5个核心发现
- 逐条深入分析
- 数据支撑说明

【深度解读】（500-600字）
- 发现背后的原因
- 多维度关联分析
- 深层逻辑解读

【趋势预测】（300-400字）
- 基于数据的趋势判断
- 未来发展预测
- 机会/风险提示

【应用建议】（300-400字）
- 对读者的建议
- 如何利用这些数据
- 行动指南
'''
        },
        {
            'id': 'buying_guide',
            'name': '选购指南型',
            'word_count': '3000-4000字',
            'reading_time': '8-10分钟',
            'desc': '决策全流程深度指导，降低决策门槛',
            'sections': ['选购背景', '关键指标', '常见误区', '选购步骤', '产品推荐', '避坑清单'],
            'best_for': ['选购指南', '决策安心'],
            'keywords': ['选购', '指南', '怎么选', '选择', '避坑'],
            'structure': '''
## 选购指南型模板结构

【选购背景】（200-300字）
- 选购重要性说明
- 选购难点分析
- 文章价值预告

【关键指标】（500-600字）
- 必须关注的指标
- 每项指标含义
- 重要性说明

【常见误区】（400-500字）
- 大多数人犯的错误
- 商家营销陷阱
- 识别误区方法

【选购步骤】（600-700字）
- 5-8步选购流程
- 每步详细说明
- 注意事项提示

【产品推荐】（500-600字）
- 不同价位推荐
- 适用人群说明
- 推荐理由分析

【避坑清单】（400-500字）
- 最后提醒
- 必查清单
- 售后注意事项
'''
        },
        {
            'id': 'solution_guide',
            'name': '解决方案型',
            'word_count': '2500-3500字',
            'reading_time': '6-9分钟',
            'desc': '问题系统化深度解决，提供完整方案',
            'sections': ['问题描述', '问题分析', '方案设计', '实施步骤', '效果预期', '持续优化'],
            'best_for': ['痛点解决', '效果展示', '实操技巧'],
            'keywords': ['解决', '方案', '方法', '搞定', '学会'],
            'structure': '''
## 解决方案型模板结构

【问题描述】（200-300字）
- 问题详细描述
- 影响的严重性
- 读者的共鸣

【问题分析】（400-500字）
- 问题根本原因
- 涉及的因素
- 难点分析

【方案设计】（500-600字）
- 整体解决思路
- 方案框架
- 核心方法论

【实施步骤】（600-700字）
- 具体操作步骤
- 每步详细说明
- 时间/资源要求

【效果预期】（300-400字）
- 预期效果说明
- 见效时间
- 效果评估标准

【持续优化】（300-400字）
- 后续优化建议
- 常见问题解答
- 进阶方向
'''
        }
    ]

    # Token消耗估算
    TOKEN_ESTIMATE = {
        'prompt': 2000,
        'completion': 4000,
        'total': 6000
    }

    def __init__(self):
        self.llm = get_llm_service()

    def generate_article(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        content_direction: str = '种草型',
        template_id: str = None,
        content_style: str = ''
    ) -> dict:
        """
        生成长文内容

        Args:
            topic_title: 选题标题
            topic_type: 选题类型
            business_description: 业务描述
            portrait: 用户画像
            content_direction: 内容方向
            template_id: 指定模板ID（可选）
            content_style: 内容风格

        Returns:
            {
                "success": bool,
                "article": {...},
                "tokens_used": int
            }
        """
        try:
            # 确定使用哪种模板
            if template_id:
                template = self._get_template_by_id(template_id)
            else:
                template = self._select_best_template(topic_type, content_direction)

            # 构建Prompt
            prompt = self._build_article_prompt(
                topic_title=topic_title,
                topic_type=topic_type,
                business_description=business_description,
                portrait=portrait,
                template=template,
                content_direction=content_direction,
                content_style=content_style
            )

            # 调用LLM生成
            messages = [
                {"role": "system", "content": "你是一位资深的内容创作者，精通微信公众号/知乎/头条等内容平台的长文创作。必须严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            article = self._parse_article_response(response)

            # 合并模板信息
            article['template'] = template
            article['template_name'] = template['name']

            return {
                'success': True,
                'article': article,
                'tokens_used': self.TOKEN_ESTIMATE['total']
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def generate_content(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        content_style: str = ''
    ) -> dict:
        """
        生成长文内容（generate_article 的别名，支持 content_style 参数）

        Args:
            topic_title: 选题标题
            topic_type: 选题类型
            business_description: 业务描述
            portrait: 用户画像
            content_style: 内容风格（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）

        Returns:
            {
                "success": bool,
                "content": {...},
                "tokens_used": int
            }
        """
        # 根据 content_style 推导 content_direction
        style_to_direction = {
            '情绪共鸣': '种草型',
            '干货科普': '种草型',
            '犀利吐槽': '种草型',
            '故事叙述': '种草型',
            '权威背书': '转化型',
        }
        content_direction = style_to_direction.get(content_style, '种草型')

        result = self.generate_article(
            topic_title=topic_title,
            topic_type=topic_type,
            business_description=business_description,
            portrait=portrait,
            content_direction=content_direction,
        )

        # 统一返回格式
        if result.get('success'):
            return {
                'success': True,
                'content': result.get('article', {}),
                'tokens_used': result.get('tokens_used', 0),
            }
        else:
            return {
                'success': False,
                'error': result.get('error', '生成失败'),
            }

    def _select_best_template(self, topic_type: str, content_direction: str) -> Dict:
        """根据选题类型和内容方向选择最佳模板"""
        for template in self.TEXT_TEMPLATES:
            if topic_type in template['best_for']:
                return template

        # 默认返回知识科普型
        return self.TEXT_TEMPLATES[0]

    def _get_template_by_id(self, template_id: str) -> Optional[Dict]:
        """根据ID获取模板"""
        for template in self.TEXT_TEMPLATES:
            if template['id'] == template_id:
                return template
        return None

    def _build_article_prompt(
        self,
        topic_title: str,
        topic_type: str,
        business_description: str,
        portrait: dict,
        template: Dict,
        content_direction: str,
        content_style: str = ''
    ) -> str:
        """构建长文生成Prompt"""

        portrait_info = self._get_portrait_info(portrait)
        current_month = datetime.now().month
        current_season = self._get_current_season()

        sections_desc = '\n'.join([f"- {s}" for s in template['sections']])

        # 风格指导
        style_guide = self._get_style_guide(content_style) if content_style else ''

        prompt = f"""你是一位资深的内容创作者。请根据以下信息，生成一篇完整的公众号/知乎长文。

## 选题信息
- 选题标题：{topic_title}
- 选题类型：{topic_type}
- 内容方向：{content_direction}

## 业务信息
- 业务描述：{business_description}

## 目标用户画像
{portrait_info}

## 当前时间
- 月份：{current_month}月
- 季节：{current_season}

## 文章模板：{template['name']}
- 预估字数：{template['word_count']}
- 预估阅读时间：{template['reading_time']}
- 适用选题：{', '.join(template['best_for'])}

## 文章结构（{len(template['sections'])}个部分）
{sections_desc}

{style_guide}

## 长文基础规范
1. **字数**：{template['word_count']}（约{template['reading_time']}阅读）
2. **风格**：深度、专业、有价值、有温度
3. **结构**：逻辑清晰、层次分明、可读性强
4. **开头**：吸引眼球，引发阅读兴趣
5. **结尾**：总结要点，引导互动评论

## 输出格式（严格JSON）
```json
{{
  "title": "文章标题（公众号风格，≤30字）",
  "subtitle": "文章副标题（可选，补充说明）",
  "sections": [
    {{
      "title": "章节标题",
      "content": "章节内容（完整段落，200-500字）"
    }},
    ...
  ],
  "summary": "全文核心要点总结（100字内）",
  "hashtags": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"],
  "cta": "文末行动号召（引导关注/评论）",
  "reading_time": "{template['reading_time']}",
  "word_count_estimate": {template['word_count']}
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

        return prompt

    def _get_portrait_info(self, portrait: dict) -> str:
        """获取画像信息"""
        if not portrait:
            return "暂无详细画像信息"

        if isinstance(portrait, dict):
            identity = portrait.get('identity', '')
            pain_point = portrait.get('pain_point', portrait.get('核心痛点', ''))
            concern = portrait.get('concern', portrait.get('核心顾虑', ''))
            scenario = portrait.get('scenario', portrait.get('场景', ''))

            info = f"用户身份：{identity}" if identity else ""
            info += f"\n核心痛点：{pain_point}" if pain_point else ""
            info += f"\n核心顾虑：{concern}" if concern else ""
            info += f"\n使用场景：{scenario}" if scenario else ""

            return info or "暂无详细画像信息"

        return str(portrait)

    def _get_current_season(self) -> str:
        """获取当前季节"""
        month = datetime.now().month
        if month in [3, 4, 5]:
            return "春季"
        elif month in [6, 7, 8]:
            return "夏季"
        elif month in [9, 10, 11]:
            return "秋季"
        else:
            return "冬季"

    def _get_style_guide(self, content_style: str) -> str:
        """
        根据内容风格生成指导说明

        Args:
            content_style: 风格类型（情绪共鸣/干货科普/犀利吐槽/故事叙述/权威背书）

        Returns:
            风格指导文本
        """
        style_guides = {
            '情绪共鸣': """
【风格：情绪共鸣】
- 文案基调：感性、走心、戳痛点、引发共情
- 开头方式：用情感故事或场景切入，让读者"感同身受"
- 句式特点：使用"你是不是也..."、"没想到..."、"原来..."等句式
- 情绪词：焦虑、担心、后悔、迷茫、无奈、可惜、扎心
- 结尾：温暖、希望的解决方案
""",
            '干货科普': """
【风格：干货科普】
- 文案基调：专业、严谨、有深度，信息量大
- 开头方式：用知识点或数据吸引眼球
- 句式特点：使用"3个技巧"、"5个方法"、"核心关键是..."等结构化表达
- 关键词：揭秘、内幕、原理、技巧、方法、步骤、数据
- 结尾：总结要点，提供可操作的方法论
""",
            '犀利吐槽': """
【风格：犀利吐槽】
- 文案基调：反讽、自嘲、打破常规、引发争议
- 开头方式：用反问或颠覆认知的标题吸引眼球
- 句式特点：使用"别再..."、"你以为..."、"XX都是骗人的"等句式
- 情绪词：错误、误区、坑、骗、傻，白花钱、多此一举
- 结尾：反转或给出正确的做法
""",
            '故事叙述': """
【风格：故事叙述】
- 文案基调：叙事性强、画面感强、有代入感
- 开头方式：从一个具体场景或故事开头
- 句式特点：使用"那天..."、"我曾经..."、"朋友告诉我..."等叙事句式
- 关键词：经历、故事、回忆、那一刻、后来、终于
- 结尾：升华主题，总结感悟
""",
            '权威背书': """
【风格：权威背书】
- 文案基调：可信、有说服力、数据支撑
- 开头方式：用权威数据、专家观点、真实案例吸引信任
- 句式特点：使用"研究表明..."、"数据显示..."、"XX专家建议..."等句式
- 关键词：研究、数据、专家、案例、证明、验证、实测
- 结尾：给出权威背书的产品或服务
""",
        }

        return style_guides.get(content_style, '')

    def _parse_article_response(self, response: str) -> dict:
        """解析LLM返回的文章结果"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                article = json.loads(json_str)
                if isinstance(article, dict):
                    return self._validate_article(article)

            return self._get_default_article()

        except Exception as e:
            return self._get_default_article()

    def _validate_article(self, article: dict) -> dict:
        """验证并补充文章字段"""
        default = self._get_default_article()

        return {
            'title': article.get('title', default['title']),
            'subtitle': article.get('subtitle', ''),
            'sections': article.get('sections', []),
            'summary': article.get('summary', ''),
            'hashtags': article.get('hashtags', default['hashtags']),
            'cta': article.get('cta', '感谢阅读，欢迎评论区交流！'),
            'reading_time': article.get('reading_time', '5分钟'),
            'word_count_estimate': article.get('word_count_estimate', '2000字')
        }

    def _get_default_article(self) -> dict:
        """获取默认文章结构"""
        return {
            'title': '文章标题',
            'subtitle': '',
            'sections': [],
            'summary': '核心要点总结',
            'hashtags': ['#文章', '#干货', '#分享', '#知识', '#建议'],
            'cta': '感谢阅读，欢迎评论区交流！',
            'reading_time': '5分钟',
            'word_count_estimate': '2000字'
        }

    def get_templates(self) -> List[Dict]:
        """获取所有长文模板"""
        return [{
            'id': t['id'],
            'name': t['name'],
            'word_count': t['word_count'],
            'reading_time': t['reading_time'],
            'desc': t['desc'],
            'sections': t['sections'],
            'best_for': t['best_for'],
            'keywords': t['keywords']
        } for t in self.TEXT_TEMPLATES]

    def recommend_template(self, topic_type: str, content_direction: str) -> List[Dict]:
        """推荐适合某选题类型的文章模板"""
        recommendations = []

        for template in self.TEXT_TEMPLATES:
            if topic_type in template['best_for']:
                recommendations.append({
                    'id': template['id'],
                    'name': template['name'],
                    'word_count': template['word_count'],
                    'reading_time': template['reading_time'],
                    'desc': template['desc'],
                    'match_score': 0.95
                })
            else:
                recommendations.append({
                    'id': template['id'],
                    'name': template['name'],
                    'word_count': template['word_count'],
                    'reading_time': template['reading_time'],
                    'desc': template['desc'],
                    'match_score': 0.6
                })

        recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        return recommendations[:3]


# 全局实例
long_text_generator = LongTextGenerator()
