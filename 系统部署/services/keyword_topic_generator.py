"""
画像专属关键词库 + 选题库生成服务

功能：
1. 基于单个画像的 problem_type 和 pain_points，生成该画像专属的关键词库
2. 基于关键词，生成选题库（五段式内容框架）
3. 关键词来自画像的问题，不是来自业务词拼接
4. 每个画像独立生成关键词库和选题库，不再有"公用关键词"
5. 选题标题中必须包含核心业务词，让用户一眼看出是针对什么产品/服务

使用方式：
from services.keyword_topic_generator import KeywordTopicGenerator

generator = KeywordTopicGenerator()
result = generator.generate_for_portrait(
    core_business='XX产品定制服务',
    portrait={'problem_type': '信息匮乏型', 'pain_points': [...]},
)

result.success
result.keyword_library
result.topic_library
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class PortraitKeywordLibrary:
    """画像专属关键词库"""
    portrait_id: str = ""
    problem_type: str = ""
    problem_type_keywords: List[str] = field(default_factory=list)
    pain_point_keywords: List[str] = field(default_factory=list)
    scene_keywords: List[str] = field(default_factory=list)
    concern_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'portrait_id': self.portrait_id,
            'problem_type': self.problem_type,
            'problem_type_keywords': self.problem_type_keywords,
            'pain_point_keywords': self.pain_point_keywords,
            'scene_keywords': self.scene_keywords,
            'concern_keywords': self.concern_keywords,
        }


@dataclass
class PortraitTopicLibrary:
    """画像专属选题库（五段式内容框架）"""
    portrait_id: str = ""
    problem_type: str = ""
    audience_lock_topics: List[str] = field(default_factory=list)   # 受众锁定类
    pain_amplify_topics: List[str] = field(default_factory=list)    # 痛点放大类
    solution_compare_topics: List[str] = field(default_factory=list)  # 方案对比类
    vision_topics: List[str] = field(default_factory=list)           # 愿景勾画类
    barrier_remove_topics: List[str] = field(default_factory=list)  # 顾虑消除类
    direct_need_topics: List[str] = field(default_factory=list)    # 直接需求类
    skill_tutorial_topics: List[str] = field(default_factory=list)  # 技巧干货类

    def to_dict(self) -> Dict[str, Any]:
        return {
            'portrait_id': self.portrait_id,
            'problem_type': self.problem_type,
            'audience_lock_topics': self.audience_lock_topics,
            'pain_amplify_topics': self.pain_amplify_topics,
            'solution_compare_topics': self.solution_compare_topics,
            'vision_topics': self.vision_topics,
            'barrier_remove_topics': self.barrier_remove_topics,
            'direct_need_topics': self.direct_need_topics,
            'skill_tutorial_topics': self.skill_tutorial_topics,
        }


@dataclass
class KeywordTopicResult:
    """关键词库+选题库生成结果"""
    success: bool = False
    portrait_id: str = ""
    error_message: str = ""
    keyword_library: Optional[PortraitKeywordLibrary] = None
    topic_library: Optional[PortraitTopicLibrary] = None
    raw_output: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'portrait_id': self.portrait_id,
            'error_message': self.error_message,
            'keyword_library': self.keyword_library.to_dict() if self.keyword_library else {},
            'topic_library': self.topic_library.to_dict() if self.topic_library else {},
        }


class KeywordTopicGenerator:
    """
    画像专属关键词库 + 选题库生成器

    核心理念：
    - 关键词来自画像的 problem_type 和 pain_points，不是业务词拼接
    - 每个画像独立生成，不共享"公用关键词"
    - 选题对应关键词，遵循五段式内容框架
    - 【重要】选题标题中必须包含核心业务词，避免泛化内容
    """

    # 全局限流：最多同时运行 N 个 LLM 调用
    _llm_semaphore: Optional['threading.BoundedSemaphore'] = None
    _semaphore_lock: 'threading.Lock' = None

    def __init__(self):
        self.llm = get_llm_service()
        # 延迟初始化信号量（线程安全单例）
        if KeywordTopicGenerator._llm_semaphore is None:
            import threading
            with threading.Lock():
                if KeywordTopicGenerator._llm_semaphore is None:
                    KeywordTopicGenerator._llm_semaphore = threading.BoundedSemaphore(5)
                    KeywordTopicGenerator._semaphore_lock = threading.Lock()

    def generate_for_portrait(
        self,
        core_business: str,
        portrait: Dict[str, Any],
        portrait_id: str = "",
    ) -> KeywordTopicResult:
        """
        为单个画像生成关键词库和选题库

        Args:
            core_business: 核心业务词（用于提示，不要作为关键词前缀）
            portrait: 画像字典，包含：
                - problem_type: 问题类型
                - problem_type_description: 问题类型描述
                - identity: 身份标签
                - pain_points: 核心痛点列表
                - pain_scenarios: 痛点场景列表
                - barriers: 顾虑列表
            portrait_id: 画像ID

        Returns:
            KeywordTopicResult: 生成结果
        """
        result = KeywordTopicResult()
        result.portrait_id = portrait_id

        try:
            problem_type = portrait.get('problem_type', '')
            problem_type_desc = portrait.get('problem_type_description', '')
            identity = portrait.get('identity', '')
            pain_points = portrait.get('pain_points', [])
            pain_scenarios = portrait.get('pain_scenarios', [])
            barriers = portrait.get('barriers', [])

            if not problem_type:
                result.error_message = "画像的 problem_type 不能为空"
                return result

            logger.info(f"[KeywordTopicGenerator] 为画像「{problem_type}」生成关键词库+选题库")
            logger.info(f"[KeywordTopicGenerator] 核心痛点: {pain_points[:3]}")

            # 构建 Prompt
            prompt = self._build_prompt(
                core_business=core_business,
                problem_type=problem_type,
                problem_type_desc=problem_type_desc,
                identity=identity,
                pain_points=pain_points,
                pain_scenarios=pain_scenarios,
                barriers=barriers,
            )

            # 调用 LLM
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=6000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            # 解析结果
            result = self._parse_result(response, portrait, portrait_id)

            if result.success:
                logger.info(
                    f"[KeywordTopicGenerator] 生成完成: 关键词={len(result.keyword_library.problem_type_keywords) + len(result.keyword_library.pain_point_keywords) + len(result.keyword_library.scene_keywords) + len(result.keyword_library.concern_keywords)}, "
                    f"选题={len(result.topic_library.audience_lock_topics) + len(result.topic_library.pain_amplify_topics) + len(result.topic_library.solution_compare_topics) + len(result.topic_library.vision_topics) + len(result.topic_library.barrier_remove_topics) + len(result.topic_library.direct_need_topics) + len(result.topic_library.skill_tutorial_topics)}"
                )

        except Exception as e:
            logger.error(f"[KeywordTopicGenerator] 生成异常: {str(e)}")
            result.error_message = f"生成异常: {str(e)}"

        return result

    def generate_batch(
        self,
        core_business: str,
        portraits: List[Dict[str, Any]],
        portrait_ids: List[str] = None,
    ) -> List[KeywordTopicResult]:
        """
        批量为多个画像生成关键词库和选题库（并行执行）

        Args:
            core_business: 核心业务词
            portraits: 画像列表
            portrait_ids: 画像ID列表（可选，默认用 A/B/C...）

        Returns:
            List[KeywordTopicResult]: 每个画像的生成结果
        """
        ids = portrait_ids or [chr(65 + i) for i in range(len(portraits))]

        def gen_one(idx: int, portrait: Dict[str, Any]) -> tuple:
            pid = ids[idx] if idx < len(ids) else chr(65 + idx)
            logger.info(f"[KeywordTopicGenerator] 批量生成画像 {pid}: {portrait.get('problem_type', '')}")
            result = self.generate_for_portrait(
                core_business=core_business,
                portrait=portrait,
                portrait_id=pid,
            )
            return idx, result

        results = [None] * len(portraits)
        max_workers = min(5, len(portraits))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(gen_one, i, p): i
                for i, p in enumerate(portraits)
            }
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    _, result = future.result()
                    results[idx] = result
                except Exception as e:
                    logger.error("[KeywordTopicGenerator] 画像 %s 生成异常: %s", ids[idx], str(e))
                    from .keyword_topic_generator import KeywordTopicResult
                    results[idx] = KeywordTopicResult()

        return results

    def _build_prompt(
        self,
        core_business: str,
        problem_type: str,
        problem_type_desc: str,
        identity: str,
        pain_points: List[str],
        pain_scenarios: List[str],
        barriers: List[str],
    ) -> str:
        """构建生成 Prompt"""

        pain_points_str = "\n".join([f"- {p}" for p in pain_points]) if pain_points else "（未提供）"
        pain_scenarios_str = "\n".join([f"- {s}" for s in pain_scenarios]) if pain_scenarios else "（未提供）"
        barriers_str = "\n".join([f"- {b}" for b in barriers]) if barriers else "（未提供）"

        prompt = f"""你是关键词库和选题库生成专家。

