#!/usr/bin/env python3
"""
测试奶粉场景的LLM返回
"""

import os
import sys
sys.path.insert(0, '/Volumes/增元/项目/douyin/系统部署')

# 关键：加载 .env 文件
from dotenv import load_dotenv
load_dotenv('/Volumes/增元/项目/douyin/系统部署/.env')

# 确认 Key 已加载
api_key = os.environ.get('LLM_API_KEY', '')
print(f"加载的 API Key: {api_key[:10]}..." if api_key else "API Key 为空")

from services.llm import LLMService

# 获取配置 - 支持硅基流动
provider = os.environ.get('LLM_PROVIDER', 'siliconflow')
model = os.environ.get('LLM_MODEL', os.environ.get('LLM_MODEL_TURBO', 'Qwen/Qwen2.5-7B-Instruct'))
base_url = os.environ.get('LLM_BASE_URL', 'https://api.siliconflow.cn/v1')
api_key = os.environ.get('LLM_API_KEY', '')

llm = LLMService(provider=provider, model=model)
llm.base_url = base_url
llm.api_key = api_key

# 测试参数
business_desc = "婴幼儿配方奶粉销售"
business_range = "cross_region"  # 跨区域
business_type = "product"  # 消费品
business_range_text = '跨区域/全国'
business_type_text = '消费品/零售（奶粉/饮料/食品等）'

prompt = f"""你是用户画像分析专家。请根据业务信息，识别用户问题和生成画像。

【重要】先仔细阅读以下示例，理解输出格式，然后基于业务信息生成。

=== 示例1：婚宴定制水 ===
业务：瓶装定制水（主做婚宴、寿宴、满月宴等宴席场景）

输出：
{{
    "scenarios": [
        {{
            "name": "婚宴定制",
            "description": "结婚典礼上的定制水需求",
            "user_problem_types": [
                {{"identity": "新郎新娘", "problem_type": "想留独特记忆", "display_name": "新郎新娘想留独特记忆", "description": "想让宾客记住自己的婚礼", "severity": "高"}},
                {{"identity": "双方父母", "problem_type": "撑面子", "display_name": "双方父母撑面子", "description": "想让婚礼办得体面、有档次", "severity": "高"}},
                {{"identity": "宾客", "problem_type": "体验一般", "display_name": "宾客体验一般", "description": "普通婚宴没特色、记不住", "severity": "中"}}
            ],
            "buyer_concern_types": [
                {{"identity": "新郎新娘", "concern_type": "价格担忧", "display_name": "新郎新娘价格担忧", "description": "担心定制水太贵、预算不够", "examples": ["定制水多少钱一箱？"]}},
                {{"identity": "婚庆公司", "concern_type": "采购顾虑", "display_name": "婚庆公司采购顾虑", "description": "担心质量、交期、效果", "examples": ["能按时交货吗？"]}}
            ],
            "portraits_by_type": {{
                "新郎新娘想留独特记忆": [
                    {{"name": "追求浪漫型新人", "age_range": "25-30岁", "occupation": "都市白领", "description": "希望婚礼与众不同，留下美好回忆"}},
                    {{"name": "完美主义新娘", "age_range": "26-32岁", "occupation": "设计师/策划", "description": "注重婚礼每个细节，追求完美"}}
                ],
                "双方父母撑面子": [
                    {{"name": "传统家庭型父母", "age_range": "50-60岁", "occupation": "退休/传统行业", "description": "重视传统礼节，要场面"}}
                ]
            }}
        }}
    ],
    "general_user_problem_types": [
        {{"identity": "会议主办方", "problem_type": "用水体验差", "display_name": "会议主办方用水体验差", "description": "培训/会议用水没档次", "severity": "中"}}
    ],
    "general_buyer_concern_types": [
        {{"identity": "企业老板", "concern_type": "品牌宣传效果", "display_name": "企业老板品牌宣传效果担忧", "description": "担心定制水宣传效果不明显", "examples": ["能带来多少曝光？"]}}
    ]
}}

=== 示例2：奶粉行业 ===
业务：婴幼儿配方奶粉销售

输出：
{{
    "scenarios": [
        {{
            "name": "宝宝日常喂养",
            "description": "宝宝日常喝奶场景",
            "user_problem_types": [
                {{"identity": "宝宝", "problem_type": "肠道问题", "display_name": "宝宝肠道问题", "description": "拉肚子、腹胀、便秘", "severity": "高"}},
                {{"identity": "宝宝", "problem_type": "过敏问题", "display_name": "宝宝过敏问题", "description": "牛奶蛋白过敏、乳糖不耐受", "severity": "高"}}
            ],
            "buyer_concern_types": [
                {{"identity": "宝妈", "concern_type": "真假担忧", "display_name": "宝妈真假担忧", "description": "怕买到假货、怕来源不正", "examples": ["怎么验真伪？"]}}
            ],
            "portraits_by_type": {{
                "宝宝肠道问题": [
                    {{"name": "拉肚子型宝宝家长", "age_range": "0-2岁宝宝家长", "occupation": "新手爸妈", "description": "宝宝喝奶后拉肚子"}}
                ]
            }}
        }}
    ],
    "general_user_problem_types": [],
    "general_buyer_concern_types": []
}}

=== 通用推理框架（适用于所有业务） ===

**核心思维**：场景化分析！
1. 先识别：这个业务有哪些**使用场景**？
2. 再分析：每个场景下，谁是**使用者**？谁是**付费者**？
3. 最后挖掘：各方有什么**问题/顾虑**？

**场景识别要点**：
- 宴席场景：婚宴、寿宴、满月宴、乔迁宴...
- 商务场景：会议、培训、接待、展会...
- 日常场景：家庭自用、送礼、福利发放...
- 每个场景都可能涉及不同身份

**身份多样化要求**：
- 每个场景列出至少2-3种不同身份
- 不能只写"用户"，要写具体角色

=== 待分析业务信息 ===
业务描述：{business_desc}
经营范围：{business_range_text}
经营类型：{business_type_text}

辅助信息：无
【买用关系提示】消费品通常是：使用者≠付费者（如宝宝喝奶粉，宝妈买）

=== 输出要求 ===
请按照示例格式，输出JSON。只返回JSON，不要其他文字。"""

print("=" * 80)
print("发送的 Prompt:")
print("=" * 80)
print(prompt)
print("=" * 80)

# 调用 LLM
response = llm.chat(prompt)

print("\n" + "=" * 80)
print("LLM 原始响应:")
print("=" * 80)
print(response)
print("=" * 80)

# 解析 JSON
import json
try:
    result = json.loads(response.strip())
    print("\n" + "=" * 80)
    print("解析后的 JSON:")
    print("=" * 80)
    print(json.dumps(result, ensure_ascii=False, indent=2))
except json.JSONDecodeError as e:
    print(f"\nJSON 解析失败: {e}")
    print(f"原始响应长度: {len(response)}")
