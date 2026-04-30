"""
视觉风格配置模块

提供5种视觉风格配置，包括：
- warm_tone: 暖色调风格
- professional_tone: 专业商务风格
- fresh_tone: 小清新风格
- luxury_tone: 高端奢华风格
- casual_tone: 休闲生活风格

每种风格包含：
- colors: 色值列表
- light: 光线说明
- scene: 推荐场景
- font_pairing: 字体搭配
- icon_style: 图标风格
"""

from typing import Dict, List, Any

# =============================================================================
# 视觉风格配置
# =============================================================================

VISUAL_GUIDES: Dict[str, Dict[str, Any]] = {
    "warm_tone": {
        "name": "暖色调风格",
        "description": "温馨、亲切、生活感，适合消费品、生活服务类内容",
        "colors": {
            "primary": "#FF6B6B",       # 主色：珊瑚红
            "secondary": "#FFE66D",      # 辅色：暖黄
            "accent": "#FFA07A",           # 强调色：浅鲑鱼色
            "background": "#FFF5EE",      # 背景色：贝壳白
            "text": "#2D3748",           # 文字色：深灰
            "cold_pages": ["#4A5568", "#E8EEF2", "#CBD5E1"],
            "warm_pages": ["#FFF5EE", "#FFDAB9", "#F5F0EB"],
            "brand_pages": ["#FF6B6B", "#22C55E"],
        },
        "light": {
            "type": "自然暖光",
            "description": "柔和自然光，暖色调，营造温馨氛围",
            "temperature": "暖色温 (3000K-4500K)",
            "keywords": ["自然光", "柔光", "暖色调", "生活感"],
        },
        "scene": {
            "recommended": ["家庭场景", "厨房场景", "生活日常", "户外自然"],
            "avoid": ["医院", "实验室", "严肃场合"],
        },
        "font_pairing": {
            "title": "思源黑体 Bold / 站酷高端黑",
            "body": "思源宋体 / 苹方",
            "accent": "手写体 / 楷体",
        },
        "icon_style": {
            "style": "圆润线条",
            "color": "暖色系单色或双色",
            "keywords": ["圆润", "友好", "亲切", "生活化"],
        },
        "image_elements": {
            "人物风格": "自然表情、生活化动作、暖色调滤镜",
            "色调": "暖色调、高饱和度、温馨感",
            "构图": "留白适中、中心构图、生活场景",
        },
        "brand_visual_keywords": ["温馨", "品质", "生活", "温暖"],
    },

    "professional_tone": {
        "name": "专业商务风格",
        "description": "专业、权威、可信，适合B2B、企业服务、专业咨询类内容",
        "colors": {
            "primary": "#2C3E50",       # 主色：深蓝灰
            "secondary": "#3498DB",     # 辅色：专业蓝
            "accent": "#27AE60",         # 强调色：成功绿
            "background": "#ECF0F1",    # 背景色：浅灰白
            "text": "#1A202C",           # 文字色：深黑
            "cold_pages": ["#2C3E50", "#34495E", "#7F8C8D"],
            "warm_pages": ["#ECF0F1", "#BDC3C7", "#95A5A6"],
            "brand_pages": ["#2C3E50", "#3498DB", "#27AE60"],
        },
        "light": {
            "type": "专业影棚光",
            "description": "均匀柔和灯光，无明显阴影，专业感",
            "temperature": "中性色温 (4500K-5500K)",
            "keywords": ["均匀", "专业", "干净", "商务感"],
        },
        "scene": {
            "recommended": ["办公室场景", "会议室场景", "商务洽谈", "工作场景"],
            "avoid": ["卧室", "厨房", "娱乐场所"],
        },
        "font_pairing": {
            "title": "思源黑体 Bold / Helvetica Neue Bold",
            "body": "思源黑体 Regular / Arial",
            "accent": "数字字体 / DIN",
        },
        "icon_style": {
            "style": "扁平化线条",
            "color": "单色或双色，极简风格",
            "keywords": ["扁平", "极简", "专业", "商务"],
        },
        "image_elements": {
            "人物风格": "职业装、正装、专业表情、商务场景",
            "色调": "低饱和度、冷色调、专业感",
            "构图": "对齐网格、留白充足、层次分明",
        },
        "brand_visual_keywords": ["专业", "可靠", "权威", "高效"],
    },

    "fresh_tone": {
        "name": "小清新风格",
        "description": "清新、自然、文艺，适合美妆、母婴、文艺类内容",
        "colors": {
            "primary": "#48BB78",       # 主色：薄荷绿
            "secondary": "#38B2AC",     # 辅色：青色
            "accent": "#ED8936",        # 强调色：橙色
            "background": "#F7FAFC",   # 背景色：极浅灰白
            "text": "#2D3748",          # 文字色：深灰
            "cold_pages": ["#48BB78", "#38B2AC", "#81E6D9"],
            "warm_pages": ["#F7FAFC", "#EDF2F7", "#E2E8F0"],
            "brand_pages": ["#48BB78", "#ED8936", "#38B2AC"],
        },
        "light": {
            "type": "自然柔光",
            "description": "明亮的自然光，柔和不刺眼，清新感",
            "temperature": "冷白色 (5500K-6500K)",
            "keywords": ["明亮", "清新", "自然", "通透"],
        },
        "scene": {
            "recommended": ["户外自然", "咖啡馆", "文艺空间", "绿植场景"],
            "avoid": ["工厂", "车间", "嘈杂环境"],
        },
        "font_pairing": {
            "title": "站酷文艺体 / 思源宋体",
            "body": "苹方 / 思源黑体 Light",
            "accent": "手写体 / 文艺字体",
        },
        "icon_style": {
            "style": "手绘线条",
            "color": "莫兰迪色系、低饱和度",
            "keywords": ["手绘", "文艺", "清新", "自然"],
        },
        "image_elements": {
            "人物风格": "淡妆、自然表情、文艺穿搭、清新场景",
            "色调": "低饱和度、莫兰迪色系、通透感",
            "构图": "大量留白、中心或三分法、文艺感",
        },
        "brand_visual_keywords": ["清新", "自然", "文艺", "健康"],
    },

    "luxury_tone": {
        "name": "高端奢华风格",
        "description": "高端、有品质感，适合高端消费品、奢侈品、精品服务",
        "colors": {
            "primary": "#1A1A2E",       # 主色：深藏青
            "secondary": "#C9A227",     # 辅色：金色
            "accent": "#E94560",         # 强调色：宝石红
            "background": "#0F0F1A",    # 背景色：深黑
            "text": "#F7F7F7",           # 文字色：亮白
            "cold_pages": ["#1A1A2E", "#16213E", "#0F3460"],
            "warm_pages": ["#2D2D44", "#3D3D5C", "#C9A227"],
            "brand_pages": ["#C9A227", "#E94560", "#1A1A2E"],
        },
        "light": {
            "type": "戏剧性光源",
            "description": "明暗对比强烈，戏剧性光影，高端感",
            "temperature": "混合色温 (3000K-6000K)",
            "keywords": ["戏剧性", "对比", "质感", "高端"],
        },
        "scene": {
            "recommended": ["高端场景", "精致空间", "产品特写", "光影场景"],
            "avoid": ["普通家居", "街头场景", "嘈杂环境"],
        },
        "font_pairing": {
            "title": "Times New Roman Bold / Didot Bold",
            "body": "Helvetica Neue / Arial",
            "accent": "衬线字体 / 艺术字体",
        },
        "icon_style": {
            "style": "精致细线",
            "color": "金色/银色单色或双色",
            "keywords": ["精致", "高端", "奢华", "质感"],
        },
        "image_elements": {
            "人物风格": "精致妆容、高端穿搭、优雅姿态",
            "色调": "深色调、金色点缀、高对比度",
            "构图": "中心对称、大量留白、电影感",
        },
        "brand_visual_keywords": ["高端", "品质", "精致", "奢华"],
    },

    "casual_tone": {
        "name": "休闲生活风格",
        "description": "轻松、随性、接地气，适合本地生活、快消品、大众服务",
        "colors": {
            "primary": "#ED8936",       # 主色：活力橙
            "secondary": "#38A169",    # 辅色：活力绿
            "accent": "#3182CE",        # 强调色：活力蓝
            "background": "#FFFBEB",   # 背景色：米白
            "text": "#1A202C",          # 文字色：深黑
            "cold_pages": ["#3182CE", "#63B3ED", "#90CDF4"],
            "warm_pages": ["#ED8936", "#F6AD55", "#FBD38D"],
            "brand_pages": ["#ED8936", "#38A169", "#3182CE"],
        },
        "light": {
            "type": "日常自然光",
            "description": "明亮的日常光线，自然真实，接地气",
            "temperature": "自然日光 (5000K-6000K)",
            "keywords": ["明亮", "真实", "日常", "活力"],
        },
        "scene": {
            "recommended": ["日常生活", "街头场景", "工作现场", "户外运动"],
            "avoid": ["高档场所", "正式场合", "过度精致场景"],
        },
        "font_pairing": {
            "title": "思源黑体 Bold / 站酷快乐体",
            "body": "苹方 / 思源黑体 Regular",
            "accent": "圆润字体 / 手写体",
        },
        "icon_style": {
            "style": "圆润卡通",
            "color": "明亮活泼色系",
            "keywords": ["圆润", "卡通", "活泼", "接地气"],
        },
        "image_elements": {
            "人物风格": "自然表情、日常穿搭、动态动作",
            "色调": "高饱和度、暖色调、活力感",
            "构图": "紧凑自然、动态构图、生活感",
        },
        "brand_visual_keywords": ["活力", "实惠", "亲民", "实用"],
    },
}