请基于以下画像信息，生成该画像专属的**关键词库**和**选题库**。

=== 画像信息 ===

核心业务：{core_business}
问题类型：{problem_type}
问题类型描述：{problem_type_desc}
身份标签：{identity}

核心痛点：
{pain_points_str}

痛点场景：
{pain_scenarios_str}

顾虑障碍：
{barriers_str}

=== 【核心原则】 ===

1. **关键词来自问题，选题必须包含核心业务词**
   - 关键词：从画像的 pain_points 和 pain_scenarios 出发，**不要**以「{core_business}」作为关键词前缀
   - 选题：**必须**在标题中包含「{core_business}」或相关业务词，让用户一看就知道是针对什么产品/服务

   ✅ 选题正确示例（含核心业务词）：
   - 「{core_business}」全套服务多少钱
   - 「{core_business}」怎么选才不被坑
   - 「{core_business}」加工注意这几点
   - 「{core_business}」定制要注意什么

   ❌ 选题错误示例（缺少核心业务词）：
   - 防腐剂对身体健康的威胁，后果很严重（没有出现业务词）
   - 怎么判断产品是否合格（过于泛化）
   - 服务商的选择标准（没有指明是什么服务）

2. **画像关键词必须围绕该画像的问题类型**
   - 问题类型={problem_type}，关键词必须围绕这个类型的问题
   - 不要生成其他画像的问题

