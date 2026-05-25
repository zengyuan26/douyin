"""
纳瓦尔商业诊断系统 - AI分析服务
"""
import json
import re
import httpx
from typing import List, Dict, Any, Optional
from config import (
    LLM_PROVIDER,
    OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL,
    SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, SILICONFLOW_MODEL,
    STAGE_THRESHOLDS
)
from schemas import DiagnosisReport, AnswerRecord
from services.prompts import (
    PROMPT_FULL_ANALYSIS,
    PROMPT_STRENGTHS,
    PROMPT_WEAKNESSES,
    PROMPT_INSIGHTS,
    PROMPT_RECOMMENDATIONS
)


class AIAnalyzer:
    """AI分析引擎"""

    def __init__(self):
        self.llm_provider = LLM_PROVIDER

    async def analyze(
        self,
        session_id: str,
        answers: List[Dict],
        user_description: str = ""
    ) -> DiagnosisReport:
        """
        完整的诊断分析
        """
        # 1. 计算系统分数
        total_score = sum(a.get("score", 0) for a in answers)

        # 2. 确定阶段
        stage, stage_label, stage_emoji = self._determine_stage(total_score)

        # 3. 从答案中提取选项值
        answers_dict = {a["question_key"]: a["answer_value"] for a in answers}

        # 4. 调用LLM获取推断和建议
        try:
            llm_result = await self._call_llm(
                answers=answers_dict,
                user_description=user_description,
                total_score=total_score,
                stage=stage_label,
                stage_emoji=stage_emoji
            )
        except Exception as e:
            print(f"LLM调用失败: {e}")
            # 使用默认结果
            llm_result = self._get_default_result(answers_dict)

        # 5. 构建报告
        report = DiagnosisReport(
            total_score=total_score,
            stage=stage,
            stage_label=stage_label,
            stage_emoji=stage_emoji,
            value_type=llm_result.get("value_type", "skill"),
            value_type_label=llm_result.get("value_type_label", "卖手艺"),
            asset_type=llm_result.get("asset_type", "skill_only"),
            asset_type_label=llm_result.get("asset_type_label", "技艺型"),
            leverage_types=llm_result.get("leverages", []),
            leverage_labels=llm_result.get("leverage_labels", []),
            strengths=llm_result.get("strengths", []),
            weaknesses=llm_result.get("weaknesses", []),
            insights=llm_result.get("insights", []),
            recommendations=llm_result.get("recommendations", []),
            raw_answers=answers_dict
        )

        return report

    def _determine_stage(self, score: int) -> tuple:
        """根据分数确定阶段"""
        for threshold, stage, label, emoji in STAGE_THRESHOLDS:
            if score < threshold:
                return stage, label, emoji
        return STAGE_THRESHOLDS[-1][1], STAGE_THRESHOLDS[-1][2], STAGE_THRESHOLDS[-1][3]

    async def _call_llm(
        self,
        answers: Dict[str, str],
        user_description: str,
        total_score: int,
        stage: str,
        stage_emoji: str
    ) -> Dict:
        """调用LLM API"""
        # 格式化答案
        answers_text = "\n".join([f"- {k}: {v}" for k, v in answers.items()])

        # 构建Prompt
        prompt = PROMPT_FULL_ANALYSIS.format(
            description=user_description or "未提供",
            answers=answers_text
        )

        # 根据provider调用不同的API
        if self.llm_provider == "openai":
            return await self._call_openai(prompt)
        elif self.llm_provider == "siliconflow":
            return await self._call_siliconflow(prompt)
        else:
            return self._get_default_result(answers)

    async def _call_openai(self, prompt: str) -> Dict:
        """调用OpenAI API"""
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个专业的商业模式分析师。你的回答只包含JSON格式，不要有其他内容。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OPENAI_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_json_response(content)

    async def _call_siliconflow(self, prompt: str) -> Dict:
        """调用硅基流动API"""
        headers = {
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": SILICONFLOW_MODEL,
            "messages": [
                {"role": "system", "content": "你是一个专业的商业模式分析师。你的回答只包含JSON格式，不要有其他内容。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{SILICONFLOW_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_json_response(content)

    def _parse_json_response(self, content: str) -> Dict:
        """解析JSON响应"""
        # 尝试提取JSON块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 尝试解析整个内容
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

    def _get_default_result(self, answers: Dict[str, str]) -> Dict:
        """获取默认结果（LLM调用失败时使用）"""
        # 基于答案推断基础结果
        value_type = "skill"
        if answers.get("q1_earn_type") == "product":
            value_type = "product"
        elif answers.get("q1_earn_type") == "knowledge":
            value_type = "knowledge"
        elif answers.get("q1_earn_type") == "labor":
            value_type = "labor"

        # 推断杠杆
        leverages = []
        if answers.get("q5_content") in ["yes_active", "yes_sometimes"]:
            leverages.append("content")
        if answers.get("q4_team") in ["small_team", "big_team"]:
            leverages.append("team")
        if answers.get("q7_passive_income") in ["yes", "some"]:
            leverages.append("passive")

        return {
            "value_type": value_type,
            "value_type_label": {
                "product": "卖产品",
                "skill": "卖手艺",
                "knowledge": "卖知识",
                "labor": "卖体力"
            }.get(value_type, "卖手艺"),
            "asset_type": "skill_only",
            "asset_type_label": "技艺型",
            "leverages": leverages,
            "leverage_labels": [
                {"content": "内容杠杆", "team": "劳动力杠杆", "passive": "被动收入"}.get(l, l)
                for l in leverages
            ],
            "strengths": [
                "✨ 有专业技能",
                "💪 亲自服务客户",
                "🌟 口碑积累中"
            ],
            "weaknesses": [
                "⚠️ 过度依赖自己",
                "🚧 缺乏杠杆放大",
                "📈 收入有天花板"
            ],
            "insights": [
                "你的技能很值钱，但被困在时间牢笼里",
                "每次只能服务一个客户，收入有上限",
                "需要把能力产品化，才能突破",
                "现在是用杠杆的最佳时机"
            ],
            "recommendations": [
                {
                    "icon": "1️⃣",
                    "title": "整理你的方法论",
                    "action": "花3天时间，把你的工作流程写成文档",
                    "result": "形成可复制的方法"
                },
                {
                    "icon": "2️⃣",
                    "title": "开始发布内容",
                    "action": "每周在小红书发2条作品展示",
                    "result": "建立个人品牌，吸引客户"
                },
                {
                    "icon": "3️⃣",
                    "title": "开发一个低价产品",
                    "action": "把你的经验做成教程或模板",
                    "result": "边际成本为零的收入"
                }
            ]
        }
