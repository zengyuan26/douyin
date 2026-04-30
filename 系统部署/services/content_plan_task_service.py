"""
内容计划异步任务服务

功能：
- 任务创建和管理
- 后台线程执行
- SSE进度推送
- 任务状态查询
"""

import time
import json
import logging
import threading
import asyncio
from datetime import datetime
from typing import Dict, Optional, Callable
from functools import wraps

from flask import request, Response, stream_with_context, current_app
from werkzeug.serving import make_server

from app import db
from models.content_plan_models import Task, TaskStep
from models.public_models import PublicUser
from services.content_plan_task_executor import task_executor, STEPS, STEP_DEPENDENCIES

logger = logging.getLogger(__name__)


class ContentPlanTaskService:
    """
    内容计划异步任务服务

    使用方式：
    1. 创建任务：task = task_service.create_task(user_id, task_type, input_data)
    2. 查询状态：status = task_service.get_task_status(task_id)
    3. SSE推送：task_service.create_sse_response(task_id)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self._running_tasks = {}  # task_id -> asyncio.Task
        self._sse_clients = {}  # task_id -> list of callbacks
        self._executor_thread = None
        self._executor_loop = None
        self._running = False

        # 注册步骤处理器
        self._register_step_handlers()

    def _register_step_handlers(self):
        """注册步骤处理器"""
        from services.topic_library_generator_v3 import TopicLibraryGeneratorV3

        generator = TopicLibraryGeneratorV3()
        task_executor.register_step_handler('step_1', generator.handle_step_1)
        task_executor.register_step_handler('step_2', generator.handle_step_2)
        task_executor.register_step_handler('step_3', generator.handle_step_3)
        task_executor.register_step_handler('step_4', generator.handle_step_4)
        task_executor.register_step_handler('step_5', generator.handle_step_5)
        task_executor.register_step_handler('step_6', generator.handle_step_6)

    def start(self):
        """启动后台执行器"""
        if self._running:
            return

        self._running = True
        self._executor_thread = threading.Thread(target=self._run_executor_loop, daemon=True)
        self._executor_thread.start()
        logger.info("内容计划任务执行器已启动")

    def stop(self):
        """停止后台执行器"""
        self._running = False
        if self._executor_loop:
            asyncio.run_coroutine_threadsafe(asyncio.shutdown_default_except_loop(), self._executor_loop)
        logger.info("内容计划任务执行器已停止")

    def _run_executor_loop(self):
        """运行事件循环"""
        self._executor_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._executor_loop)
        self._executor_loop.run_forever()

    def create_task(self, user_id: int, task_type: str, input_data: Dict) -> Task:
        """
        创建新任务

        Args:
            user_id: 用户ID
            task_type: 任务类型
            input_data: 输入参数

        Returns:
            Task实例
        """
        # 预估时间（秒）
        estimated_time = self._estimate_time(task_type, input_data)

        task = Task(
            user_id=user_id,
            task_type=task_type,
            status='queued',
            progress=0,
            input_data=input_data,
            estimated_time=estimated_time,
            created_at=datetime.utcnow()
        )
        db.session.add(task)
        db.session.commit()

        logger.info(f"创建任务: id={task.id}, type={task_type}, user_id={user_id}")

        # 创建任务步骤记录
        self._create_task_steps(task)

        # 启动后台执行
        self._schedule_task(task.id)

        return task

    def _create_task_steps(self, task: Task):
        """创建任务步骤记录"""
        for step_config in STEPS:
            step = TaskStep(
                task_id=task.id,
                step_id=step_config['id'],
                step_name=step_config['name'],
                status='pending'
            )
            db.session.add(step)
        db.session.commit()

    def _estimate_time(self, task_type: str, input_data: Dict) -> int:
        """预估执行时间（秒）"""
        # 根据内容和步骤数量估算
        base_time = 60  # 基础60秒

        if input_data.get('content_types'):
            base_time += len(input_data['content_types']) * 15

        if input_data.get('topic_count'):
            base_time += input_data['topic_count'] * 0.5

        return base_time

    def _schedule_task(self, task_id: int):
        """调度任务执行"""
        if not self._executor_loop:
            self.start()

        def run_task():
            asyncio.set_event_loop(self._executor_loop)
            task = asyncio.create_task(self._execute_task(task_id))
            self._running_tasks[task_id] = task
            task.add_done_callback(lambda t: self._on_task_done(task_id, t))

        self._executor_loop.call_soon_threadsafe(run_task)

    async def _execute_task(self, task_id: int):
        """执行任务"""
        task = db.session.get(Task, task_id)
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        logger.info(f"开始执行任务: {task_id}")

        try:
            result = await task_executor.execute(
                task=task,
                progress_callback=self._broadcast_progress
            )
            return result
        except Exception as e:
            logger.exception(f"任务执行异常: {task_id}")
            with current_app.app_context():
                task.status = 'failed'
                task.error_message = str(e)
                db.session.commit()
            return None

    def _on_task_done(self, task_id: int, future):
        """任务完成回调"""
        self._running_tasks.pop(task_id, None)
        result = future.result() if not future.exception() else None
        logger.info(f"任务完成: {task_id}, result={result}")

        # 广播完成消息
        self._broadcast_progress({
            'task_id': task_id,
            'status': 'completed',
            'progress': 100,
            'result': result
        })

    def _broadcast_progress(self, data: Dict):
        """广播进度更新"""
        task_id = data.get('task_id')
        if not task_id:
            return

        # 更新SSE客户端
        if task_id in self._sse_clients:
            callbacks = self._sse_clients[task_id]
            for callback in callbacks:
                try:
                    callback(data)
                except Exception as e:
                    logger.warning(f"SSE回调失败: {e}")

    def get_task_status(self, task_id: int) -> Optional[Dict]:
        """获取任务状态"""
        task = db.session.get(Task, task_id)
        if not task:
            return None

        return {
            'id': task.id,
            'task_type': task.task_type,
            'status': task.status,
            'progress': task.progress,
            'current_step': task.current_step,
            'error_message': task.error_message,
            'estimated_time': task.estimated_time,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'created_at': task.created_at.isoformat() if task.created_at else None,
        }

    def get_task_with_steps(self, task_id: int) -> Optional[Dict]:
        """获取任务详情（含步骤）"""
        task = db.session.get(Task, task_id)
        if not task:
            return None

        steps = []
        for step in task.steps:
            steps.append({
                'step_id': step.step_id,
                'step_name': step.step_name,
                'status': step.status,
                'started_at': step.started_at.isoformat() if step.started_at else None,
                'completed_at': step.completed_at.isoformat() if step.completed_at else None,
                'duration_ms': step.duration_ms,
                'error_message': step.error_message,
            })

        return {
            'task': self.get_task_status(task_id),
            'steps': steps
        }

    def cancel_task(self, task_id: int) -> bool:
        """取消任务"""
        task = db.session.get(Task, task_id)
        if not task or task.status in ['completed', 'failed', 'cancelled']:
            return False

        task.status = 'cancelled'
        task.completed_at = datetime.utcnow()
        db.session.commit()

        # 通知执行器
        # TODO: 需要传递取消信号到执行上下文

        logger.info(f"任务已取消: {task_id}")
        return True

    def retry_task(self, task_id: int) -> Optional[Task]:
        """重试失败任务"""
        task = db.session.get(Task, task_id)
        if not task or task.status != 'failed':
            return None

        # 重置任务状态
        task.status = 'queued'
        task.progress = 0
        task.current_step = None
        task.error_message = None
        task.started_at = None
        task.completed_at = None
        db.session.commit()

        # 重置步骤状态
        for step in task.steps:
            step.status = 'pending'
            step.started_at = None
            step.completed_at = None
            step.error_message = None
        db.session.commit()

        # 重新调度
        self._schedule_task(task_id)

        logger.info(f"任务已重新调度: {task_id}")
        return task

    def subscribe_sse(self, task_id: int, callback: Callable):
        """订阅任务进度更新"""
        if task_id not in self._sse_clients:
            self._sse_clients[task_id] = []
        self._sse_clients[task_id].append(callback)

        def unsubscribe():
            if task_id in self._sse_clients and callback in self._sse_clients[task_id]:
                self._sse_clients[task_id].remove(callback)

        return unsubscribe

    def create_sse_response(self, task_id: int) -> Response:
        """创建SSE响应"""

        def generate():
            import queue
            import time

            # 发送初始连接消息
            yield f"event: connected\ndata: {json.dumps({'task_id': task_id})}\n\n"

            # 使用线程安全的队列
            q = queue.Queue()

            def on_progress(data):
                q.put_nowait(data)

            unsubscribe = self.subscribe_sse(task_id, on_progress)

            try:
                # 持续发送进度更新直到任务完成
                while True:
                    try:
                        # 使用超时获取队列数据
                        data = q.get(timeout=30)
                        event_type = data.get('status', 'progress')
                        yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                        # 检查是否完成
                        if data.get('status') in ['completed', 'failed', 'cancelled']:
                            break
                    except queue.Empty:
                        # 发送心跳
                        yield f"event: heartbeat\ndata: {json.dumps({'task_id': task_id, 'time': datetime.utcnow().isoformat()})}\n\n"

            finally:
                unsubscribe()

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    def get_running_tasks(self) -> list:
        """获取运行中的任务"""
        tasks = Task.query.filter(
            Task.status.in_(['queued', 'running'])
        ).order_by(Task.created_at.desc()).all()

        return [self.get_task_status(t.id) for t in tasks]


# =============================================================================
# 全局实例
# =============================================================================

content_plan_task_service = ContentPlanTaskService()


def init_app(app):
    """初始化应用"""
    with app.app_context():
        # 启动后台执行器
        content_plan_task_service.start()
