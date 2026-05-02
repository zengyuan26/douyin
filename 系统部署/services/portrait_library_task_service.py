"""
画像专属词库后台任务服务

核心功能：
1. ThreadPoolExecutor 线程池（限制最大并发线程数，防止线程爆炸）
2. BoundedSemaphore 限制 LLM 并发调用数（防止第三方 API 限流）
3. 全局队列，所有画像词库生成任务共享资源
4. Flask app context 支持（后台线程在请求结束后执行，必须手动创建 context）
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict

logger = logging.getLogger(__name__)

# 配置常量
MAX_POOL_WORKERS = 10          # 线程池最大工作线程数（限制总资源）
MAX_LLM_CONCURRENCY = 5        # LLM 最大并发数（防 API 限流）
POOL_NAME = "portrait_library"

# 全局存储 Flask app 引用（由 create_app 初始化时注入）
_flask_app = None


def init_app(app):
    """由 Flask app 初始化时调用，注入 app 引用"""
    global _flask_app
    _flask_app = app
    logger.info("[PortraitLibraryTask] Flask app 已注入")


class PortraitLibraryTaskService:
    """
    画像词库任务服务（全局单例）

    使用 BoundedSemaphore 控制 LLM 并发数，ThreadPoolExecutor 控制总线程数。
    所有画像的词库生成请求共享同一个线程池和信号量。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._executor = ThreadPoolExecutor(
            max_workers=MAX_POOL_WORKERS,
            thread_name_prefix=POOL_NAME,
        )
        self._llm_semaphore = threading.BoundedSemaphore(MAX_LLM_CONCURRENCY)
        self._active_count = 0
        self._active_lock = threading.Lock()

        logger.info(
            "[PortraitLibraryTask] 初始化完成，"
            "max_pool_workers=%d, max_llm_concurrency=%d",
            MAX_POOL_WORKERS, MAX_LLM_CONCURRENCY
        )

    def submit(
        self,
        fn,
        *args,
        **kwargs
    ) -> Future:
        """
        提交词库生成任务到线程池

        Args:
            fn: 执行函数（通常是 _generate_with_semaphore 包装过的函数）
            *args, **kwargs: 传给 fn 的参数

        Returns:
            concurrent.futures.Future 对象
        """
        future = self._executor.submit(fn, *args, **kwargs)
        return future

    def get_status(self) -> Dict:
        """获取服务状态"""
        with self._active_lock:
            active = self._active_count
        return {
            'max_pool_workers': MAX_POOL_WORKERS,
            'max_llm_concurrency': MAX_LLM_CONCURRENCY,
            'active_llm_calls': active,
            'llm_available': MAX_LLM_CONCURRENCY - active,
        }


# 全局单例（Flask 多进程环境下，每个进程独立）
task_service = PortraitLibraryTaskService()


def generate_with_semaphore(
    portrait_id: int,
    user_id: int,
    plan_type: str = 'free',
) -> None:
    """
    带 Semaphore 限制的词库生成函数

    调用流程：
    1. 获取 Semaphore（阻塞直到有空闲 LLM 槽位）
    2. 原子计数器 +1
    3. 在 Flask app context 中执行词库生成
    4. 计数器 -1，释放 Semaphore
    """
    semaphore = task_service._llm_semaphore

    with semaphore:
        # 原子计数 +1
        with task_service._active_lock:
            task_service._active_count += 1
            active = task_service._active_count

        try:
            logger.info(
                "[PortraitLibraryTask] 开始生成，portrait_id=%d，"
                "当前活跃 LLM 调用: %d/%d",
                portrait_id, active, MAX_LLM_CONCURRENCY
            )

            # 后台线程在 HTTP 请求结束后执行，必须手动创建 Flask app context
            if _flask_app is None:
                logger.error("[PortraitLibraryTask] Flask app 未注入，无法创建 context")
                return

            with _flask_app.app_context():
                _do_generate_library(portrait_id, user_id, plan_type)

        finally:
            # 原子计数 -1
            with task_service._active_lock:
                task_service._active_count -= 1
                remaining = task_service._active_count
            logger.info(
                "[PortraitLibraryTask] 生成完成，portrait_id=%d，"
                "剩余活跃 LLM 调用: %d/%d",
                portrait_id, remaining, MAX_LLM_CONCURRENCY
            )


