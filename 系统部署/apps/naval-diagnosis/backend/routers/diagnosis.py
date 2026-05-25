"""
纳瓦尔商业诊断系统 - 诊断API路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json

from config import API_PREFIX, STAGE_SCORE_CONFIG
from schemas import (
    StartDiagnosisRequest,
    SubmitAnswerRequest,
    CompleteDiagnosisRequest,
    QuestionResponse,
    QuestionOption,
)

router = APIRouter(prefix=f"{API_PREFIX}/diagnosis", tags=["诊断"])

# 依赖注入：获取数据库会话
async def get_db():
    from main import get_database
    async for session in get_database():
        yield session


@router.post("/start", response_model=dict)
async def start_diagnosis(
    request: StartDiagnosisRequest,
    db: AsyncSession = Depends(get_db)
):
    """开始一个新的诊断会话"""
    # 创建会话
    result = await db.execute(
        text("""
            INSERT INTO diagnosis_sessions (user_id, status, current_question, session_data)
            VALUES (:user_id, 'in_progress', 0, '{}')
            RETURNING id
        """),
        {"user_id": request.user_id}
    )
    session_id = result.scalar()
    await db.commit()

    return {
        "session_id": str(session_id),
        "message": "诊断会话已创建",
        "total_questions": 10
    }


@router.get("/questions", response_model=List[QuestionResponse])
async def get_questions(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取所有问题"""
    # 查询所有问题
    result = await db.execute(
        text("""
            SELECT question_key, question_type, category, content, options, is_required, display_order
            FROM questions
            WHERE is_active = true
            ORDER BY display_order
        """)
    )
    rows = result.fetchall()

    questions = []
    for idx, row in enumerate(rows):
        content = row.content if isinstance(row.content, dict) else json.loads(row.content)
        options = row.options if isinstance(row.options, list) else json.loads(row.options) if row.options else []

        questions.append(QuestionResponse(
            key=row.question_key,
            type=row.question_type,
            title=content.get("title", ""),
            subtitle=content.get("subtitle"),
            image=content.get("image"),
            options=[QuestionOption(**opt) for opt in options] if options else None,
            is_required=row.is_required,
            total_questions=len(rows),
            current_index=idx + 1
        ))

    return questions


@router.post("/answer")
async def submit_answer(
    request: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db)
):
    """提交答案"""
    # 检查会话是否存在
    session_check = await db.execute(
        text("SELECT id FROM diagnosis_sessions WHERE id = :session_id"),
        {"session_id": request.session_id}
    )
    if not session_check.scalar():
        raise HTTPException(status_code=404, detail="会话不存在")

    # 保存答案
    await db.execute(
        text("""
            INSERT INTO answers (session_id, question_key, answer_value)
            VALUES (:session_id, :question_key, :answer_value::jsonb)
        """),
        {
            "session_id": request.session_id,
            "question_key": request.question_key,
            "answer_value": json.dumps(request.answer_value)
        }
    )

    # 更新会话进度
    result = await db.execute(
        text("""
            UPDATE diagnosis_sessions
            SET current_question = (
                SELECT COUNT(*) FROM answers WHERE session_id = :session_id
            ), updated_at = NOW()
            WHERE id = :session_id
            RETURNING current_question
        """),
        {"session_id": request.session_id}
    )
    current_question = result.scalar()

    # 计算当前进度分数（预估）
    preview_score = 0
    answers_result = await db.execute(
        text("""
            SELECT a.question_key, a.answer_value
            FROM answers a
            WHERE a.session_id = :session_id
        """),
        {"session_id": request.session_id}
    )
    for row in answers_result.fetchall():
        q_key = row.question_key
        answer_val = row.answer_value if isinstance(row.answer_value, str) else row.answer_value.get("value", "")
        if q_key in STAGE_SCORE_CONFIG and answer_val in STAGE_SCORE_CONFIG[q_key]:
            preview_score += STAGE_SCORE_CONFIG[q_key][answer_val]

    await db.commit()

    return {
        "success": True,
        "current_question": current_question,
        "preview_score": preview_score,
        "message": "答案已保存"
    }


@router.post("/complete")
async def complete_diagnosis(
    request: CompleteDiagnosisRequest,
    db: AsyncSession = Depends(get_db)
):
    """完成诊断，触发AI分析"""
    from services.ai_analyzer import AIAnalyzer

    # 获取会话和答案
    session_result = await db.execute(
        text("SELECT * FROM diagnosis_sessions WHERE id = :session_id"),
        {"session_id": request.session_id}
    )
    session = session_result.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 获取所有答案
    answers_result = await db.execute(
        text("""
            SELECT question_key, answer_value
            FROM answers
            WHERE session_id = :session_id
        """),
        {"session_id": request.session_id}
    )
    answers = []
    for row in answers_result.fetchall():
        answer_val = row.answer_value if isinstance(row.answer_value, str) else row.answer_value.get("value", "")
        score = 0
        if row.question_key in STAGE_SCORE_CONFIG and answer_val in STAGE_SCORE_CONFIG[row.question_key]:
            score = STAGE_SCORE_CONFIG[row.question_key][answer_val]
        answers.append({
            "question_key": row.question_key,
            "answer_value": answer_val,
            "score": score
        })

    # 调用AI分析
    analyzer = AIAnalyzer()
    report = await analyzer.analyze(
        session_id=request.session_id,
        answers=answers,
        user_description=request.user_description
    )

    # 保存结果
    await db.execute(
        text("""
            INSERT INTO diagnosis_results (
                session_id, user_id, total_score, inferred_value_type, inferred_asset_type,
                inferred_leverage, current_stage, stage_label, strengths, weaknesses,
                insights, recommendations, raw_data
            )
            VALUES (
                :session_id, :user_id, :total_score, :inferred_value_type, :inferred_asset_type,
                :inferred_leverage::jsonb, :current_stage, :stage_label, :strengths::jsonb,
                :weaknesses::jsonb, :insights::jsonb, :recommendations::jsonb, :raw_data::jsonb
            )
            RETURNING id
        """),
        {
            "session_id": request.session_id,
            "user_id": session.user_id,
            "total_score": report.total_score,
            "inferred_value_type": report.value_type,
            "inferred_asset_type": report.asset_type,
            "inferred_leverage": json.dumps(report.leverage_types),
            "current_stage": report.stage,
            "stage_label": f"{report.stage_emoji} {report.stage_label}",
            "strengths": json.dumps(report.strengths),
            "weaknesses": json.dumps(report.weaknesses),
            "insights": json.dumps(report.insights),
            "recommendations": json.dumps(report.recommendations),
            "raw_data": json.dumps({"answers": report.raw_answers, "description": request.user_description})
        }
    )

    # 更新会话状态
    await db.execute(
        text("""
            UPDATE diagnosis_sessions
            SET status = 'completed', completed_at = NOW(), updated_at = NOW()
            WHERE id = :session_id
        """),
        {"session_id": request.session_id}
    )

    await db.commit()

    return {
        "success": True,
        "message": "诊断完成",
        "result_id": str(report.total_score)  # 临时返回分数
    }


@router.get("/status/{session_id}")
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取诊断进度"""
    result = await db.execute(
        text("""
            SELECT s.id, s.status, s.current_question, s.started_at,
                   (SELECT COUNT(*) FROM answers WHERE session_id = s.id) as answered
            FROM diagnosis_sessions s
            WHERE s.id = :session_id
        """),
        {"session_id": session_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {
        "session_id": str(row.id),
        "status": row.status,
        "current_question": row.answered,
        "total_questions": 10,
        "progress_percent": int(row.answered / 10 * 100)
    }
