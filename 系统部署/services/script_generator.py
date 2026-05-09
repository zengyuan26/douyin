"""
短视频脚本生成器

职责划分：
- 系统做：流程编排、参数传递、输出格式化、评分调用
- LLM做：文案生成、创意发挥、语言润色

核心流程：
1. 系统收集参数（选题、人设、均衡器配置等）
2. 系统计算结构（奖励点分布、场景切分等）
3. LLM生成内容（各场景口播、画面描述等）
4. 系统整合输出、调用评分
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class GenerationRequest:
    """生成请求"""
    topic: str
    topic_type: str
    duration: int
    ip_config: Dict[str, Any]
    balance_config: Dict[str, Any]
    trust_source: str
    template_id: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None


@dataclass
class Scene:
    """场景"""
    index: int
    name: str
    time_range: str
    time_start: float
    time_end: float
    content_type: str
    emotion: str
    visual_guide: str
    narration: str  # LLM生成
    hook_type: Optional[str] = None
    reward_type: Optional[str] = None
    interaction: Optional[Dict[str, str]] = None


@dataclass
class ScriptOutput:
    """脚本输出"""
    meta: Dict[str, Any]
    style_guide: Dict[str, Any]
    equalizer: Dict[str, Any]
    script_info: Dict[str, Any]
    scenes: List[Dict[str, Any]]
    quality_report: Dict[str, Any]
    generated_at: str


class ScriptGenerator:
    """
    脚本生成器

    协调系统计算和LLM生成
    """

    def __init__(self, llm_service=None):
        """
        Args:
            llm_service: LLM服务实例（可选，测试时可用mock）
        """
        self.llm_service = llm_service
        self._init_components()

    def _init_components(self):
        """初始化组件"""
        # 延迟导入避免循环依赖
        from services.reward_point_system import RewardPointService
        from services.script_template import get_template_library
        from services.script_scorer import ScriptScorer

        self.reward_service = RewardPointService()
        self.template_library = get_template_library()
        self.scorer = ScriptScorer()

    def generate(self, request: GenerationRequest) -> ScriptOutput:
        """
        生成脚本

        流程：
        1. 系统准备参数
        2. 系统计算结构
        3. LLM生成内容
        4. 系统整合评分
        """
        logger.info(f"开始生成脚本: {request.topic}")

        # 1. 系统：获取模板
        template = self._get_template(request)

        # 2. 系统：计算奖励点分布
        reward_data = self.reward_service.calculate(
            request.duration,
            request.balance_config
        )

        # 3. 系统：构建场景结构
        scene_structure = self._build_scene_structure(
            request,
            template,
            reward_data
        )

        # 4. LLM：生成场景内容
        scenes_with_content = self._generate_scene_content(
            scene_structure,
            request
        )

        # 5. 系统：整合输出
        output = self._assemble_output(
            request,
            template,
            reward_data,
            scenes_with_content
        )

        # 6. 系统：评分
        quality_report = self._score_script(output)

        output.quality_report = quality_report.to_dict() if hasattr(quality_report, 'to_dict') else quality_report

        logger.info(f"脚本生成完成: {request.topic}, 评分: {output.quality_report.get('total_score', 0)}")

        return output

    def _get_template(self, request: GenerationRequest) -> Optional[Dict]:
        """获取模板"""
        if request.template_id:
            from services.script_template import get_template
            template = get_template(request.template_id)
            if template:
                return template

        # 根据选题类型推荐
        from services.script_template import recommend_template
        from services.topic_system import TopicType

        # 映射选题类型
        type_mapping = {
            "问题诊断类": "problem_diagnosis",
            "解决方案类": "solution",
            "案例分享类": "case_share",
            "产品推荐类": "product_recommend",
            "知识科普类": "knowledge",
            "热点关联类": "hot_topic",
            "人设故事类": "persona_story",
            "人设价值观类": "persona_value",
            "观点输出类": "viewpoint",
            "机构产品类": "institution_product"
        }

        template_type = type_mapping.get(request.topic_type)
        return recommend_template(content_type=template_type, duration=self._duration_to_level(request.duration))

    def _duration_to_level(self, duration: int) -> str:
        """时长转等级"""
        if duration <= 30:
            return "short"
        elif duration <= 60:
            return "medium"
        elif duration <= 90:
            return "long"
        else:
            return "extra_long"

    def _build_scene_structure(
        self,
        request: GenerationRequest,
        template: Optional[Dict],
        reward_data: Dict
    ) -> List[Dict[str, Any]]:
        """构建场景结构"""
        scenes = []

        if template and template.get("scenes"):
            # 使用模板
            for scene_template in template["scenes"]:
                scene = {
                    "index": scene_template["index"],
                    "name": scene_template["name"],
                    "time_range": scene_template["time_range"],
                    "content_type": scene_template["content_type"],
                    "emotion": scene_template["emotion"],
                    "visual_guide": scene_template["visual_guide"],
                    "narration_guide": scene_template.get("narration_guide", ""),
                    "hook_type": scene_template.get("hook_type"),
                    "reward_type": None
                }
                scenes.append(scene)
        else:
            # 系统自动生成场景结构
            scenes = self._auto_generate_scenes(request, reward_data)

        # 标记奖励点
        for point in reward_data.get("points", []):
            point_start = point["time_start"]
            for scene in scenes:
                start, end = self._parse_time_range(scene["time_range"])
                if start <= point_start < end:
                    scene["reward_type"] = point["reward_type"]
                    break

        return scenes

    def _auto_generate_scenes(
        self,
        request: GenerationRequest,
        reward_data: Dict
    ) -> List[Dict[str, Any]]:
        """自动生成场景结构"""
        duration = request.duration
        scenes = []

        # 根据时长决定场景数
        if duration <= 30:
            scene_count = 3
        elif duration <= 60:
            scene_count = 4
        else:
            scene_count = 5

        scene_duration = duration / scene_count
        cumulative = 0

        scene_types = self._get_scene_types(request.topic_type, scene_count)

        for i in range(scene_count):
            start = cumulative
            end = min(cumulative + scene_duration, duration)

            scene = {
                "index": i + 1,
                "name": scene_types[i]["name"],
                "time_range": f"{int(start)}-{int(end)}秒",
                "content_type": scene_types[i]["type"],
                "emotion": scene_types[i]["emotion"],
                "visual_guide": scene_types[i]["visual"],
                "narration_guide": scene_types[i]["guide"],
                "hook_type": scene_types[i].get("hook"),
                "reward_type": None
            }
            scenes.append(scene)
            cumulative = end

        return scenes

    def _get_scene_types(self, topic_type: str, count: int) -> List[Dict]:
        """获取场景类型配置"""
        base_types = {
            "问题诊断类": [
                {"name": "痛点开场", "type": "痛点冲击", "emotion": "高情绪", "visual": "真人表情/文字冲击", "guide": "[强痛点描述]，你中招了吗？", "hook": "痛点钩子"},
                {"name": "问题分析", "type": "原因分析", "emotion": "中情绪", "visual": "图解/字幕配合", "guide": "原因主要有[数字]个..."},
                {"name": "解决方案", "type": "方案输出", "emotion": "正面", "visual": "演示/步骤展示", "guide": "正确做法是..."},
                {"name": "总结CTA", "type": "总结+CTA", "emotion": "正面", "visual": "关注引导", "guide": "记住了吗？关注我..."},
                {"name": "延伸话题", "type": "延伸引导", "emotion": "期待", "visual": "话题预告", "guide": "下期告诉你..."}
            ],
            "解决方案类": [
                {"name": "问题铺垫", "type": "问题铺垫", "emotion": "低", "visual": "问题场景", "guide": "你是不是也遇到过..."},
                {"name": "方案揭晓", "type": "核心方案", "emotion": "中情绪", "visual": "演示/操作展示", "guide": "今天教你[数字]招..."},
                {"name": "效果验证", "type": "效果展示", "emotion": "正面", "visual": "前后对比", "guide": "用这个方法..."},
                {"name": "总结CTA", "type": "总结+CTA", "emotion": "正面", "visual": "总结字幕", "guide": "记住了吗？关注我..."}
            ],
            "人设价值观类": [
                {"name": "话题抛出", "type": "话题抛出", "emotion": "高", "visual": "人像/字幕", "guide": "我发现一个现象...", "hook": "话题钩子"},
                {"name": "观点表达", "type": "观点表达", "emotion": "中高", "visual": "人像特写", "guide": "我觉得..."},
                {"name": "冲突展开", "type": "冲突分析", "emotion": "高", "visual": "对比展示", "guide": "为什么会有..."},
                {"name": "价值观升华", "type": "价值观输出", "emotion": "高", "visual": "金句字幕", "guide": "所以，我的态度是..."},
                {"name": "互动引导", "type": "互动+CTA", "emotion": "正面", "visual": "评论引导", "guide": "你们怎么看？关注我..."}
            ]
        }

        default_types = [
            {"name": "开场", "type": "开场", "emotion": "高", "visual": "吸引眼球", "guide": "[开场内容]", "hook": "悬念钩子"},
            {"name": "展开", "type": "内容展开", "emotion": "中", "visual": "素材配合", "guide": "[展开内容]"},
            {"name": "高潮", "type": "价值点", "emotion": "高", "visual": "关键展示", "guide": "[高潮内容]"},
            {"name": "收尾", "type": "总结+CTA", "emotion": "正面", "visual": "引导", "guide": "[总结]关注我..."}
        ]

        return base_types.get(topic_type, default_types)[:count]

    def _generate_scene_content(
        self,
        scene_structure: List[Dict],
        request: GenerationRequest
    ) -> List[Dict[str, Any]]:
        """
        调用LLM生成场景内容

        系统传递结构化提示，LLM生成具体文案
        """
        # 构建LLM提示
        prompt = self._build_llm_prompt(scene_structure, request)

        # 调用LLM（如果有服务）
        if self.llm_service:
            llm_result = self.llm_service.generate(prompt)
            content = self._parse_llm_result(llm_result)
        else:
            # Mock结果（测试用）
            content = self._mock_llm_result(scene_structure, request)

        # 合并结构与内容
        scenes = []
        for i, scene in enumerate(scene_structure):
            scene_data = scene.copy()
            scene_data["time_start"] = self._parse_time_start(scene["time_range"])
            scene_data["time_end"] = self._parse_time_end(scene["time_range"])

            if i < len(content):
                scene_data["narration"] = content[i].get("narration", scene["narration_guide"])
                scene_data["visual_description"] = content[i].get("visual", scene["visual_guide"])
                scene_data["interaction"] = content[i].get("interaction")
            else:
                scene_data["narration"] = scene["narration_guide"]
                scene_data["visual_description"] = scene["visual_guide"]
                scene_data["interaction"] = None

            scenes.append(scene_data)

        return scenes

    def _build_llm_prompt(
        self,
        scene_structure: List[Dict],
        request: GenerationRequest
    ) -> str:
        """构建LLM提示词"""
        prompt = f"""你是一个短视频脚本专家。请为以下选题生成各场景的口播文案。

