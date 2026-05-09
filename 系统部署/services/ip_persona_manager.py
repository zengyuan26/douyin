"""
IP人设管理系统

职责划分：
- 系统做：人设配置管理、出镜方式决策、配置存储
- LLM做：人设描述优化、语言风格适配

IP人设类型：
- 陪伴者、教导者、崇拜者、陪衬者、搞笑者
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib


class IPPersonaType(Enum):
    """IP人设类型"""
    COMPANION = "陪伴者"      # 温暖、共情
    MENTOR = "教导者"        # 专业、权威
    ADVOCATE = "崇拜者"      # 热情、种草
    WITNESS = "陪衬者"       # 真实、共鸣
    HUMORIST = "搞笑者"      # 轻松、娱乐


class IPSpeakingMode(Enum):
    """出镜方式"""
    NO_APPEARANCE = "不出镜"    # 完全不出镜，旁白
    DIGITAL_HUMAN = "数字人出镜"  # 数字人


class DigitalHumanStyle(Enum):
    """数字人形象风格"""
    NEIGHBOR_SISTER = "邻家姐姐"
    KNOWLEDGEABLE_MOM = "知性妈妈"
    PROFESSIONAL_CONSULTANT = "专业顾问"
    SUNNY_BOY = "阳光男孩"
    YOUNG_TALENT = "年轻才俊"
    CUSTOM = "自定义"


@dataclass
class IPConfig:
    """IP配置"""
    id: str
    name: str
    persona_type: IPPersonaType
    speaking_mode: IPSpeakingMode
    digital_style: Optional[DigitalHumanStyle] = None
    custom_style: Optional[str] = None  # 自定义风格描述
    appearance_desc: str = ""          # 外貌描述
    voice_desc: str = ""               # 声音描述
    gesture_desc: str = ""             # 肢体语言描述
    speech_style: str = ""            # 说话风格
    personality_tags: List[str] = field(default_factory=list)
    backstory: str = ""               # 背景故事
    values: List[str] = field(default_factory=list)  # 价值观标签

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "persona_type": self.persona_type.value,
            "speaking_mode": self.speaking_mode.value,
            "digital_style": self.digital_style.value if self.digital_style else None,
            "custom_style": self.custom_style,
            "appearance_desc": self.appearance_desc,
            "voice_desc": self.voice_desc,
            "gesture_desc": self.gesture_desc,
            "speech_style": self.speech_style,
            "personality_tags": self.personality_tags,
            "backstory": self.backstory,
            "values": self.values
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPConfig":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            persona_type=IPPersonaType(data.get("persona_type", "陪伴者")),
            speaking_mode=IPSpeakingMode(data.get("speaking_mode", "数字人出镜")),
            digital_style=DigitalHumanStyle(data.get("digital_style")) if data.get("digital_style") else None,
            custom_style=data.get("custom_style"),
            appearance_desc=data.get("appearance_desc", ""),
            voice_desc=data.get("voice_desc", ""),
            gesture_desc=data.get("gesture_desc", ""),
            speech_style=data.get("speech_style", ""),
            personality_tags=data.get("personality_tags", []),
            backstory=data.get("backstory", ""),
            values=data.get("values", [])
        )


class IPConfigManager:
    """IP配置管理器"""

    def __init__(self):
        self._configs: Dict[str, IPConfig] = {}
        self._init_default_presets()

    def _init_default_presets(self):
        """初始化默认预设"""
        presets = [
            self._create_companion_preset(),
            self._create_mentor_preset(),
            self._create_advocate_preset(),
        ]

        for preset in presets:
            self._configs[preset.id] = preset

    def _create_companion_preset(self) -> IPConfig:
        """创建陪伴者预设"""
        return IPConfig(
            id="preset_companion",
            name="陪伴者",
            persona_type=IPPersonaType.COMPANION,
            speaking_mode=IPSpeakingMode.DIGITAL_HUMAN,
            digital_style=DigitalHumanStyle.NEIGHBOR_SISTER,
            appearance_desc="25-30岁邻家姐姐形象，温暖亲切，眼神柔和",
            voice_desc="温柔、语速适中、有亲和力，略带笑意",
            gesture_desc="适度手势、点头、微笑，肢体语言自然放松",
            speech_style="温暖共情，像朋友聊天，常用'咱们'、'一起'",
            personality_tags=["温暖", "共情", "陪伴", "理解"],
            backstory="经历过类似困惑，通过学习找到了解决方法",
            values=["陪伴成长", "共情理解", "真诚分享"]
        )

    def _create_mentor_preset(self) -> IPConfig:
        """创建教导者预设"""
        return IPConfig(
            id="preset_mentor",
            name="教导者",
            persona_type=IPPersonaType.MENTOR,
            speaking_mode=IPSpeakingMode.DIGITAL_HUMAN,
            digital_style=DigitalHumanStyle.PROFESSIONAL_CONSULTANT,
            appearance_desc="30-40岁专业人士形象，知性干练，眼神坚定",
            voice_desc="清晰、专业、沉稳，语速适中",
            gesture_desc="手势精准、动作稳健、表达清晰",
            speech_style="专业权威，像老师讲解，常用'记住'、'关键'",
            personality_tags=["专业", "权威", "可靠", "信赖"],
            backstory="深耕行业多年，积累了大量实战经验",
            values=["专业分享", "授人以渔", "匠心精神"]
        )

    def _create_advocate_preset(self) -> IPConfig:
        """创建崇拜者预设（种草型）"""
        return IPConfig(
            id="preset_advocate",
            name="崇拜者",
            persona_type=IPPersonaType.ADVOCATE,
            speaking_mode=IPSpeakingMode.DIGITAL_HUMAN,
            digital_style=DigitalHumanStyle.SUNNY_BOY,
            appearance_desc="20-25岁阳光形象，充满活力，表情丰富",
            voice_desc="热情、活泼、语速较快，情绪饱满",
            gesture_desc="动作夸张、表情丰富、充满感染力",
            speech_style="热情种草，像朋友安利，常用'太棒了'、'强推'",
            personality_tags=["热情", "种草", "活力", "阳光"],
            backstory="热爱发现好东西，热衷分享优质产品",
            values=["真诚种草", "分享好物", "快乐分享"]
        )

    def add_config(self, config: IPConfig) -> str:
        """添加配置"""
        if not config.id:
            config.id = hashlib.md5(config.name.encode()).hexdigest()[:8]

        self._configs[config.id] = config
        return config.id

    def get_config(self, config_id: str) -> Optional[IPConfig]:
        """获取配置"""
        return self._configs.get(config_id)

    def list_configs(self) -> List[IPConfig]:
        """列出所有配置"""
        return list(self._configs.values())

    def list_presets(self) -> List[IPConfig]:
        """列出预设配置"""
        return [c for c in self._configs.values() if c.id.startswith("preset_")]

    def delete_config(self, config_id: str) -> bool:
        """删除配置"""
        if config_id.startswith("preset_"):
            return False  # 不能删除预设
        if config_id in self._configs:
            del self._configs[config_id]
            return True
        return False

    def update_config(self, config_id: str, updates: Dict[str, Any]) -> Optional[IPConfig]:
        """更新配置"""
        config = self._configs.get(config_id)
        if not config:
            return None

        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config


class IPSpeakingModeDecider:
    """
    出镜方式决策器

    系统根据选题类型和信任来源决定出镜方式
    """

    # 决策规则
    RULES = {
        # 选题类型 -> 推荐出镜方式
        "问题诊断类": IPSpeakingMode.DIGITAL_HUMAN,
        "解决方案类": IPSpeakingMode.DIGITAL_HUMAN,
        "案例分享类": IPSpeakingMode.DIGITAL_HUMAN,
        "产品推荐类": IPSpeakingMode.DIGITAL_HUMAN,
        "知识科普类": IPSpeakingMode.DIGITAL_HUMAN,
        "热点关联类": IPSpeakingMode.DIGITAL_HUMAN,
        "人设故事类": IPSpeakingMode.DIGITAL_HUMAN,
        "人设价值观类": IPSpeakingMode.DIGITAL_HUMAN,
        "观点输出类": IPSpeakingMode.DIGITAL_HUMAN,
        "机构产品类": IPSpeakingMode.NO_APPEARANCE,  # 机构型不需要出镜
    }

    def decide(
        self,
        topic_type: str,
        trust_source: str,
        user_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        决定出镜方式

        Args:
            topic_type: 选题类型
            trust_source: 信任来源
            user_preference: 用户偏好（可选）

        Returns:
            Dict: 决策结果
        """
        # 用户偏好优先
        if user_preference == "不出镜":
            return {
                "mode": IPSpeakingMode.NO_APPEARANCE.value,
                "reason": "用户偏好不出镜",
                "style": None
            }
        elif user_preference == "数字人出镜":
            return {
                "mode": IPSpeakingMode.DIGITAL_HUMAN.value,
                "reason": "用户偏好数字人出镜",
                "style": DigitalHumanStyle.NEIGHBOR_SISTER.value
            }

        # 机构型信任不需要出镜
        if trust_source == "机构型":
            return {
                "mode": IPSpeakingMode.NO_APPEARANCE.value,
                "reason": "机构型信任不需要出镜，以品牌/产品为主",
                "style": None
            }

        # 根据选题类型决定
        recommended_mode = self.RULES.get(topic_type, IPSpeakingMode.DIGITAL_HUMAN)

        # 人设型信任建议出镜
        if trust_source == "人设型" and recommended_mode == IPSpeakingMode.NO_APPEARANCE:
            recommended_mode = IPSpeakingMode.DIGITAL_HUMAN

        return {
            "mode": recommended_mode.value,
            "reason": self._get_reason(topic_type, recommended_mode),
            "style": self._recommend_style(trust_source)
        }

    def _get_reason(self, topic_type: str, mode: IPSpeakingMode) -> str:
        """获取决策理由"""
        reasons = {
            IPSpeakingMode.DIGITAL_HUMAN: f"{topic_type}建议真人出镜，增强信任感",
            IPSpeakingMode.NO_APPEARANCE: "机构型内容以产品/品牌展示为主"
        }
        return reasons.get(mode, "")

    def _recommend_style(self, trust_source: str) -> Optional[str]:
        """推荐数字人风格"""
        style_map = {
            "知识型": DigitalHumanStyle.PROFESSIONAL_CONSULTANT.value,
            "人设型": DigitalHumanStyle.NEIGHBOR_SISTER.value,
            "产品型": DigitalHumanStyle.SUNNY_BOY.value
        }
        return style_map.get(trust_source)


