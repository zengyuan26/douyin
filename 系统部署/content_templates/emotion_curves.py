"""
情绪曲线配置模块

提供7种内容类型的情绪动线配置，包括：
- 种草型
- 干货型
- 测评型
- 对比型
- 故事型
- 悬念型
- 温情型

每种类型包含：
- stages: 情绪阶段列表
- ratios: 各阶段字数比例
- keywords: 情绪触发关键词
- visual_hints: 画面提示
"""

from typing import Dict, List, Any

# =============================================================================
# 情绪曲线配置
# =============================================================================

EMOTION_CURVES: Dict[str, Dict[str, Any]] = {
    "种草型": {
        "name": "种草型",
        "description": "通过痛点共鸣和解决方案展示，引导用户产生购买欲望",
        "stages": [
            {"name": "引发好奇", "emotion": "好奇", "duration_ratio": 0.15},
            {"name": "共情痛点", "emotion": "心酸/代入", "duration_ratio": 0.25},
            {"name": "展示方案", "emotion": "坚定", "duration_ratio": 0.30},
            {"name": "建立信任", "emotion": "信任", "duration_ratio": 0.15},
            {"name": "行动号召", "emotion": "温暖/行动", "duration_ratio": 0.15},
        ],
        "keywords": ["竟然", "原来", "终于", "没想到", "原来如此", "太值了", "后悔没早知道"],
        "visual_hints": [
            "封面：大场景+身份标签",
            "痛点：真实扎心场景还原",
            "方案：分步演示+对比呈现",
            "信任：品牌/案例展示",
            "转化：CTA按钮+联系方式",
        ],
        "color_progression": ["#4A5568", "#718096", "#A0AEC0", "#CBD5E0"],
        "cta_keywords": ["私信", "咨询", "联系", "购买", "下单"],
    },

    "干货型": {
        "name": "干货型",
        "description": "以实用性为核心，通过系统化知识输出建立专业形象",
        "stages": [
            {"name": "抛出问题", "emotion": "好奇", "duration_ratio": 0.10},
            {"name": "分析原因", "emotion": "专注", "duration_ratio": 0.20},
            {"name": "解决方案", "emotion": "收获", "duration_ratio": 0.35},
            {"name": "案例验证", "emotion": "信服", "duration_ratio": 0.20},
            {"name": "总结要点", "emotion": "满足", "duration_ratio": 0.15},
        ],
        "keywords": ["首先", "其次", "最后", "关键", "重点", "核心", "要点", "揭秘"],
        "visual_hints": [
            "封面：数据/成果展示",
            "分析：逻辑框架/思维导图",
            "方案：分步图解/清单",
            "案例：前后对比/数据展示",
            "总结：核心要点归纳",
        ],
        "color_progression": ["#2D3748", "#4A5568", "#718096", "#A0AEC0"],
        "cta_keywords": ["收藏", "分享", "关注", "学习", "实践"],
    },

    "测评型": {
        "name": "测评型",
        "description": "通过真实测试和对比，建立客观公正形象",
        "stages": [
            {"name": "测试前提问", "emotion": "好奇", "duration_ratio": 0.12},
            {"name": "测试过程", "emotion": "专注", "duration_ratio": 0.30},
            {"name": "结果揭晓", "emotion": "惊讶", "duration_ratio": 0.25},
            {"name": "分析解读", "emotion": "理性", "duration_ratio": 0.20},
            {"name": "推荐建议", "emotion": "信任", "duration_ratio": 0.13},
        ],
        "keywords": ["测评", "对比", "测试", "结果", "揭晓", "真相", "实测", "数据"],
        "visual_hints": [
            "封面：对比图/问号",
            "测试：过程记录/参数展示",
            "结果：大数字/排名展示",
            "分析：表格/图表",
            "建议：推荐卡片/总结",
        ],
        "color_progression": ["#E53E3E", "#DD6B20", "#D69E2E", "#38A169"],
        "cta_keywords": ["点赞", "投币", "评论", "转发", "关注"],
    },

    "对比型": {
        "name": "对比型",
        "description": "通过对比凸显差异化，建立选择优势",
        "stages": [
            {"name": "引入对比话题", "emotion": "好奇", "duration_ratio": 0.10},
            {"name": "选项A展示", "emotion": "了解", "duration_ratio": 0.20},
            {"name": "选项B展示", "emotion": "了解", "duration_ratio": 0.20},
            {"name": "核心差异对比", "emotion": "理性", "duration_ratio": 0.30},
            {"name": "推荐选择", "emotion": "决策", "duration_ratio": 0.20},
        ],
        "keywords": ["对比", "区别", "差异", "哪个好", "怎么选", "优缺点", "区别在哪"],
        "visual_hints": [
            "封面：VS符号/对比图",
            "A选项：左侧/冷色调",
            "B选项：右侧/暖色调",
            "对比：表格/雷达图",
            "推荐：徽章/标签",
        ],
        "color_progression": ["#3182CE", "#805AD5", "#38A169", "#D69E2E"],
        "cta_keywords": ["收藏", "对比", "选择", "私信", "咨询"],
    },

    "故事型": {
        "name": "故事型",
        "description": "通过真实故事引发情感共鸣，建立深度连接",
        "stages": [
            {"name": "故事开场", "emotion": "好奇", "duration_ratio": 0.12},
            {"name": "冲突展开", "emotion": "紧张", "duration_ratio": 0.25},
            {"name": "高潮转折", "emotion": "惊讶", "duration_ratio": 0.25},
            {"name": "解决升华", "emotion": "感动", "duration_ratio": 0.25},
            {"name": "感悟收尾", "emotion": "温暖", "duration_ratio": 0.13},
        ],
        "keywords": ["真实故事", "亲身经历", "原来", "没想到", "后来", "结果", "感悟"],
        "visual_hints": [
            "开场：场景还原/人像特写",
            "冲突：情绪特写/对比",
            "转折：惊喜元素/数据",
            "解决：方案展示/成果",
            "感悟：温暖画面/总结",
        ],
        "color_progression": ["#E53E3E", "#DD6B20", "#D69E2E", "#38A169"],
        "cta_keywords": ["感动", "加油", "支持", "转发", "关注"],
    },

    "悬念型": {
        "name": "悬念型",
        "description": "通过设置悬念和反转，吸引用户持续关注",
        "stages": [
            {"name": "抛出悬念", "emotion": "好奇", "duration_ratio": 0.15},
            {"name": "铺垫背景", "emotion": "专注", "duration_ratio": 0.20},
            {"name": "层层递进", "emotion": "紧张", "duration_ratio": 0.25},
            {"name": "揭晓答案", "emotion": "惊讶", "duration_ratio": 0.25},
            {"name": "总结升华", "emotion": "释然", "duration_ratio": 0.15},
        ],
        "keywords": ["没想到", "竟然", "真相是", "揭秘", "99%人不知道", "看完才懂", "反转"],
        "visual_hints": [
            "封面：问号/悬念图",
            "铺垫：神秘感/暗示",
            "递进：数字/倒计时",
            "揭晓：答案展示/恍然大悟",
            "总结：恍然大悟感",
        ],
        "color_progression": ["#2D3748", "#4A5568", "#718096", "#805AD5"],
        "cta_keywords": ["点赞", "关注", "收藏", "下期见", "转发"],
    },

    "温情型": {
        "name": "温情型",
        "description": "通过情感表达建立温暖形象，触达用户内心",
        "stages": [
            {"name": "情感引入", "emotion": "温暖", "duration_ratio": 0.15},
            {"name": "情感共鸣", "emotion": "感动", "duration_ratio": 0.30},
            {"name": "情感升华", "emotion": "温暖", "duration_ratio": 0.30},
            {"name": "行动引导", "emotion": "期待", "duration_ratio": 0.15},
            {"name": "温暖收尾", "emotion": "满足", "duration_ratio": 0.10},
        ],
        "keywords": ["爱", "感动", "温暖", "幸福", "感谢", "加油", "陪伴", "珍惜"],
        "visual_hints": [
            "引入：暖色调/温情场景",
            "共鸣：真实故事/情感特写",
            "升华：美好画面/希望",
            "引导：鼓励话语/支持",
            "收尾：品牌温暖感",
        ],
        "color_progression": ["#ED8936", "#F6AD55", "#FBD38D", "#FEEBC8"],
        "cta_keywords": ["支持", "加油", "点赞", "转发", "陪伴"],
    },
}