3. **选题必须对应关键词**
   - 选题从关键词出发，不是凭空想象
   - 每个选题能回答至少一个关键词代表的问题

4. **关键词长度控制**
   - 关键词：6-12个字，越短越好
   - 选题：10-25个字

=== 【关键词库生成】 ===

**关键词结构（4类，共30个）：**

1. **问题类型关键词**（10个）
   目的：该画像面临的具体问题
   要求：围绕 problem_type 生成，直接是问题本身
   格式：疑问词 + 问题

2. **痛点关键词**（10个）
   目的：该画像的核心痛点
   要求：围绕 pain_points 生成，是用户最关心的问题
   格式：问题现象 + 怎么办/怎么解决

3. **场景关键词**（5个）
   目的：该画像的具体使用场景
   要求：围绕 pain_scenarios 生成
   格式：场景 + 问题

4. **顾虑关键词**（5个）
   目的：该画像的担忧和疑虑
   要求：围绕 barriers 生成
   格式：顾虑 + 怎么办/安全吗/有风险吗

=== 【选题库生成】 ===

**选题结构（7类，基于五段式内容框架）：**
**【重要】每个选题标题中必须包含核心业务「{core_business}」或相关业务词，让用户一眼看出是针对什么产品/服务。**

1. **受众锁定类**（8个）
   目的：让人立刻判断"这说的是不是我"
   公式：核心业务「{core_business}」+ 人群特征 + 问题
   标题示例：「{core_business}」找上门，你属于哪种情况
   注意：标题中必须有「{core_business}」或业务同义词

2. **痛点放大类**（10个）
   目的：让人意识到"我的问题有多严重"
   公式：核心业务「{core_business}」+ 痛点 + 后果
   标题示例：做「{core_business}」的人，最怕听到这句话
   注意：标题中必须有「{core_business}」或业务同义词

