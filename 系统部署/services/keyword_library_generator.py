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
            
            # 调试日志
            logger.info("[KeywordLibraryGenerator] 业务信息: business_description=%s, industry=%s", 
                business_info.get('business_description', ''), business_info.get('industry', ''))
            logger.info("[KeywordLibraryGenerator] 业务描述上下文: %s", context.get('业务描述', ''))

            # 直接使用默认提示词，不使用数据库模板（模板包含示例数据会干扰生成）
            prompt = self._build_default_prompt(context, realtime, max_keywords)

            # 调用 LLM
            system_msg = (
                "【强制要求】你必须严格按照用户提供的业务描述生成关键词！\n"
                "禁止添加任何未提供的信息！禁止编造产品名称！\n"
                "\n"
                "你是一位抖音SEO关键词专家，精通本地商家获客关键词挖掘。\n"
                "必须严格按照JSON格式输出，关键词必须符合抖音搜索习惯。\n"
                "关键词必须全部来源于用户提供的业务描述，不得包含任何其他产品。"
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

        # 支持多种画像格式
        # 新格式（超级定位）：portrait_summary, user_perspective, buyer_perspective, identity_tags
        # 旧格式：identity, pain_point, concern, scenario
        identity_tags = portrait_data.get('identity_tags', {})
        user_persp = portrait_data.get('user_perspective', {})
        buyer_persp = portrait_data.get('buyer_perspective', {})

        # 目标客户身份
        identity = portrait_data.get('identity', portrait_data.get('用户身份', ''))
        if not identity:
            identity = identity_tags.get('user', '') or identity_tags.get('buyer', '')

        # 核心痛点
        pain_point = portrait_data.get('pain_point', portrait_data.get('核心痛点', ''))
        if not pain_point:
            pain_point = user_persp.get('problem', '')
            if not pain_point:
                # 从 portrait_summary 提取
                summary = portrait_data.get('portrait_summary', '')
                if summary and '，' in summary:
                    pain_point = summary.split('，')[0]

        # 核心顾虑
        concern = portrait_data.get('concern', portrait_data.get('核心顾虑', ''))
        if not concern:
            concern = buyer_persp.get('obstacles', '')
            if not concern:
                concern = buyer_persp.get('psychology', '')

        # 使用场景
        scenario = portrait_data.get('scenario', portrait_data.get('场景', ''))
        if not scenario:
            scenario = user_persp.get('current_state', '')

        # 优先使用表单输入的业务描述和行业（business_info）
        # 这些是用户当前输入的最新数据
        business_desc = business_info.get('business_description', '')
        industry = business_info.get('industry', '')
        
        # 产品信息：如果表单提供了业务描述，忽略画像数据中的产品信息
        products = business_info.get('products', [])
        if not products and business_desc:
            # 从业务描述提取产品
            products = [business_desc]
        
        # 地域信息
        region = business_info.get('region', '')
        target_customer = business_info.get('target_customer', '')

        context = {
            # 画像信息（支持新旧格式）
            '目标客户身份': identity,
            '核心痛点': pain_point,
            '核心顾虑': concern,
            '使用场景': scenario,

            # 业务信息（优先使用表单输入 business_info）
            '业务描述': business_desc,
            '行业': industry,
            '产品': ', '.join(products) if isinstance(products, list) and products else str(products or ''),
            '地域': region,
            '目标客户': target_customer,

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

## 输出格式要求
必须输出标准的JSON格式，包含以下字段：
- categories: 关键词分类数组，每个分类包含 name, key, count, keywords
- blue_ocean: 蓝海长尾词数组
- ratio_strategy: 配比策略对象
- hot_keywords: 热点关键词数组

## 重要提醒
1. 必须使用真实的中文关键词，不要使用任何占位符如 {{变量名}}
2. 关键词必须与上述业务信息紧密相关
3. 关键词数量不少于100个
4. 输出必须是可直接解析的标准JSON格式

请生成JSON格式的关键词库："""

    def _parse_response(self, response: str, realtime: Dict) -> Dict:
        """解析 LLM 返回"""
        import re
        import json
        try:
            # 预处理：去除 markdown 代码块
            clean_response = response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            elif clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            result = None
            
            # 方法1：直接解析
            try:
                result = json.loads(clean_response)
                if result:
                    # 检查是否需要格式转换
                    result = self._convert_to_standard_format(result)
            except json.JSONDecodeError:
                pass
            
            # 方法2：正则匹配 JSON 对象
            if result is None:
                json_match = re.search(r'\{[\s\S]*\}', clean_response)
                if json_match:
                    json_str = json_match.group(0)
                    json_str = json_str.replace('{{', '{').replace('}}', '}')
                    try:
                        result = json.loads(json_str)
                        if result:
                            result = self._convert_to_standard_format(result)
                    except json.JSONDecodeError as e:
                        logger.debug("[KeywordLibraryGenerator] 正则匹配JSON解析失败: %s", e)
            
            # 方法3：修复常见 JSON 错误后重试
            if result is None:
                fixed = self._fix_json_errors(clean_response)
                if fixed:
                    try:
                        result = json.loads(fixed)
                        if result:
                            result = self._convert_to_standard_format(result)
                    except json.JSONDecodeError as e:
                        logger.debug("[KeywordLibraryGenerator] 修复后仍解析失败: %s", e)
            
            # 方法4：更激进的修复
            if result is None:
                # 移除注释
                lines = clean_response.split('\n')
                cleaned_lines = []
                for line in lines:
                    if '//' in line:
                        in_string = False
                        escape = False
                        for c in line:
                            if escape:
                                escape = False
                                continue
                            if c == '\\':
                                escape = True
                                continue
                            if c == '"':
                                in_string = not in_string
                        if not in_string:
                            line = line[:line.index('//')]
                    cleaned_lines.append(line)
                fixed = '\n'.join(cleaned_lines)
                
                # 修复末尾多余逗号
                fixed = re.sub(r',(\s*[\]}])', r'\1', fixed)
                
                try:
                    result = json.loads(fixed)
                    if result:
                        result = self._convert_to_standard_format(result)
                except json.JSONDecodeError:
                    pass
            
            if result is None:
                logger.error("[KeywordLibraryGenerator] 所有JSON解析方式均失败")
                logger.error("[KeywordLibraryGenerator] 原始响应前500字符: %s", response[:500])
                return self._get_default_library(realtime)
            
            # 注入实时热点
            if 'hot_keywords' not in result:
                result['hot_keywords'] = []
            return self._validate_and_fill(result)
        except Exception as e:
            logger.error("[KeywordLibraryGenerator] Parse error: %s", e)
            logger.error("[KeywordLibraryGenerator] 原始响应前500字符: %s", response[:500])
            return self._get_default_library(realtime)
    
    def _convert_to_standard_format(self, result: Dict) -> Dict:
        """将 LLM 返回的任意格式转换为标准格式"""
        if not isinstance(result, dict):
            return None
        
        # 已经是标准格式
        if 'categories' in result and isinstance(result.get('categories'), list):
            return result
        
        # 尝试转换 "关键词库" 或 "关键词" 格式
        # 例如: {"关键词库": {"直接需求关键词": [...]}} -> {"categories": [...]}
        converted = {
            'categories': [],
            'blue_ocean': [],
            'ratio_strategy': {
                'stage': '成长期',
                'long_tail_ratio': 0.35,
                'region_ratio': 0.30,
                'core_ratio': 0.35,
            },
            'hot_keywords': [],
        }
        
        # 定义关键词分类映射
        category_map = {
            '直接需求关键词': 'direct',
            '痛点关键词': 'pain_point',
            '搜索关键词': 'search',
            '场景关键词': 'scene',
            '品牌关键词': 'brand',
            '长尾关键词': 'long_tail',
            '对比关键词': 'compare',
            '地域关键词': 'region',
            '人群关键词': 'crowd',
            '时效关键词': 'time_limited',
        }
        
        # 尝试从多个可能的结构中提取关键词
        keywords_data = None
        
        # 结构1: {"关键词库": {...}}
        if '关键词库' in result and isinstance(result['关键词库'], dict):
            keywords_data = result['关键词库']
        # 结构2: 直接是关键词字典
        else:
            # 检查是否是嵌套结构（如 {"直接需求关键词": {"核心品类词": [...]}}）
            # 找出所有关键词分类
            for cat_name in category_map.keys():
                if cat_name in result:
                    keywords_data = result
                    break
            # 如果没有找到标准分类名，检查整个 result
            if keywords_data is None:
                keywords_data = result
        
        # 遍历关键词分类
        for cat_name, cat_key in category_map.items():
            if cat_name in keywords_data:
                cat_data = keywords_data[cat_name]
                keywords_list = []
                
                if isinstance(cat_data, list):
                    # 直接是关键词列表
                    for item in cat_data:
                        if isinstance(item, dict):
                            kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                            if kw:
                                keywords_list.append(kw)
                        elif isinstance(item, str):
                            keywords_list.append(item)
                elif isinstance(cat_data, dict):
                    # 嵌套结构：{"核心品类词": [...], "品质保障": [...]}
                    for sub_cat_name, sub_keywords in cat_data.items():
                        if isinstance(sub_keywords, list):
                            for item in sub_keywords:
                                if isinstance(item, dict):
                                    kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                                    if kw:
                                        keywords_list.append(kw)
                                elif isinstance(item, str):
                                    keywords_list.append(item)
                
                if keywords_list:
                    converted['categories'].append({
                        'name': cat_name,
                        'key': cat_key,
                        'count': len(keywords_list),
                        'keywords': keywords_list
                    })
        
        # 如果没有提取到任何关键词，尝试更通用的方式
        if not converted['categories']:
            # 遍历 result 中所有的值，尝试提取关键词
            for key, value in keywords_data.items():
                if isinstance(value, list) and len(value) > 0:
                    keywords_list = []
                    for item in value:
                        if isinstance(item, dict):
                            kw = item.get('关键词') or item.get('keyword') or item.get('kw')
                            if kw:
                                keywords_list.append(kw)
                        elif isinstance(item, str):
                            keywords_list.append(item)
                    if keywords_list:
                        converted['categories'].append({
                            'name': key,
                            'key': category_map.get(key, 'other'),
                            'count': len(keywords_list),
                            'keywords': keywords_list
                        })
                elif isinstance(value, dict):
                    # 嵌套结构
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, list):
                            keywords_list = []
                            for item in sub_value:
                                if isinstance(item, str):
                                    keywords_list.append(item)
                                elif isinstance(item, dict):
                                    kw = item.get('关键词') or item.get('keyword')
                                    if kw:
                                        keywords_list.append(kw)
                            if keywords_list:
                                converted['categories'].append({
                                    'name': f"{key}_{sub_key}",
                                    'key': category_map.get(key, 'other'),
                                    'count': len(keywords_list),
                                    'keywords': keywords_list
                                })
        
        # 如果仍然没有提取到，返回失败
        if not converted['categories']:
            logger.warning("[KeywordLibraryGenerator] 无法从响应中提取关键词格式")
            return None
        
        return converted
    
    def _fix_json_errors(self, json_str: str) -> str:
        """修复常见 JSON 格式错误"""
        import re
        
        # 移除注释（// 开头的行）
        lines = json_str.split('\n')
        cleaned_lines = []
        for line in lines:
            if '//' in line:
                in_string = False
                escape = False
                for c in line:
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"':
                        in_string = not in_string
                if not in_string:
                    line = line[:line.index('//')]
            cleaned_lines.append(line)
        json_str = '\n'.join(cleaned_lines)
        
        # 修复末尾多余逗号
        json_str = re.sub(r',(\s*[\]}])', r'\1', json_str)
        
        # 移除不可见控制字符
        json_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', json_str)
        
        return json_str

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
