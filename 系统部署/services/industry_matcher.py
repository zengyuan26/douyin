"""
公开内容生成平台 - 行业AI匹配服务

功能：
1. 行业别名映射表
2. AI智能匹配
3. 待处理行业队列
"""

import re
from typing import Dict, List, Optional, Tuple
from models.public_models import PublicIndustryKeyword


# 行业别名映射表
INDUSTRY_ALIASES = {
    "桶装水/矿泉水": [
        "桶装水", "送水", "矿泉水", "定制水", "饮用水", "净水",
        "桶装水配送", "瓶装水", "山泉水", "纯净水", "直饮水",
        "企业用水", "办公用水", "家庭桶装水"
    ],
    "美食餐饮": [
        "餐饮", "餐厅", "饭店", "小吃", "外卖", "火锅", "烧烤",
        "川菜", "粤菜", "湘菜", "私房菜", "农家乐", "快餐",
        "奶茶店", "咖啡店", "烘焙", "蛋糕", "面包店", "早点"
    ],
    "服装": [
        "衣服", "服装", "女装", "男装", "童装", "鞋子", "鞋子",
        "包包", "箱包", "饰品", "配饰", "帽子", "围巾", "袜子"
    ],
    "美容护肤": [
        "美容", "护肤", "化妆品", "护肤品", "美妆", "美发", "美甲",
        "纹眉", "纹绣", "皮肤管理", "SPA", "按摩", "养生",
        "减肥", "纤体", "化妆品店", "美容店"
    ],
    "家电数码": [
        "电器", "手机", "电脑", "家电", "数码", "电视", "冰箱",
        "空调", "洗衣机", "小家电", "厨房电器", "数码配件",
        "电脑配件", "智能家居", "智能设备"
    ],
    "家居用品": [
        "家具", "家居", "家纺", "床上用品", "窗帘", "地毯",
        "装饰画", "摆件", "收纳", "收纳箱", "收纳盒", "日用百货"
    ],
    "教育培训": [
        "培训", "教育", "培训", "补习", "辅导", "家教", "兴趣班",
        "才艺培训", "乐器培训", "舞蹈培训", "美术培训", "外语培训",
        "K12", "中小学辅导", "学前教育", "幼儿园"
    ],
    "丽人": [
        "美发", "美甲", "美容", "化妆", "造型", "纹绣", "美睫",
        "美瞳", "美体", "SPA", "瑜伽", "健身", "瘦身"
    ],
    "母婴用品": [
        "母婴", "奶粉", "尿不湿", "婴儿用品", "童装", "玩具",
        "奶瓶", "婴儿车", "儿童座椅", "孕妇装", "产后恢复"
    ],
    "汽车用品": [
        "汽车", "汽车用品", "汽车配件", "车载用品", "洗车",
        "汽车美容", "汽车维修", "汽车保养", "汽车装饰"
    ],
    "宠物用品": [
        "宠物", "宠物店", "宠物用品", "宠物食品", "宠物美容",
        "宠物医院", "猫粮", "狗粮", "水族", "宠物玩具"
    ],
    "医疗健康": [
        "医疗", "医院", "诊所", "药店", "药房", "医疗器械",
        "体检", "齿科", "眼科", "中医", "养生馆", "保健品"
    ],
    "运动户外": [
        "运动", "户外", "体育用品", "健身器材", "运动鞋",
        "运动服装", "户外装备", "露营", "登山", "徒步"
    ],
    "金融保险": [
        "金融", "保险", "理财", "投资", "贷款", "信用卡",
        "银行", "证券", "基金", "典当"
    ],
    "商务服务": [
        "商务服务", "代理记账", "工商注册", "法律咨询", "设计服务",
        "印刷", "图文广告", "翻译", "猎头", "人力资源"
    ],
}

# 反向映射：别名 -> 主行业
_ALIAS_TO_INDUSTRY = {}
for main_industry, aliases in INDUSTRY_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_INDUSTRY[alias.lower()] = main_industry