# =============================================================================
# 行业视觉风格推荐
# =============================================================================

INDUSTRY_VISUAL_MAP: Dict[str, str] = {
    # 消费品
    "母婴": "warm_tone",
    "美妆护肤": "fresh_tone",
    "食品饮料": "warm_tone",
    "服装鞋帽": "casual_tone",
    "家居用品": "warm_tone",

    # 专业服务
    "教育培训": "professional_tone",
    "企业服务": "professional_tone",
    "法律咨询": "professional_tone",
    "财务咨询": "professional_tone",
    "医疗健康": "professional_tone",

    # 本地生活
    "餐饮服务": "warm_tone",
    "家政服务": "casual_tone",
    "美容美发": "fresh_tone",
    "摄影服务": "luxury_tone",
    "装修服务": "casual_tone",

    # 高端消费
    "奢侈品": "luxury_tone",
    "珠宝首饰": "luxury_tone",
    "高端定制": "luxury_tone",

    # 默认
    "default": "casual_tone",
}

# =============================================================================
# 画面构图模式
# =============================================================================

LAYOUT_PATTERNS: Dict[str, Dict[str, Any]] = {
    "center_composition": {
        "name": "中心构图",
        "description": "主体位于画面中心，简洁大气",
        "suitable_for": ["产品特写", "人物特写", "LOGO展示"],
        "tips": ["主体占比60-80%", "背景简洁", "光线均匀"],
    },
    "rule_of_thirds": {
        "name": "三分法构图",
        "description": "主体位于三分线交点，打破呆板",
        "suitable_for": ["场景展示", "故事叙述", "信息展示"],
        "tips": ["主体位于1/3或2/3处", "留白创造呼吸感", "视线引导"],
    },
    "symmetry": {
        "name": "对称构图",
        "description": "左右/上下对称，庄重大气",
        "suitable_for": ["建筑展示", "产品陈列", "品牌展示"],
        "tips": ["严格对称", "中轴线明确", "背景干净"],
    },
    "diagonal": {
        "name": "对角线构图",
        "description": "沿对角线分布，动感有力",
        "suitable_for": ["动态场景", "流程展示", "对比展示"],
        "tips": ["对角线引导视线", "前后层次分明", "动感增强"],
    },
    "frame_in_frame": {
        "name": "框中框构图",
        "description": "利用门窗等元素形成框架",
        "suitable_for": ["人物故事", "场景带入", "氛围营造"],
        "tips": ["框架作为引导", "突出主体", "增加层次"],
    },
}