# =============================================================================
# 五段式阶段映射
# =============================================================================

STAGE_EMOTION_MAP: Dict[str, Dict[str, Any]] = {
    "audience": {
        "name": "受众锁定",
        "emotions": ["好奇", "认同", "期待"],
        "visual_keywords": ["身份标签", "人群特写", "场景代入"],
        "color_scheme": "cold",
    },
    "pain": {
        "name": "痛点放大",
        "emotions": ["焦虑", "恍然大悟", "后怕"],
        "visual_keywords": ["真实场景", "问题展示", "对比冲击"],
        "color_scheme": "cold",
    },
    "compare": {
        "name": "方案对比",
        "emotions": ["纠结", "理性", "释然"],
        "visual_keywords": ["对比表格", "优缺点", "选择展示"],
        "color_scheme": "neutral",
    },
    "vision": {
        "name": "愿景勾画",
        "emotions": ["期待", "信心", "满足"],
        "visual_keywords": ["美好画面", "效果展示", "希望感"],
        "color_scheme": "warm",
    },
    "hesitation": {
        "name": "顾虑消除",
        "emotions": ["焦虑", "放心", "坚定"],
        "visual_keywords": ["信任证明", "案例展示", "保障说明"],
        "color_scheme": "warm",
    },
}

# =============================================================================
# 决策阶段映射
# =============================================================================

