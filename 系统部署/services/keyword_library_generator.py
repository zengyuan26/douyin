"""
关键词库生成服务

功能：
1. 基于业务描述，生成精准的关键词库（原子零件 + 问句示范）
2. 生成问题类型标签
3. 区分蓝海/红海关键词

关键词结构（新版）：
- atom_keywords：原子关键词（组成问句的零件）
  - 人群标签：定位谁有这个痛点
  - 场景/时机：定位问题发生的具体情境
  - 症状/困境：描述用户当前的苦恼
  - 顾虑/疑问：用户搜索时的问题词
- red_ocean_keywords：红海关键词
  - 品类大词、通用需求词、品牌词
- question_samples：问句示范
  - pre_questions：前置问句（用户遇到问题但还没找到解决方案）
  - post_questions：后置问句（用户用了产品后发现新问题）

使用方式：
from services.keyword_library_generator import KeywordLibraryGenerator, KeywordLibraryResult

generator = KeywordLibraryGenerator()
result = generator.generate(
    business_info={'business_description': '卖奶粉', 'industry': '奶粉'},
    core_business='特殊配方奶粉',
    max_keywords=200
)

result.keyword_library  # 关键词库（新结构）
result.question_samples  # 问句示范
result.problem_types    # 问题类型
"""

import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class ProblemType:
    """问题类型（画像分类标签）"""
    type_name: str                   # 类型名称，如"肠道问题"
    description: str                 # 描述
    target_audience: str             # 目标人群
    keywords: List[str]               # 关联关键词
    scene_keywords: List[str] = field(default_factory=list)  # 场景关键词列表（用于选题扩展）


@dataclass
class QuestionSample:
    """问句示范（前置/后置）"""
    question: str           # 问句
    question_type: str      # pre（前置）/ post（后置）
    components: Dict[str, str] = field(default_factory=dict)  # 组成成分：{人群: "...", 场景: "...", 症状: "...", 解决方案: "..."}


@dataclass
class KeywordLibraryResult:
    """关键词库生成结果"""
    success: bool = False
    error_message: str = ""

    # 核心产出
    keyword_library: Dict[str, Any] = field(default_factory=dict)
    problem_types: List[ProblemType] = field(default_factory=list)
    question_samples: List[QuestionSample] = field(default_factory=list)  # 新增：问句示范

    # 原始LLM输出（用于调试）
    raw_output: Dict[str, Any] = field(default_factory=dict)

    # 统计信息
    total_keywords: int = 0
    blue_ocean_keywords: int = 0
    red_ocean_keywords: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'success': self.success,
            'error_message': self.error_message,
            'keyword_library': self.keyword_library,
            'problem_types': [
                {
                    'type_name': pt.type_name,
                    'description': pt.description,
                    'target_audience': pt.target_audience,
                    'keywords': pt.keywords,
                    'scene_keywords': pt.scene_keywords,
                }
                for pt in self.problem_types
            ],
            'question_samples': [
                {
                    'question': qs.question,
                    'question_type': qs.question_type,
                    'components': qs.components,
                }
                for qs in self.question_samples
            ],
            'total_keywords': self.total_keywords,
            'blue_ocean_keywords': self.blue_ocean_keywords,
            'red_ocean_keywords': self.red_ocean_keywords,
        }


