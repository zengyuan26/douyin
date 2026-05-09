"""
机构产品类内容模板

机构型信任 = 企业品牌 → 个人信任

特点：
- 不需要做人设
- 不需要讲故事
- 重点讲产品、讲服务、讲优惠
- 信任由机构承担

出镜方式：画面 + 旁白 / 产品特写 / 客服出镜
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class InstitutionProductType(Enum):
    """机构产品类子类型"""
    PRODUCT_SPEC = "product_spec"         # 产品规格型
    SERVICE_GUARANTEE = "service_guarantee"  # 服务保障型
    BRAND_STORY = "brand_story"           # 品牌故事型
    PRICE_COMPARE = "price_compare"       # 价格对比型
    USER_REVIEW = "user_review"           # 用户评价型


@dataclass
class InstitutionTemplate:
    """机构产品类模板"""
    id: str
    name: str
    description: str
    duration_range: str
    structure: str
    scenes: List[Dict[str, Any]]
    style_tips: List[str]
    suitable_for: List[str]


# =============================================================================
# 机构产品类模板库
# =============================================================================

INSTITUTION_TEMPLATES = {
    InstitutionProductType.PRODUCT_SPEC: InstitutionTemplate(
        id="product_spec",
        name="产品规格型",
        description="详细介绍产品参数、规格、特点",
        duration_range="30-60秒",
        structure="痛点引入 → 产品介绍 → 规格对比 → 优势总结 → CTA",
        scenes=[
            {
                "scene_index": 1,
                "scene_name": "痛点引入",
                "time_range": "0-5秒",
                "emotion": "平静",
                "content_type": "问题场景",
                "visual": "真实使用场景",
                "narration_template": "还在为[痛点问题]烦恼？"
            },
            {
                "scene_index": 2,
                "scene_name": "产品介绍",
                "time_range": "5-20秒",
                "emotion": "平稳",
                "content_type": "产品展示",
                "visual": "产品特写 + 参数标注",
                "narration_template": "来看看这款[产品名称]，它有[核心参数1]、[核心参数2]、[核心参数3]"
            },
            {
                "scene_index": 3,
                "scene_name": "规格对比",
                "time_range": "20-35秒",
                "emotion": "平稳",
                "content_type": "数据展示",
                "visual": "对比图表/表格",
                "narration_template": "和市面上同类产品相比，[产品名]的[优势指标]提升了[数据]%"
            },
            {
                "scene_index": 4,
                "scene_name": "优势总结",
                "time_range": "35-45秒",
                "emotion": "正面",
                "content_type": "价值提炼",
                "visual": "产品 + 场景",
                "narration_template": "简单来说，就是[一句话总结核心价值]"
            },
            {
                "scene_index": 5,
                "scene_name": "CTA",
                "time_range": "45-60秒",
                "emotion": "正面",
                "content_type": "行动号召",
                "visual": "购买链接/二维码",
                "narration_template": "点击下方链接[优惠信息]，立即体验！"
            }
        ],
        style_tips=[
            "画面以产品特写为主，清晰展示细节",
            "数据用图表呈现，一目了然",
            "口播节奏平稳，专业但不冰冷",
            "避免过度情绪化，保持机构专业感"
        ],
        suitable_for=[
            "电子产品",
            "家电产品",
            "工业设备",
            "标准化的服务产品"
        ]
    ),

    InstitutionProductType.SERVICE_GUARANTEE: InstitutionTemplate(
        id="service_guarantee",
        name="服务保障型",
        description="强调售后服务、退换政策、质量保证",
        duration_range="15-45秒",
        structure="服务承诺 → 保障内容 → 案例证明 → 信任强化 → CTA",
        scenes=[
            {
                "scene_index": 1,
                "scene_name": "服务承诺",
                "time_range": "0-5秒",
                "emotion": "温暖",
                "content_type": "承诺宣言",
                "visual": "品牌Logo + 服务口号",
                "narration_template": "买得放心，用得安心——这是[品牌名]对您的承诺"
            },
            {
                "scene_index": 2,
                "scene_name": "保障内容",
                "time_range": "5-20秒",
                "emotion": "平稳",
                "content_type": "政策说明",
                "visual": "图标 + 文字说明",
                "narration_template": "我们提供[保障1]、[保障2]、[保障3]，让您购物零风险"
            },
            {
                "scene_index": 3,
                "scene_name": "案例证明",
                "time_range": "20-30秒",
                "emotion": "正面",
                "content_type": "案例展示",
                "visual": "用户反馈截图/视频",
                "narration_template": "已有[X]万用户选择我们，好评率[数据]%"
            },
            {
                "scene_index": 4,
                "scene_name": "信任强化",
                "time_range": "30-40秒",
                "emotion": "正面",
                "content_type": "权威背书",
                "visual": "资质证书/合作logo",
                "narration_template": "[品牌名]拥有[资质/认证]，值得信赖"
            },
            {
                "scene_index": 5,
                "scene_name": "CTA",
                "time_range": "40-45秒",
                "emotion": "温暖",
                "content_type": "行动号召",
                "visual": "联系方式/店铺链接",
                "narration_template": "现在就下单，享受[优惠]，或联系客服了解详情"
            }
        ],
        style_tips=[
            "整体风格温暖但不煽情",
            "强调具体数字和承诺",
            "资质证书增加权威感",
            "CTA明确但不催促"
        ],
        suitable_for=[
            "电商平台",
            "连锁品牌",
            "服务型企业",
            "有资质的专业服务"
        ]
    ),

    InstitutionProductType.BRAND_STORY: InstitutionTemplate(
        id="brand_story",
        name="品牌故事型",
        description="讲述品牌历程、理念、价值观",
        duration_range="60-90秒",
        structure="悬念引入 → 品牌起源 → 发展历程 → 核心理念 → 品牌愿景 → CTA",
        scenes=[
            {
                "scene_index": 1,
                "scene_name": "悬念引入",
                "time_range": "0-5秒",
                "emotion": "好奇",
                "content_type": "悬念钩子",
                "visual": "品牌历史物件/老照片",
                "narration_template": "你知道[品牌名]是怎么诞生的吗？"
            },
            {
                "scene_index": 2,
                "scene_name": "品牌起源",
                "time_range": "5-20秒",
                "emotion": "平静",
                "content_type": "故事讲述",
                "visual": "创业场景/创始人",
                "narration_template": "20XX年，[创始人名]创立了[品牌名]，起因是[起因故事]"
            },
            {
                "scene_index": 3,
                "scene_name": "发展历程",
                "time_range": "20-40秒",
                "emotion": "正面",
                "content_type": "里程碑展示",
                "visual": "时间线/成就展示",
                "narration_template": "从[起点]到[现状]，[品牌名]已经走过了[X]年"
            },
            {
                "scene_index": 4,
                "scene_name": "核心理念",
                "time_range": "40-55秒",
                "emotion": "坚定",
                "content_type": "价值观输出",
                "visual": "产品+理念文字",
                "narration_template": "[品牌名]始终坚持'[核心理念]'，这是我们的灵魂"
            },
            {
                "scene_index": 5,
                "scene_name": "品牌愿景",
                "time_range": "55-70秒",
                "emotion": "展望",
                "content_type": "未来展望",
                "visual": "未来愿景图",
                "narration_template": "未来，[品牌名]将[愿景目标]，让更多人[受益描述]"
            },
            {
                "scene_index": 6,
                "scene_name": "CTA",
                "time_range": "70-90秒",
                "emotion": "邀请",
                "content_type": "行动号召",
                "visual": "品牌Logo+店铺",
                "narration_template": "感谢您的信任，欢迎体验[品牌名]的产品和服务"
            }
        ],
        style_tips=[
            "讲述有温度但不煽情的故事",
            "适当展示创始人增加亲切感",
            "用具体数据支撑品牌实力",
            "结尾简洁有力"
        ],
        suitable_for=[
            "老字号品牌",
            "有历史沉淀的企业",
            "注重品牌文化的机构",
            "连锁品牌"
        ]
    ),

    InstitutionProductType.PRICE_COMPARE: InstitutionTemplate(
        id="price_compare",
        name="价格对比型",
        description="同价位产品对比，突出性价比",
        duration_range="30-60秒",
        structure="价格悬念 → 参数对比 → 结论揭晓 → 价值强调 → CTA",
        scenes=[
            {
                "scene_index": 1,
                "scene_name": "价格悬念",
                "time_range": "0-5秒",
                "emotion": "好奇",
                "content_type": "悬念设置",
                "visual": "价格标签/对比图",
                "narration_template": "同样花了[价格区间]，别人买的是[对比品]，而你买的应该是[我们的产品]"
            },
            {
                "scene_index": 2,
                "scene_name": "参数对比",
                "time_range": "5-25秒",
                "emotion": "理性",
                "content_type": "数据对比",
                "visual": "对比表格/图表",
                "narration_template": "来看详细对比：[参数1]我们[X] vs 他们[Y]，[参数2]我们[A] vs 他们[B]"
            },
            {
                "scene_index": 3,
                "scene_name": "结论揭晓",
                "time_range": "25-40秒",
                "emotion": "自信",
                "content_type": "结论输出",
                "visual": "优势标注",
                "narration_template": "结论：[品牌名]的[产品名]在[关键指标]上完胜，[性价比]更高"
            },
            {
                "scene_index": 4,
                "scene_name": "价值强调",
                "time_range": "40-50秒",
                "emotion": "正面",
                "content_type": "价值强化",
                "visual": "产品+价值点",
                "narration_template": "而且，[附加价值]，让您买得超值"
            },
            {
                "scene_index": 5,
                "scene_name": "CTA",
                "time_range": "50-60秒",
                "emotion": "引导",
                "content_type": "行动号召",
                "visual": "购买入口",
                "narration_template": "[优惠信息]，点击下方链接立即购买！"
            }
        ],
        style_tips=[
            "对比数据要客观真实",
            "突出优势但不贬低竞品",
            "用具体数字说明问题",
            "避免价格战思维"
        ],
        suitable_for=[
            "电商产品",
            "电子产品",
            "性价比产品",
            "需要说服购买的场景"
        ]
    ),

    InstitutionProductType.USER_REVIEW: InstitutionTemplate(
        id="user_review",
        name="用户评价型",
        description="展示真实用户评价和使用体验",
        duration_range="30-60秒",
        structure="问题引入 → 用户声音 → 真实反馈 → 信任强化 → CTA",
        scenes=[
            {
                "scene_index": 1,
                "scene_name": "问题引入",
                "time_range": "0-5秒",
                "emotion": "共鸣",
                "content_type": "痛点共情",
                "visual": "问题场景",
                "narration_template": "买[产品类型]最怕什么？怕[痛点1]、怕[痛点2]..."
            },
            {
                "scene_index": 2,
                "scene_name": "用户声音",
                "time_range": "5-20秒",
                "emotion": "惊喜",
                "content_type": "评价展示",
                "visual": "评价截图/视频",
                "narration_template": "来看看已经购买的用户怎么说：'[用户评价1]'"
            },
            {
                "scene_index": 3,
                "scene_name": "真实反馈",
                "time_range": "20-35秒",
                "emotion": "正面",
                "content_type": "多角度反馈",
                "visual": "多用户评价",
                "narration_template": "另一位用户说：'[用户评价2]'，还有用户说：'[用户评价3]'"
            },
            {
                "scene_index": 4,
                "scene_name": "信任强化",
                "time_range": "35-45秒",
                "emotion": "信任",
                "content_type": "数据背书",
                "visual": "评价数据统计",
                "narration_template": "目前[产品名]累计[销量]，[好评率]，[复购率]的用户选择"
            },
            {
                "scene_index": 5,
                "scene_name": "CTA",
                "time_range": "45-60秒",
                "emotion": "邀请",
                "content_type": "行动号召",
                "visual": "购买入口",
                "narration_template": "真实评价，真实口碑。点击下方链接，开启您的体验之旅！"
            }
        ],
        style_tips=[
            "评价要真实可查",
            "多角度展示（质量、服务、性价比）",
            "用数据增强说服力",
            "避免过度加工的评价"
        ],
        suitable_for=[
            "电商产品",
            "体验型服务",
            "口碑重要产品",
            "需要建立信任的产品"
        ]
    )
}


class InstitutionContentGenerator:
    """机构产品类内容生成器"""

    def __init__(self):
        self.templates = INSTITUTION_TEMPLATES

    def get_template(self, template_type: InstitutionProductType) -> InstitutionTemplate:
        """获取指定类型模板"""
        return self.templates.get(template_type)

    def list_templates(self) -> List[Dict[str, str]]:
        """列出所有模板"""
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "duration_range": t.duration_range
            }
            for t in self.templates.values()
        ]

    def generate_script(
        self,
        template_type: InstitutionProductType,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成机构产品类脚本

        Args:
            template_type: 模板类型
            context: 上下文数据，包含：
                - brand_name: 品牌名称
                - product_name: 产品名称
                - product_features: 产品特点
                - price: 价格
                - discount: 优惠信息
                - pain_points: 目标痛点
                - target_audience: 目标受众

        Returns:
            dict: 生成的脚本数据
        """
        template = self.get_template(template_type)
        if not template:
            raise ValueError(f"Unknown template type: {template_type}")

        scenes = []
        for scene_template in template.scenes:
            scene = self._fill_scene(scene_template, context)
            scenes.append(scene)

        return {
            "template_id": template.id,
            "template_name": template.name,
            "structure": template.structure,
            "duration_range": template.duration_range,
            "scenes": scenes,
            "style_tips": template.style_tips,
            "suitable_for": template.suitable_for
        }

    def _fill_scene(
        self,
        scene_template: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """填充场景模板"""
        narration = scene_template["narration_template"]

        # 替换占位符
        replacements = {
            "[品牌名]": context.get("brand_name", ""),
            "[产品名]": context.get("product_name", ""),
            "[痛点问题]": context.get("pain_points", ["质量担忧", "价格不透明", "售后困难"]),
            "[核心参数1]": context.get("product_features", [{}])[0].get("name", "参数1") if context.get("product_features") else "参数1",
            "[核心参数2]": context.get("product_features", [{}])[1].get("name", "参数2") if len(context.get("product_features", [])) > 1 else "参数2",
            "[核心参数3]": context.get("product_features", [{}])[2].get("name", "参数3") if len(context.get("product_features", [])) > 2 else "参数3",
            "[优势指标]": context.get("advantage_metric", "性价比"),
            "[数据]": context.get("advantage_value", "30"),
            "[一句话总结核心价值]": context.get("core_value", "更优质、更实惠、更放心"),
            "[优惠信息]": context.get("discount", "限时优惠中"),
            "[保障1]": context.get("guarantees", ["7天无理由退换", "终身质保", "24小时客服"])[0] if context.get("guarantees") else "7天无理由退换",
            "[保障2]": context.get("guarantees", ["7天无理由退换", "终身质保", "24小时客服"])[1] if context.get("guarantees") and len(context.get("guarantees", [])) > 1 else "终身质保",
            "[保障3]": context.get("guarantees", ["7天无理由退换", "终身质保", "24小时客服"])[2] if context.get("guarantees") and len(context.get("guarantees", [])) > 2 else "24小时客服",
            "[用户评价1]": context.get("user_reviews", ["非常好用，值得购买！"])[0] if context.get("user_reviews") else "非常好用，值得购买！",
            "[用户评价2]": context.get("user_reviews", ["服务超赞！"])[1] if context.get("user_reviews") and len(context.get("user_reviews", [])) > 1 else "服务超赞！",
            "[用户评价3]": context.get("user_reviews", ["已经回购好几次了"])[2] if context.get("user_reviews") and len(context.get("user_reviews", [])) > 2 else "已经回购好几次了",
            "[销量]": context.get("sales_count", "10万+"),
            "[好评率]": context.get("positive_rate", "98%"),
            "[复购率]": context.get("repurchase_rate", "85%"),
            "[价格区间]": context.get("price_range", "200-500元"),
            "[对比品]": context.get("competitor_product", "普通产品"),
            "[产品类型]": context.get("product_category", "这类产品"),
        }

        for placeholder, value in replacements.items():
            narration = narration.replace(placeholder, str(value))

        return {
            "scene_index": scene_template["scene_index"],
            "scene_name": scene_template["scene_name"],
            "time_range": scene_template["time_range"],
            "emotion": scene_template["emotion"],
            "content_type": scene_template["content_type"],
            "visual": scene_template["visual"],
            "narration": narration
        }


# =============================================================================
# 便捷函数
# =============================================================================

def get_institution_templates() -> List[Dict[str, Any]]:
    """获取所有机构产品类模板"""
    generator = InstitutionContentGenerator()
    return generator.list_templates()


def generate_institution_script(
    template_type: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    生成机构产品类脚本的便捷函数

    Args:
        template_type: 模板类型 (product_spec, service_guarantee, brand_story, price_compare, user_review)
        context: 上下文数据

    Returns:
        dict: 生成的脚本
    """
    type_map = {
        "product_spec": InstitutionProductType.PRODUCT_SPEC,
        "service_guarantee": InstitutionProductType.SERVICE_GUARANTEE,
        "brand_story": InstitutionProductType.BRAND_STORY,
        "price_compare": InstitutionProductType.PRICE_COMPARE,
        "user_review": InstitutionProductType.USER_REVIEW,
    }

    product_type = type_map.get(template_type, InstitutionProductType.PRODUCT_SPEC)
    generator = InstitutionContentGenerator()
    return generator.generate_script(product_type, context)
