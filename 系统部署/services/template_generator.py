"""
结构化模板生成器 - 最小化 LLM token 消耗

策略：LLM 只填充 ? 部分，后端组装模板
"""

import json
from typing import List, Dict, Any

import logging
logger = logging.getLogger(__name__)



# 预定义模板结构（固定不变）
PORTRAIT_TEMPLATE = {
    "name": "?",           # 画像名称
    "age_range": "?",      # 年龄段
    "pain_point": "?",     # 核心痛点
    "goal": "?",           # 目标
    "occupation": "?",     # 职业（可选）
    "income_level": "?",   # 收入（可选）
}

# 问题类型模板
PROBLEM_TYPE_TEMPLATE = {
    "type_name": "?",
    "severity": "?",
    "description": "?"
}


class TemplateGenerator:
    """模板生成器 - 最小化 LLM 输出"""

    # 模板提示词 - 只需要 LLM 填充简短答案
    MINIMAL_PORTRAIT_PROMPT = """## 任务
基于"{problem_type}"问题，生成 {count} 个精准人群画像。

## 要求
每行一个画像，用 | 分隔字段：
名称|年龄段|核心痛点|目标

示例：
乳糖不耐受宝宝妈妈|25-35岁职场白领|担心产品效果不明显|找到效果更好的产品
深海鱼油消费者|40-55岁中年群体|不确定补多少才够|明确每日推荐剂量

直接输出 {count} 行，不要其他文字。"""

    # 解析 LLM 响应
    @classmethod
    def parse_minimal_response(cls, response: str) -> List[Dict[str, str]]:
        """
        解析最小化响应
        输入: "某产品用户家长|25-35岁职场白领|担心产品效果不明显|找到合适的产品"
        输出: [{"name": "乳糖不耐受宝宝妈妈", "age_range": "25-35岁职场白领", ...}]
        """
        portraits = []
        lines = response.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split('|')
            if len(parts) >= 4:
                portrait = {
                    "name": parts[0].strip(),
                    "age_range": parts[1].strip(),
                    "pain_point": parts[2].strip(),
                    "goal": parts[3].strip(),
                }
                # 可选的额外字段
                if len(parts) >= 5:
                    portrait["occupation"] = parts[4].strip()
                if len(parts) >= 6:
                    portrait["income_level"] = parts[5].strip()

                portraits.append(portrait)

        return portraits

    # 生成最小化提示词
    @classmethod
    def generate_minimal_prompt(cls, problem_type: str, count: int = 5) -> str:
        """生成最小化提示词"""
        return cls.MINIMAL_PORTRAIT_PROMPT.format(
            problem_type=problem_type,
            count=count
        )


# 示例使用
if __name__ == "__main__":
    # 模拟 LLM 返回
    llm_response = """
某产品用户家长|25-35岁职场白领|担心用完症状加重|找到用完有不适怎么处理
某产品选择困难用户|28-38岁职场人士|担心用完有副作用|找到适合自己的调理方案
产品安全担忧家长|22-30岁新手家长|担心用完皮肤发红/过敏|找到安全可靠的产品
    """

    # 解析
    generator = TemplateGenerator()
    portraits = generator.parse_minimal_response(llm_response)

logger.debug("解析结果：")
for p in portraits:
    logger.debug("  - %s: %s → %s", p['name'], p['pain_point'], p['goal'])
