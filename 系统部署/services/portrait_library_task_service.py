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
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def _convert_keyword_library_for_frontend(kl: Dict[str, Any]) -> Dict[str, Any]:
    """
    将关键词库转换为前端期望的格式（Geo SEO 结构）
    
    后端格式: {pre_search_keywords, post_search_keywords, trust_keywords, competitive_keywords, ...}
    前端格式: {categories: [...], total_count: int}
    """
    if not kl:
        return {}
    
    categories = []
    total_count = 0
    
    # 1. 搜前搜关键词 -> categories
    pre_search = kl.get('pre_search_keywords') or {}
    for cat_name, keywords in pre_search.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'red_ocean',
                    'category_type': '搜前搜'
                })
    
    # 2. 搜后搜关键词 -> categories
    post_search = kl.get('post_search_keywords') or {}
    for cat_name, keywords in post_search.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'blue_ocean',
                    'category_type': '搜后搜'
                })
    
    # 3. 信任佐证关键词 -> categories
    trust = kl.get('trust_keywords') or {}
    for cat_name, keywords in trust.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'blue_ocean',
                    'category_type': '信任佐证'
                })
    
    # 4. 竞争优势关键词 -> categories
    competitive = kl.get('competitive_keywords') or {}
    for cat_name, keywords in competitive.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'blue_ocean',
                    'category_type': '竞争优势'
                })
    
    # 5. 地域关键词 -> categories
    region = kl.get('region_keywords') or {}
    for cat_name, keywords in region.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'blue_ocean',
                    'category_type': '地域关联'
                })
    
    # 6. 直接需求关键词 -> categories
    direct_demand = kl.get('direct_demand_keywords') or {}
    for cat_name, keywords in direct_demand.items():
        if isinstance(keywords, list) and keywords:
            cat_kws = []
            for kw in keywords:
                word = kw
                if isinstance(kw, dict):
                    word = kw.get('keyword', '') or kw.get('word', '') or ''
                if word and isinstance(word, str):
                    cat_kws.append(word)
                    total_count += 1
            if cat_kws:
                categories.append({
                    'category_name': cat_name,
                    'keywords': cat_kws,
                    'market_type': 'red_ocean',
                    'category_type': '直接需求'
                })
    
    # 7. 上下游关键词 -> 分别作为分类
    upstream_kws = []
    for kw in (kl.get('upstream_keywords') or []):
        word = kw if isinstance(kw, str) else (kw.get('keyword', '') or '')
        if word:
            upstream_kws.append(word)
            total_count += 1
    if upstream_kws:
        categories.append({
            'category_name': '上游关键词',
            'keywords': upstream_kws,
            'market_type': 'blue_ocean',
            'category_type': '上下游'
        })
    
    downstream_kws = []
    for kw in (kl.get('downstream_keywords') or []):
        word = kw if isinstance(kw, str) else (kw.get('keyword', '') or '')
        if word:
            downstream_kws.append(word)
            total_count += 1
    if downstream_kws:
        categories.append({
            'category_name': '下游关键词',
            'keywords': downstream_kws,
            'market_type': 'blue_ocean',
            'category_type': '上下游'
        })
    
    tools_kws = []
    for kw in (kl.get('supporting_tools_keywords') or []):
        word = kw if isinstance(kw, str) else (kw.get('keyword', '') or '')
        if word:
            tools_kws.append(word)
            total_count += 1
    if tools_kws:
        categories.append({
            'category_name': '配套工具',
            'keywords': tools_kws,
            'market_type': 'blue_ocean',
            'category_type': '上下游'
        })
    
    tech_kws = []
    for kw in (kl.get('technique_keywords') or []):
        word = kw if isinstance(kw, str) else (kw.get('keyword', '') or '')
        if word:
            tech_kws.append(word)
            total_count += 1
    if tech_kws:
        categories.append({
            'category_name': '技艺工艺',
            'keywords': tech_kws,
            'market_type': 'blue_ocean',
            'category_type': '上下游'
        })
    
    # 8. 构建前端格式
    result = {
        'categories': categories,
        'total_count': total_count,
        # 扁平字段：兼容下游服务
        'problem_type_keywords': [],
        'pain_point_keywords': [],
        'scene_keywords': [],
        'concern_keywords': [],
        'direct_demand_keywords': [],
    }
    
    return result


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
        """提交任务到线程池"""
        return self._executor.submit(fn, *args, **kwargs)

    def submit_with_semaphore(
        self,
        fn,
        *args,
        **kwargs
    ) -> Future:
        """
        提交任务并自动获取 LLM 信号量
        
        在任务执行前获取信号量，任务完成后自动释放。
        使用 functools.partial 包装任务来自动管理信号量。
        """
        import functools
        
        def wrapped_fn():
            with self._llm_semaphore:
                with self._active_lock:
                    self._active_count += 1
                    logger.debug(
                        "[PortraitLibraryTask] LLM并发占用，当前活跃数=%d",
                        self._active_count
                    )
                
                try:
                    return fn(*args, **kwargs)
                finally:
                    with self._active_lock:
                        self._active_count -= 1
                        logger.debug(
                            "[PortraitLibraryTask] LLM并发释放，当前活跃数=%d",
                            self._active_count
                        )
        
        return self._executor.submit(wrapped_fn)

    def get_active_count(self) -> int:
        """获取当前活跃的 LLM 并发数"""
        with self._active_lock:
            return self._active_count

    def shutdown(self, wait: bool = True):
        """关闭线程池"""
        self._executor.shutdown(wait=wait)
        logger.info("[PortraitLibraryTask] 线程池已关闭")


