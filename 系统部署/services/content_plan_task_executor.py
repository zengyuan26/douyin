"""
内容计划任务执行引擎

支持：
- 步骤依赖管理
- 并行执行
- 进度追踪
- 错误处理和重试
- 实时进度回调
"""

import time
import json
import logging
import threading
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from models.content_plan_models import Task, TaskStep, TopicLibrary, ContentPlan
from models.public_models import db, SavedPortrait

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """步骤状态"""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'


class TaskStatus(Enum):
    """任务状态"""
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'


# =============================================================================
# 步骤配置
# =============================================================================

# 步骤定义
STEPS = [
    # Phase 1: 读取现有选题库（复用已有数据）
    {'id': 'step_1', 'name': '读取选题库', 'group': 0},

    # Phase 2: 内容计划生成
    {'id': 'step_2', 'name': 'H-V-F标题', 'group': 1},
    {'id': 'step_3', 'name': '金字塔标签', 'group': 1},  # 与step_2并行

    # Phase 3: 情绪动线
    {'id': 'step_4', 'name': '情绪动线', 'group': 2},  # 依赖step_2/3

    # Phase 4: 组装汇总
    {'id': 'step_5', 'name': '内容组装', 'group': 3},
    {'id': 'step_6', 'name': '最终汇总', 'group': 4},
]

# 步骤依赖关系
STEP_DEPENDENCIES = {
    'step_1': [],
    'step_2': ['step_1'],
    'step_3': ['step_1'],
    'step_4': ['step_1'],  # 情绪动线只需要选题基本信息
    'step_5': ['step_1', 'step_2', 'step_3', 'step_4'],  # 组装需要所有步骤的数据
    'step_6': ['step_5'],
}

