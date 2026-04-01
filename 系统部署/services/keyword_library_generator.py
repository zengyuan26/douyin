"""
画像专属关键词库生成服务

功能：
1. 读取模板配置，生成专属关键词库
2. 结合实时上下文（季节/节日/热点）
3. 持久化到 saved_portraits.keyword_library
4. 支持实时刷新 + 配额检查
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from models.public_models import SavedPortrait, db
from services.template_config_service import template_config_service, TemplateConfigService
from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class KeywordLibraryGenerator:
    """
    关键词库生成器

    复用 geo-seo skill 中的关键词库模板逻辑：
    - 10大关键词分类
    - 蓝海词挖掘
    - 配比策略（起号期/成长期/成熟期）
    """

    # 关键词分类常量（与 geo-seo 保持一致）
    CATEGORIES = [
        {'name': '直接需求关键词', 'key': 'direct', 'min': 20,
         'desc': '核心词+品质服务词，直接表达购买意向'},
        {'name': '痛点关键词', 'key': 'pain_point', 'min': 15,
         'desc': '问题型+担心型+后果型，从评论区挖痛点'},
        {'name': '搜索关键词', 'key': 'search', 'min': 15,
         'desc': '疑问型+方法型+对比型，从搜索框挖需求'},
        {'name': '场景关键词', 'key': 'scene', 'min': 15,
         'desc': '客户类型+具体场景，场景细分'},
        {'name': '地域关键词', 'key': 'region', 'min': 10,
         'desc': '本地+周边扩展，本地流量词'},
        {'name': '季节关键词', 'key': 'season', 'min': 10,
         'desc': '旺季+淡季季节性关键词'},
        {'name': '技巧干货关键词', 'key': 'skill', 'min': 10,
         'desc': '干货型+数字型技巧词'},
        {'name': '认知颠覆关键词', 'key': 'rethink', 'min': 5,
         'desc': '反向+辟谣类，颠覆常识类'},
        {'name': '节日节气关键词', 'key': 'festival', 'min': 15,
         'desc': '传统节日+现代节日+24节气方法论'},
        {'name': '行业关联关键词', 'key': 'industry', 'min': 10,
         'desc': '上下游业务关联词，行业生态'},
    ]

    def __init__(self):
        self.llm = get_llm_service()

    def generate(
        self,
        portrait_data: Dict,
        business_info: Dict,
        plan_type: str = 'professional',
        use_template: bool = True,
        max_keywords: int = 200,
        portrait_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        生成关键词库（缓存优先）

        Args:
            portrait_data: 画像数据（身份/痛点/顾虑/场景）
            business_info: 业务信息
            plan_type: 套餐类型（影响配比策略）
            use_template: 是否使用模板配置（False=简单模式）
            max_keywords: 最大关键词数量
            portrait_id: 画像ID（用于缓存检查）
        """
        try:
            # 缓存检查：如果画像有关键词库且未过期，直接返回
            if portrait_id:
                portrait = SavedPortrait.query.get(portrait_id)
                if portrait and not portrait.keyword_library_expired:
                    logger.info("[KeywordLibraryGenerator] 命中缓存，跳过生成 portrait_id=%s", portrait_id)
                    return {
                        'success': True,
                        'keyword_library': portrait.keyword_library,
                        'tokens_used': 0,
                        '_meta': {'from_cache': True},
                    }

            # 防御性检查
            if not isinstance(portrait_data, dict):
                portrait_data = {}
            if not isinstance(business_info, dict):
                business_info = {}

            # 获取实时上下文（季节/节日/热点）
            realtime = template_config_service.get_realtime_context()

            # 构建变量上下文
            context = self._build_context(portrait_data, business_info, realtime)

            # 获取模板内容
            if use_template:
                template = template_config_service.get_template('keyword')
                if template:
                    prompt = template_config_service.replace_variables(
                        template['template_content'], context
                    )
                else:
                    prompt = self._build_default_prompt(context, realtime, max_keywords)
            else:
                prompt = self._build_default_prompt(context, realtime, max_keywords)

            # 调用 LLM
            system_msg = (
                "你是一位抖音SEO关键词专家，精通本地商家获客关键词挖掘。"
                "必须严格按照JSON格式输出，关键词必须符合抖音搜索习惯。"
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
            response = self.llm.chat(messages)

            # 解析结果
            result = self._parse_response(response, realtime)

            return {
                'success': True,
                'keyword_library': result,
                'tokens_used': self._estimate_tokens(prompt, response),
                '_meta': {
                    'plan_type': plan_type,
                    'realtime': realtime,
                    'used_template': use_template,
                }
            }

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] Error: %s", e)
            return {'success': False, 'error': str(e)}

    def save_to_portrait(
        self,
        portrait_id: int,
        keyword_library: Dict,
        user_id: int,
        plan_type: str = 'professional',
    ) -> bool:
        """
        将关键词库保存到画像记录

        Args:
            portrait_id: 画像ID
            keyword_library: 关键词库数据
            user_id: 用户ID
            plan_type: 套餐类型（决定过期时间）

        Returns:
            是否保存成功
        """
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return False

        # 计算过期时间（根据套餐）
        ttl_hours = {
            'basic': 24,
            'professional': 168,  # 7天
            'enterprise': 720,    # 30天
        }.get(plan_type, 24)

        portrait.keyword_library = keyword_library
        portrait.keyword_updated_at = datetime.utcnow()
        portrait.keyword_update_count = (portrait.keyword_update_count or 0) + 1
        portrait.keyword_cache_expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)

        db.session.commit()
        return True

    def get_from_portrait(self, portrait_id: int) -> Optional[Dict]:
        """
        从画像获取已保存的关键词库

        Returns:
            关键词库数据 或 None
        """
        portrait = SavedPortrait.query.get(portrait_id)
        if not portrait:
            return None

        # 检查过期
        if portrait.keyword_library_expired:
            return None

        return portrait.keyword_library

    def _build_context(
        self,
        portrait_data: Dict,
        business_info: Dict,
        realtime: Dict,
    ) -> Dict:
        """构建模板变量上下文"""
        # 防御性检查
        if not isinstance(portrait_data, dict):
            portrait_data = {}
        if not isinstance(business_info, dict):
            business_info = {}
        if not isinstance(realtime, dict):
            realtime = {}

        context = {
            # 画像信息
            '目标客户身份': portrait_data.get('identity', portrait_data.get('用户身份', '')),
            '核心痛点': portrait_data.get('pain_point', portrait_data.get('核心痛点', '')),
            '核心顾虑': portrait_data.get('concern', portrait_data.get('核心顾虑', '')),
            '使用场景': portrait_data.get('scenario', portrait_data.get('场景', '')),

            # 业务信息
            '业务描述': business_info.get('business_description', ''),
            '行业': business_info.get('industry', ''),
            '产品': ', '.join(business_info.get('products', [])),
            '地域': business_info.get('region', ''),
            '目标客户': business_info.get('target_customer', ''),

            # 实时上下文
            '当前季节': realtime.get('当前季节', ''),
            '月份名称': realtime.get('月份名称', ''),
            '季节消费特点': realtime.get('季节消费特点', ''),
            '月度热点前缀': realtime.get('月度热点前缀', ''),
            '当前节日': realtime.get('当前节日', '无'),
            '当前节气': realtime.get('当前节气', '无'),
        }
        return context

    def _build_default_prompt(
        self,
        context: Dict,
        realtime: Dict,
        max_keywords: int,
    ) -> str:
        """构建默认提示词（当模板不存在时使用）"""

        category_rules = '\n'.join([
            f"{i+1}. **{c['name']}**（≥{c['min']}个）：{c['desc']}"
            for i, c in enumerate(self.CATEGORIES)
        ])

        return f"""你是一位抖音SEO关键词专家。请为以下业务生成关键词库。

## 业务信息
- 行业：{context['行业']}
- 业务描述：{context['业务描述']}
- 产品：{context['产品']}
- 地域：{context['地域']}
- 目标客户：{context['目标客户']}

## 目标用户画像
- 用户身份：{context['目标客户身份']}
- 核心痛点：{context['核心痛点']}
- 核心顾虑：{context['核心顾虑']}
- 使用场景：{context['使用场景']}

## 实时上下文
- 当前季节：{context['当前季节']}（{context['月份名称']}）
- 季节消费特点：{context['季节消费特点']}
- 月度热点：{context['月度热点前缀']}
- 当前节日：{context['当前节日']}
- 当前节气：{context['当前节气']}

## 关键词分类要求
请生成以下10大分类的关键词：

{category_rules}

## 蓝海长尾词挖掘
使用修饰词公式生成蓝海词：
- 修饰词类型：人群细分、场景细分、痛点细分、地域细分、价格细分、时间细分、功能细分、材质细分
- 公式：核心大词 + 差异化修饰词

## 配比策略
- 起号期：长尾词50% + 地域词30% + 大词20%
- 成长期：长尾词35% + 地域词30% + 大词35%
- 成熟期：长尾词20% + 地域词20% + 大词60%

## 输出格式（严格JSON，最多{max_keywords}个关键词）
```json
{{
  "categories": [
    {{
      "name": "直接需求关键词",
      "key": "direct",
      "count": 20,
      "keywords": ["关键词1", "关键词2", ...]
    }},
    ...
  ],
  "blue_ocean": [
    {{
      "core_word": "核心词",
      "modifier": "修饰词",
      "full_keyword": "完整蓝海词",
      "type": "人群细分"
    }}
  ],
  "ratio_strategy": {{
    "stage": "成长期",
    "long_tail_ratio": 0.35,
    "region_ratio": 0.30,
    "core_ratio": 0.35
  }},
  "hot_keywords": ["热点词1", "热点词2", "热点词3"]
}}
```

请严格按照JSON格式输出，不要包含其他内容。"""

    def _parse_response(self, response: str, realtime: Dict) -> Dict:
        """解析 LLM 返回"""
        import re
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
                # 注入实时热点
                if 'hot_keywords' not in result:
                    result['hot_keywords'] = []
                return self._validate_and_fill(result)
            return self._get_default_library(realtime)
        except Exception as e:
            logger.debug("[KeywordLibraryGenerator] Parse error: %s", e)
            return self._get_default_library(realtime)

    def _validate_and_fill(self, result: Dict) -> Dict:
        """验证并补充关键词库"""
        default = self._get_default_library({})
        for key in ['categories', 'blue_ocean', 'ratio_strategy', 'hot_keywords']:
            if key not in result:
                result[key] = default.get(key, [] if key != 'ratio_strategy' else {})
        return result

    def _get_default_library(self, realtime: Dict) -> Dict:
        """获取默认关键词库"""
        return {
            'categories': [
                {'name': c['name'], 'key': c['key'], 'count': c['min'], 'keywords': []}
                for c in self.CATEGORIES
            ],
            'blue_ocean': [],
            'ratio_strategy': {
                'stage': '成长期',
                'long_tail_ratio': 0.35,
                'region_ratio': 0.30,
                'core_ratio': 0.35,
            },
            'hot_keywords': [],
        }

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """估算 token 消耗"""
        # 粗略估算：中文约2字/token，英文约4字符/token
        return int((len(prompt) / 2) + (len(response) / 2))


# 全局实例
keyword_library_generator = KeywordLibraryGenerator()