# =============================================================================
# 辅助函数
# =============================================================================

def get_visual_guide(style_name: str) -> Dict[str, Any]:
    """
    获取指定名称的视觉风格配置

    Args:
        style_name: 风格名称

    Returns:
        视觉风格配置字典
    """
    return VISUAL_GUIDES.get(style_name, VISUAL_GUIDES["casual_tone"])


def get_recommended_style(industry: str = None, business_type: str = None) -> str:
    """
    根据行业和业务类型推荐视觉风格

    Args:
        industry: 行业名称
        business_type: 业务类型 (b2b/b2c/both)

    Returns:
        推荐的视觉风格名称
    """
    # B2B 类型优先专业风格
    if business_type == "b2b":
        return "professional_tone"

    # 根据行业推荐
    if industry:
        # 精确匹配
        if industry in INDUSTRY_VISUAL_MAP:
            return INDUSTRY_VISUAL_MAP[industry]

        # 模糊匹配
        for ind, style in INDUSTRY_VISUAL_MAP.items():
            if ind != "default" and ind in industry:
                return style

    # 默认
    return INDUSTRY_VISUAL_MAP["default"]


def get_color_scheme(style_name: str, page_type: str = "normal") -> Dict[str, str]:
    """
    获取指定风格的配色方案

    Args:
        style_name: 风格名称
        page_type: 页面类型 (normal/cold/warm/brand)

    Returns:
        配色方案字典
    """
    guide = get_visual_guide(style_name)
    colors = guide.get("colors", {})

    if page_type == "cold":
        return {"primary": colors.get("cold_pages", ["#4A5568"])[0]}
    elif page_type == "warm":
        return {"primary": colors.get("warm_pages", ["#FFF5EE"])[0]}
    elif page_type == "brand":
        return {"primary": colors.get("brand_pages", ["#FF6B6B"])[0]}
    else:
        return {
            "primary": colors.get("primary", "#4A5568"),
            "secondary": colors.get("secondary", "#718096"),
            "accent": colors.get("accent", "#A0AEC0"),
            "background": colors.get("background", "#F7FAFC"),
            "text": colors.get("text", "#1A202C"),
        }