# 步骤组（同一组的可以并行）
# 顺序：step_1 → [step_2, step_3] 并行 → step_4 → step_5 → step_6
STEP_GROUPS = {
    0: ['step_1'],
    1: ['step_2', 'step_3'],  # 并行，依赖 step_1
    2: ['step_4'],  # 依赖 step_1
    3: ['step_5'],  # 依赖所有步骤
    4: ['step_6'],
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: str
    status: StepStatus
    output_data: Optional[Dict] = None
    error_message: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ExecutionContext:
    """执行上下文"""
    task_id: int
    user_id: int
    input_data: Dict
    results: Dict[str, StepResult] = field(default_factory=dict)
    progress_callback: Optional[Callable] = None
    cancelled: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


# =============================================================================
# 任务执行引擎
# =============================================================================

class ContentPlanTaskExecutor:
    """
    内容计划任务执行引擎

    特性：
    - 步骤依赖管理
    - 组内并行执行
    - 实时进度回调
    - 错误自动重试
    - 中间结果缓存
    """

    def __init__(self, max_retries: int = 2, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.step_handlers = {}  # 步骤处理器映射

    def register_step_handler(self, step_id: str, handler: Callable):
        """注册步骤处理器"""
        self.step_handlers[step_id] = handler

    async def execute(self, task: Task, progress_callback: Optional[Callable] = None) -> Dict:
        """
        执行任务

        Args:
            task: Task模型实例
            progress_callback: 进度回调函数

        Returns:
            执行结果
        """
        # 创建执行上下文
        context = ExecutionContext(
            task_id=task.id,
            user_id=task.user_id,
            input_data=task.input_data or {},
            progress_callback=progress_callback
        )

        try:
            # 更新任务状态
            self._update_task_status(task, TaskStatus.RUNNING)

            # 按组执行步骤
            for group_id in sorted(STEP_GROUPS.keys()):
                if context.cancelled:
                    break

                steps_in_group = STEP_GROUPS[group_id]

                # 检查依赖是否都完成
                ready_steps = []
                for step_id in steps_in_group:
                    deps = STEP_DEPENDENCIES.get(step_id, [])
                    deps_completed = all(
                        context.results.get(d) is not None and context.results.get(d).status == StepStatus.COMPLETED
                        for d in deps
                    )
                    if deps_completed and step_id not in context.results:
                        ready_steps.append(step_id)

                if not ready_steps:
                    continue

                # 并行执行组内步骤
                results = await self._execute_parallel(context, ready_steps)

                # 更新进度
                progress = self._calculate_progress(context)
                self._update_task_progress(task, progress, context.results)

            # 汇总结果
            if context.cancelled:
                self._update_task_status(task, TaskStatus.CANCELLED)
                return {'status': 'cancelled'}
            else:
                self._update_task_status(task, TaskStatus.COMPLETED)
                return self._summarize_results(context)

        except Exception as e:
            logger.exception(f"任务执行失败: {e}")
            self._update_task_status(task, TaskStatus.FAILED, str(e))
            return {'status': 'failed', 'error': str(e)}

    async def _execute_parallel(self, context: ExecutionContext, step_ids: List[str]) -> List[StepResult]:
        """并行执行多个步骤"""
        tasks = []
        for step_id in step_ids:
            task = asyncio.create_task(self._execute_step(context, step_id))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        step_results = []
        for step_id, result in zip(step_ids, results):
            if isinstance(result, Exception):
                step_results.append(StepResult(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error_message=str(result)
                ))
            else:
                step_results.append(result)

            # 更新上下文
            with context.lock:
                context.results[step_id] = step_results[-1]

        return step_results

    async def _execute_step(self, context: ExecutionContext, step_id: str) -> StepResult:
        """执行单个步骤"""
        start_time = time.time()
        step_config = next((s for s in STEPS if s['id'] == step_id), None)
        step_name = step_config['name'] if step_config else step_id

        logger.info(f"[Task {context.task_id}] 开始执行步骤: {step_id} - {step_name}")

        # 更新任务当前步骤
        task = db.session.get(Task, context.task_id)
        if task:
            task.current_step = step_id
            db.session.commit()

        # 获取依赖结果
        deps_results = {}
        for dep_id in STEP_DEPENDENCIES.get(step_id, []):
            if dep_id in context.results:
                dep_result = context.results[dep_id]
                if dep_result.output_data:
                    deps_results[dep_id] = dep_result.output_data

        # 调用处理器
        handler = self.step_handlers.get(step_id)
        if not handler:
            return StepResult(
                step_id=step_id,
                status=StepStatus.SKIPPED,
                error_message=f"No handler for {step_id}"
            )

        # 执行（带重试）
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                output_data = await handler(
                    context=context,
                    step_id=step_id,
                    input_data=context.input_data,
                    deps_results=deps_results
                )

                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[Task {context.task_id}] 步骤完成: {step_id}, 耗时: {duration_ms}ms")

                return StepResult(
                    step_id=step_id,
                    status=StepStatus.COMPLETED,
                    output_data=output_data,
                    duration_ms=duration_ms
                )

            except Exception as e:
                last_error = e
                logger.warning(f"[Task {context.task_id}] 步骤失败 (尝试 {attempt + 1}/{self.max_retries + 1}): {step_id}, 错误: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        return StepResult(
            step_id=step_id,
            status=StepStatus.FAILED,
            error_message=str(last_error),
            duration_ms=int((time.time() - start_time) * 1000)
        )

    def _calculate_progress(self, context: ExecutionContext) -> int:
        """计算进度百分比"""
        total_steps = len(STEPS)
        completed_steps = sum(
            1 for r in context.results.values()
            if r.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]
        )
        return int((completed_steps / total_steps) * 100)

    def _update_task_status(self, task: Task, status: TaskStatus, error_message: str = None):
        """更新任务状态"""
        task.status = status.value
        if status == TaskStatus.RUNNING:
            task.started_at = datetime.utcnow()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            task.completed_at = datetime.utcnow()
        if error_message:
            task.error_message = error_message
        db.session.commit()

    def _update_task_progress(self, task: Task, progress: int, results: Dict[str, StepResult]):
        """更新任务进度"""
        task.progress = progress
        # 设置当前步骤为最后一个正在运行的步骤
        running_steps = [r.step_id for r in results.values() if r.status == StepStatus.RUNNING]
        if running_steps:
            task.current_step = running_steps[-1]
        db.session.commit()

        # 调用进度回调
        if task.input_data.get('_progress_callback'):
            try:
                task.input_data['_progress_callback']({
                    'task_id': task.id,
                    'progress': progress,
                    'current_step': task.current_step,
                    'results': {k: v.status.value for k, v in results.items()}
                })
            except Exception as e:
                logger.warning(f"进度回调失败: {e}")

    def _summarize_results(self, context: ExecutionContext) -> Dict:
        """汇总执行结果"""
        topics = []
        summary = {}

        # 从 step_6 (最终汇总) 获取结果
        for step_id, result in context.results.items():
            if result.step_id == 'step_6' and result.output_data:
                topics = result.output_data.get('topics_with_plan', []) or result.output_data.get('topics', [])
                summary = result.output_data.get('summary', {})

        # 保存内容计划到数据库
        self._save_content_plans(context, topics)

        return {
            'status': 'completed',
            'task_id': context.task_id,
            'topics_count': len(topics),
            'topics': topics[:10] if topics else [],
            'summary': summary
        }

    def _save_content_plans(self, context: ExecutionContext, topics: List[Dict]):
        """保存内容计划到数据库"""
        from app import db

        input_data = context.input_data or {}
        portrait_id = input_data.get('portrait_id')

        if not portrait_id:
            logger.warning("[_save_content_plans] 没有 portrait_id，无法保存")
            return

        try:
            from models.public_models import SavedPortrait
            portrait = db.session.get(SavedPortrait, portrait_id)
            if not portrait:
                logger.warning(f"[_save_content_plans] 找不到画像: {portrait_id}")
                return

            topic_library = portrait.topic_library or {}

            saved_count = 0
            for topic_data in topics:
                topic_id = topic_data.get('id')
                topic_title = topic_data.get('title', '').strip()
                content_plan_data = topic_data.get('content_plan', {})

                if not content_plan_data:
                    continue

                matched = False

                # 匹配函数
                def match_topic(db_topic):
                    if not isinstance(db_topic, dict):
                        return False
                    db_title = db_topic.get('title', '').strip()
                    db_id = db_topic.get('id')
                    # 标题匹配
                    if topic_title and db_title and db_title == topic_title:
                        return True
                    # ID 匹配
                    if topic_id and db_id and str(db_id) == str(topic_id):
                        return True
                    return False

                # 1. 先尝试在 topics 数组中匹配（旧格式）
                all_topics = topic_library.get('topics', [])
                for topic in all_topics:
                    if match_topic(topic):
                        topic['content_plan'] = content_plan_data
                        saved_count += 1
                        matched = True
                        logger.info(f"[_save_content_plans] 在 topics 中匹配: {topic_title}")
                        break

                # 2. 再尝试在各 section 中匹配（新格式）
                if not matched:
                    sections = [
                        'audience_lock_topics', 'pain_amplify_topics',
                        'solution_compare_topics', 'vision_topics',
                        'barrier_remove_topics', 'direct_need_topics',
                        'skill_tutorial_topics'
                    ]
                    for section in sections:
                        section_topics = topic_library.get(section, [])
                        for topic in section_topics:
                            if match_topic(topic):
                                topic['content_plan'] = content_plan_data
                                saved_count += 1
                                matched = True
                                logger.info(f"[_save_content_plans] 在 {section} 中匹配: {topic_title}")
                                break
                        if matched:
                            break

                if not matched:
                    logger.warning(f"[_save_content_plans] 未找到: {topic_title}")

            if saved_count > 0:
                # 强制标记 JSON 列为已修改（SQLite + SQLAlchemy JSON 列的 bug）
                db.session.flush()
                import sqlalchemy.orm.attributes
                sqlalchemy.orm.attributes.flag_modified(portrait, 'topic_library')
                portrait.topic_library = topic_library
                db.session.commit()
            else:
                logger.warning(f"[_save_content_plans] 没有找到匹配的选题")

        except Exception as e:
            logger.exception(f"[_save_content_plans] 保存失败: {e}")
            db.session.rollback()


# =============================================================================
# 步骤处理器示例
# =============================================================================

async def handle_step_1(context: ExecutionContext, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
    """读取选题库"""
    # 从 input_data 获取选题
    topics = input_data.get('topics', []) or []
    return {
        'topics': topics,
        'industry': input_data.get('industry', ''),
        'business': input_data.get('business_description', ''),
    }


async def handle_step_6(context: ExecutionContext, step_id: str, input_data: Dict, deps_results: Dict) -> Dict:
    """最终汇总 - 收集所有选题数据"""
    all_topics = []
    for dep_id in ['step_2', 'step_3', 'step_5']:
        if dep_id in deps_results:
            data = deps_results[dep_id]
            topics = data.get('topics', []) or []
            all_topics.extend(topics)

    # 去重（按选题ID）
    seen = set()
    unique_topics = []
    for t in all_topics:
        tid = t.get('id') or t.get('title', '')
        if tid not in seen:
            seen.add(tid)
            unique_topics.append(t)

    return {
        'topics': unique_topics,
        'topics_count': len(unique_topics),
    }


# =============================================================================
# 全局实例
# =============================================================================

task_executor = ContentPlanTaskExecutor(max_retries=2, retry_delay=1.0)
