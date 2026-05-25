"""
纳瓦尔商业诊断系统 - 后端主入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os

from config import DATABASE_URL, DEBUG, FRONTEND_URL, API_PREFIX

# 数据库引擎
engine = create_async_engine(DATABASE_URL, echo=DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_database():
    """获取数据库会话的生成器"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print(f"🚀 纳瓦尔商业诊断系统启动")
    print(f"📦 数据库: {DATABASE_URL}")
    print(f"🌐 前端地址: {FRONTEND_URL}")
    yield
    # 关闭时
    await engine.dispose()
    print("👋 系统已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="纳瓦尔商业诊断系统",
    description="基于纳瓦尔财富观的商业模式诊断工具",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from routers.diagnosis import router as diagnosis_router
from routers.results import router as results_router

app.include_router(diagnosis_router)
app.include_router(results_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "纳瓦尔商业诊断系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG
    )
