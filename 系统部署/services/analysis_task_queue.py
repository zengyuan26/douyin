"""
分析任务队列服务

用于管理账号分析任务的并发控制，避免大量任务同时执行导致 LLM API 拥堵。
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


class AnalysisTask:
    """分析任务"""

    def __init__(self, account_id, task_types, app=None, callback=None, extra_data=None):
        self.account_id = account_id
        self.task_types = task_types if isinstance(task_types, list) else [task_types]
        self.app = app  # Flask app 对象
        self.callback = callback
        self.extra_data = extra_data or {}  # 额外数据（如 target_sub_cats）
        self.status = 'pending'  # pending, running, completed, failed
        self.started_at = None
        self.completed_at = None
        self.error = None
        self.progress = 0  # 0-100

    def __repr__(self):
        return f"<AnalysisTask account_id={self.account_id} status={self.status} progress={self.progress}>"


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
        self._running_tasks = {}  # 正在执行的任务 {account_id: task}
        self._completed_tasks = {}  # 已完成的任务 {account_id: task}
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
        with self._task_lock:
            task.status = 'running'
            task.started_at = datetime.now()
            self._running_tasks[task.account_id] = task

        logger.info(f"[AnalysisTaskQueue] 开始执行任务: {task}")

        try:
            # 使用任务中保存的 app 对象
            app = task.app
            if not app:
                raise ValueError("任务缺少 Flask app 对象")

            total_types = len(task.task_types)

            with app.app_context():
                for i, task_type in enumerate(task.task_types):
                    task.progress = int((i / total_types) * 100)

                    if task_type == TASK_TYPE_PROFILE:
                        logger.info(f"[AnalysisTaskQueue] 执行 PROFILE 分析，account_id={task.account_id}")
                        from routes.knowledge_api import _run_account_profile_analysis
                        _run_account_profile_analysis(app, task.account_id)
                        logger.info(f"[AnalysisTaskQueue] PROFILE 分析完成")
                    elif task_type == TASK_TYPE_DESIGN:
                        from routes.knowledge_api import _run_account_design_analysis
                        _run_account_design_analysis(app, task.account_id)
                    elif task_type == TASK_TYPE_SUB_CATEGORY:
                        logger.info(f"[AnalysisTaskQueue] 执行 SUB_CATEGORY 分析，account_id={task.account_id}, extra_data={task.extra_data}")
                        from routes.knowledge_api import _run_account_sub_category_analysis
                        target_sub_cats = task.extra_data.get('target_sub_cats') if task.extra_data else None
                        _run_account_sub_category_analysis(app, task.account_id, target_sub_cats=target_sub_cats)
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
                if task.account_id in self._running_tasks:
                    del self._running_tasks[task.account_id]
                self._completed_tasks[task.account_id] = task

                # 清理旧任务（只保留最近100个）
                if len(self._completed_tasks) > 100:
                    keys_to_remove = list(self._completed_tasks.keys())[:50]
                    for key in keys_to_remove:
                        del self._completed_tasks[key]

    def add_task(self, account_id, task_types, app=None, callback=None, extra_data=None):
        """添加任务到队列

        Args:
            account_id: 账号ID
            task_types: 任务类型列表或单一类型
            app: Flask app 对象（必须）
            callback: 完成后回调函数
            extra_data: 额外数据（如 target_sub_cats）

        Returns:
            AnalysisTask: 添加的任务
        """
        task = AnalysisTask(account_id, task_types, app=app, callback=callback, extra_data=extra_data)

        logger.info(f"[AnalysisTaskQueue] 添加任务: account_id={account_id}, task_types={task_types}")

        with self._task_lock:
            # 检查是否已有相同账号的任务在等待或运行
            for existing_task in self._queue:
                if existing_task.account_id == account_id:
                    logger.info(f"[AnalysisTaskQueue] 账号 {account_id} 已有等待中的任务，跳过")
                    return None

            if account_id in self._running_tasks:
                running_task = self._running_tasks[account_id]
                if running_task.status == 'running':
                    logger.info(f"[AnalysisTaskQueue] 账号 {account_id} 正在分析中，跳过")
                    return None

            self._queue.append(task)
            logger.info(f"[AnalysisTaskQueue] 添加任务到队列: {task}, 队列长度: {len(self._queue)}, task_types: {task.task_types}")

        # 确保工作线程运行
        self._start_worker()

        return task

    def get_task_status(self, account_id):
        """获取任务状态

        Returns:
            dict: {status, progress, error}
        """
        with self._task_lock:
            # 检查等待队列
            for task in self._queue:
                if task.account_id == account_id:
                    return {
                        'status': 'queued',
                        'progress': 0,
                        'queue_position': list(self._queue).index(task) + 1,
                        'total_in_queue': len(self._queue)
                    }

            # 检查运行中
            if account_id in self._running_tasks:
                task = self._running_tasks[account_id]
                return {
                    'status': task.status,
                    'progress': task.progress,
                    'started_at': task.started_at.isoformat() if task.started_at else None
                }

            # 检查已完成
            if account_id in self._completed_tasks:
                task = self._completed_tasks[account_id]
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
                    {'account_id': t.account_id, 'task_types': t.task_types}
                    for t in list(self._queue)[:5]
                ],
                'running_preview': [
                    {'account_id': t.account_id, 'task_types': t.task_types, 'progress': t.progress}
                    for t in self._running_tasks.values()
                ]
            }

    def cancel_task(self, account_id):
        """取消任务（仅能取消等待中的任务）"""
        with self._task_lock:
            for i, task in enumerate(self._queue):
                if task.account_id == account_id:
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
