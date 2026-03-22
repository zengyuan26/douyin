"""
分析任务队列服务

用于管理账号分析和内容分析任务的并发控制，避免大量任务同时执行导致 LLM API 拥堵。
"""
import threading
import time
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

# 最大同时执行的任务数
MAX_CONCURRENT_TASKS = 2

# 任务类型
TASK_TYPE_PROFILE = 'profile'           # 账号画像分析
TASK_TYPE_DESIGN = 'design'              # 账号设计分析
TASK_TYPE_SUB_CATEGORY = 'sub_category' # 二级分类分析
TASK_TYPE_ALL = 'all'                    # 全部分析
TASK_TYPE_CONTENT = 'content'            # 内容分析


class AnalysisTask:
    """分析任务"""

    def __init__(self, task_type, app=None, callback=None, extra_data=None):
        self.task_type = task_type
        self.app = app  # Flask app 对象
        self.callback = callback
        self.extra_data = extra_data or {}  # 额外数据
        self.status = 'pending'  # pending, running, completed, failed
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.progress = 0  # 0-100

    def __repr__(self):
        task_id = self.extra_data.get('content_id') or self.extra_data.get('account_id')
        return f"<AnalysisTask type={self.task_type} id={task_id} status={self.status}>"

    @property
    def task_key(self):
        """任务的唯一标识键"""
        return self.extra_data.get('content_id') or self.extra_data.get('account_id')

    @property
    def is_account_task(self):
        return 'account_id' in self.extra_data

    @property
    def is_content_task(self):
        return 'content_id' in self.extra_data