# 全局服务实例（延迟初始化）
_service: PortraitLibraryTaskService = None


def get_service() -> PortraitLibraryTaskService:
    """获取服务实例（线程安全单例）"""
    global _service
    if _service is None:
        with threading.Lock():
            if _service is None:
                _service = PortraitLibraryTaskService()
    return _service


def submit_task(fn, *args, **kwargs) -> Future:
    """
    便捷函数：提交画像词库生成任务
    
    使用示例：
        from services.portrait_library_task_service import submit_task
        from models.public_models import SavedPortrait, db
        
        future = submit_task(
            generate_portrait_library_task,
            portrait_id=123,
            app_context={
                'app': current_app._get_current_object(),
                'db': db,
            }
        )
    """
    service = get_service()
    return service.submit(fn, *args, **kwargs)


def submit_llm_task(fn, *args, **kwargs) -> Future:
    """
    便捷函数：提交 LLM 密集型任务（自动信号量控制）
    
    使用示例：
        from services.portrait_library_task_service import submit_llm_task
        
        future = submit_llm_task(
            generate_portrait_library_task,
            portrait_id=123,
            app_context={
                'app': current_app._get_current_object(),
                'db': db,
            }
        )
    """
    service = get_service()
    return service.submit_with_semaphore(fn, *args, **kwargs)


def _run_in_context(app_context: Dict[str, Any], fn, *args, **kwargs):
    """
    在 Flask 应用上下文中执行函数
    
    Args:
        app_context: 包含 app 和 db 引用的字典
        fn: 要执行的函数
        *args, **kwargs: 函数的参数
    """
    app = app_context.get('app')
    if app is None:
        raise ValueError("app_context must contain 'app' key")
    
    with app.app_context():
        # 设置 db session 到 app
        db = app_context.get('db')
        if db is not None:
            @db.event.listens_for(db.session, "after_commit")
            def receive_after_commit(session):
                pass  # 提交后回调，可用于日志等
        
        return fn(*args, **kwargs)