DECISION_STAGE_MAP: Dict[str, Dict[str, Any]] = {
    "awareness": {
        "name": "认知阶段",
        "description": "用户发现问题但还没确定方向",
        "focus": "痛点共鸣 + 解决方案介绍",
        "recommended_curve": "悬念型",
        "content_ratio": {"pain": 0.4, "compare": 0.3, "vision": 0.3},
    },
    "consideration": {
        "name": "考量阶段",
        "description": "用户有方向后在比较方案",
        "focus": "方案对比 + 信任建立",
        "recommended_curve": "对比型",
        "content_ratio": {"compare": 0.4, "pain": 0.2, "vision": 0.2, "hesitation": 0.2},
    },
    "decision": {
        "name": "决策阶段",
        "description": "用户在做最终选择",
        "focus": "顾虑消除 + 行动号召",
        "recommended_curve": "种草型",
        "content_ratio": {"hesitation": 0.4, "vision": 0.3, "compare": 0.3},
    },
}

# =============================================================================
# 辅助函数
# =============================================================================

def get_emotion_curve(curve_name: str) -> Dict[str, Any]:
    """
    获取指定名称的情绪曲线配置

    Args:
        curve_name: 曲线名称

    Returns:
        情绪曲线配置字典
    """
    return EMOTION_CURVES.get(curve_name, EMOTION_CURVES["种草型"])


def get_curve_by_portrait(pain_point_level: str = "medium", decision_stage: str = "consideration") -> str:
    """
    根据画像特征推荐情绪曲线

    Args:
        pain_point_level: 痛点强度 (high/medium/low)
        decision_stage: 决策阶段 (awareness/consideration/decision)

    Returns:
        推荐的情绪曲线名称
    """
    # 强痛点 + 认知阶段 = 悬念型
    if pain_point_level == "high" and decision_stage == "awareness":
        return "悬念型"

    # 强痛点 + 决策阶段 = 种草型
    if pain_point_level == "high" and decision_stage == "decision":
        return "种草型"

    # 中等痛点 + 考量阶段 = 对比型
    if pain_point_level == "medium" and decision_stage == "consideration":
        return "对比型"

    # 低痛点 + 考量阶段 = 干货型
    if pain_point_level == "low" and decision_stage == "consideration":
        return "干货型"

    # 默认种草型
    return "种草型"


def get_stage_emotion(stage_key: str) -> Dict[str, Any]:
    """
    获取指定五段式阶段的情绪配置

    Args:
        stage_key: 阶段键 (audience/pain/compare/vision/hesitation)

    Returns:
        阶段情绪配置
    """
    return STAGE_EMOTION_MAP.get(stage_key, STAGE_EMOTION_MAP["audience"])


def get_decision_stage_config(stage: str) -> Dict[str, Any]:
    """
    获取决策阶段配置

    Args:
        stage: 阶段名称 (awareness/consideration/decision)

    Returns:
        阶段配置
    """
    return DECISION_STAGE_MAP.get(stage, DECISION_STAGE_MAP["consideration"])


def build_emotion_plan(
    curve_name: str,
    total_frames: int = 7,
    custom_stages: List[Dict] = None,
) -> List[Dict[str, Any]]:
    """
    构建情绪规划方案

    Args:
        curve_name: 情绪曲线名称
        total_frames: 总帧数
        custom_stages: 自定义阶段（可选）

    Returns:
        每帧的情绪规划列表
    """
    curve = get_emotion_curve(curve_name)
    stages = custom_stages or curve.get("stages", [])

    # 按比例分配帧数
    frame_plan = []
    for i, stage in enumerate(stages):
        stage_frames = max(1, round(stage.get("duration_ratio", 1/len(stages)) * total_frames))
        for j in range(stage_frames):
            frame_plan.append({
                "frame_index": len(frame_plan) + 1,
                "stage_name": stage.get("name", ""),
                "emotion": stage.get("emotion", ""),
                "color_tone": _get_frame_color(curve.get("color_progression", []), len(frame_plan), total_frames),
            })

    # 确保总帧数正确
    while len(frame_plan) < total_frames:
        frame_plan.append({
            "frame_index": len(frame_plan) + 1,
            "stage_name": frame_plan[-1]["stage_name"],
            "emotion": frame_plan[-1]["emotion"],
            "color_tone": frame_plan[-1]["color_tone"],
        })

    return frame_plan[:total_frames]


def _get_frame_color(color_progression: List[str], index: int, total: int) -> str:
    """根据帧位置获取颜色"""
    if not color_progression:
        return "#4A5568"
    if len(color_progression) == 1:
        return color_progression[0]

    step = (len(color_progression) - 1) / max(1, total - 1)
    idx = int(index * step)
    return color_progression[min(idx, len(color_progression) - 1)]