class IPPromptBuilder:
    """
    IP提示词构建器

    为LLM构建人设相关提示词
    """

    def build_ip_description(self, config: IPConfig) -> str:
        """
        构建人设描述（给LLM用）

        系统提取配置，LLM优化表达
        """
        desc = f"""
你是{config.name}，一个{config.persona_type.value}型的短视频博主。

【人设特征】
- 外貌: {config.appearance_desc}
- 声音: {config.voice_desc}
- 肢体: {config.gesture_desc}
- 说话风格: {config.speech_style}

【性格标签】
{', '.join(config.personality_tags)}

【背景故事】
{config.backstory}

【价值观】
{', '.join(config.values)}
"""
        return desc

    def build_script_prompt(
        self,
        config: IPConfig,
        topic: str,
        speaking_mode: IPSpeakingMode
    ) -> str:
        """
        构建脚本提示词

        根据出镜方式调整提示词
        """
        base_prompt = self.build_ip_description(config)

        if speaking_mode == IPSpeakingMode.NO_APPEARANCE:
            base_prompt += """

【出镜方式】
你不出现在画面中，使用旁白形式表达。

【脚本格式】
旁白: [口播内容]
画面: [画面描述]
字幕: [字幕内容]
"""
        else:
            base_prompt += f"""

【出镜方式】
你以{DigitalHumanStyle(config.digital_style.value).value if config.digital_style else '数字人'}形象出镜，直接与观众对话。

【脚本格式】
主播: [口播内容]（看向镜头说）
画面: [画面描述]
动作: [肢体动作描述]
表情: [表情变化]
"""

        base_prompt += f"""

【当前选题】
{topic}

请以你的人设风格生成脚本内容。
"""
        return base_prompt

    def build_voice_prompt(self, config: IPConfig) -> str:
        """构建声音提示词（给语音合成用）"""
        return f"{config.voice_desc}，{config.speech_style}"


# =============================================================================
# 便捷函数
# =============================================================================

def get_ip_presets() -> List[Dict[str, Any]]:
    """获取IP预设"""
    manager = IPConfigManager()
    return [p.to_dict() for p in manager.list_presets()]


def create_ip_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """创建IP配置"""
    manager = IPConfigManager()
    config = IPConfig.from_dict(config_data)
    manager.add_config(config)
    return config.to_dict()


def decide_speaking_mode(
    topic_type: str,
    trust_source: str,
    user_preference: Optional[str] = None
) -> Dict[str, Any]:
    """决定出镜方式"""
    decider = IPSpeakingModeDecider()
    return decider.decide(topic_type, trust_source, user_preference)


def build_ip_prompt(
    ip_config: Dict[str, Any],
    topic: str,
    speaking_mode: str
) -> str:
    """构建IP提示词"""
    config = IPConfig.from_dict(ip_config)
    builder = IPPromptBuilder()
    mode = IPSpeakingMode(speaking_mode)
    return builder.build_script_prompt(config, topic, mode)