def generate_portrait_library_task(
    portrait_id: int,
    app_context: Dict[str, Any] = None
):
    """
    画像词库生成任务（后台执行）
    
    在后台线程中执行，需要手动创建 Flask app context。
    
    Args:
        portrait_id: 画像记录ID
        app_context: Flask 应用上下文信息，包含：
            - app: Flask 应用实例
            - db: SQLAlchemy db 实例
    """
    global _flask_app
    
    logger.info(f"[PortraitLibraryTask] 开始生成画像词库，portrait_id={portrait_id}")
    
    try:
        # 获取 Flask app
        app = _flask_app
        if app is None:
            app = app_context.get('app') if app_context else None
        
        if app is None:
            raise ValueError("Flask app not available")
        
        # 在 app context 中执行
        with app.app_context():
            from models.public_models import SavedPortrait, db
            from services.keyword_library_generator import KeywordLibraryGenerator
            from services.topic_library_generator import TopicLibraryGenerator
            
            # 1. 获取画像数据
            portrait_row = SavedPortrait.query.get(portrait_id)
            if not portrait_row:
                logger.error(f"[PortraitLibraryTask] 画像记录不存在，portrait_id={portrait_id}")
                return
            
            # 如果有 else 分支，应该在这里
            if portrait_row is None:
                raise Exception("画像记录不存在，无法保存")
            portrait_row.generation_status = 'generating'
            db.session.commit()
            
            # 2. 准备业务信息
            portrait_data = portrait_row.portrait_data or {}
            business_info = portrait_row.business_info or {}
            
            # 3. 生成关键词库
            logger.info(f"[PortraitLibraryTask] 开始生成关键词库 portrait_id={portrait_id}")
            kl_generator = KeywordLibraryGenerator()
            kl_result = kl_generator.generate(
                business_info=business_info,
                portrait_data=portrait_data
            )
            
            if not kl_result.success:
                logger.error(
                    f"[PortraitLibraryTask] 关键词库生成失败 portrait_id={portrait_id}: {kl_result.error_message}"
                )
                portrait_row.generation_status = 'failed'
                portrait_row.error_message = kl_result.error_message
                db.session.commit()
                return
            
            kl = kl_result.keyword_library
            logger.info(f"[PortraitLibraryTask] 关键词库生成完成 portrait_id={portrait_id}: 总关键词={kl_result.total_keywords}")
            
            # 4. 生成选题库
            logger.info(f"[PortraitLibraryTask] 开始生成选题库 portrait_id={portrait_id}")
            tl_generator = TopicLibraryGenerator()
            tl_result = tl_generator.generate(
                business_info=business_info,
                portrait_data=portrait_data,
                keyword_library=kl
            )
            
            if not tl_result.success:
                logger.error(
                    f"[PortraitLibraryTask] 选题库生成失败 portrait_id={portrait_id}: {tl_result.error_message}"
                )
                portrait_row.generation_status = 'failed'
                portrait_row.error_message = tl_result.error_message
                db.session.commit()
                return
            
            tl = tl_result.topic_library
            logger.info(f"[PortraitLibraryTask] 选题库生成完成 portrait_id={portrait_id}: 总选题={len(tl.get('topics') or [])}")
            
            # ── ⑤ 保存关键词库+选题库，更新状态 ─────────────────────────────
            # 将关键词库转换为前端期望的格式（categories 数组）
            kl_for_save = _convert_keyword_library_for_frontend(kl)
            
            # 调试日志：显示转换后的 categories 数量
            if kl_for_save.get('categories'):
                cat_count = len(kl_for_save['categories'])
                logger.info(
                    "[PortraitLibraryTask] 关键词库转换后: %d 个分类, 总关键词=%d",
                    cat_count, kl_for_save.get('total_count', 0)
                )
            
            portrait_row.keyword_library = kl_for_save
            portrait_row.topic_library = tl
            portrait_row.generation_status = 'completed'

            db.session.commit()

            logger.info(
                "[PortraitLibraryTask] 关键词库+选题库生成完成 portrait_id=%d（运营规划待客户信息提交后生成）",
                portrait_id
            )
    
    except Exception as e:
        logger.error(f"[PortraitLibraryTask] 任务执行异常 portrait_id={portrait_id}: {str(e)}")
        
        # 尝试更新状态为失败
        try:
            with _flask_app.app_context():
                from models.public_models import SavedPortrait, db
                portrait_row = SavedPortrait.query.get(portrait_id)
                if portrait_row:
                    portrait_row.generation_status = 'failed'
                    portrait_row.error_message = str(e)
                    db.session.commit()
        except:
            pass
        
        raise


