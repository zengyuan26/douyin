"""
纳瓦尔商业诊断系统 - 结果和分享API
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import json
import random
import string
from datetime import datetime, timedelta

from config import API_PREFIX, REPORT_CACHE_TTL
from schemas import DiagnosisResultResponse, ShareResponse

router = APIRouter(prefix=f"{API_PREFIX}", tags=["结果"])

async def get_db():
    from main import get_database
    async for session in get_database():
        yield session


def generate_share_code(length=8):
    """生成随机分享码"""
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


# 价值类型标签映射
VALUE_TYPE_LABELS = {
    "product": "卖产品",
    "skill": "卖手艺",
    "knowledge": "卖知识",
    "labor": "卖体力"
}

# 资产类型标签映射
ASSET_TYPE_LABELS = {
    "skill_only": "技艺型",
    "knowledge": "知识型",
    "resource": "资源型",
    "system": "系统型"
}

# 杠杆类型标签映射
LEVERAGE_TYPE_LABELS = {
    "content": "内容杠杆",
    "team": "劳动力杠杆",
    "capital": "资本杠杆",
    "word_of_mouth": "口碑杠杆",
    "passive": "被动收入"
}


@router.get("/result/{session_id}", response_model=DiagnosisResultResponse)
async def get_result(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取诊断结果"""
    result = await db.execute(
        text("""
            SELECT * FROM diagnosis_results WHERE session_id = :session_id
        """),
        {"session_id": session_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="诊断结果不存在")

    # 计算百分比
    percentage = min(int(row.total_score / 400 * 100), 100)

    # 解析JSON字段
    strengths = row.strengths if isinstance(row.strengths, list) else json.loads(row.strengths) if row.strengths else []
    weaknesses = row.weaknesses if isinstance(row.weaknesses, list) else json.loads(row.weaknesses) if row.weaknesses else []
    insights = row.insights if isinstance(row.insights, list) else json.loads(row.insights) if row.insights else []
    recommendations = row.recommendations if isinstance(row.recommendations, list) else json.loads(row.recommendations) if row.recommendations else []

    leverage_types = row.inferred_leverage if isinstance(row.inferred_leverage, list) else json.loads(row.inferred_leverage) if row.inferred_leverage else []

    return DiagnosisResultResponse(
        id=str(row.id),
        session_id=str(row.session_id),
        total_score=row.total_score,
        percentage=percentage,
        stage=row.current_stage,
        stage_label=row.stage_label,
        stage_emoji="",
        value_type_label=VALUE_TYPE_LABELS.get(row.inferred_value_type, row.inferred_value_type or "待分析"),
        asset_type_label=ASSET_TYPE_LABELS.get(row.inferred_asset_type, row.inferred_asset_type or "待分析"),
        leverage_labels=[LEVERAGE_TYPE_LABELS.get(l, l) for l in leverage_types],
        strengths=strengths,
        weaknesses=weaknesses,
        insights=insights,
        recommendations=recommendations,
        created_at=str(row.created_at)
    )


@router.post("/share/{result_id}", response_model=ShareResponse)
async def create_share(
    result_id: str,
    db: AsyncSession = Depends(get_db)
):
    """创建分享链接"""
    # 检查结果是否存在
    result = await db.execute(
        text("SELECT id FROM diagnosis_results WHERE id = :result_id"),
        {"result_id": result_id}
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="诊断结果不存在")

    # 生成唯一分享码
    share_code = generate_share_code()
    while True:
        check = await db.execute(
            text("SELECT id FROM report_shares WHERE share_code = :code"),
            {"code": share_code}
        )
        if not check.scalar():
            break
        share_code = generate_share_code()

    # 设置7天过期
    expires_at = datetime.now() + timedelta(days=7)

    # 保存分享记录
    await db.execute(
        text("""
            INSERT INTO report_shares (result_id, share_code, expires_at)
            VALUES (:result_id, :share_code, :expires_at)
        """),
        {
            "result_id": result_id,
            "share_code": share_code,
            "expires_at": expires_at
        }
    )
    await db.commit()

    return ShareResponse(
        share_url=f"/share/{share_code}",
        share_code=share_code,
        expires_at=expires_at.isoformat()
    )


@router.get("/share/{share_code}")
async def get_shared_result(
    share_code: str,
    db: AsyncSession = Depends(get_db)
):
    """通过分享码获取结果"""
    # 查询分享记录
    share_result = await db.execute(
        text("""
            SELECT rs.*, dr.*
            FROM report_shares rs
            JOIN diagnosis_results dr ON dr.id = rs.result_id
            WHERE rs.share_code = :share_code
        """),
        {"share_code": share_code}
    )
    row = share_result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="分享不存在或已过期")

    # 检查是否过期
    if row.expires_at and row.expires_at < datetime.now():
        raise HTTPException(status_code=410, detail="分享已过期")

    # 增加浏览次数
    await db.execute(
        text("UPDATE report_shares SET view_count = view_count + 1 WHERE share_code = :share_code"),
        {"share_code": share_code}
    )
    await db.commit()

    # 返回结果（简化版，不包含recommendations）
    return {
        "total_score": row.total_score,
        "percentage": min(int(row.total_score / 400 * 100), 100),
        "stage": row.current_stage,
        "stage_label": row.stage_label,
        "value_type_label": VALUE_TYPE_LABELS.get(row.inferred_value_type, "待分析"),
        "asset_type_label": ASSET_TYPE_LABELS.get(row.inferred_asset_type, "待分析"),
        "strengths": json.loads(row.strengths) if isinstance(row.strengths, str) else row.strengths,
        "weaknesses": json.loads(row.weaknesses) if isinstance(row.weaknesses, str) else row.weaknesses,
        "insights": json.loads(row.insights) if isinstance(row.insights, str) else row.insights,
        "view_count": row.view_count + 1
    }