def get_layout_pattern(pattern_name: str = None) -> Dict[str, Any]:
    """
    获取指定构图模式

    Args:
        pattern_name: 构图模式名称

    Returns:
        构图模式配置
    """
    if pattern_name and pattern_name in LAYOUT_PATTERNS:
        return LAYOUT_PATTERNS[pattern_name]
    return LAYOUT_PATTERNS["center_composition"]


def generate_visual_spec(
    style_name: str,
    industry: str = None,
    page_type: str = "normal",
) -> Dict[str, Any]:
    """
    生成完整的视觉规范

    Args:
        style_name: 风格名称
        industry: 行业名称
        page_type: 页面类型

    Returns:
        完整的视觉规范字典
    """
    guide = get_visual_guide(style_name)
    colors = get_color_scheme(style_name, page_type)

    return {
        "style_name": style_name,
        "style_description": guide.get("description", ""),
        "colors": colors,
        "light": guide.get("light", {}),
        "recommended_scenes": guide.get("scene", {}).get("recommended", []),
        "avoid_scenes": guide.get("scene", {}).get("avoid", []),
        "font_pairing": guide.get("font_pairing", {}),
        "icon_style": guide.get("icon_style", {}),
        "image_elements": guide.get("image_elements", {}),
        "brand_keywords": guide.get("brand_visual_keywords", []),
        "industry_recommendation": industry,
    }
