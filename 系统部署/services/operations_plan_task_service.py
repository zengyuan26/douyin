"""
运营规划异步任务服务

功能：
- 运营规划生成任务管理
- 后台线程执行
- 与画像生成流程集成
"""

import time
import json
import logging
import threading
import asyncio
from datetime import datetime
from typing import Dict, Optional

from flask import current_app

from app import db
from models.public_models import SavedPortrait
from services.operations_planner import (
    OperationsPlanner,
    generate_operations_plan,
    ContentStage,
)

logger = logging.getLogger(__name__)


class OperationsPlanTaskService:
    """
    运营规划异步任务服务

    使用方式：
    1. 创建任务：task_id = service.create_task(portrait_id, content_stage)
    2. 查询状态：status = service.get_task_status(task_id)
    3. 获取结果：result = service.get_result(task_id)
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
        self._running_tasks = {}  # portrait_id -> asyncio.Task
        self._task_results = {}  # portrait_id -> result dict
        self._task_status = {}   # portrait_id -> status dict
        self._executor_thread = None
        self._executor_loop = None
        self._running = False

    def start(self):
        """启动后台执行器"""
        if self._running:
            return

        self._running = True
        self._executor_thread = threading.Thread(target=self._run_executor_loop, daemon=True)
        self._executor_thread.start()
        logger.info("运营规划任务执行器已启动")

    def stop(self):
        """停止后台执行器"""
        self._running = False
        if self._executor_loop:
            asyncio.run_coroutine_threadsafe(asyncio.shutdown_default_except_loop(), self._executor_loop)
        logger.info("运营规划任务执行器已停止")

    def _run_executor_loop(self):
        """运行事件循环"""
        self._executor_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._executor_loop)
        self._executor_loop.run_forever()

    def create_task(
        self,
        portrait_id: int,
        content_stage: str = '成长阶段',
        target_topic_count: int = 30,
    ) -> int:
        """
        创建运营规划生成任务

        Args:
            portrait_id: 画像ID
            content_stage: 账号内容阶段
            target_topic_count: 目标选题数量

        Returns:
            任务ID（portrait_id）
        """
        # 检查是否已有运行中的任务
        if portrait_id in self._running_tasks:
            logger.info(f"运营规划任务已在运行: portrait_id={portrait_id}")
            return portrait_id

        # 启动执行器
        if not self._executor_loop:
            self.start()

        # 创建任务状态
        self._task_status[portrait_id] = {
            'status': 'queued',
            'progress': 0,
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': None,
            'error': None,
        }

        # 调度任务
        def run_task():
            asyncio.set_event_loop(self._executor_loop)
            task = asyncio.create_task(self._execute_task(
                portrait_id=portrait_id,
                content_stage=content_stage,
                target_topic_count=target_topic_count,
            ))
            self._running_tasks[portrait_id] = task
            task.add_done_callback(lambda t: self._on_task_done(portrait_id, t))

        self._executor_loop.call_soon_threadsafe(run_task)

        logger.info(f"创建运营规划任务: portrait_id={portrait_id}, stage={content_stage}")
        return portrait_id

    async def _execute_task(
        self,
        portrait_id: int,
        content_stage: str,
        target_topic_count: int,
    ):
        """执行任务"""
        self._task_status[portrait_id]['status'] = 'running'
        self._task_status[portrait_id]['progress'] = 10

        try:
            # 获取画像数据
            with current_app.app_context():
                portrait = db.session.get(SavedPortrait, portrait_id)
                if not portrait:
                    raise ValueError(f"画像不存在: {portrait_id}")

                portraits = portrait.portraits or []
                business_info = portrait.business_info or {}
                if portrait.industry:
                    business_info['industry'] = portrait.industry
                business_info['business_name'] = portrait.business_name or portrait.industry or '未知客户'

            if not portraits:
                raise ValueError(f"画像数据为空: {portrait_id}")

            self._task_status[portrait_id]['progress'] = 30

            # 生成运营规划
            plan = generate_operations_plan(
                portraits=portraits,
                business_info=business_info,
                content_stage=content_stage,
                target_topic_count=target_topic_count,
            )

            self._task_status[portrait_id]['progress'] = 70

            # 保存到画像
            with current_app.app_context():
                portrait = db.session.get(SavedPortrait, portrait_id)
                if portrait:
                    extra_data = portrait.extra_data or {}
                    extra_data['operations_plan'] = plan
                    extra_data['operations_plan_updated_at'] = datetime.utcnow().isoformat()
                    portrait.extra_data = extra_data
                    db.session.commit()

            self._task_status[portrait_id]['progress'] = 100

            # 保存结果
            self._task_results[portrait_id] = plan

            logger.info(f"运营规划生成完成: portrait_id={portrait_id}")
            return plan

        except Exception as e:
            logger.exception(f"运营规划生成失败: portrait_id={portrait_id}")
            self._task_status[portrait_id]['status'] = 'failed'
            self._task_status[portrait_id]['error'] = str(e)
            raise

    def _on_task_done(self, portrait_id: int, future):
        """任务完成回调"""
        self._running_tasks.pop(portrait_id, None)

        if future.exception():
            self._task_status[portrait_id]['status'] = 'failed'
            self._task_status[portrait_id]['error'] = str(future.exception())
            logger.error(f"运营规划任务失败: portrait_id={portrait_id}, error={future.exception()}")
        else:
            self._task_status[portrait_id]['status'] = 'completed'
            self._task_status[portrait_id]['completed_at'] = datetime.utcnow().isoformat()
            logger.info(f"运营规划任务完成: portrait_id={portrait_id}")

    def get_task_status(self, portrait_id: int) -> Optional[Dict]:
        """获取任务状态"""
        if portrait_id in self._task_status:
            return self._task_status[portrait_id]

        # 检查数据库中是否有已保存的运营规划
        try:
            with current_app.app_context():
                portrait = db.session.get(SavedPortrait, portrait_id)
                if portrait:
                    extra_data = portrait.extra_data or {}
                    if extra_data.get('operations_plan'):
                        return {
                            'status': 'completed',
                            'progress': 100,
                            'completed_at': extra_data.get('operations_plan_updated_at'),
                        }
        except Exception as e:
            logger.warning(f"查询运营规划状态失败: {e}")

        return None

    def get_result(self, portrait_id: int) -> Optional[Dict]:
        """获取任务结果"""
        # 优先从内存获取
        if portrait_id in self._task_results:
            return self._task_results[portrait_id]

        # 从数据库获取
        try:
            with current_app.app_context():
                portrait = db.session.get(SavedPortrait, portrait_id)
                if portrait:
                    extra_data = portrait.extra_data or {}
                    return extra_data.get('operations_plan')
        except Exception as e:
            logger.warning(f"获取运营规划结果失败: {e}")

        return None

    def is_task_running(self, portrait_id: int) -> bool:
        """检查任务是否正在运行"""
        return portrait_id in self._running_tasks

    def cancel_task(self, portrait_id: int) -> bool:
        """取消任务"""
        if portrait_id in self._running_tasks:
            task = self._running_tasks[portrait_id]
            task.cancel()
            self._running_tasks.pop(portrait_id, None)
            self._task_status[portrait_id]['status'] = 'cancelled'
            logger.info(f"运营规划任务已取消: portrait_id={portrait_id}")
            return True
        return False


# =============================================================================
# 全局实例
# =============================================================================

operations_plan_task_service = OperationsPlanTaskService()


def init_app(app):
    """初始化应用"""
    with app.app_context():
        # 启动后台执行器
        operations_plan_task_service.start()