3. **方案对比类**（8个）
   目的：突出"为什么选你不选别人"
   公式：核心业务「{core_business}」+ 方案 + 优势
   标题示例：「{core_business}」选对方法，省心又省钱
   注意：标题中必须有「{core_business}」或业务同义词

4. **愿景勾画类**（8个）
   目的：让用户代入"用之后会变多好"
   公式：核心业务「{core_business}」+ 使用后 + 改变
   标题示例：「{core_business}」做对了，效果翻倍
   注意：标题中必须有「{core_business}」或业务同义词

5. **顾虑消除类**（8个）
   目的：打消"用了之后有问题怎么办"
   公式：核心业务「{core_business}」+ 顾虑 + 解答
   标题示例：「{core_business}」常见顾虑，一次说清楚
   注意：标题中必须有「{core_business}」或业务同义词

6. **直接需求类**（8个）
   目的：画像专属的精准需求
   公式：核心业务「{core_business}」+ 场景 + 需求
   标题示例：「{core_business}」客户最常问的几个问题
   注意：标题中必须有「{core_business}」或业务同义词

7. **技巧干货类**（8个）
   目的：画像专属场景的操作教程
   公式：核心业务「{core_business}」+ 人群 + 场景 + 教程
   标题示例：「{core_business}」加工技巧，学会少走弯路
   注意：标题中必须有「{core_business}」或业务同义词

=== 【输出格式】 ===

请严格按以下JSON格式输出，不要输出任何其他内容：

**【关键】每个选题标题中必须包含「{core_business}」或相关业务词，否则选题无效。**

{{
    "keyword_library": {{
        "problem_type_keywords": [
            "XX问题怎么处理",
            "XX情况怎么解决",
            "XX选择哪个更好"
        ],
        "pain_point_keywords": [
            "XX问题困扰怎么办",
            "XX痛点如何解决"
        ],
        "scene_keywords": [
            "遇到XX情况怎么处理",
            "XX场景问题"
        ],
        "concern_keywords": [
            "XX风险大吗",
            "XX有保障吗"
        ]
    }},
    "topic_library": {{
        "audience_lock_topics": [
            "「{core_business}」找上门，你属于哪种情况",
            "注意！做「{core_business}」的人最容易踩的坑"
        ],
        "pain_amplify_topics": [
            "做「{core_business}」的人，最怕听到这句话",
            "「{core_business}」处理顺序做错一步，后果很严重"
        ],
        "solution_compare_topics": [
            "「{core_business}」选对方法，省心又省钱",
            "选A还是选B？看完你就明白了"
        ],
        "vision_topics": [
            "「{core_business}」做对了，效果翻倍",
            "掌握这个技巧，「{core_business}」轻松搞定"
        ],
        "barrier_remove_topics": [
            "「{core_business}」常见顾虑，一次说清楚",
            "「{core_business}」真的有保障吗"
        ],
        "direct_need_topics": [
            "「{core_business}」客户最常问的几个问题",
            "「{core_business}」怎么处理才不会出错"
        ],
        "skill_tutorial_topics": [
            "「{core_business}」加工技巧，学会少走弯路",
            "「{core_business}」正确打开方式"
        ]
    }}
}}

=== 【强制约束】 ===

1. 关键词库：问题类型关键词10个、痛点关键词10个、场景关键词5个、顾虑关键词5个，共30个
2. 选题库：受众锁定8个、痛点放大10个、方案对比8个、愿景勾画8个、顾虑消除8个、直接需求8个、技巧干货8个，共58个
3. **【最高优先级】每个选题标题中必须包含「{core_business}」或业务同义词**
   - 示例（核心业务=灌香肠加工）：
     - ✅ 灌香肠加工怎么选才不被坑
     - ✅ 灌香肠加工注意这几点
     - ❌ 防腐剂对身体健康的威胁，后果很严重（缺少业务词，无效）
     - ❌ 服务商的选择标准（过于泛化，无效）
4. 关键词禁止以核心业务「{core_business}」开头！（选标题不受此限制）
5. 关键词必须是真实用户搜索词，不是产品介绍
6. 选题必须能回答关键词代表的问题
7. 选题标题要有吸引力，符合短视频/图文的传播特点

