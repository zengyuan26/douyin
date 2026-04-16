"""
画像专属词库后台任务服务

核心功能：
1. ThreadPoolExecutor 线程池（限制最大并发线程数，防止线程爆炸）
2. BoundedSemaphore 限制 LLM 并发调用数（防止第三方 API 限流）
3. 全局队列，所有画像词库生成任务共享资源
4. Flask app context 支持（后台线程在请求结束后执行，必须手动创建 context）
"""

import json
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional

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
    plan_type: str,
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


def _do_generate_library(portrait_id: int, user_id: int, plan_type: str) -> None:
    """
    执行词库生成（核心逻辑，在 Semaphore 内执行）

    流程：
    1. 更新状态 = 'generating'
    2. 检查是否已有关键词库：
       - 已有关键词库：跳过关键词库生成，只生成选题库
       - 没有关键词库：生成关键词库 → 保存 → 生成选题库
    3. 更新状态 = 'completed' / 'failed'
    """
    from models.public_models import SavedPortrait, db
    from services.portrait_save_service import portrait_save_service
    from services.keyword_library_generator import keyword_library_generator
    from services.topic_library_generator import topic_library_generator

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

        portrait_data_dict = portrait.get('portrait_data', {})
        business_description = portrait.get('business_description', '')
        target_customer = portrait.get('target_customer', '')
        keyword_library_from_db = portrait.get('keyword_library')  # 已有关键词库

        # 确保画像数据包含必要的结构化信息
        if not portrait_data_dict:
            portrait_data_dict = {}

        # 从 business_description 和 target_customer 中提取身份和痛点
        if not portrait_data_dict.get('identity') and target_customer:
            portrait_data_dict['identity'] = target_customer
        if not portrait_data_dict.get('pain_point') and business_description:
            portrait_data_dict['pain_point'] = business_description

        business_info = {
            'business_description': business_description,
            'industry': portrait.get('industry', ''),
            'products': portrait.get('products', []),
            'region': portrait.get('region', ''),
            'target_customer': target_customer,
        }
        # 调试日志
        business_str = json.dumps(business_info, ensure_ascii=False) if business_info else '{}'
        logger.info("[PortraitLibraryTask] portrait_data keys=" + str(list(portrait_data_dict.keys()) if portrait_data_dict else []))
        logger.info("[PortraitLibraryTask] portrait_data identity=" + str(portrait_data_dict.get('identity', '')))
        logger.info("[PortraitLibraryTask] portrait_data pain_point=" + str(portrait_data_dict.get('pain_point', '')))
        logger.info("[PortraitLibraryTask] business_info: " + business_str)
        logger.info("[PortraitLibraryTask] 已有关键词库: %s", "是" if keyword_library_from_db else "否")

        # 3. 判断是否需要生成关键词库
        kw_library = keyword_library_from_db  # 默认使用已有关键词库

        if not kw_library:
            # 没有已有关键词库，需要生成
            kw_result = keyword_library_generator.generate(
                portrait_data=portrait_data_dict,
                business_info=business_info,
                plan_type=plan_type,
                portrait_id=portrait_id,
            )

            if kw_result.get('success') and not kw_result.get('_meta', {}).get('from_cache'):
                keyword_library_generator.save_to_portrait(
                    portrait_id=portrait_id,
                    keyword_library=kw_result['keyword_library'],
                    user_id=user_id,
                    plan_type=plan_type,
                )
                logger.info(
                    "[PortraitLibraryTask] 关键词库生成完成 portrait_id=%d",
                    portrait_id
                )

            kw_library = kw_result.get('keyword_library')
        else:
            logger.info(
                "[PortraitLibraryTask] 使用已有关键词库，跳过生成 portrait_id=%d",
                portrait_id
            )

        # 4. 生成选题库（使用已有关键词库或刚生成的关键词库）
        topic_result = topic_library_generator.generate(
            portrait_data=portrait_data_dict,
            business_info=business_info,
            keyword_library=kw_library,
            plan_type=plan_type,
            portrait_id=portrait_id,
        )

        if topic_result.get('success') and not topic_result.get('_meta', {}).get('from_cache'):
            topic_library_generator.save_to_portrait(
                portrait_id=portrait_id,
                topic_library=topic_result['topic_library'],
                user_id=user_id,
                plan_type=plan_type,
            )
            logger.info(
                "[PortraitLibraryTask] 选题库生成完成 portrait_id=%d",
                portrait_id
            )

        # 5. 更新状态：完成
        portrait_row = SavedPortrait.query.get(portrait_id)
        if portrait_row:
            portrait_row.generation_status = 'completed'
            db.session.commit()
            logger.info(
                "[PortraitLibraryTask] 双库生成全部完成 portrait_id=%d",
                portrait_id
            )

    except Exception as e:
        import traceback
        error_str = str(e)
        if len(error_str) > 300:
            error_str = error_str[:300] + '...'
        # 异常信息本身可能含 { } 或 %，用字符串拼接避免二次格式化
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