class IndustryMatcher:
    """行业匹配器"""

    # 置信度阈值
    CONFIDENCE_THRESHOLD = 0.7

    # 精确匹配缓存
    _exact_cache = {}

    @classmethod
    def match(cls, user_input: str) -> Dict:
        """
        匹配用户输入的行业

        Args:
            user_input: 用户输入的行业描述

        Returns:
            {
                'matched': bool,
                'industry': str,       # 匹配到的行业名称
                'confidence': float,    # 置信度 0-1
                'is_new': bool,         # 是否是新行业
                'alternatives': []      # 备选行业列表
            }
        """
        if not user_input:
            return {
                'matched': False,
                'industry': None,
                'confidence': 0,
                'is_new': True,
                'alternatives': []
            }

        # 清理输入
        user_input = user_input.strip().lower()

        # 1. 精确匹配别名
        if user_input in _ALIAS_TO_INDUSTRY:
            industry = _ALIAS_TO_INDUSTRY[user_input]
            return {
                'matched': True,
                'industry': industry,
                'confidence': 1.0,
                'is_new': False,
                'alternatives': []
            }

        # 2. 模糊匹配（包含关系）
        matches = []
        for main_industry, aliases in INDUSTRY_ALIASES.items():
            for alias in aliases:
                if alias in user_input or user_input in alias:
                    # 计算相似度
                    similarity = len(alias) / max(len(user_input), len(alias))
                    matches.append({
                        'industry': main_industry,
                        'alias': alias,
                        'similarity': similarity
                    })

        if matches:
            # 按相似度排序
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            best_match = matches[0]

            if best_match['similarity'] >= cls.CONFIDENCE_THRESHOLD:
                return {
                    'matched': True,
                    'industry': best_match['industry'],
                    'confidence': best_match['similarity'],
                    'is_new': False,
                    'alternatives': [m['industry'] for m in matches[1:4] if m['industry'] != best_match['industry']]
                }

            # 低置信度，返回建议但标记为新行业
            return {
                'matched': True,
                'industry': best_match['industry'],
                'confidence': best_match['similarity'],
                'is_new': True,
                'alternatives': [m['industry'] for m in matches[1:3] if m['industry'] != best_match['industry']]
            }

        # 3. 未能匹配，返回空
        return {
            'matched': False,
            'industry': user_input,
            'confidence': 0,
            'is_new': True,
            'alternatives': []
        }

    @classmethod
    def get_standard_industry(cls, industry_name: str) -> Optional[str]:
        """
        获取标准化行业名称

        Args:
            industry_name: 行业名称或别名

        Returns:
            标准行业名称，如果不在列表中返回 None
        """
        # 直接查找
        if industry_name in INDUSTRY_ALIASES:
            return industry_name

        # 别名查找
        normalized = industry_name.strip().lower()
        return _ALIAS_TO_INDUSTRY.get(normalized)

    @classmethod
    def get_all_industries(cls) -> List[str]:
        """获取所有标准行业列表"""
        return list(INDUSTRY_ALIASES.keys())

    @classmethod
    def get_industry_aliases(cls, industry: str) -> List[str]:
        """获取行业的所有别名"""
        return INDUSTRY_ALIASES.get(industry, [])

    @classmethod
    def search_industry(cls, keyword: str) -> List[Dict]:
        """
        搜索行业

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的行业列表
        """
        if not keyword:
            return []

        keyword = keyword.lower().strip()
        results = []

        # 搜索标准行业
        for industry in INDUSTRY_ALIASES.keys():
            if keyword in industry.lower():
                results.append({
                    'industry': industry,
                    'match_type': 'name',
                    'aliases': INDUSTRY_ALIASES[industry]
                })

        # 搜索别名
        for alias, main_industry in _ALIAS_TO_INDUSTRY.items():
            if keyword in alias and main_industry not in [r['industry'] for r in results]:
                results.append({
                    'industry': main_industry,
                    'match_type': 'alias',
                    'aliases': INDUSTRY_ALIASES[main_industry],
                    'matched_alias': alias
                })

        return results

    @classmethod
    def parse_industry_from_description(cls, description: str) -> Dict:
        """
        从业务描述中提取行业信息

        Args:
            description: 业务描述文本

        Returns:
            提取的行业信息
        """
        if not description:
            return {'industry': None, 'keywords': [], 'confidence': 0}

        # 提取关键词
        keywords = []
        for main_industry, aliases in INDUSTRY_ALIASES.items():
            for alias in aliases:
                if alias in description.lower():
                    keywords.append(alias)
                    break

        # 如果找到多个匹配，返回最相关的
        if keywords:
            # 优先使用较长的匹配词
            keywords = sorted(keywords, key=len, reverse=True)
            best_keyword = keywords[0]

            # 找到对应的行业
            for industry, aliases in INDUSTRY_ALIASES.items():
                if best_keyword in aliases or best_keyword == industry.lower():
                    return {
                        'industry': industry,
                        'keywords': keywords[:5],
                        'confidence': len(best_keyword) / len(description) * 10
                    }

        return {'industry': None, 'keywords': keywords, 'confidence': 0}


# 全局实例
industry_matcher = IndustryMatcher()