class KeywordLibraryGenerator:
    """
    关键词库生成器

    核心能力：
    1. 基于选定的业务方向，生成精准的关键词库
    2. 生成问题类型标签
    3. 区分蓝海/红海关键词

    与 MarketAnalyzer 的区别：
    - MarketAnalyzer：一次性生成蓝海机会 + 关键词库（快速但不精准）
    - KeywordLibraryGenerator：基于已选定的业务方向，精准生成关键词库
    """

    def __init__(self):
        self.llm = get_llm_service()

    def generate(
        self,
        business_info: Dict[str, Any],
        core_business: str = None,
        max_keywords: int = 200,
        blue_ocean_opportunity: str = None,
    ) -> KeywordLibraryResult:
        """
        生成关键词库

        Args:
            business_info: 业务信息
                - business_description: 原始业务描述
                - industry: 行业
                - business_type: 业务类型 (product/service)
            core_business: 核心业务词（可选，默认从业务描述提取）
            max_keywords: 最大关键词数量
            blue_ocean_opportunity: 蓝海机会描述（可选，用于指导关键词生成方向）

        Returns:
            KeywordLibraryResult: 生成结果
        """
        result = KeywordLibraryResult()

        try:
            # 参数提取
            business_desc = business_info.get('business_description', '')
            industry = business_info.get('industry', '')
            business_type = business_info.get('business_type', 'product')

            if not business_desc:
                result.error_message = "业务描述不能为空"
                return result

            # 获取核心业务词：优先使用传入的 core_business，其次从业务描述提取
            keyword_core = core_business
            if not keyword_core:
                # 从业务描述中提取核心业务词
                keyword_core = self._extract_core_business(business_desc, industry)

            if not keyword_core:
                result.error_message = "核心业务不能为空"
                return result

            # 生成Prompt
            prompt = self._build_keyword_prompt(
                business_desc=business_desc,
                industry=industry,
                business_type=business_type,
                keyword_core=keyword_core,
                max_keywords=max_keywords,
                blue_ocean_opportunity=blue_ocean_opportunity,
            )

            # 调用LLM
            logger.info("[KeywordLibraryGenerator] 开始调用LLM...")
            logger.info(f"[KeywordLibraryGenerator] 核心业务: {keyword_core}")
            if blue_ocean_opportunity:
                logger.info(f"[KeywordLibraryGenerator] 蓝海机会: {blue_ocean_opportunity}")

            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.7, max_tokens=5000)

            if not response or not response.strip():
                result.error_message = "LLM调用返回为空"
                return result

            # 解析结果
            result = self._parse_result(response, result)

            # 过滤关键词
            if result.keyword_library:
                result.keyword_library = self._filter_keywords(result.keyword_library, keyword_core)

            # 统计关键词
            if result.keyword_library:
                all_kw = []
                for cat in result.keyword_library.get('categories', []):
                    all_kw.extend(cat.get('keywords', []))
                result.total_keywords = len(all_kw)
                result.blue_ocean_keywords = sum(
                    1 for cat in result.keyword_library.get('categories', [])
                    if cat.get('market_type') == 'blue_ocean'
                    for kw in cat.get('keywords', [])
                )
                result.red_ocean_keywords = result.total_keywords - result.blue_ocean_keywords

            result.success = True
            logger.info(
                "[KeywordLibraryGenerator] 生成完成: 问题类型=%d, 关键词=%d (蓝海=%d, 红海=%d), 问句=%d",
                len(result.problem_types),
                result.total_keywords,
                result.blue_ocean_keywords,
                result.red_ocean_keywords,
                len(result.question_samples),
            )

        except Exception as e:
            logger.error("[KeywordLibraryGenerator] 生成异常: %s", str(e))
            result.error_message = f"生成异常: {str(e)}"

        return result

    def _build_keyword_prompt(
        self,
        business_desc: str,
        industry: str,
        business_type: str,
        keyword_core: str,
        max_keywords: int,
        blue_ocean_opportunity: str = None,
    ) -> str:
        """构建关键词库生成Prompt（新结构：原子零件 + 问句示范）"""

        # 蓝海机会引导语
        blue_ocean_hint = ""
        if blue_ocean_opportunity:
            blue_ocean_hint = f"\n=== 蓝海机会背景 ===\n用户已选择以下蓝海机会：「{blue_ocean_opportunity}」\n请围绕这个细分方向生成关键词，重点挖掘该方向下的细分人群、场景和痛点。\n"

        # 业务类型适配
        business_type_hint = ""
        if business_type == 'product':
            business_type_hint = "业务为消费品，重点关注：使用者症状、购买者顾虑、选择对比"
        elif business_type == 'local_service':
            business_type_hint = "业务为本地服务，重点关注：服务场景、时效顾虑、信任问题"
        elif business_type == 'enterprise':
            business_type_hint = "业务为企业服务，重点关注：决策流程、ROI顾虑、供应商选择"
        else:
            business_type_hint = "业务为个人服务，重点关注：使用场景、效果顾虑、服务选择"

        # 数量计算
        n_crowd = int(max_keywords * 0.12)
        n_scene = int(max_keywords * 0.12)
        n_symptom = int(max_keywords * 0.18)
        n_concern = int(max_keywords * 0.08)
        n_category = int(max_keywords * 0.05)
        n_brand = int(max_keywords * 0.05)
        n_generic = int(max_keywords * 0.10)

        prompt = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成精准的关键词库和问题类型。

=== 业务信息 ===
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
业务类型：{business_type_hint}{blue_ocean_hint}

=== 核心业务（必须围绕此词生成关键词）===
{keyword_core}

=== 生成任务 ===