def _do_generate_library(portrait_id: int, user_id: int, plan_type: str = 'free') -> None:
    """
    执行词库生成（核心逻辑，在 Semaphore 内执行）

    流程：
    1. 更新状态 = 'generating'
    2. 使用 KeywordLibraryGenerator.generate_template() 按模板生成关键词库（9分类，100+个）
    3. 使用 TopicLibraryGenerator.generate() 生成选题库（五段式）
    4. 【新增】使用 OperationsPlanner 生成运营规划（五段式配比 + GEO模式匹配）
    5. 保存结果，更新状态 = 'completed' / 'failed'
    """
    from models.public_models import SavedPortrait, db
    from services.portrait_save_service import portrait_save_service
    from services.keyword_library_generator import KeywordLibraryGenerator

    try:
        # 1. 更新状态：生成中
        portrait = SavedPortrait.query.get(portrait_id)
        if portrait:
            portrait.generation_status = 'generating'
            portrait.generation_error = None
            db.session.commit()

        # 2. 获取画像数据
        portrait = portrait_save_service.get_saved_portrait(portrait_id)
        if not portrait:
            logger.warning(
                "[PortraitLibraryTask] 画像不存在 portrait_id=%d",
                portrait_id
            )
            return

        portrait_data_dict = portrait.get('portrait_data', {}) or {}
        business_description = portrait.get('business_description', '') or ''
        target_customer = portrait.get('target_customer', '') or ''
        industry = portrait.get('industry', '') or ''
        region = portrait.get('region', '') or ''

        def _to_list(val):
            if val is None:
                return []
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                return [val] if val.strip() else []
            return []

        pain_points = _to_list(portrait_data_dict.get('pain_points', []))
        if not pain_points:
            pp = portrait_data_dict.get('pain_point', '')
            if isinstance(pp, str) and pp.strip():
                pain_points = [pp.strip()]

        portrait_data = {
            'pain_points': pain_points,
            'pain_scenarios': _to_list(portrait_data_dict.get('pain_scenarios', [])),
            'barriers': _to_list(portrait_data_dict.get('barriers', [])),
        }

        # ── ① 生成关键词库（9分类，100+）─────────────────────────────
        keyword_generator = KeywordLibraryGenerator()
        kw_result = keyword_generator.generate_template(
            business_info={
                'business_description': business_description,
                'industry': industry,
            },
            core_business=business_description,
            region=region,
            portrait_data=portrait_data,
        )

        if not kw_result.success:
            raise Exception(kw_result.error_message or "关键词库生成失败")

        kl = kw_result.keyword_library or {}
        total_kw = kw_result.total_keywords
        logger.info(
            "[PortraitLibraryTask] 关键词库生成完成 portrait_id=%d: 总关键词=%d",
            portrait_id, total_kw,
        )

        # ── ② 生成选题库（五段式）─────────────────────────────
        from services.topic_library_generator import topic_library_generator
        topic_result = topic_library_generator.generate(
            portrait_data=portrait_data_dict,
            business_info={
                'business_description': business_description,
                'industry': industry,
                'products': [],
                'region': region,
                'target_customer': target_customer,
            },
            keyword_library=kl,
            plan_type=plan_type,
            portrait_id=portrait_id,
            content_stage='起号阶段',
            user_id=user_id,
        )

        if not topic_result.get('success'):
            raise Exception(topic_result.get('error', '选题库生成失败'))

        tl = topic_result.get('topic_library', {})
        logger.info(
            "[PortraitLibraryTask] 选题库生成完成 portrait_id=%d: 总选题=%d",
            portrait_id, len(tl.get('topics', [])),
        )

        # ── ③ 生成运营规划（五段式配比 + GEO模式匹配）【新增】─────
        from services.operations_planner import generate_operations_plan
        from datetime import datetime

        # 构建业务信息
        business_info_for_plan = {
            'business_description': business_description,
            'business_name': portrait.get('portrait_name', '') or industry,
            'industry': industry,
            'target_customer': target_customer,
        }

        # 获取画像列表
        portraits_list = portrait.get('portraits', []) if isinstance(portrait.get('portraits'), list) else []

        # 如果画像数据中没有portraits，尝试从portrait_data中提取
        if not portraits_list:
            # 兼容旧格式：portrait_data可能是单个画像
            if portrait_data_dict and isinstance(portrait_data_dict, dict):
                portraits_list = [portrait_data_dict]

        operations_plan = {}
        try:
            if portraits_list:
                operations_plan = generate_operations_plan(
                    portraits=portraits_list,
                    business_info=business_info_for_plan,
                    content_stage='起号阶段',
                    target_topic_count=len(tl.get('topics', [])) or 30,
                )
                logger.info(
                    "[PortraitLibraryTask] 运营规划生成完成 portrait_id=%d: plan_id=%s",
                    portrait_id, operations_plan.get('plan_id', 'N/A')
                )
            else:
                logger.warning(
                    "[PortraitLibraryTask] 无画像数据，跳过运营规划生成 portrait_id=%d",
                    portrait_id
                )
        except Exception as e:
            logger.warning(
                "[PortraitLibraryTask] 运营规划生成失败 portrait_id=%d: %s",
                portrait_id, str(e)
            )
            # 运营规划失败不影响整体流程，继续保存其他数据

        # ── ④ 保存三个库，更新状态 ──────────────────────────────
        portrait_row = SavedPortrait.query.get(portrait_id)
        if portrait_row:
            portrait_row.keyword_library = kl
            portrait_row.topic_library = tl
            portrait_row.generation_status = 'completed'

            # 保存运营规划到 extra_data
            if operations_plan:
                extra_data = portrait_row.extra_data or {}
                extra_data['operations_plan'] = operations_plan
                extra_data['operations_plan_updated_at'] = datetime.utcnow().isoformat()
                portrait_row.extra_data = extra_data

            db.session.commit()

            logger.info(
                "[PortraitLibraryTask] 关键词库+选题库+运营规划全部生成完成 portrait_id=%d",
                portrait_id
            )
        else:
            raise Exception("画像记录不存在，无法保存")

    except Exception as e:
        import traceback
        error_str = str(e)
        if len(error_str) > 300:
            error_str = error_str[:300] + '...'
        logger.error("[PortraitLibraryTask] 异常 portrait_id=%d: " + error_str, portrait_id)
        logger.debug(
            "[PortraitLibraryTask] 堆栈 portrait_id=%d: " + traceback.format_exc(),
            portrait_id
        )
        try:
            from models.public_models import SavedPortrait, db
            portrait_row = SavedPortrait.query.get(portrait_id)
            if portrait_row:
                portrait_row.generation_status = 'failed'
                portrait_row.generation_error = str(e)[:500]
                db.session.commit()
        except Exception:
            pass
