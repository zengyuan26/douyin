"""
公开内容生成平台 - 后台任务服务

功能：
1. 行业处理任务队列
2. 定时任务调度
3. 任务执行记录
"""

import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

import logging
logger = logging.getLogger(__name__)



class TaskStatus(Enum):
    """任务状态"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


class TaskType(Enum):
    """任务类型"""
    INDUSTRY_ANALYSIS = 'industry_analysis'
    KEYWORD_GENERATION = 'keyword_generation'
    TOPIC_GENERATION = 'topic_generation'
    REPORT_GENERATION = 'report_generation'


class Task:
    """任务对象"""

    def __init__(self, task_id: str, task_type: TaskType, params: Dict, callback: Callable = None):
        self.task_id = task_id
        self.task_type = task_type
        self.params = params
        self.callback = callback
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
        self.retry_count = 0
        self.max_retries = 3

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type.value,
            'status': self.status.value,
            'params': self.params,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'retry_count': self.retry_count
        }


class TaskQueue:
    """任务队列"""

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._pending_tasks: List[Task] = []
        self._lock = threading.Lock()
        self._worker_thread = None
        self._running = False

    def add_task(self, task: Task) -> str:
        """添加任务"""
        with self._lock:
            self._tasks[task.task_id] = task
            self._pending_tasks.append(task)
            return task.task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        with self._lock:
            return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.get_task(task_id)
        if task:
            return task.to_dict()
        return None

    def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        with self._lock:
            return [t for t in self._pending_tasks if t.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> List[Task]:
        """获取运行中任务"""
        with self._lock:
            return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]

    def update_task_status(self, task_id: str, status: TaskStatus,
                          result: Any = None, error: str = None):
        """更新任务状态"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                task.status = status
                task.result = result
                task.error = error

                if status == TaskStatus.RUNNING:
                    task.started_at = datetime.utcnow()
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    task.completed_at = datetime.utcnow()
                    # 从待处理列表移除
                    if task in self._pending_tasks:
                        self._pending_tasks.remove(task)

                    # 调用回调
                    if task.callback:
                        try:
                            task.callback(task)
                        except Exception as e:
                            logger.error("[TaskQueue] 回调执行失败: %s", e)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            self.update_task_status(task_id, TaskStatus.CANCELLED)
            return True
        return False

    def retry_task(self, task_id: str) -> bool:
        """重试任务"""
        task = self.get_task(task_id)
        if task and task.status == TaskStatus.FAILED and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            task.error = None
            with self._lock:
                self._pending_tasks.append(task)
            return True
        return False

    def start_worker(self, max_workers: int = 2):
        """启动任务处理工作线程"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, args=(max_workers,), daemon=True)
        self._worker_thread.start()
logger.debug("[TaskQueue] 工作线程已启动")

    def stop_worker(self):
        """停止工作线程"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
logger.debug("[TaskQueue] 工作线程已停止")

    def _worker_loop(self, max_workers: int):
        """工作线程主循环"""
        while self._running:
            pending = self.get_pending_tasks()
            if not pending:
                time.sleep(1)
                continue

            task = pending[0]
            self._execute_task(task)

    def _execute_task(self, task: Task):
        """执行任务"""
        try:
            self.update_task_status(task.task_id, TaskStatus.RUNNING)

            if task.task_type == TaskType.INDUSTRY_ANALYSIS:
                result = self._execute_industry_analysis(task.params)
            elif task.task_type == TaskType.KEYWORD_GENERATION:
                result = self._execute_keyword_generation(task.params)
            elif task.task_type == TaskType.TOPIC_GENERATION:
                result = self._execute_topic_generation(task.params)
            elif task.task_type == TaskType.REPORT_GENERATION:
                result = self._execute_report_generation(task.params)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")

            self.update_task_status(task.task_id, TaskStatus.COMPLETED, result=result)

        except Exception as e:
            error_msg = f"任务执行失败: {str(e)}"
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                logger.warning("[TaskQueue] 任务失败，将在 %s 次后重试", task.max_retries - task.retry_count)
            else:
                self.update_task_status(task.task_id, TaskStatus.FAILED, error=error_msg)
                logger.error("[TaskQueue] %s", error_msg)

    def _execute_industry_analysis(self, params: Dict) -> Dict:
        """执行行业分析任务"""
        # TODO: 调用行业分析服务
        return {'status': 'completed'}

    def _execute_keyword_generation(self, params: Dict) -> Dict:
        """执行关键词生成任务"""
        # TODO: 调用关键词生成服务
        return {'status': 'completed'}

    def _execute_topic_generation(self, params: Dict) -> Dict:
        """执行选题生成任务"""
        # TODO: 调用选题生成服务
        return {'status': 'completed'}

    def _execute_report_generation(self, params: Dict) -> Dict:
        """执行报告生成任务"""
        # TODO: 调用报告生成服务
        return {'status': 'completed'}


class BackgroundTaskService:
    """后台任务服务"""

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
        self._queue = TaskQueue()
        self._start_time = datetime.utcnow()

    @property
    def queue(self) -> TaskQueue:
        """获取任务队列"""
        return self._queue

    def submit_industry_analysis(self, industry_name: str, params: Dict) -> str:
        """提交行业分析任务"""
        task_id = f"industry_{industry_name}_{int(time.time())}"
        task = Task(
            task_id=task_id,
            task_type=TaskType.INDUSTRY_ANALYSIS,
            params={'industry_name': industry_name, **params}
        )
        return self._queue.add_task(task)

    def submit_keyword_generation(self, industry: str, params: Dict) -> str:
        """提交关键词生成任务"""
        task_id = f"keyword_{industry}_{int(time.time())}"
        task = Task(
            task_id=task_id,
            task_type=TaskType.KEYWORD_GENERATION,
            params={'industry': industry, **params}
        )
        return self._queue.add_task(task)

    def submit_topic_generation(self, industry: str, params: Dict) -> str:
        """提交选题生成任务"""
        task_id = f"topic_{industry}_{int(time.time())}"
        task = Task(
            task_id=task_id,
            task_type=TaskType.TOPIC_GENERATION,
            params={'industry': industry, **params}
        )
        return self._queue.add_task(task)

    def submit_report_generation(self, industry: str, params: Dict) -> str:
        """提交报告生成任务"""
        task_id = f"report_{industry}_{int(time.time())}"
        task = Task(
            task_id=task_id,
            task_type=TaskType.REPORT_GENERATION,
            params={'industry': industry, **params}
        )
        return self._queue.add_task(task)

    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self._queue.get_task_status(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self._queue.cancel_task(task_id)

    def retry_task(self, task_id: str) -> bool:
        """重试任务"""
        return self._queue.retry_task(task_id)

    def start(self):
        """启动服务"""
        self._queue.start_worker(max_workers=2)
logger.debug("[BackgroundTaskService] 服务已启动")

    def stop(self):
        """停止服务"""
        self._queue.stop_worker()
logger.debug("[BackgroundTaskService] 服务已停止")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        pending = len(self._queue.get_pending_tasks())
        running = len(self._queue.get_running_tasks())
        total = len(self._queue._tasks)

        return {
            'total_tasks': total,
            'pending_tasks': pending,
            'running_tasks': running,
            'uptime': (datetime.utcnow() - self._start_time).total_seconds()
        }


# 全局实例
task_service = BackgroundTaskService()