1. **问题类型生成**：基于核心业务，生成3-6个问题类型
   - 一个类型对应一类痛点
   - 每个类型必须生成5-10个场景关键词，用于后续画像生成

2. **关键词库生成**（新版结构：原子零件 + 问句示范）

一、原子关键词（组成问句的零件）

1. **人群标签**（{n_crowd}个）：定位谁有这个痛点
   - 格式：年龄/体质/阶段/身份 + 核心业务
   - 举例：乳糖不耐受宝宝、早产儿、剖腹产宝宝、断奶期宝宝
   - 注意：不要太泛（宝宝、婴儿、儿童是泛词）

2. **场景/时机**（{n_scene}个）：定位问题发生的具体情境
   - 格式：具体情境 + 核心业务
   - 举例：断奶期转奶、夜醒频繁、高铁出行、添加辅食后、打疫苗后
   - 注意：要有具体时机，不要太泛

3. **症状/困境**（{n_symptom}个）：描述用户当前的苦恼
   - 格式：具体症状 + 核心业务
   - 举例：拉肚子不长肉、喝了还哭闹、过敏起疹子、拒奶胀气
   - 注意：症状要可感知，不要太模糊

4. **顾虑/疑问**（{n_concern}个）：用户搜索时的问题词
   - 格式：怎么办/怎么/哪个/能否
   - 举例：怎么办、怎么回事、怎么选、能不能、会不会

二、红海关键词

5. **品类大词**（{n_category}个，允许填空）
   - 核心品类：{keyword_core}

6. **品牌词**（{n_brand}个，允许填空）
   - 竞品品牌

7. **通用需求词**（{n_generic}个）
   - 格式：核心业务 + 推荐/哪个好/多少钱
   - 举例：{keyword_core}推荐、{keyword_core}哪个牌子好、{keyword_core}多少钱

三、问句示范（选题种子）

【前置问句】：用户遇到问题但还没找到解决方案时会问什么
- 模板：「人群」+「症状」+「顾虑」 → "乳糖不耐受宝宝拉肚子怎么办"
- 模板：「场景」+「人群」+「困境」 → "早产儿断奶期怎么追重"
- 模板：「顾虑」+「人群」+「品类」 → "深度水解奶粉太苦宝宝不喝怎么办"

【后置问句】：用户用了产品后发现新问题会问什么
- 模板：「产品」+「使用后症状」 → "喝了氨基酸奶粉还过敏怎么回事"
- 模板：「转奶」+「症状」 → "深度水解转普通奶粉拉肚子正常吗"
- 模板：「长期使用」+「顾虑」 → "无乳糖奶粉可以一直喝吗"

=== 输出格式 ===
请严格按以下JSON格式输出，不要输出任何其他内容：