【选题】{request.topic}
【选题类型】{request.topic_type}
【视频时长】{request.duration}秒
【IP人设】{request.ip_config.get('name', '未设置')}
【出镜方式】{request.ip_config.get('mode', '数字人出镜')}

"""

        # 添加均衡器配置说明
        prompt += "【内容风格配置】\n"
        for param, value in request.balance_config.items():
            prompt += f"- {param}: {value:.0%}\n"

        prompt += "\n【场景结构】\n"
        for scene in scene_structure:
            prompt += f"""
---
场景{scene['index']}: {scene['name']} ({scene['time_range']})
类型: {scene['content_type']}
情绪: {scene['emotion']}
画面: {scene['visual_guide']}
"""

            if scene.get("hook_type"):
                prompt += f"钩子类型: {scene['hook_type']}\n"

            if scene.get("reward_type"):
                prompt += f"奖励点类型: {scene['reward_type']}\n"

            prompt += f"内容引导: {scene['narration_guide']}\n"

        prompt += """
【要求】
1. 每个场景的口播文案要简洁有力，15-30字
2. 语言口语化，有节奏感
3. 情绪要符合场景设定
4. 适当使用情绪词和悬念词
5. 结尾场景需要有互动引导（点赞、关注、评论）

请以JSON数组格式返回每个场景的详细内容：
```json
[
  {
    "narration": "口播文案",
    "visual": "补充的视觉描述（可选）",
    "interaction": {"type": "互动类型", "content": "互动引导文案（可选）"}
  }
]
```
"""
        return prompt

    def _mock_llm_result(
        self,
        scene_structure: List[Dict],
        request: GenerationRequest
    ) -> List[Dict[str, Any]]:
        """模拟LLM返回（测试用）"""
        results = []
        for scene in scene_structure:
            results.append({
                "narration": f"【{scene['name']}】场景的口播内容，正在生成中...",
                "visual": scene["visual_guide"],
                "interaction": None
            })
        return results

    def _parse_llm_result(self, llm_output: str) -> List[Dict[str, Any]]:
        """解析LLM输出"""
        # 尝试解析JSON
        try:
            # 提取JSON部分
            import re
            json_match = re.search(r'\[.*\]', llm_output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM结果解析失败: {e}")

        return []

    def _assemble_output(
        self,
        request: GenerationRequest,
        template: Optional[Dict],
        reward_data: Dict,
        scenes: List[Dict]
    ) -> ScriptOutput:
        """整合输出"""
        return ScriptOutput(
            meta={
                "topic": request.topic,
                "topic_type": request.topic_type,
                "duration": request.duration,
                "generated_at": datetime.now().isoformat()
            },
            style_guide=self._generate_style_guide(request),
            equalizer=request.balance_config,
            script_info={
                "trust_source": request.trust_source,
                "ip_mode": request.ip_config.get("mode", "数字人出镜"),
                "ip_name": request.ip_config.get("name", "")
            },
            scenes=scenes,
            quality_report={},
            generated_at=datetime.now().isoformat()
        )

    def _generate_style_guide(self, request: GenerationRequest) -> Dict[str, str]:
        """生成风格指南"""
        guides = {
            "问题诊断类": {
                "视觉风格": "真实场景 + 痛点特写",
                "色调": "对比强烈，引发共鸣",
                "光效": "自然光或戏剧性光效"
            },
            "解决方案类": {
                "视觉风格": "演示场景 + 步骤展示",
                "色调": "清晰明亮，专业感",
                "光效": "柔和均匀，清晰展示"
            },
            "人设价值观类": {
                "视觉风格": "人像特写 + 金句字幕",
                "色调": "温暖色调，人物为主",
                "光效": "柔光，突出人物"
            }
        }

        return guides.get(request.topic_type, {
            "视觉风格": "根据内容灵活调整",
            "色调": "根据情绪调整",
            "光效": "自然光为主"
        })

    def _score_script(self, output: ScriptOutput) -> Any:
        """评分"""
        # 转换为评分器需要的格式
        script_data = {
            "title": output.meta["topic"],
            "scenes": [
                {
                    "narration": s.get("narration", ""),
                    "emotion_stage": s.get("emotion", "")
                }
                for s in output.scenes
            ]
        }

        # 根据信任来源确定评分类型
        from services.script_scorer import TrustSourceType

        type_mapping = {
            "知识型": TrustSourceType.KNOWLEDGE,
            "人设型": TrustSourceType.PERSONA,
            "机构型": TrustSourceType.INSTITUTION,
            "产品型": TrustSourceType.PRODUCT
        }

        trust_type = type_mapping.get(
            output.script_info.get("trust_source", "知识型"),
            TrustSourceType.KNOWLEDGE
        )

        return self.scorer.score(script_data, trust_type)

    def _parse_time_range(self, time_range: str) -> tuple:
        """解析时间范围"""
        parts = time_range.replace("秒", "").split("-")
        start = float(parts[0]) if len(parts) > 0 else 0
        end = float(parts[1]) if len(parts) > 1 else start
        return start, end

    def _parse_time_start(self, time_range: str) -> float:
        """解析开始时间"""
        return self._parse_time_range(time_range)[0]

    def _parse_time_end(self, time_range: str) -> float:
        """解析结束时间"""
        return self._parse_time_range(time_range)[1]


# =============================================================================
# 便捷函数
# =============================================================================

def generate_script(
    topic: str,
    topic_type: str,
    duration: int,
    ip_config: Dict[str, Any],
    balance_config: Dict[str, Any],
    trust_source: str,
    llm_service=None
) -> Dict[str, Any]:
    """
    生成脚本的便捷函数

    Args:
        topic: 选题
        topic_type: 选题类型
        duration: 时长（秒）
        ip_config: IP配置
        balance_config: 均衡器配置
        trust_source: 信任来源
        llm_service: LLM服务

    Returns:
        dict: 脚本输出
    """
    request = GenerationRequest(
        topic=topic,
        topic_type=topic_type,
        duration=duration,
        ip_config=ip_config,
        balance_config=balance_config,
        trust_source=trust_source
    )

    generator = ScriptGenerator(llm_service)
    output = generator.generate(request)

    return {
        "meta": output.meta,
        "style_guide": output.style_guide,
        "equalizer": output.equalizer,
        "script_info": output.script_info,
        "scenes": output.scenes,
        "quality_report": output.quality_report,
        "generated_at": output.generated_at
    }
