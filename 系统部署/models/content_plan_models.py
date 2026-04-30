"""
内容计划相关模型

包含：TopicLibrary, ContentPlan, Task, TaskStep
"""

from datetime import datetime
from models.models import db


class TopicLibrary(db.Model):
    """
    选题库

    存储用户生成的选题列表，包含：
    - 选题基本信息（标题、类型、优先级、阶段）
    - 内容类型（图文/长文/短视频）
    - 关联的内容计划
    """
    __tablename__ = 'topic_libraries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)
    portrait_id = db.Column(db.Integer)  # 关联的画像ID

    # 选题基本信息
    title = db.Column(db.String(500), nullable=False)  # 选题标题
    type = db.Column(db.String(50), nullable=False)  # 选题类型：人群锁定/场景细分/原因分析/方案对比...
    priority = db.Column(db.String(10), nullable=False)  # 优先级：P0/P1/P2/P3
    stage = db.Column(db.String(50), nullable=False)  # 五段式阶段：受众锁定/痛点放大/方案对比/愿景勾画/顾虑消除
    content_type = db.Column(db.String(20), nullable=False)  # 内容形式：graphic/long_text/short_video

    # 状态
    status = db.Column(db.String(20), default='draft')  # draft/pending/generating/completed/failed

    # 元数据（使用 extra_data 而非 metadata）
    extra_data = db.Column(db.JSON)  # 额外信息

    # 排序
    sort_order = db.Column(db.Integer, default=0)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relationships
    content_plans = db.relationship('ContentPlan', backref='topic', lazy='dynamic', cascade='all, delete-orphan')

    # 索引
    __table_args__ = (
        db.Index('idx_topic_library_user', 'user_id'),
        db.Index('idx_topic_library_portrait', 'portrait_id'),
        db.Index('idx_topic_library_priority', 'priority'),
        db.Index('idx_topic_library_content_type', 'content_type'),
    )

    def to_dict(self, include_plans=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'portrait_id': self.portrait_id,
            'title': self.title,
            'type': self.type,
            'priority': self.priority,
            'stage': self.stage,
            'content_type': self.content_type,
            'status': self.status,
            'extra_data': self.extra_data,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_plans:
            result['content_plans'] = [plan.to_dict() for plan in self.content_plans]
        return result


class ContentPlan(db.Model):
    """
    内容计划

    存储选题的内容规划，包含：
    - 标题（H-V-F分析）
    - 标签（金字塔L1-L3）
    - 情绪动线（P1-P7）
    - 版式和视觉规范
    - 形式特有字段（图文/长文/短视频）
    """
    __tablename__ = 'content_plans'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic_libraries.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # graphic/long_text/short_video

    # ==================== 标题相关 ====================
    recommended_title = db.Column(db.String(200))  # 推荐标题
    title_options = db.Column(db.JSON, default=list)  # 备选标题列表
    title_pattern = db.Column(db.String(50))  # 标题模式：A干货/B情绪/C权威/D反常识/E悬念
    hvf_analysis = db.Column(db.JSON)  # H-V-F分析结果

    # ==================== 标签相关 ====================
    l1_tags = db.Column(db.JSON, default=list)  # L1核心公域标签
    l2_tags = db.Column(db.JSON, default=list)  # L2垂直细分标签
    l3_tags = db.Column(db.JSON, default=list)  # L3长尾场景标签
    final_tags = db.Column(db.JSON, default=list)  # 最终去重标签

    # ==================== 情绪动线 ====================
    emotional_curve = db.Column(db.JSON)  # 情绪曲线数据
    topic_type = db.Column(db.String(50))  # 选题类型：问题诊断类/知识科普类/技巧教学类/案例分享类

    # ==================== 版式相关 ====================
    layouts = db.Column(db.JSON, default=list)  # 版式序列
    colors = db.Column(db.JSON)  # 色彩策略
    visual_requirements = db.Column(db.JSON)  # 视觉规范

    # ==================== 长文特有 ====================
    article_structure = db.Column(db.JSON)  # 文章结构：开头/中间/高潮/结尾
    writing_style = db.Column(db.JSON)  # 写作风格

    # ==================== 短视频特有 ====================
    hook = db.Column(db.JSON)  # 前3秒钩子
    script_outline = db.Column(db.JSON)  # 分镜脚本
    visual_notes = db.Column(db.JSON)  # 视觉备注

    # ==================== 状态和版本 ====================
    status = db.Column(db.String(20), default='draft')  # draft/editing/completed
    version = db.Column(db.Integer, default=1)  # 版本号

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # 索引
    __table_args__ = (
        db.Index('idx_content_plan_topic', 'topic_id'),
        db.UniqueConstraint('topic_id', 'content_type', name='uq_content_plan_topic_type'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'topic_id': self.topic_id,
            'content_type': self.content_type,
            # 标题
            'recommended_title': self.recommended_title,
            'title_options': self.title_options or [],
            'title_pattern': self.title_pattern,
            'hvf_analysis': self.hvf_analysis,
            # 标签
            'l1_tags': self.l1_tags or [],
            'l2_tags': self.l2_tags or [],
            'l3_tags': self.l3_tags or [],
            'final_tags': self.final_tags or [],
            # 情绪
            'emotional_curve': self.emotional_curve,
            'topic_type': self.topic_type,
            # 版式
            'layouts': self.layouts or [],
            'colors': self.colors,
            'visual_requirements': self.visual_requirements,
            # 长文
            'article_structure': self.article_structure,
            'writing_style': self.writing_style,
            # 短视频
            'hook': self.hook,
            'script_outline': self.script_outline,
            'visual_notes': self.visual_notes,
            # 状态
            'status': self.status,
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Task(db.Model):
    """
    任务表

    存储异步任务执行记录，包含：
    - 任务类型（选题生成/内容计划生成）
    - 执行状态和进度
    - 输入输出数据
    """
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)  # topic_generation/content_plan_generation

    # 状态
    status = db.Column(db.String(20), default='queued')  # queued/running/completed/failed/cancelled
    progress = db.Column(db.Integer, default=0)  # 0-100
    current_step = db.Column(db.String(50))  # 当前执行的步骤

    # 数据
    input_data = db.Column(db.JSON, nullable=False)  # 输入参数
    result_data = db.Column(db.JSON)  # 执行结果

    # 错误
    error_message = db.Column(db.Text)

    # 时间估算
    estimated_time = db.Column(db.Integer)  # 预估秒数

    # 时间戳
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('PublicUser', backref='tasks')
    steps = db.relationship('TaskStep', backref='task', lazy='dynamic', cascade='all, delete-orphan')

    # 索引
    __table_args__ = (
        db.Index('idx_task_user', 'user_id'),
        db.Index('idx_task_status', 'status'),
    )

    def to_dict(self, include_steps=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'current_step': self.current_step,
            'input_data': self.input_data,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'estimated_time': self.estimated_time,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_steps:
            result['steps'] = [step.to_dict() for step in self.steps]
        return result

    @property
    def duration(self):
        """计算执行时长（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class TaskStep(db.Model):
    """
    任务步骤表

    存储每个任务的执行步骤详情
    """
    __tablename__ = 'task_steps'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    step_id = db.Column(db.String(50), nullable=False)  # step_1/step_2...
    step_name = db.Column(db.String(100))  # 步骤名称

    # 状态
    status = db.Column(db.String(20), default='pending')  # pending/running/completed/failed/skipped
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)  # 执行时长（毫秒）
    retry_count = db.Column(db.Integer, default=0)  # 重试次数

    # 数据
    input_data = db.Column(db.JSON)  # 输入参数
    output_data = db.Column(db.JSON)  # 输出结果

    # 错误
    error_message = db.Column(db.Text)

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 索引
    __table_args__ = (
        db.Index('idx_task_step_task', 'task_id'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'step_id': self.step_id,
            'step_name': self.step_name,
            'status': self.status,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_ms': self.duration_ms,
            'retry_count': self.retry_count,
            'input_data': self.input_data,
            'output_data': self.output_data,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def duration_seconds(self):
        """执行时长（秒）"""
        if self.duration_ms:
            return self.duration_ms / 1000
        return None