{{
    "problem_types": [
        {{
            "type_name": "过敏担忧",
            "description": "担心宝宝对普通奶粉蛋白过敏，不知道如何选择特殊配方",
            "target_audience": "有家族过敏史或宝宝已出现过敏症状的新手父母",
            "scene_keywords": [
                "宝宝喝普通奶粉起疹子怎么办",
                "蛋白过敏宝宝怎么选奶粉",
                "水解奶粉味道苦宝宝不喝怎么办"
            ],
            "keywords": ["特殊配方奶粉", "水解奶粉", "抗过敏奶粉"]
        }}
    ],
    "keyword_library": {{
        "keyword_core": "{keyword_core}",
        "categories": [
            {{
                "category_name": "人群标签",
                "category_desc": "定位谁有这个痛点",
                "keywords": [
                    "乳糖不耐受宝宝",
                    "早产儿",
                    "剖腹产宝宝",
                    "断奶期宝宝"
                ],
                "market_type": "blue_ocean"
            }},
            {{
                "category_name": "场景/时机",
                "category_desc": "定位问题发生的具体情境",
                "keywords": [
                    "断奶期转奶",
                    "夜醒频繁",
                    "添加辅食后",
                    "打疫苗后"
                ],
                "market_type": "blue_ocean"
            }},
            {{
                "category_name": "症状/困境",
                "category_desc": "描述用户当前的苦恼",
                "keywords": [
                    "拉肚子不长肉",
                    "喝了还哭闹",
                    "过敏起疹子"
                ],
                "market_type": "blue_ocean"
            }},
            {{
                "category_name": "顾虑/疑问",
                "category_desc": "用户搜索时的问题词",
                "keywords": [
                    "怎么办",
                    "怎么回事",
                    "怎么选",
                    "能不能",
                    "会不会"
                ],
                "market_type": "blue_ocean"
            }},
            {{
                "category_name": "品类大词",
                "category_desc": "核心品类词",
                "keywords": ["{keyword_core}"],
                "market_type": "red_ocean"
            }},
            {{
                "category_name": "品牌词",
                "category_desc": "竞品品牌",
                "keywords": [],
                "market_type": "red_ocean"
            }},
            {{
                "category_name": "通用需求词",
                "category_desc": "通用搜索意图词",
                "keywords": ["{keyword_core}推荐", "{keyword_core}哪个牌子好"],
                "market_type": "red_ocean"
            }}
        ]
    }},
    "question_samples": {{
        "pre_questions": [
            {{
                "question": "乳糖不耐受宝宝拉肚子怎么办",
                "components": {{"人群": "乳糖不耐受宝宝", "症状": "拉肚子", "顾虑": "怎么办"}}
            }},
            {{
                "question": "早产儿断奶期怎么追重",
                "components": {{"人群": "早产儿", "场景": "断奶期", "困境": "追重"}}
            }},
            {{
                "question": "深度水解奶粉太苦宝宝不喝怎么办",
                "components": {{"顾虑": "太苦", "产品": "深度水解奶粉", "困境": "不喝", "疑问": "怎么办"}}
            }}
        ],
        "post_questions": [
            {{
                "question": "喝了氨基酸奶粉还过敏怎么回事",
                "components": {{"产品": "氨基酸奶粉", "症状": "还过敏"}}
            }},
            {{
                "question": "深度水解转普通奶粉拉肚子正常吗",
                "components": {{"场景": "深度水解转普通奶粉", "症状": "拉肚子"}}
            }},
            {{
                "question": "无乳糖奶粉可以一直喝吗",
                "components": {{"产品": "无乳糖奶粉", "顾虑": "可以一直喝吗"}}
            }}
        ]
    }}
}}

重要说明：
1. 关键词必须是真实用户搜索词，体现具体搜索意图
2. 人群标签要具体（体质/年龄/阶段），场景要具体（时机/情境），症状要可感知
3. 前置问句覆盖"发现→搜索→比较"全链路，后置问句覆盖"使用→问题→转化"全链路
4. 每个分类关键词数量不得少于规定数量
5. 品牌词如果没有具体品牌可以填空数组
6. 蓝海关键词（人群/场景/症状/顾虑）应占总量60%以上

请开始生成："""

        return prompt

        # 问题类型分类指引（通用版本，无行业示例）
        problem_type_guide = """
【问题类型分类指引】（重要！用于指导内容选题和画像生成）

每个问题类型需要包含：
1. type_name：类型名称（2-4个字，如"时效担忧"、"信任顾虑"）
2. description：类型描述（一句话说明）
3. target_audience：目标人群
4. scene_keywords：场景关键词列表（5-15个，用于选题扩展，覆盖该类型的多种场景）
5. keywords：内容关键词（用于SEO/投放）

=== 场景关键词设计原则 ===
- 场景关键词是用户搜索的具体问题/需求
- 同一个问题类型下，场景关键词应该有差异性
- 场景关键词决定选题的广度，内容不要过于垂直单一

=== 示例（本地服务行业） ===

问题类型1: 时效担忧
  - description: 服务响应时间和时效相关顾虑
  - target_audience: 需要快速响应的客户
  - scene_keywords: ["需要紧急上门", "周末能约吗", "晚上下班后能服务吗", "最快多久能到", "临时需要加急", "预约要等多久", "工作日没时间"]
  - keywords: ["上门服务", "时效", "预约", "响应"]

问题类型2: 信任顾虑
  - description: 服务质量和专业性相关担忧
  - target_audience: 首次尝试服务的客户
  - scene_keywords: ["服务靠谱吗", "会不会乱收费", "有售后保障吗", "专业吗", "经验怎么样", "用的什么材料", "有没有资质"]
  - keywords: ["服务", "质量", "保障", "专业"]
"""

        # 关键词库分类 - 核心要求
        keyword_guide = """
【关键词库生成要求】
基于核心业务「{keyword_core}」，生成精准的关键词库。

【强制要求 - 数量约束】
每个分类必须严格按照以下数量生成，禁止少于指定数量：
- 细分人群词：{crowd}个
- 细分场景词：{scene}个
- 细分痛点词：{pain_point}个
- 长尾问题词：{long_tail}个
- 品类大词：{category}个（允许填空数组）
- 品牌词：{brand}个（允许填空数组）
- 通用需求词：{generic}个