def submit_portrait_library_task(
    portrait_id: int,
    background: bool = True
):
    """
    提交画像词库生成任务
    
    Args:
        portrait_id: 画像记录ID
        background: 是否后台执行（默认True）
    
    Returns:
        如果 background=True，返回 Future 对象
        如果 background=False，返回生成结果
    """
    global _flask_app
    
    service = get_service()
    
    if background:
        # 后台执行：通过 submit_llm_task 自动控制 LLM 并发
        return service.submit_with_semaphore(
            generate_portrait_library_task,
            portrait_id=portrait_id,
            app_context={'app': _flask_app}
        )
    else:
        # 同步执行
        return generate_portrait_library_task(
            portrait_id=portrait_id,
            app_context={'app': _flask_app}
        )


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
    service = get_service()
    semaphore = service._llm_semaphore

    with semaphore:
        # 原子计数 +1
        with service._active_lock:
            service._active_count += 1
            active = service._active_count

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
            with service._active_lock:
                service._active_count -= 1
                remaining = service._active_count
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
    2. 生成关键词库（Geo SEO 结构）
    3. 生成选题库（五段式）
    4. 保存结果，更新状态 = 'completed' / 'failed'
    """
    from models.public_models import SavedPortrait, db
    from services.keyword_library_generator import KeywordLibraryGenerator
    from services.topic_library_generator import TopicLibraryGenerator

    try:
        # 1. 更新状态：生成中
        portrait = SavedPortrait.query.get(portrait_id)
        if portrait:
            portrait.generation_status = 'generating'
            portrait.error_message = None
            db.session.commit()

        # 2. 获取画像数据
        portrait_data_dict = portrait.portrait_data or {}
        business_description = portrait.business_description or ''
        industry = portrait.industry or ''

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

        # ── ① 生成关键词库（Geo SEO 结构）─────────────────────────────
        keyword_generator = KeywordLibraryGenerator()
        kw_result = keyword_generator.generate(
            business_info={
                'business_description': business_description,
                'industry': industry,
            },
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
        from services.topic_library_generator import TopicLibraryGenerator
        topic_generator = TopicLibraryGenerator()
        topic_result = topic_generator.generate(
            portrait_data=portrait_data_dict,
            business_info={
                'business_description': business_description,
                'industry': industry,
                'products': [],
                'target_customer': portrait.target_customer or '',
            },
            keyword_library=kl,
            plan_type=plan_type,
            portrait_id=portrait_id,
            content_stage='起号阶段',
            user_id=user_id,
        )

        if not topic_result.get('success'):
            raise Exception(topic_result.get('error', '选题库生成失败'))

        tl = topic_result.get('topic_library', {}) or {}
        logger.info(
            "[PortraitLibraryTask] 选题库生成完成 portrait_id=%d: 总选题=%d",
            portrait_id, len(tl.get('topics') or []),
        )

        # ── ③ 保存关键词库+选题库，更新状态 ─────────────────────────────
        portrait = SavedPortrait.query.get(portrait_id)
        if portrait:
            # 转换为前端格式
            kl_for_save = _convert_keyword_library_for_frontend(kl)
            portrait.keyword_library = kl_for_save
            portrait.topic_library = tl
            portrait.generation_status = 'completed'
            db.session.commit()

            logger.info(
                "[PortraitLibraryTask] 关键词库+选题库生成完成 portrait_id=%d（运营规划待客户信息提交后生成）",
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
            portrait = SavedPortrait.query.get(portrait_id)
            if portrait:
                portrait.generation_status = 'failed'
                portrait.error_message = str(e)[:500]
                db.session.commit()
        except Exception:
            pass