请开始生成："""

        return prompt

    def _parse_result(
        self,
        response: str,
        portrait: Dict[str, Any],
        portrait_id: str,
    ) -> KeywordTopicResult:
        """解析 LLM 返回结果"""

        result = KeywordTopicResult()
        result.portrait_id = portrait_id
        problem_type = portrait.get('problem_type', '')

        # 解析 JSON
        try:
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            # json.loads('null') 会返回 Python None，需要兜底
            if data is None:
                logger.warning("[KeywordTopicGenerator] LLM返回了null JSON")
                result.error_message = "LLM返回了null JSON"
                return result
            result.raw_output = data

        except json.JSONDecodeError:
            logger.warning("[KeywordTopicGenerator] JSON解析失败，尝试修复")
            data = self._try_fix_json(response)
            if not data or not isinstance(data, dict):
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

        # 解析关键词库
        kw_lib_data = data.get('keyword_library') or {}
        kw_lib = PortraitKeywordLibrary(
            portrait_id=portrait_id,
            problem_type=problem_type,
            problem_type_keywords=kw_lib_data.get('problem_type_keywords', []),
            pain_point_keywords=kw_lib_data.get('pain_point_keywords', []),
            scene_keywords=kw_lib_data.get('scene_keywords', []),
            concern_keywords=kw_lib_data.get('concern_keywords', []),
        )
        result.keyword_library = kw_lib

        # 解析选题库
        topic_lib_data = data.get('topic_library') or {}
        topic_lib = PortraitTopicLibrary(
            portrait_id=portrait_id,
            problem_type=problem_type,
            audience_lock_topics=topic_lib_data.get('audience_lock_topics', []),
            pain_amplify_topics=topic_lib_data.get('pain_amplify_topics', []),
            solution_compare_topics=topic_lib_data.get('solution_compare_topics', []),
            vision_topics=topic_lib_data.get('vision_topics', []),
            barrier_remove_topics=topic_lib_data.get('barrier_remove_topics', []),
            direct_need_topics=topic_lib_data.get('direct_need_topics', []),
            skill_tutorial_topics=topic_lib_data.get('skill_tutorial_topics', []),
        )
        result.topic_library = topic_lib

        result.success = True
        return result

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的 JSON"""
        import re

        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            try:
                return json.loads(json_str)
            except:
                pass

            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)

            try:
                return json.loads(json_str)
            except:
                pass

        return None


# ============================================================
# 便捷函数
# ============================================================

def generate_keywords_topics_for_portrait(
    core_business: str,
    portrait: Dict[str, Any],
    portrait_id: str = "",
) -> KeywordTopicResult:
    """
    便捷函数：为单个画像生成关键词库和选题库

    使用方式：
        from services.keyword_topic_generator import generate_keywords_topics_for_portrait

        result = generate_keywords_topics_for_portrait(
            core_business='XX产品定制服务',
            portrait={
                'problem_type': '价格困惑型',
                'pain_points': ['XX价格多少合适', '怎么选最划算'],
                'pain_scenarios': ['初次接触时', '对比方案时'],
                'barriers': ['担心价格不透明'],
            },
            portrait_id='A',
        )

        if result.success:
            print(result.keyword_library.to_dict())
            print(result.topic_library.to_dict())
    """
    generator = KeywordTopicGenerator()
    return generator.generate_for_portrait(
        core_business=core_business,
        portrait=portrait,
        portrait_id=portrait_id,
    )


def generate_keywords_topics_batch(
    core_business: str,
    portraits: List[Dict[str, Any]],
    portrait_ids: List[str] = None,
) -> List[KeywordTopicResult]:
    """
    便捷函数：批量为多个画像生成关键词库和选题库

    使用方式：
        from services.keyword_topic_generator import generate_keywords_topics_batch

        results = generate_keywords_topics_batch(
            core_business='XX产品定制服务',
            portraits=[portrait_a, portrait_b, portrait_c],
            portrait_ids=['A', 'B', 'C'],
        )

        for r in results:
            print(r.success, r.portrait_id)
    """
    generator = KeywordTopicGenerator()
    return generator.generate_batch(
        core_business=core_business,
        portraits=portraits,
        portrait_ids=portrait_ids,
    )