【什么是真正的"细分"关键词？】

细分人群词 = 细分维度（年龄/职业/体质/阶段） + 核心业务
  ✅ "6个月宝宝奶粉推荐"、"剖腹产宝宝吃什么奶粉好"、"乳糖不耐受宝宝奶粉"、"早产儿追重奶粉"
  ❌ "奶粉推荐"、"宝宝奶粉"、"婴儿奶粉"
  ❌ "奶粉冲泡方法"（这是场景词，不是人群词）

细分场景词 = 具体使用场景/时机 + 核心业务
  ✅ "断奶期奶粉怎么选"、"宝宝转奶怎么过渡"、"高铁上宝宝饿了怎么办"、"夜醒频繁要换奶粉吗"
  ❌ "奶粉喂养时间"（太泛，缺乏具体情境）
  ❌ "奶粉冲泡注意事项"（这更偏向问题词，不是场景词）

细分痛点词 = 具体担忧/问题 + 核心业务
  ✅ "宝宝喝奶粉不长肉怎么办"、"奶粉腥味太重宝宝不爱喝"、"换新奶粉宝宝拉肚子"、"奶粉挂壁是不是质量有问题"
  ❌ "奶粉宝宝过敏"（缺少"怎么办"的搜索意图）
  ❌ "奶粉宝宝不喝"（过于简短，缺乏具体性）

长尾问题词 = 用户实际搜索时的完整问句
  ✅ "1岁宝宝奶粉段位怎么选择"、"深度水解奶粉要喝多久才能换普通奶粉"、"有机奶粉和普通奶粉营养差别大吗"
  ✅ "早产儿奶粉吃到几个月转普通奶粉"、"宝宝换了奶粉牌子便秘是怎么回事"
  ❌ "奶粉宝宝长牙齿"（缺少搜索意图）
  ❌ "奶粉宝宝生长发育"（用户不会这样搜）

【关于「特殊配方奶粉」的关键词生成指导】
核心业务 = 特殊配方奶粉，关键词必须体现以下细分方向：
- 特殊配方类型细分：深度水解、适度水解、氨基酸、无乳糖、部分水解
- 宝宝体质细分：乳糖不耐受、蛋白过敏、早产/低体重、追重/偏瘦、乳糖酶缺乏
- 阶段细分：断奶期、转奶期、厌奶期、辅食添加期
- 问题导向细分：不长肉、拉肚子、过敏症状、拒奶、胀气

错误示范（太平淡）：
- "特殊配方奶粉推荐" — 太泛
- "奶粉怎么选择" — 脱离了特殊配方语境

正确示范（真细分）：
- "乳糖不耐受宝宝喝什么奶粉"
- "深度水解奶粉哪个品牌好"
- "蛋白过敏宝宝奶粉怎么选"
- "无乳糖奶粉长期喝可以吗"
- "早产儿追赶生长吃什么奶粉"
""".format(
            keyword_core=keyword_core,
            total_count=max_keywords,
            crowd=int(max_keywords * 0.25),
            scene=int(max_keywords * 0.20),
            pain_point=int(max_keywords * 0.20),
            long_tail=int(max_keywords * 0.15),
            category=int(max_keywords * 0.05),
            brand=int(max_keywords * 0.05),
            generic=int(max_keywords * 0.10),
        )

        # 业务类型适配
        business_type_hint = ""
        if business_type == 'product':
            business_type_hint = "业务为消费品，重点关注：使用者症状、购买者顾虑、选择对比"
        elif business_type == 'local_service':
            business_type_hint = "业务为本地服务，重点关注：服务场景、时效顾虑、信任问题"
        elif business_type == 'enterprise':
            business_type_hint = "业务为企业服务，重点关注：决策流程、ROI顾虑、供应商选择"
        else:
            business_type_hint = "业务为个人服务，重点关注：使用场景、效果顾虑、服务选择"

        prompt = f"""你是关键词库生成专家。请基于核心业务「{keyword_core}」，生成精准的关键词库和问题类型。

=== 业务信息 ===
原始业务描述：{business_desc}
行业：{industry or '根据业务描述推断'}
业务类型：{business_type_hint}

=== 核心业务（必须围绕此词生成关键词）===
{keyword_core}

这是你的核心业务词，所有关键词都必须围绕这个业务生成。

=== 生成任务 ===

1. **问题类型生成**：基于核心业务，生成3-6个问题类型
   - 一个类型对应一类痛点
   - **【重要】每个类型必须生成5-10个场景关键词，用于后续画像生成**
{problem_type_guide}

