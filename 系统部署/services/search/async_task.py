"""
异步搜索任务

处理后台搜索任务
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AsyncTaskStatus(Enum):
    """异步任务状态"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"        # 失败
    SKIPPED = "skipped"      # 跳过


@dataclass
class AsyncSearchTask:
    """
    异步搜索任务

    在后台执行搜索，并更新脚本
    """

    script_id: int
    topic: str
    topic_type: str = ""
    duration: int = 60
    search_service = None  # 将在初始化时注入

    # 配置
    max_retries: int = 3
    retry_delay: float = 5.0

    # 状态
    status: AsyncTaskStatus = AsyncTaskStatus.PENDING
    references: List[Any] = field(default_factory=list)
    error_message: str = ""
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        """初始化后处理"""
        if self.search_service is None:
            # 延迟导入，避免循环引用
            from services.search.search_service import SearchService
            self.search_service = SearchService()

    async def execute(self) -> Dict[str, Any]:
        """
        执行异步搜索任务

        Returns:
            执行结果字典
        """
        self.status = AsyncTaskStatus.RUNNING
        self.started_at = datetime.now()

        logger.info(f"开始异步搜索任务: script_id={self.script_id}, topic={self.topic[:20]}...")

        try:
            # 1. 分析搜索需求
            needs = self.search_service.analyzer.analyze(
                self.topic,
                self.topic_type,
                self.duration
            )

            if not needs:
                logger.info(f"无需搜索，跳过任务: script_id={self.script_id}")
                self.status = AsyncTaskStatus.SKIPPED
                self.completed_at = datetime.now()
                return {
                    "status": AsyncTaskStatus.SKIPPED.value,
                    "message": "无需搜索"
                }

            # 2. 执行搜索
            all_refs = []
            for need in needs:
                try:
                    refs = await self.search_service.search_reference(
                        queries=need["keywords"],
                        ref_type=need["type"],
                    )
                    all_refs.extend(refs)
                except Exception as e:
                    logger.error(f"搜索失败: {e}")

            # 3. 去重
            seen = set()
            unique_refs = []
            for ref in all_refs:
                if ref.source_url not in seen:
                    seen.add(ref.source_url)
                    unique_refs.append(ref)

            # 4. 保存引用
            if unique_refs:
                await self._save_references(unique_refs)

            # 5. 更新脚本状态
            await self._update_script_status(unique_refs)

            self.status = AsyncTaskStatus.COMPLETED
            self.completed_at = datetime.now()
            self.references = unique_refs

            logger.info(
                f"异步搜索任务完成: script_id={self.script_id}, "
                f"refs={len(unique_refs)}, duration={self._get_duration()}s"
            )

            return {
                "status": AsyncTaskStatus.COMPLETED.value,
                "references_count": len(unique_refs),
                "duration_seconds": self._get_duration(),
            }

        except Exception as e:
            self.status = AsyncTaskStatus.FAILED
            self.error_message = str(e)
            self.completed_at = datetime.now()

            logger.error(f"异步搜索任务失败: script_id={self.script_id}, error={e}")

            return {
                "status": AsyncTaskStatus.FAILED.value,
                "error": str(e),
            }

    async def _save_references(self, references: List[Any]) -> None:
        """
        保存引用到数据库

        Args:
            references: 引用列表
        """
        # TODO: 实现数据库保存
        # 这里需要注入数据库服务
        logger.debug(f"保存引用: count={len(references)}")

    async def _update_script_status(self, references: List[Any]) -> None:
        """
        更新脚本状态

        Args:
            references: 引用列表
        """
        # TODO: 实现脚本更新
        # 这里需要注入脚本服务
        logger.debug(f"更新脚本状态: script_id={self.script_id}, refs={len(references)}")

    def _get_duration(self) -> float:
        """获取任务执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "script_id": self.script_id,
            "topic": self.topic,
            "topic_type": self.topic_type,
            "status": self.status.value,
            "references_count": len(self.references),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AsyncTaskQueue:
    """
    异步任务队列

    管理后台搜索任务
    """

    def __init__(self):
        """初始化任务队列"""
        self._tasks: Dict[int, AsyncSearchTask] = {}
        self._running = False

    async def add(self, task: AsyncSearchTask) -> str:
        """
        添加任务到队列

        Args:
            task: 异步搜索任务

        Returns:
            任务ID
        """
        task_id = f"search_{task.script_id}_{datetime.now().timestamp()}"
        self._tasks[task_id] = task

        logger.info(f"任务已添加: task_id={task_id}")

        # 异步执行
        asyncio.create_task(self._run_task(task_id))

        return task_id

    async def _run_task(self, task_id: str) -> None:
        """
        执行任务

        Args:
            task_id: 任务ID
        """
        task = self._tasks.get(task_id)
        if not task:
            return

        await task.execute()

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态字典
        """
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        列出所有任务

        Returns:
            任务列表
        """
        return [task.to_dict() for task in self._tasks.values()]


# 全局任务队列实例
_task_queue: Optional[AsyncTaskQueue] = None


def get_task_queue() -> AsyncTaskQueue:
    """获取任务队列实例"""
    global _task_queue
    if _task_queue is None:
        _task_queue = AsyncTaskQueue()
    return _task_queue
