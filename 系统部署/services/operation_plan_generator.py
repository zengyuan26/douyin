"""
运营规划生成器
参考 operations-expert skill
"""

import json
from typing import Dict, Any, Optional
from services.llm import LLMService


class OperationPlanGenerator:
    """运营规划生成器"""

    def __init__(self):
        self.llm = LLMService()

    def generate(self, blue_ocean_analysis) -> Dict[str, Any]:
        """
        生成运营规划方案

        Args:
            blue_ocean_analysis: 蓝海分析对象

        Returns:
            运营规划数据
        """
        # 提取关键信息
        analysis_data = self._extract_analysis_data(blue_ocean_analysis)

        # 生成账号设计
        account_design = self._generate_account_design(analysis_data)

        # 生成内容配比
        content_ratio = self._generate_content_ratio(analysis_data)

        # 生成完整方案
        plan_content = self._generate_plan_content(analysis_data, account_design)

        return {
            'account_name': account_design.get('account_name'),
            'account_bio': account_design.get('account_bio'),
            'avatar_suggestion': account_design.get('avatar_suggestion'),
            'content_tags': account_design.get('content_tags', []),
            'content_ratio': content_ratio,
            'plan_content': plan_content
        }

    def _extract_analysis_data(self, analysis) -> Dict[str, Any]:
        """提取分析数据"""
        # 如果是对象，转为字典
        if hasattr(analysis, '__dict__'):
            return {
                'industry': analysis.industry or '',
                'business_type': analysis.business_type or 'toc',
                'industry_report': analysis.industry_report or {},
                'blue_ocean_opportunities': analysis.blue_ocean_opportunities or [],
                'target_personas': analysis.target_personas or [],
                'time_insights': analysis.time_insights or {},
                'keyword_library': analysis.keyword_library or {},
                'topic_library': analysis.topic_library or {}
            }
        return analysis

    def _generate_account_design(self, analysis_data: Dict) -> Dict[str, Any]:
        """生成账号设计"""
        # 提取蓝海机会
        opportunities = analysis_data.get('blue_ocean_opportunities', [])
        personas = analysis_data.get('target_personas', [])

        if not opportunities and not personas:
            # 默认账号设计
            return self._get_default_account_design(analysis_data)

        # 取第一个机会作为主要切入点
        main_opportunity = opportunities[0] if opportunities else {}
        main_persona = personas[0] if personas else {}

        # 构造 Prompt
        prompt = f"""你是账号设计专家。请基于以下蓝海分析结果，设计账号方案。

【行业】：{analysis_data.get('industry', '未知行业')}
【业务类型】：{analysis_data.get('business_type', 'toc')}

【主要蓝海机会】：
{json.dumps(main_opportunity, ensure_ascii=False, indent=2)}

【主要目标人群】：
{json.dumps(main_persona, ensure_ascii=False, indent=2)}

请设计以下内容：

1. 账号昵称（围绕问题，不围绕产品）
2. 账号简介（强调能解决什么问题）
3. 头像建议（风格、颜色、元素）
4. 内容标签（5-10个标签）

输出格式：
{{
    "account_name": "账号昵称",
    "account_bio": "账号简介",
    "avatar_suggestion": "头像建议",
    "content_tags": ["标签1", "标签2", ...]
}}
"""

        # 同步调用（也可以改为异步）
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.llm.chat(prompt))
        finally:
            loop.close()

        # 解析响应
        return self._parse_account_design(response)

    def _parse_account_design(self, response: str) -> Dict[str, Any]:
        """解析账号设计响应"""
        import re
        try:
            # 提取 JSON
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                return json.loads(match.group())
        except:
            pass
        return self._get_default_account_design({})

    def _get_default_account_design(self, analysis_data: Dict) -> Dict[str, Any]:
        """获取默认账号设计"""
        industry = analysis_data.get('industry', '行业')
        return {
            'account_name': f'{industry}专家',
            'account_bio': f'专注{industry}，分享专业知识和解决方案',
            'avatar_suggestion': '使用行业相关的图标或专业形象照片',
            'content_tags': [industry, '专业知识', '解决方案', '行业洞察']
        }

    def _generate_content_ratio(self, analysis_data: Dict) -> Dict[str, Any]:
        """生成内容配比"""
        time_insights = analysis_data.get('time_insights', {})
        season = time_insights.get('season', '常规期')

        # 根据季节调整配比
        if '旺季' in season or '大促' in season:
            return {
                'promotion': 50,
                'product': 20,
                'knowledge': 15,
                'case': 10,
                'persona': 5
            }
        elif '淡季' in season:
            return {
                'promotion': 20,
                'product': 20,
                'knowledge': 30,
                'case': 20,
                'persona': 10
            }
        else:
            # 常规期
            return {
                'promotion': 30,
                'product': 25,
                'knowledge': 20,
                'case': 15,
                'persona': 10
            }

    def _generate_plan_content(self, analysis_data: Dict, account_design: Dict) -> Dict[str, Any]:
        """生成完整运营规划方案"""
        opportunities = analysis_data.get('blue_ocean_opportunities', [])
        personas = analysis_data.get('target_personas', [])
        time_insights = analysis_data.get('time_insights', {})

        return {
            'market_opportunity': {
                'opportunities': opportunities,
                'main_opportunity': opportunities[0] if opportunities else {}
            },
            'target_audience': {
                'personas': personas,
                'main_persona': personas[0] if personas else {}
            },
            'account_design': account_design,
            'time_insights': time_insights,
            'monthly_plan': self._generate_monthly_plan(time_insights),
            'monetization': self._generate_monetization(analysis_data)
        }

    def _generate_monthly_plan(self, time_insights: Dict) -> Dict[str, Any]:
        """生成月度计划"""
        season = time_insights.get('season', '常规期')
        content_dir = time_insights.get('content_direction', '')

        return {
            'week1': {
                'theme': '账号基础建设',
                'content': ['账号装修', '人设定位', '内容规划']
            },
            'week2': {
                'theme': '内容测试',
                'content': ['发布测试内容', '观察数据反馈', '优化内容方向']
            },
            'week3': {
                'theme': '内容矩阵',
                'content': ['稳定更新频率', '多类型内容测试', '建立选题库']
            },
            'week4': {
                'theme': '数据分析',
                'content': ['复盘本月数据', '优化内容策略', '制定下月计划']
            }
        }

    def _generate_monetization(self, analysis_data: Dict) -> Dict[str, Any]:
        """生成变现方案"""
        business_type = analysis_data.get('business_type', 'toc')

        if business_type == 'toc':
            return {
                'primary': '产品销售',
                'secondary': ['私域引流', '直播带货'],
                'conversion_path': '内容引流 → 主页 → 私信 → 成交'
            }
        elif business_type == 'tob':
            return {
                'primary': '企业服务',
                'secondary': ['解决方案销售', '定制服务'],
                'conversion_path': '内容引流 → 主页 → 留咨 → 商务洽谈'
            }
        else:
            return {
                'primary': '产品销售 + 企业服务',
                'secondary': ['私域运营', '直播', '定制方案'],
                'conversion_path': '内容引流 → 分流 → C端/B端转化'
            }