2. **关键词库生成**（区分蓝海/红海）：
{keyword_guide}

=== 输出格式 ===
请严格按以下JSON格式输出，不要输出任何其他内容：

{{
    "problem_types": [
        {{
            "type_name": "过敏担忧",
            "description": "担心宝宝对普通奶粉蛋白过敏，不知道如何选择特殊配方",
            "target_audience": "有家族过敏史或宝宝已出现过敏症状的新手父母",
            "scene_keywords": [
                "宝宝喝普通奶粉起疹子怎么办",
                "蛋白过敏宝宝怎么选奶粉",
                "适度水解奶粉能预防过敏吗",
                "氨基酸奶粉和深度水解奶粉区别",
                "宝宝过敏症状好了能转普通奶粉吗",
                "有湿疹的宝宝喝什么奶粉",
                "水解奶粉味道苦宝宝不喝怎么办"
            ],
            "keywords": ["特殊配方奶粉", "水解奶粉", "抗过敏奶粉", "低敏奶粉"]
        }},
        {{
            "type_name": "不长肉",
            "description": "宝宝喝奶粉体重增长不理想，担心营养不够",
            "target_audience": "宝宝偏瘦、体重增长缓慢的家长",
            "scene_keywords": [
                "宝宝喝奶粉不长肉怎么回事",
                "早产儿追赶体重吃什么奶粉好",
                "一岁宝宝偏瘦奶粉推荐",
                "奶粉宝宝体重不达标怎么办",
                "高热量奶粉能让宝宝长肉吗",
                "脾胃虚弱的宝宝喝什么奶粉",
                "宝宝光吃奶粉不长肉是奶粉问题吗"
            ],
            "keywords": ["追重奶粉", "长肉奶粉", "早产儿奶粉", "高能量奶粉"]
        }}
    ],
    "keyword_library": {{
        "total_count": {max_keywords},
        "keyword_core": "{keyword_core}",
        "categories": [
            {{
                "category_name": "细分人群词",
                "keywords": [
                    "6个月宝宝奶粉推荐",
                    "剖腹产宝宝吃什么奶粉好",
                    "乳糖不耐受宝宝奶粉怎么选",
                    "早产儿追赶生长奶粉",
                    "蛋白过敏宝宝专用奶粉",
                    "体弱多病宝宝增强体质奶粉",
                    "脾胃虚弱宝宝好消化奶粉",
                    "厌奶期宝宝开胃奶粉",
                    "混合喂养宝宝奶粉推荐",
                    "断奶期宝宝奶粉过渡"
                ],
                "market_type": "blue_ocean",
                "proportion": 0.25
            }},
            {{
                "category_name": "细分场景词",
                "keywords": [
                    "断奶期怎么选合适奶粉",
                    "宝宝转奶怎么过渡最安全",
                    "高铁上宝宝饿了怎么办",
                    "夜醒频繁要换奶粉吗",
                    "宝宝厌奶期持续多久",
                    "宝宝打疫苗前后能换奶粉吗",
                    "换季宝宝拉肚子要换奶粉吗",
                    "宝宝上火了换什么奶粉",
                    "宝宝便秘是奶粉的原因吗",
                    "宝宝发烧期间喂养注意什么"
                ],
                "market_type": "blue_ocean",
                "proportion": 0.20
            }},
            {{
                "category_name": "细分痛点词",
                "keywords": [
                    "宝宝喝奶粉不长肉怎么办",
                    "奶粉腥味太重宝宝不爱喝怎么办",
                    "换新奶粉宝宝拉肚子怎么回事",
                    "奶粉挂壁是不是质量有问题",
                    "深度水解奶粉太苦宝宝不喝",
                    "宝宝喝完奶粉嘴边发红是过敏吗",
                    "长期喝无乳糖奶粉会有影响吗",
                    "特殊奶粉价格太贵负担不起",
                    "不知道什么时候该换奶粉段位",
                    "水解奶粉营养够不够"
                ],
                "market_type": "blue_ocean",
                "proportion": 0.20
            }},
            {{
                "category_name": "长尾问题词",
                "keywords": [
                    "深度水解奶粉要喝多久才能转普通奶粉",
                    "氨基酸奶粉和深度水解奶粉哪个好",
                    "早产儿奶粉吃到几个月可以换普通奶粉",
                    "乳糖不耐受和蛋白过敏怎么判断",
                    "适度水解奶粉可以长期喝吗",
                    "部分水解奶粉转普通奶粉怎么过渡",
                    "宝宝换奶粉牌子便秘是怎么回事",
                    "特殊配方奶粉医保能报销吗",
                    "过敏宝宝辅食添加和奶粉冲突吗",
                    "水解奶粉化了有颗粒是正常的吗"
                ],
                "market_type": "blue_ocean",
                "proportion": 0.15
            }},
            {{
                "category_name": "品类大词",
                "keywords": ["{keyword_core}", "特殊配方奶粉品牌"],
                "market_type": "red_ocean",
                "proportion": 0.05
            }},
            {{
                "category_name": "品牌词",
                "keywords": [],
                "market_type": "red_ocean",
                "proportion": 0.05
            }},
            {{
                "category_name": "通用需求词",
                "keywords": ["{keyword_core}推荐", "{keyword_core}哪个牌子好", "{keyword_core}多少钱一罐"],
                "market_type": "red_ocean",
                "proportion": 0.10
            }}
        ]
    }}
}}

