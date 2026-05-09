"""
短视频脚本模板系统

提供预设场景模板，支持不同内容类型和风格：
- 问题诊断类
- 解决方案类
- 人设故事类
- 机构产品类
- 人设价值观类
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class ContentType(Enum):
    """内容类型"""
    PROBLEM_DIAGNOSIS = "problem_diagnosis"     # 问题诊断类
    SOLUTION = "solution"                       # 解决方案类
    CASE_SHARE = "case_share"                  # 案例分享类
    PRODUCT_RECOMMEND = "product_recommend"    # 产品推荐类
    KNOWLEDGE = "knowledge"                     # 知识科普类
    HOT_TOPIC = "hot_topic"                    # 热点关联类
    PERSONA_STORY = "persona_story"           # 人设故事类
    PERSONA_VALUE = "persona_value"            # 人设价值观类
    VIEWPOINT = "viewpoint"                    # 观点输出类
    INSTITUTION_PRODUCT = "institution_product" # 机构产品类


class Duration(Enum):
    """视频时长"""
    SHORT = "short"      # 15-30秒
    MEDIUM = "medium"   # 30-60秒
    LONG = "long"       # 60-90秒
    EXTRA_LONG = "extra_long"  # 90秒以上


@dataclass
class SceneTemplate:
    """场景模板"""
    index: int
    name: str
    time_range: str
    emotion: str
    content_type: str
    visual_guide: str
    narration_guide: str
    hook_type: Optional[str] = None
    reward_type: Optional[str] = None


@dataclass
class ScriptTemplate:
    """脚本模板"""
    id: str
    name: str
    content_type: ContentType
    duration: Duration
    description: str
    scenes: List[SceneTemplate]
    balance_config: Dict[str, float]  # 均衡器配置
    trust_source: str
    ip_required: bool  # 是否需要IP出镜
    tips: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "content_type": self.content_type.value,
            "duration": self.duration.value,
            "description": self.description,
            "scenes": [
                {
                    "index": s.index,
                    "name": s.name,
                    "time_range": s.time_range,
                    "emotion": s.emotion,
                    "content_type": s.content_type,
                    "visual_guide": s.visual_guide,
                    "narration_guide": s.narration_guide,
                    "hook_type": s.hook_type,
                    "reward_type": s.reward_type
                }
                for s in self.scenes
            ],
            "balance_config": self.balance_config,
            "trust_source": self.trust_source,
            "ip_required": self.ip_required,
            "tips": self.tips
        }


class TemplateLibrary:
    """模板库"""

    def __init__(self):
        self._templates: Dict[str, ScriptTemplate] = {}
        self._init_default_templates()

    def _init_default_templates(self):
        """初始化默认模板"""
        templates = [
            self._create_problem_diagnosis_short(),
            self._create_problem_diagnosis_medium(),
            self._create_solution_medium(),
            self._create_solution_long(),
            self._create_case_share_long(),
            self._create_product_recommend_short(),
            self._create_persona_story_long(),
            self._create_persona_value_medium(),
            self._create_institution_product_short(),
            self._create_institution_product_medium(),
        ]

        for t in templates:
            self._templates[t.id] = t

    def get(self, template_id: str) -> Optional[ScriptTemplate]:
        """获取模板"""
        return self._templates.get(template_id)

    def list_by_type(self, content_type: ContentType) -> List[ScriptTemplate]:
        """按类型筛选模板"""
        return [t for t in self._templates.values() if t.content_type == content_type]

    def list_by_duration(self, duration: Duration) -> List[ScriptTemplate]:
        """按时长筛选模板"""
        return [t for t in self._templates.values() if t.duration == duration]

    def list_all(self) -> List[ScriptTemplate]:
        """列出所有模板"""
        return list(self._templates.values())

    def search(self, keyword: str) -> List[ScriptTemplate]:
        """搜索模板"""
        keyword = keyword.lower()
        results = []
        for t in self._templates.values():
            if keyword in t.name.lower() or keyword in t.description.lower():
                results.append(t)
        return results

    # =========================================================================
    # 模板定义
    # =========================================================================

    def _create_problem_diagnosis_short(self) -> ScriptTemplate:
        """问题诊断类 - 短版"""
        return ScriptTemplate(
            id="problem_diagnosis_short",
            name="问题诊断·15秒快剪",
            content_type=ContentType.PROBLEM_DIAGNOSIS,
            duration=Duration.SHORT,
            description="快速戳中痛点，引发共鸣，适合涨粉",
            scenes=[
                SceneTemplate(
                    index=1, name="痛点开场", time_range="0-3秒",
                    emotion="高情绪", content_type="痛点冲击",
                    visual_guide="真人表情/文字冲击",
                    narration_guide="[强痛点描述]，你中招了吗？",
                    hook_type="痛点钩子", reward_type=None
                ),
                SceneTemplate(
                    index=2, name="问题展开", time_range="3-12秒",
                    emotion="中情绪", content_type="问题分析",
                    visual_guide="图文/素材混剪",
                    narration_guide="原因主要有[数字]个：[原因1]、[原因2]、[原因3]",
                    hook_type=None, reward_type="知识奖励"
                ),
                SceneTemplate(
                    index=3, name="引导互动", time_range="12-15秒",
                    emotion="疑问", content_type="互动引导",
                    visual_guide="字幕/评论区引导",
                    narration_guide="评论区说说你是哪种情况？",
                    hook_type=None, reward_type="互动奖励"
                )
            ],
            balance_config={
                "信息密度": 0.60,
                "问题悬念": 0.70,
                "情绪波动": 0.60,
                "互动频率": 0.60,
                "奖励分布": 0.60,
                "难度递进": 0.50
            },
            trust_source="知识型",
            ip_required=False,
            tips=["痛点要具体，不要泛泛而谈", "原因不要超过3个，便于记忆"]
        )

    def _create_problem_diagnosis_medium(self) -> ScriptTemplate:
        """问题诊断类 - 中版"""
        return ScriptTemplate(
            id="problem_diagnosis_medium",
            name="问题诊断·30秒详解",
            content_type=ContentType.PROBLEM_DIAGNOSIS,
            duration=Duration.MEDIUM,
            description="痛点+分析+解决方案，适合教育类账号",
            scenes=[
                SceneTemplate(
                    index=1, name="痛点开场", time_range="0-5秒",
                    emotion="高情绪", content_type="痛点冲击",
                    visual_guide="真人出镜/真实场景",
                    narration_guide="[具体痛点场景描述]",
                    hook_type="痛点钩子"
                ),
                SceneTemplate(
                    index=2, name="问题分析", time_range="5-15秒",
                    emotion="中情绪", content_type="原因分析",
                    visual_guide="图解/字幕配合",
                    narration_guide="为什么会出现这个问题？主要是[原因1]、[原因2]、[原因3]",
                    reward_type="知识奖励"
                ),
                SceneTemplate(
                    index=3, name="解决方案", time_range="15-25秒",
                    emotion="正面", content_type="方案输出",
                    visual_guide="演示/步骤展示",
                    narration_guide="正确做法是[步骤1]、[步骤2]、[步骤3]",
                    reward_type="知识奖励"
                ),
                SceneTemplate(
                    index=4, name="行动引导", time_range="25-30秒",
                    emotion="正面", content_type="CTA",
                    visual_guide="关注引导",
                    narration_guide="关注我，下期告诉你[延伸话题]"
                )
            ],
            balance_config={
                "信息密度": 0.70,
                "问题悬念": 0.60,
                "情绪波动": 0.50,
                "互动频率": 0.45,
                "奖励分布": 0.60,
                "难度递进": 0.65
            },
            trust_source="知识型",
            ip_required=True,
            tips=["分析要有逻辑性", "解决方案要可操作"]
        )

    def _create_solution_medium(self) -> ScriptTemplate:
        """解决方案类 - 中版"""
        return ScriptTemplate(
            id="solution_medium",
            name="解决方案·干货输出",
            content_type=ContentType.SOLUTION,
            duration=Duration.MEDIUM,
            description="完整的问题解决过程，转化效果好",
            scenes=[
                SceneTemplate(
                    index=1, name="问题引入", time_range="0-5秒",
                    emotion="低情绪", content_type="问题铺垫",
                    visual_guide="问题场景/素材",
                    narration_guide="你是不是也遇到过[问题描述]？",
                    hook_type="痛点钩子"
                ),
                SceneTemplate(
                    index=2, name="方案揭晓", time_range="5-20秒",
                    emotion="中情绪", content_type="核心方案",
                    visual_guide="演示/操作展示",
                    narration_guide="今天教你[数字]招解决这个问题：\n第一，[技巧1]；\n第二，[技巧2]；\n第三，[技巧3]",
                    reward_type="知识奖励"
                ),
                SceneTemplate(
                    index=3, name="效果验证", time_range="20-30秒",
                    emotion="正面", content_type="效果展示",
                    visual_guide="前后对比/成功案例",
                    narration_guide="用这个方法，[效果描述]",
                    reward_type="效果奖励"
                ),
                SceneTemplate(
                    index=4, name="总结CTA", time_range="30-40秒",
                    emotion="正面", content_type="总结+CTA",
                    visual_guide="总结文字/关注引导",
                    narration_guide="记住了吗？[核心要点]。关注我，持续分享[领域]干货！"
                )
            ],
            balance_config={
                "信息密度": 0.75,
                "问题悬念": 0.50,
                "情绪波动": 0.45,
                "互动频率": 0.40,
                "奖励分布": 0.60,
                "难度递进": 0.70
            },
            trust_source="知识型",
            ip_required=True,
            tips=["方案要有差异化", "效果要有数据支撑"]
        )

    def _create_solution_long(self) -> ScriptTemplate:
        """解决方案类 - 长版"""
        return ScriptTemplate(
            id="solution_long",
            name="深度解决方案·60秒",
            content_type=ContentType.SOLUTION,
            duration=Duration.LONG,
            description="深度讲解，适合复杂问题",
            scenes=[
                SceneTemplate(
                    index=1, name="问题铺垫", time_range="0-8秒",
                    emotion="低", content_type="背景铺垫",
                    visual_guide="问题场景",
                    narration_guide="[背景描述]，这是一个很多人都会遇到的问题",
                    hook_type="痛点钩子"
                ),
                SceneTemplate(
                    index=2, name="误区揭示", time_range="8-20秒",
                    emotion="中", content_type="误区纠正",
                    visual_guide="错误做法展示",
                    narration_guide="首先，你需要避开这个最大的误区：[误区描述]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=3, name="核心方法", time_range="20-40秒",
                    emotion="中", content_type="方法论",
                    visual_guide="方法图解/步骤演示",
                    narration_guide="正确的方法是[核心方法]：[步骤1]、[步骤2]、[步骤3]",
                    reward_type="知识奖励"
                ),
                SceneTemplate(
                    index=4, name="案例验证", time_range="40-50秒",
                    emotion="正面", content_type="案例展示",
                    visual_guide="成功案例",
                    narration_guide="就像[案例描述]，[用户/客户]用这个方法，[效果]",
                    reward_type="效果奖励"
                ),
                SceneTemplate(
                    index=5, name="总结升华", time_range="50-60秒",
                    emotion="正面", content_type="金句+CTA",
                    visual_guide="总结字幕",
                    narration_guide="[金句总结]。关注我，一起[目标]"
                )
            ],
            balance_config={
                "信息密度": 0.80,
                "问题悬念": 0.55,
                "情绪波动": 0.50,
                "互动频率": 0.40,
                "奖励分布": 0.55,
                "难度递进": 0.75
            },
            trust_source="知识型",
            ip_required=True,
            tips=["方法论要成体系", "案例要真实可信"]
        )

    def _create_case_share_long(self) -> ScriptTemplate:
        """案例分享类 - 长版"""
        return ScriptTemplate(
            id="case_share_long",
            name="案例分享·故事驱动",
            content_type=ContentType.CASE_SHARE,
            duration=Duration.LONG,
            description="通过真实案例建立信任，高转化",
            scenes=[
                SceneTemplate(
                    index=1, name="背景介绍", time_range="0-10秒",
                    emotion="平静", content_type="场景铺垫",
                    visual_guide="背景场景",
                    narration_guide="这是[时间]，[地点]的一个[故事背景]",
                    hook_type="故事钩子"
                ),
                SceneTemplate(
                    index=2, name="冲突呈现", time_range="10-30秒",
                    emotion="高", content_type="冲突展开",
                    visual_guide="冲突场景/对话",
                    narration_guide="但是没想到，[冲突描述]，[困难/问题]",
                    reward_type="悬念奖励"
                ),
                SceneTemplate(
                    index=3, name="转折解决", time_range="30-50秒",
                    emotion="正面", content_type="解决方案",
                    visual_guide="解决过程",
                    narration_guide="后来，[转折点]，[解决方法]，[最终结果]",
                    reward_type="情节奖励"
                ),
                SceneTemplate(
                    index=4, name="价值提炼", time_range="50-65秒",
                    emotion="正面", content_type="经验总结",
                    visual_guide="要点总结",
                    narration_guide="这个故事告诉我们：[核心经验]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=5, name="互动CTA", time_range="65-75秒",
                    emotion="正面", content_type="互动+CTA",
                    visual_guide="关注引导",
                    narration_guide="你有没有类似的经历？评论区聊聊。关注我，[领域]干货持续更新"
                )
            ],
            balance_config={
                "信息密度": 0.50,
                "问题悬念": 0.65,
                "情绪波动": 0.70,
                "互动频率": 0.60,
                "奖励分布": 0.55,
                "难度递进": 0.60
            },
            trust_source="知识型+人设型",
            ip_required=True,
            tips=["故事要一波三折", "经验提炼要简洁有力"]
        )

    def _create_product_recommend_short(self) -> ScriptTemplate:
        """产品推荐类 - 短版"""
        return ScriptTemplate(
            id="product_recommend_short",
            name="产品推荐·种草快剪",
            content_type=ContentType.PRODUCT_RECOMMEND,
            duration=Duration.SHORT,
            description="快速种草，适合带货",
            scenes=[
                SceneTemplate(
                    index=1, name="痛点引入", time_range="0-3秒",
                    emotion="高情绪", content_type="痛点",
                    visual_guide="痛点场景",
                    narration_guide="[痛点]？这个问题困扰你多久了？",
                    hook_type="痛点钩子"
                ),
                SceneTemplate(
                    index=2, name="产品展示", time_range="3-18秒",
                    emotion="正面", content_type="产品展示",
                    visual_guide="产品特写",
                    narration_guide="试试[产品名]，它有[特点1]、[特点2]、[特点3]",
                    reward_type="产品奖励"
                ),
                SceneTemplate(
                    index=3, name="效果展示", time_range="18-25秒",
                    emotion="正面", content_type="效果",
                    visual_guide="使用效果",
                    narration_guide="用完之后，[效果描述]",
                    reward_type="效果奖励"
                ),
                SceneTemplate(
                    index=4, name="CTA", time_range="25-30秒",
                    emotion="正面", content_type="CTA",
                    visual_guide="购买链接",
                    narration_guide="[优惠信息]，点击下方链接[行动]",
                    hook_type="优惠钩子"
                )
            ],
            balance_config={
                "信息密度": 0.55,
                "问题悬念": 0.50,
                "情绪波动": 0.65,
                "互动频率": 0.50,
                "奖励分布": 0.65,
                "难度递进": 0.45
            },
            trust_source="知识型",
            ip_required=True,
            tips=["产品卖点不要超过3个", "优惠信息要突出"]
        )

    def _create_persona_story_long(self) -> ScriptTemplate:
        """人设故事类 - 长版"""
        return ScriptTemplate(
            id="persona_story_long",
            name="人设故事·情感共鸣",
            content_type=ContentType.PERSONA_STORY,
            duration=Duration.LONG,
            description="讲述个人故事，建立情感连接",
            scenes=[
                SceneTemplate(
                    index=1, name="故事引入", time_range="0-10秒",
                    emotion="平静", content_type="场景导入",
                    visual_guide="真实场景/生活场景",
                    narration_guide="[时间/地点/人物]，[故事开场]",
                    hook_type="故事钩子"
                ),
                SceneTemplate(
                    index=2, name="经历展开", time_range="10-35秒",
                    emotion="波动", content_type="经历讲述",
                    visual_guide="情景再现/素材配合",
                    narration_guide="那时候，[经历描述]，[内心感受]，[转折点]",
                    reward_type="情感奖励"
                ),
                SceneTemplate(
                    index=3, name="感悟输出", time_range="35-55秒",
                    emotion="正面", content_type="观点输出",
                    visual_guide="人像特写",
                    narration_guide="这件事让我明白：[核心感悟]",
                    reward_type="观点奖励"
                ),
                SceneTemplate(
                    index=4, name="价值观传递", time_range="55-70秒",
                    emotion="坚定", content_type="价值观",
                    visual_guide="金句字幕",
                    narration_guide="我的原则是：[价值观金句]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=5, name="人设强化", time_range="70-80秒",
                    emotion="温暖", content_type="人设强化+CTA",
                    visual_guide="人像/品牌露出",
                    narration_guide="这就是我，一个[人设标签]，关注我，一起[共同目标]"
                )
            ],
            balance_config={
                "信息密度": 0.25,
                "问题悬念": 0.60,
                "情绪波动": 0.80,
                "互动频率": 0.65,
                "奖励分布": 0.55,
                "难度递进": 0.60
            },
            trust_source="人设型",
            ip_required=True,
            tips=["故事要真实动人", "价值观要鲜明独特"]
        )

    def _create_persona_value_medium(self) -> ScriptTemplate:
        """人设价值观类 - 中版"""
        return ScriptTemplate(
            id="persona_value_medium",
            name="人设价值观·观点输出",
            content_type=ContentType.PERSONA_VALUE,
            duration=Duration.MEDIUM,
            description="输出观点和态度，适合建立个人IP",
            scenes=[
                SceneTemplate(
                    index=1, name="话题引入", time_range="0-5秒",
                    emotion="高", content_type="话题抛出",
                    visual_guide="人像/字幕",
                    narration_guide="我发现一个现象：[社会现象/话题]",
                    hook_type="话题钩子"
                ),
                SceneTemplate(
                    index=2, name="观点输出", time_range="5-20秒",
                    emotion="中高", content_type="观点表达",
                    visual_guide="人像特写",
                    narration_guide="我觉得，[核心观点]",
                    reward_type="观点奖励"
                ),
                SceneTemplate(
                    index=3, name="冲突展开", time_range="20-35秒",
                    emotion="高", content_type="冲突分析",
                    visual_guide="对比/冲突展示",
                    narration_guide="为什么会有这种现象？[原因分析]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=4, name="价值观升华", time_range="35-50秒",
                    emotion="高", content_type="价值观输出",
                    visual_guide="金句字幕",
                    narration_guide="所以，我的态度是：[价值观金句]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=5, name="互动引导", time_range="50-60秒",
                    emotion="正面", content_type="互动+CTA",
                    visual_guide="评论引导",
                    narration_guide="你们怎么看？评论区说说。关注我，[领域]视角持续分享"
                )
            ],
            balance_config={
                "信息密度": 0.20,
                "问题悬念": 0.70,
                "情绪波动": 0.80,
                "互动频率": 0.70,
                "奖励分布": 0.55,
                "难度递进": 0.70
            },
            trust_source="人设型",
            ip_required=True,
            tips=["观点要有独特性", "态度要鲜明"]
        )

    def _create_institution_product_short(self) -> ScriptTemplate:
        """机构产品类 - 短版"""
        return ScriptTemplate(
            id="institution_product_short",
            name="机构产品·品牌背书",
            content_type=ContentType.INSTITUTION_PRODUCT,
            duration=Duration.SHORT,
            description="不需要出镜，适合品牌账号",
            scenes=[
                SceneTemplate(
                    index=1, name="问题/需求", time_range="0-5秒",
                    emotion="平静", content_type="需求引入",
                    visual_guide="场景/产品",
                    narration_guide="[需求场景]，你需要的是[产品/服务]",
                    hook_type="需求钩子"
                ),
                SceneTemplate(
                    index=2, name="产品介绍", time_range="5-20秒",
                    emotion="平稳", content_type="产品展示",
                    visual_guide="产品特写/参数",
                    narration_guide="[品牌名]的[产品]，[核心卖点1]、[核心卖点2]、[核心卖点3]",
                    reward_type="产品奖励"
                ),
                SceneTemplate(
                    index=3, name="信任背书", time_range="20-25秒",
                    emotion="信任", content_type="背书",
                    visual_guide="资质/数据",
                    narration_guide="[品牌背书信息]，[销量/用户数]的选择"
                ),
                SceneTemplate(
                    index=4, name="CTA", time_range="25-30秒",
                    emotion="正面", content_type="CTA",
                    visual_guide="购买入口",
                    narration_guide="[优惠信息]，[行动引导]"
                )
            ],
            balance_config={
                "信息密度": 0.70,
                "问题悬念": 0.40,
                "情绪波动": 0.50,
                "互动频率": 0.50,
                "奖励分布": 0.50,
                "难度递进": 0.60
            },
            trust_source="机构型",
            ip_required=False,
            tips=["画面以产品为主", "数据要权威可信"]
        )

    def _create_institution_product_medium(self) -> ScriptTemplate:
        """机构产品类 - 中版"""
        return ScriptTemplate(
            id="institution_product_medium",
            name="机构产品·深度介绍",
            content_type=ContentType.INSTITUTION_PRODUCT,
            duration=Duration.MEDIUM,
            description="完整的产品/服务介绍，适合机构账号",
            scenes=[
                SceneTemplate(
                    index=1, name="需求场景", time_range="0-8秒",
                    emotion="平静", content_type="需求铺垫",
                    visual_guide="使用场景",
                    narration_guide="当您遇到[需求场景]，是否在寻找[解决方案]？"
                ),
                SceneTemplate(
                    index=2, name="产品/服务介绍", time_range="8-25秒",
                    emotion="平稳", content_type="核心介绍",
                    visual_guide="产品展示/参数",
                    narration_guide="[品牌名]提供[产品/服务]：[核心功能1]、[核心功能2]、[核心功能3]",
                    reward_type="产品奖励"
                ),
                SceneTemplate(
                    index=3, name="差异化优势", time_range="25-35秒",
                    emotion="自信", content_type="优势展示",
                    visual_guide="对比/优势图",
                    narration_guide="与同类相比，我们的特点：[差异化优势]",
                    reward_type="认知奖励"
                ),
                SceneTemplate(
                    index=4, name="信任保障", time_range="35-45秒",
                    emotion="信任", content_type="保障说明",
                    visual_guide="资质/承诺",
                    narration_guide="我们提供：[保障1]、[保障2]、[保障3]"
                ),
                SceneTemplate(
                    index=5, name="行动引导", time_range="45-55秒",
                    emotion="正面", content_type="CTA",
                    visual_guide="联系方式/链接",
                    narration_guide="[优惠信息]，立即[行动]"
                )
            ],
            balance_config={
                "信息密度": 0.75,
                "问题悬念": 0.40,
                "情绪波动": 0.45,
                "互动频率": 0.45,
                "奖励分布": 0.50,
                "难度递进": 0.65
            },
            trust_source="机构型",
            ip_required=False,
            tips=["信息要全面但不啰嗦", "保障要具体可执行"]
        )


# =============================================================================
# 便捷函数
# =============================================================================

def get_template_library() -> TemplateLibrary:
    """获取模板库实例"""
    return TemplateLibrary()


def get_all_templates() -> List[Dict[str, Any]]:
    """获取所有模板"""
    library = TemplateLibrary()
    return [t.to_dict() for t in library.list_all()]


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """获取指定模板"""
    library = TemplateLibrary()
    template = library.get(template_id)
    return template.to_dict() if template else None


def get_templates_by_type(content_type: str) -> List[Dict[str, Any]]:
    """按类型获取模板"""
    library = TemplateLibrary()
    try:
        ct = ContentType(content_type)
        return [t.to_dict() for t in library.list_by_type(ct)]
    except ValueError:
        return []


def get_templates_by_duration(duration: str) -> List[Dict[str, Any]]:
    """按时长获取模板"""
    library = TemplateLibrary()
    try:
        d = Duration(duration)
        return [t.to_dict() for t in library.list_by_duration(d)]
    except ValueError:
        return []


def search_templates(keyword: str) -> List[Dict[str, Any]]:
    """搜索模板"""
    library = TemplateLibrary()
    return [t.to_dict() for t in library.search(keyword)]


def recommend_template(
    content_type: Optional[str] = None,
    duration: Optional[str] = None,
    trust_source: Optional[str] = None
) -> Dict[str, Any]:
    """根据条件推荐模板"""
    library = TemplateLibrary()

    # 按信任来源推荐
    default_by_trust = {
        "知识型": "solution_medium",
        "人设型": "persona_value_medium",
        "机构型": "institution_product_medium"
    }

    # 如果有信任来源，直接返回推荐模板
    if trust_source and trust_source in default_by_trust:
        template_id = default_by_trust[trust_source]
        template = library.get(template_id)
        if template:
            return template.to_dict()

    # 按内容类型筛选
    if content_type:
        templates = get_templates_by_type(content_type)
        if templates:
            return templates[0]

    # 按时长筛选
    if duration:
        templates = get_templates_by_duration(duration)
        if templates:
            return templates[0]

    # 默认返回解决方案中版
    template = library.get("solution_medium")
    return template.to_dict() if template else {}
