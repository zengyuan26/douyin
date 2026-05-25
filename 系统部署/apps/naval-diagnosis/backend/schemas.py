"""
纳瓦尔商业诊断系统 - Pydantic模型
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


# ============ 请求模型 ============

class StartDiagnosisRequest(BaseModel):
    """开始诊断请求"""
    user_id: Optional[str] = None
    nickname: Optional[str] = None


class SubmitAnswerRequest(BaseModel):
    """提交答案请求"""
    session_id: str
    question_key: str
    answer_value: Any


class CompleteDiagnosisRequest(BaseModel):
    """完成诊断请求"""
    session_id: str
    user_description: Optional[str] = ""


# ============ 响应模型 ============

class QuestionOption(BaseModel):
    """问题选项"""
    value: str
    label: str
    icon: str
    description: Optional[str] = None


class QuestionResponse(BaseModel):
    """问题响应"""
    key: str
    type: str
    title: str
    subtitle: Optional[str] = None
    image: Optional[str] = None
    options: Optional[List[QuestionOption]] = None
    is_required: bool = True
    total_questions: int = 10
    current_index: int = 1


class DiagnosisResultResponse(BaseModel):
    """诊断结果响应"""
    id: str
    session_id: str
    total_score: int
    max_score: int = 400
    percentage: int  # 百分比

    # 阶段信息
    stage: str
    stage_label: str
    stage_emoji: str

    # LLM推断
    value_type_label: str
    asset_type_label: str
    leverage_labels: List[str]

    # 详情
    strengths: List[str]
    weaknesses: List[str]
    insights: List[str]
    recommendations: List[Dict[str, str]]  # [{title, description, icon}]

    created_at: str


class ShareResponse(BaseModel):
    """分享响应"""
    share_url: str
    share_code: str
    expires_at: Optional[str] = None


# ============ 内部模型 ============

class AnswerRecord(BaseModel):
    """答案记录"""
    question_key: str
    answer_value: str
    score: int = 0


class AnalysisContext(BaseModel):
    """分析上下文"""
    session_id: str
    answers: List[AnswerRecord]
    user_description: str = ""

    @property
    def total_score(self) -> int:
        return sum(a.score for a in self.answers)

    @property
    def answers_dict(self) -> Dict[str, str]:
        return {a.question_key: a.answer_value for a in self.answers}


class DiagnosisReport(BaseModel):
    """诊断报告"""
    total_score: int
    stage: str
    stage_label: str
    stage_emoji: str

    # LLM推断
    value_type: str
    value_type_label: str
    asset_type: str
    asset_type_label: str
    leverage_types: List[str]
    leverage_labels: List[str]

    # 内容
    strengths: List[str]
    weaknesses: List[str]
    insights: List[str]
    recommendations: List[Dict[str, str]]

    # 原始数据
    raw_answers: Dict[str, str]


# ============ 错误响应 ============

class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: Optional[str] = None