class AnalysisTaskQueue:
    """分析任务队列 - 单例模式"""

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

        self._queue = deque()  # 等待执行的任务队列
        self._running_tasks = {}  # 正在执行的任务 {task_key: task}
        self._completed_tasks = {}  # 已完成的任务 {task_key: task}
        self._task_lock = threading.Lock()
        self._worker_thread = None
        self._stop_worker = False

    def _start_worker(self):
        """启动工作线程"""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_worker = False
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        """工作线程 - 从队列中取任务执行"""
        while not self._stop_worker:
            task = None

            with self._task_lock:
                # 检查是否有空余槽位
                if len(self._running_tasks) < MAX_CONCURRENT_TASKS and self._queue:
                    task = self._queue.popleft()

            if task:
                self._execute_task(task)
            else:
                time.sleep(0.5)  # 没有任务时休眠

    def _execute_task(self, task):
        """执行任务"""
        task_key = task.task_key

        with self._task_lock:
            task.status = 'running'
            task.started_at = datetime.now()
            self._running_tasks[task_key] = task

        logger.info(f"[AnalysisTaskQueue] 开始执行任务: {task}")

        try:
            app = task.app
            if not app:
                raise ValueError("任务缺少 Flask app 对象")

            with app.app_context():
                if task.task_type == TASK_TYPE_CONTENT:
                    # 内容分析任务
                    content_id = task.extra_data.get('content_id')
                    logger.info(f"[AnalysisTaskQueue] 执行 CONTENT 分析，content_id={content_id}")

                    from services.content_analyzer import get_content_analyzer
                    analyzer = get_content_analyzer()
                    analyzer.analyze(content_id, db=None)

                    task.progress = 100
                    logger.info(f"[AnalysisTaskQueue] CONTENT 分析完成")
                else:
                    # 账号分析任务
                    account_id = task.extra_data.get('account_id')
                    task_types = task.extra_data.get('task_types', [task.task_type])

                    total_types = len(task_types)
                    for i, task_type in enumerate(task_types):
                        task.progress = int((i / total_types) * 100)

                        if task_type == TASK_TYPE_PROFILE:
                            logger.info(f"[AnalysisTaskQueue] 执行 PROFILE 分析，account_id={account_id}")
                            from routes.knowledge_api import _run_account_profile_analysis
                            _run_account_profile_analysis(app, account_id)
                            logger.info(f"[AnalysisTaskQueue] PROFILE 分析完成")
                        elif task_type == TASK_TYPE_DESIGN:
                            from routes.knowledge_api import _run_account_design_analysis
                            _run_account_design_analysis(app, account_id)
                        elif task_type == TASK_TYPE_SUB_CATEGORY:
                            logger.info(f"[AnalysisTaskQueue] 执行 SUB_CATEGORY 分析，account_id={account_id}")
                            from routes.knowledge_api import _run_account_sub_category_analysis
                            target_sub_cats = task.extra_data.get('target_sub_cats')
                            _run_account_sub_category_analysis(app, account_id, target_sub_cats=target_sub_cats)
                            logger.info(f"[AnalysisTaskQueue] SUB_CATEGORY 分析完成")

            task.status = 'completed'
            task.progress = 100
            task.completed_at = datetime.now()
            logger.info(f"[AnalysisTaskQueue] 任务完成: {task}")

        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            task.completed_at = datetime.now()
            logger.error(f"[AnalysisTaskQueue] 任务失败: {task}, error: {e}", exc_info=True)

        finally:
            with self._task_lock:
                if task_key in self._running_tasks:
                    del self._running_tasks[task_key]
                self._completed_tasks[task_key] = task

                # 清理旧任务（只保留最近100个）
                if len(self._completed_tasks) > 100:
                    keys_to_remove = list(self._completed_tasks.keys())[:50]
                    for key in keys_to_remove:
                        del self._completed_tasks[key]

    def add_task(self, task_type, app=None, callback=None, extra_data=None):
        """添加任务到队列

        Args:
            task_type: 任务类型
            app: Flask app 对象（必须）
            callback: 完成后回调函数
            extra_data: 额外数据（如 account_id, content_id, task_types）

        Returns:
            AnalysisTask: 添加的任务
        """
        task = AnalysisTask(task_type, app=app, callback=callback, extra_data=extra_data)
        task_key = task.task_key

        logger.info(f"[AnalysisTaskQueue] 添加任务: {task}")

        with self._task_lock:
            # 检查是否已有相同任务在等待
            for existing_task in self._queue:
                if existing_task.task_key == task_key:
                    logger.info(f"[AnalysisTaskQueue] 任务 {task_key} 已在等待队列中，跳过")
                    return None

            # 检查是否正在运行
            if task_key in self._running_tasks:
                running_task = self._running_tasks[task_key]
                if running_task.status == 'running':
                    logger.info(f"[AnalysisTaskQueue] 任务 {task_key} 正在执行中，跳过")
                    return None

            self._queue.append(task)
            logger.info(f"[AnalysisTaskQueue] 添加任务到队列: {task}, 队列长度: {len(self._queue)}")

        # 确保工作线程运行
        self._start_worker()

        return task

    def add_account_task(self, account_id, task_types, app=None, callback=None, extra_data=None):
        """添加账号分析任务（兼容旧接口）"""
        extra_data = extra_data or {}
        extra_data['account_id'] = account_id
        extra_data['task_types'] = task_types if isinstance(task_types, list) else [task_types]
        return self.add_task(TASK_TYPE_PROFILE, app=app, callback=callback, extra_data=extra_data)

    def add_content_task(self, content_id, app=None, callback=None, extra_data=None):
        """添加内容分析任务"""
        extra_data = extra_data or {}
        extra_data['content_id'] = content_id
        return self.add_task(TASK_TYPE_CONTENT, app=app, callback=callback, extra_data=extra_data)

    def get_task_status(self, task_key):
        """获取任务状态

        Returns:
            dict: {status, progress, error}
        """
        with self._task_lock:
            # 检查等待队列
            for task in self._queue:
                if task.task_key == task_key:
                    return {
                        'status': 'queued',
                        'progress': 0,
                        'queue_position': list(self._queue).index(task) + 1,
                        'total_in_queue': len(self._queue)
                    }

            # 检查运行中
            if task_key in self._running_tasks:
                task = self._running_tasks[task_key]
                return {
                    'status': task.status,
                    'progress': task.progress,
                    'started_at': task.started_at.isoformat() if task.started_at else None
                }

            # 检查已完成
            if task_key in self._completed_tasks:
                task = self._completed_tasks[task_key]
                return {
                    'status': task.status,
                    'progress': task.progress,
                    'error': task.error,
                    'completed_at': task.completed_at.isoformat() if task.completed_at else None
                }

            # 没有任务记录
            return {
                'status': 'not_found',
                'progress': 0
            }

    def get_queue_status(self):
        """获取队列状态"""
        with self._task_lock:
            return {
                'queued_count': len(self._queue),
                'running_count': len(self._running_tasks),
                'max_concurrent': MAX_CONCURRENT_TASKS,
                'queue_preview': [
                    {'task_key': t.task_key, 'task_type': t.task_type, 'extra_data': t.extra_data}
                    for t in list(self._queue)[:10]
                ],
                'running_preview': [
                    {'task_key': t.task_key, 'task_type': t.task_type, 'progress': t.progress}
                    for t in self._running_tasks.values()
                ]
            }

    def cancel_task(self, task_key):
        """取消任务（仅能取消等待中的任务）"""
        with self._task_lock:
            for i, task in enumerate(self._queue):
                if task.task_key == task_key:
                    self._queue[i].status = 'cancelled'
                    return True
            return False

    def clear_completed(self):
        """清理已完成任务"""
        with self._task_lock:
            self._completed_tasks.clear()


# 全局单例
_task_queue = None


def get_task_queue():
    """获取任务队列单例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = AnalysisTaskQueue()
    return _task_queue