重要说明：
1. 关键词必须是真实用户搜索词，体现具体搜索意图，不是泛泛的"XX+核心词"
2. 细分人群词要带具体人群标签（年龄/体质/阶段），细分场景词要带具体情境，细分痛点词要带"怎么办/怎么解决"
3. 每个分类关键词数量不得少于规定数量，否则视为不合格
4. 品牌词如果没有具体品牌可以填空数组
5. 蓝海关键词（细分人群/场景/痛点/长尾）应占总量80%以上

请开始生成："""

        return prompt

    def _parse_result(
        self,
        response: str,
        result: KeywordLibraryResult
    ) -> KeywordLibraryResult:
        """解析LLM返回结果"""

        # 尝试JSON解析
        try:
            # 清理响应文本
            text = response.strip()
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            result.raw_output = data

        except json.JSONDecodeError as e:
            logger.warning("[KeywordLibraryGenerator] JSON解析失败，尝试修复: %s", e)
            data = self._try_fix_json(response)
            if not data:
                result.error_message = "JSON解析失败"
                return result
            result.raw_output = data

        # 解析问题类型
        problem_types = data.get('problem_types', [])
        for pt in problem_types:
            result.problem_types.append(ProblemType(
                type_name=pt.get('type_name', ''),
                description=pt.get('description', ''),
                target_audience=pt.get('target_audience', ''),
                keywords=pt.get('keywords', []),
                scene_keywords=pt.get('scene_keywords', []),
            ))

        # 解析关键词库
        result.keyword_library = data.get('keyword_library', {})

        # 解析问句示范
        question_samples_data = data.get('question_samples', {})
        if question_samples_data:
            # 解析前置问句
            for q in question_samples_data.get('pre_questions', []):
                result.question_samples.append(QuestionSample(
                    question=q.get('question', ''),
                    question_type='pre',
                    components=q.get('components', {}),
                ))
            # 解析后置问句
            for q in question_samples_data.get('post_questions', []):
                result.question_samples.append(QuestionSample(
                    question=q.get('question', ''),
                    question_type='post',
                    components=q.get('components', {}),
                ))

        return result

    def _extract_core_business(self, business_desc: str, industry: str = '') -> str:
        """
        从业务描述中提取核心业务词（产品/服务名称）

        Args:
            business_desc: 业务描述
            industry: 行业（可选）

        Returns:
            str: 核心业务词
        """
        if not business_desc:
            return industry or ''

        text = business_desc.strip()

        # 移除常见前缀
        prefixes = ['我们公司是', '我们是', '主要做', '主要从事', '业务是', '业务范围是',
                    '主要业务是', '公司主要做', '公司主要从事', '公司业务是',
                    '专业做', '专业从事', '从事', '做']
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # 移除常见前缀词
        for prefix in ['卖', '销售', '提供', '经营']:
            if text.startswith(prefix) and len(text) > len(prefix):
                text = text[len(prefix):].strip()

        # 移除常见后缀
        for suffix in ['的公司', '的业务', '的服务', '的产品', '的生意',
                       '有限公司', '有限责任公司', '股份公司', '集团']:
            if text.endswith(suffix):
                text = text[:-len(suffix)].strip()

        if len(text) <= 5:
            return text if text else industry or ''

        # 常见产品/服务词列表
        product_indicators = [
            '羊奶粉', '牛奶粉', '奶粉', '牛奶', '酸奶', '鲜奶',
            '婴幼儿奶粉', '儿童奶粉', '成人奶粉', '中老年奶粉',
            '有机奶粉', '配方奶粉', '辅食', '米粉', '果泥', '肉泥',
            '纸尿裤', '尿不湿', '婴儿车', '婴儿床', '奶瓶', '奶嘴',
            '护肤品', '化妆品', '面霜', '乳液', '精华', '面膜',
            '净水器', '空气净化器', '扫地机器人', '洗碗机',
            '香肠', '腊肉', '腊肠', '火腿', '肉制品', '豆制品',
            '家政服务', '保洁服务', '月嫂', '育儿嫂', '保姆', '钟点工',
            '培训服务', '咨询服务', '设计服务', '摄影服务', '摄像服务',
            '装修服务', '搬家服务', '家政保洁', '清洗服务',
            '志愿填报', '高考志愿', '留学服务', '移民服务',
            '法律咨询', '财务咨询', '税务代理', '知识产权',
            '软件开发', '网站建设', 'APP开发', '小程序开发',
            '矿泉水', '饮用水', '桶装水', '瓶装水',
            # 农村/上门服务类
            '土灶', '打土灶', '农村土灶', '土灶建造', '土灶维修',
            '上门服务', '家政', '维修', '安装', '清洗', '清洁',
            '农村服务', '农机', '农具', '农作物', '农产品',
            # 婚恋服务
            '婚姻介绍', '婚介', '相亲', '交友', '婚恋服务',
        ]

        # 检查是否包含已知产品词
        for product in product_indicators:
            if product in text:
                return product

        # 如果文本较短且不包含营销词，返回前6个字符
        if len(text) <= 8:
            # 排除营销词
            marketing_words = ['市场', '蓝海', '红海', '赛道', '机会', '定位',
                             '高端', '细分', '垂直', '特色', '专业', '品质',
                             '优质', '创新', '独特', '个性', '专属', '定制化']
            for word in marketing_words:
                if word in text:
                    # 尝试提取服务词
                    for indicator in ['服务', '维修', '安装', '建造', '清洗', '销售', '定制', '介绍']:
                        if indicator in text:
                            idx = text.index(indicator)
                            return text[:idx+len(indicator)].strip()
                    return ''
            return text

        # 返回前8个字符
        return text[:8].strip() if text else industry or ''

    def _filter_keywords(self, keyword_library: Dict, keyword_core: str) -> Dict:
        """
        过滤明显不合适的关键词

        Args:
            keyword_library: 关键词库
            keyword_core: 核心业务词

        Returns:
            过滤后的关键词库
        """
        # 不合适的关键词后缀模式
        bad_suffixes = [
            '长期喝', '长期用', '长期服用', '长期食用',
            '高铁上', '高铁', '飞机上', '旅行携带', '断奶期', '断奶',
            '早餐', '早餐用', '睡前喝', '睡前用',
            '婴儿', '新生儿', '宝宝', '儿童', '奶粉', '辅食',
        ]

        # 不合适的问题词
        bad_questions = [
            '可以长期喝', '可以长期用', '可以长期服用',
            '对身体有害吗', '会有副作用吗', '能长期喝吗',
        ]

        for cat in keyword_library.get('categories', []):
            keywords = cat.get('keywords', [])
            filtered = []
            for kw in keywords:
                # 检查后缀
                bad = False
                for suffix in bad_suffixes:
                    if kw.endswith(suffix):
                        bad = True
                        break
                # 检查问题词
                if not bad:
                    for q in bad_questions:
                        if q in kw:
                            bad = True
                            break
                if not bad:
                    filtered.append(kw)
            cat['keywords'] = filtered

        return keyword_library

    def _try_fix_json(self, text: str) -> Optional[Dict]:
        """尝试修复损坏的JSON"""

        import re

        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]

            try:
                return json.loads(json_str)
            except:
                pass

            # 修复常见问题
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

def generate_keyword_library(
    business_info: Dict[str, Any],
    business_direction: str,
    max_keywords: int = 200,
) -> KeywordLibraryResult:
    """
    便捷函数：生成关键词库

    使用方式：
        from services.keyword_library_generator import generate_keyword_library

        result = generate_keyword_library(
            business_info={'business_description': '卖奶粉', 'industry': '奶粉'},
            business_direction='进口有机羊奶粉',
            max_keywords=200
        )

        if result.success:
            print(f"生成 {result.total_keywords} 个关键词")
            print(f"蓝海关键词: {result.blue_ocean_keywords}")
    """
    generator = KeywordLibraryGenerator()
    return generator.generate(business_info, core_business=None, max_keywords=max_keywords)
