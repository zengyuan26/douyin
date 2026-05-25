"""
纳瓦尔商业诊断系统 - 配置
"""
import os
from pathlib import Path

# 基础路径
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

# 数据库
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/naval_diagnosis"
)

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# LLM配置
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai / zhipu / siliconflow
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 硅基流动配置
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "THUDM/glm-4-flash")

# API配置
API_PREFIX = "/api/v1"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# 缓存配置
CACHE_TTL = 3600  # 1小时
REPORT_CACHE_TTL = 86400  # 24小时

# 前端配置
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# 阶段分数配置（系统计算用）
STAGE_SCORE_CONFIG = {
    # 价值类型分数
    "q1_earn_type": {
        "product": 80,   # 卖产品 - 高
        "skill": 60,     # 卖手艺 - 中高
        "knowledge": 70,  # 卖知识 - 中高
        "labor": 40,     # 卖体力 - 低
    },
    # 可复制性分数
    "q2_replicable": {
        "only_me": 30,      # 只有我能做 - 低可复制性，但高壁垒
        "need_train": 60,   # 需要培训 - 中
        "anyone": 90,       # 随便谁都能 - 高可复制性
    },
    # 休息一周
    "q3_pause_week": {
        "stop": 40,         # 完全停止 - 依赖个人
        "some_impact": 60,  # 有点影响 - 中等
        "no_impact": 90,    # 完全不受影响 - 系统化
    },
    # 团队规模
    "q4_team": {
        "alone": 30,        # 一个人 - 无劳动力杠杆
        "small_team": 60,   # 2-5人 - 中等杠杆
        "big_team": 90,     # 5人以上 - 强杠杆
    },
    # 内容平台
    "q5_content": {
        "yes_active": 80,       # 定期发布 - 有内容杠杆
        "yes_sometimes": 50,    # 偶尔发 - 部分杠杆
        "no": 20,               # 没做 - 无杠杆
    },
    # 客户来源
    "q6_client_source": {
        "referral": 60,     # 口碑介绍 - 中
        "active": 40,      # 主动推广 - 效率低
        "passive": 80,     # 被动流量 - 强杠杆
    },
    # 被动收入
    "q7_passive_income": {
        "yes": 90,      # 有 - 强杠杆
        "some": 60,    # 有点 - 中
        "no": 30,      # 没有 - 无杠杆
    },
    # 收入天花板
    "q8_income_limit": {
        "very_high": 90,      # 没上限 - 商业模式好
        "some_limit": 60,    # 有一定上限 - 中
        "very_limited": 30,  # 上限明显 - 模式受限
    },
    # 可复制模式
    "q9_model": {
        "yes_standard": 90,   # 有标准流程 - 强
        "some_formal": 60,   # 有点规范 - 中
        "chaos": 30,         # 随意 - 弱
    },
    # 野心
    "q10_ambition": {
        "very_much": 80,      # 想做大 - 高动力
        "somewhat": 50,      # 还好 - 中
        "no_need": 20,      # 不想太累 - 低动力
    },
}

# 阶段阈值
STAGE_THRESHOLDS = [
    (120, "第一阶段", "起步期", "🔴"),
    (200, "第二阶段", "发展期", "🟡"),
    (280, "第三阶段", "成熟期", "🟢"),
    (360, "第四阶段", "突破期", "🌟"),
]
