# 方案B v3.0 完整实施计划

## ✅ 已完成阶段

### Phase 1: 基础架构 ✅

| 文件 | 说明 |
|------|------|
| `migrate_add_content_plan.py` | 数据库迁移脚本 |
| `models/content_plan_models.py` | ORM模型（TopicLibrary/ContentPlan/Task/TaskStep） |
| `docs/方案B_v3.0_完整实施计划.md` | 完整实施文档 |

### Phase 2: 后台核心 ✅

| 文件 | 说明 |
|------|------|
| `services/content_plan_task_executor.py` | 任务执行引擎（并行+依赖管理） |
| `services/content_plan_task_service.py` | 异步任务服务（SSE推送） |

### Phase 3: LLM集成 ✅

| 文件 | 说明 |
|------|------|
| `services/topic_library_generator_v3.py` | 10步选题库生成器（支持图文/长文/短视频） |

### Phase 4: API接口 ✅

| 文件 | 说明 |
|------|------|
| `routes/content_plan_api.py` | REST API（选题/内容计划/任务） |
| `app.py` (已更新) | 蓝图注册 |

## 项目概述

将 content-creator 方法论（标题/标签/情绪动线/版式）整合到 topic_library_generator，支持图文/长文/短视频三种内容形式，并实现异步并行执行。

## 现有架构分析

### 技术栈
- **后端**: Flask + SQLite + APScheduler
- **缓存**: LRU内存缓存
- **任务**: 同步调用LLM

### 现有服务
- `topic_library_generator.py`: 选题库生成（v2.0，6步）
- `keyword_library_generator.py`: 关键词库生成
- `content_generator.py`: 内容生成
- `public_cache.py`: LRU缓存服务
- `scheduler_service.py`: 定时任务服务

### 现有模型
- `SavedPortrait`: 用户画像
- `PublicGeneration`: 生成记录
- `TopicGenerationLink`: 选题使用记录

---

## Phase 1: 基础架构（数据库和模型）

### Phase 1.1: 数据库迁移 - 添加选题库和内容计划相关表

**新增表结构**:

```sql
-- 1. 选题库表 (TopicLibrary)
CREATE TABLE topic_libraries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    portrait_id INTEGER,
    title VARCHAR(500) NOT NULL,
    type VARCHAR(50) NOT NULL,
    priority VARCHAR(10) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    content_type VARCHAR(20) NOT NULL,  -- 图文/长文/短视频
    status VARCHAR(20) DEFAULT 'draft',
    metadata JSON,
    sort_order INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES public_users(id)
);

CREATE INDEX idx_topic_library_user ON topic_libraries(user_id);
CREATE INDEX idx_topic_library_portrait ON topic_libraries(portrait_id);
CREATE INDEX idx_topic_library_priority ON topic_libraries(priority);
CREATE INDEX idx_topic_library_content_type ON topic_libraries(content_type);

-- 2. 内容计划表 (ContentPlan)
CREATE TABLE content_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    content_type VARCHAR(20) NOT NULL,

    -- 标题相关
    recommended_title VARCHAR(200),
    title_options JSON DEFAULT '[]',
    title_pattern VARCHAR(50),
    hvf_analysis JSON,

    -- 标签相关
    l1_tags JSON DEFAULT '[]',
    l2_tags JSON DEFAULT '[]',
    l3_tags JSON DEFAULT '[]',
    final_tags JSON DEFAULT '[]',

    -- 情绪动线
    emotional_curve JSON,
    topic_type VARCHAR(50),

    -- 版式相关
    layouts JSON DEFAULT '[]',
    colors JSON,
    visual_requirements JSON,

    -- 长文特有
    article_structure JSON,
    writing_style JSON,

    -- 短视频特有
    hook JSON,
    script_outline JSON,
    visual_notes JSON,

    status VARCHAR(20) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,
    FOREIGN KEY (topic_id) REFERENCES topic_libraries(id) ON DELETE CASCADE
);

CREATE INDEX idx_content_plan_topic ON content_plans(topic_id);
CREATE UNIQUE INDEX idx_content_plan_topic_type ON content_plans(topic_id, content_type);

-- 3. 任务表 (Task)
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'queued',
    progress INTEGER DEFAULT 0,
    current_step VARCHAR(50),
    input_data JSON NOT NULL,
    result_data JSON,
    error_message TEXT,
    estimated_time INTEGER,
    started_at DATETIME,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES public_users(id)
);

CREATE INDEX idx_task_user ON tasks(user_id);
CREATE INDEX idx_task_status ON tasks(status);

-- 4. 任务步骤表 (TaskStep)
CREATE TABLE task_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    step_id VARCHAR(50) NOT NULL,
    step_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',
    started_at DATETIME,
    completed_at DATETIME,
    duration_ms INTEGER,
    input_data JSON,
    output_data JSON,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_task_step_task ON task_steps(task_id);
```

### Phase 1.2: ORM模型创建

创建 `services/models/content_plan_models.py`:

```python
# 内容计划相关模型
class TopicLibrary(db.Model):
    """选题库"""
    __tablename__ = 'topic_libraries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)
    portrait_id = db.Column(db.Integer)
    title = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(10), nullable=False)
    stage = db.Column(db.String(50), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # graphic/long_text/short_video
    status = db.Column(db.String(20), default='draft')
    metadata = db.Column(db.JSON)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relationships
    content_plans = db.relationship('ContentPlan', backref='topic', lazy='dynamic', cascade='all, delete-orphan')


class ContentPlan(db.Model):
    """内容计划"""
    __tablename__ = 'content_plans'

    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic_libraries.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)

    # 标题
    recommended_title = db.Column(db.String(200))
    title_options = db.Column(db.JSON, default=list)
    title_pattern = db.Column(db.String(50))
    hvf_analysis = db.Column(db.JSON)

    # 标签
    l1_tags = db.Column(db.JSON, default=list)
    l2_tags = db.Column(db.JSON, default=list)
    l3_tags = db.Column(db.JSON, default=list)
    final_tags = db.Column(db.JSON, default=list)

    # 情绪动线
    emotional_curve = db.Column(db.JSON)
    topic_type = db.Column(db.String(50))

    # 版式
    layouts = db.Column(db.JSON, default=list)
    colors = db.Column(db.JSON)
    visual_requirements = db.Column(db.JSON)

    # 长文特有
    article_structure = db.Column(db.JSON)
    writing_style = db.Column(db.JSON)

    # 短视频特有
    hook = db.Column(db.JSON)
    script_outline = db.Column(db.JSON)
    visual_notes = db.Column(db.JSON)

    status = db.Column(db.String(20), default='draft')
    version = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)


class Task(db.Model):
    """任务"""
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('public_users.id'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='queued')
    progress = db.Column(db.Integer, default=0)
    current_step = db.Column(db.String(50))
    input_data = db.Column(db.JSON, nullable=False)
    result_data = db.Column(db.JSON)
    error_message = db.Column(db.Text)
    estimated_time = db.Column(db.Integer)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('PublicUser', backref='tasks')
    steps = db.relationship('TaskStep', backref='task', lazy='dynamic', cascade='all, delete-orphan')


class TaskStep(db.Model):
    """任务步骤"""
    __tablename__ = 'task_steps'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    step_id = db.Column(db.String(50), nullable=False)
    step_name = db.Column(db.String(100))
    status = db.Column(db.String(20), default='pending')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_ms = db.Column(db.Integer)
    input_data = db.Column(db.JSON)
    output_data = db.Column(db.JSON)
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

---

## Phase 2: 后台核心

### Phase 2.1: 任务执行引擎

**文件**: `services/content_plan_task_executor.py`

核心功能：
- 步骤依赖管理
- 并行执行支持
- 进度追踪
- 错误处理和重试

```python
# 步骤依赖配置
STEP_DEPENDENCIES = {
    'step_1': [],  # 上下文分析，无依赖
    'step_2': ['step_1'],  # 五段式规划
    'step_3': ['step_1'],  # 公用选题
    'step_4': ['step_1'],  # 画像选题
    'step_5': ['step_1'],  # 关键词选题
    'step_6': ['step_3', 'step_4', 'step_5'],  # 标题生成
    'step_7': ['step_6'],  # 标签生成
    'step_8': ['step_6'],  # 情绪动线
    'step_9': ['step_7', 'step_8'],  # 内容组装
    'step_10': ['step_9'],  # 最终汇总
}

# 并行组
PARALLEL_GROUPS = [
    ['step_1'],  # 组0
    ['step_2'],  # 组1
    ['step_3', 'step_4', 'step_5'],  # 组2，并行
    ['step_6'],  # 组3
    ['step_7', 'step_8'],  # 组4，并行
    ['step_9'],  # 组5
    ['step_10'],  # 组6
]
```

### Phase 2.2: 异步任务服务

**文件**: `services/content_plan_task_service.py`

核心功能：
- 任务创建和队列管理
- 后台线程执行
- 进度更新和推送
- WebSocket集成

---

## Phase 3: LLM集成

### Phase 3.1: topic_library_generator v3.0

**文件**: `services/topic_library_generator_v3.py`

新增步骤：
1. step_6: 标题生成（H-V-F模型）
2. step_7: 标签生成（金字塔标签）
3. step_8: 情绪动线生成
4. step_9: 内容组装
5. step_10: 最终汇总（改造）

### Phase 3.2: 内容类型模板

**图文模板**:
```json
{
  "content_type": "graphic",
  "emotional_curve": ["P1期待", "P2焦虑", "P3专注", "P4坚定", "P5确信", "P6温暖", "P7信任"],
  "layouts": ["billboard", "problem-solver", "matrix", "matrix", "matrix", "trust-builder", "trust-builder"],
  "colors": {"p1": "#FFF5EE", "p2": "#708090", "p3_p5": "#F5F5DC", "p6": "#FFEFD5", "p7": "品牌主色"}
}
```

**长文模板**:
```json
{
  "content_type": "long_text",
  "emotional_curve": {"opening": "共情", "middle_1": "专注", "middle_2": "坚定", "climax": "羡慕", "ending": "温暖"},
  "structure": {"total_words": "3000-5000", "sections": 5}
}
```

**短视频模板**:
```json
{
  "content_type": "short_video",
  "emotional_curve": {"0_3s": "期待", "3_10s": "焦虑", "10_20s": "坚定", "20_30s": "温暖"},
  "duration": "30秒"
}
```

---

## Phase 4: API接口

### 4.1 选题库API

```
POST   /api/v1/topics/generate     # 创建选题生成任务
GET    /api/v1/topics             # 获取选题列表
GET    /api/v1/topics/:id         # 获取单个选题
PUT    /api/v1/topics/:id         # 更新选题
DELETE /api/v1/topics/:id         # 删除选题
```

### 4.2 内容计划API

```
GET    /api/v1/content-plans/:topic_id  # 获取内容计划
POST   /api/v1/content-plans/generate    # 生成内容计划
PUT    /api/v1/content-plans/:id        # 更新内容计划
```

### 4.3 任务API

```
POST   /api/v1/tasks                 # 创建任务
GET    /api/v1/tasks/:task_id        # 获取任务状态
GET    /api/v1/tasks/:task_id/stream # SSE进度推送
POST   /api/v1/tasks/:task_id/cancel # 取消任务
POST   /api/v1/tasks/:task_id/retry  # 重试任务
```

---

## Phase 5: 前端

### 5.1 组件设计

```
src/
├── components/
│   ├── TopicLibrary/
│   │   ├── TopicList.tsx
│   │   ├── TopicCard.tsx
│   │   ├── TopicFilters.tsx
│   │   └── TopicGenerator.tsx
│   ├── ContentPlan/
│   │   ├── ContentPlanModal.tsx
│   │   ├── TitleSelector.tsx
│   │   ├── EmotionalCurveChart.tsx
│   │   ├── TagEditor.tsx
│   │   └── LayoutPreview.tsx
│   ├── Task/
│   │   ├── TaskProgress.tsx
│   │   ├── TaskStatus.tsx
│   │   └── TaskError.tsx
│   └── common/
│       ├── Loading.tsx
│       ├── ErrorBoundary.tsx
│       └── VirtualList.tsx
├── hooks/
│   ├── useTopics.ts
│   ├── useContentPlan.ts
│   ├── useTask.ts
│   └── useSSE.ts
├── stores/
│   ├── topicStore.ts
│   ├── contentPlanStore.ts
│   └── taskStore.ts
└── services/
    ├── api.ts
    └── sse.ts
```

### 5.2 状态管理

使用 Zustand:

```typescript
interface TopicStore {
  topics: Topic[];
  loading: boolean;
  pagination: { page: number; pageSize: number; total: number };
  filters: TopicFilters;

  // Actions
  fetchTopics: (params: FetchParams) => Promise<void>;
  createTask: (params: CreateTaskParams) => Promise<Task>;
  updateTopic: (id: number, data: Partial<Topic>) => Promise<void>;
}

interface TaskStore {
  tasks: Record<string, TaskStatus>;
  currentTaskId: string | null;

  // SSE
  connectSSE: (taskId: string) => void;
  disconnectSSE: () => void;
}
```

---

## Phase 6: 性能优化

### 6.1 并行执行优化

```
串行: 60秒
并行: 30秒 (-50%)
```

### 6.2 缓存策略

```python
CACHE_TTL = {
    'topic_library': 24 * 60 * 60,  # 24小时
    'content_plan': 7 * 24 * 60 * 60,  # 7天
    'step_result': 2 * 60 * 60,  # 2小时
}
```

### 6.3 分页和懒加载

- 选题列表：每页20条
- 内容计划：按需加载

---

## 实施时间线

| Phase | 任务 | 预计时间 |
|-------|------|---------|
| Phase 1 | 数据库和模型 | 1天 |
| Phase 2 | 任务执行引擎 | 2天 |
| Phase 3 | LLM集成 | 2天 |
| Phase 4 | API接口 | 1天 |
| Phase 5 | 前端 | 2天 |
| Phase 6 | 测试和优化 | 1天 |
| **总计** | | **9天** |

---

## 风险和缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| LLM超时 | 中 | 高 | 重试机制、步骤拆分 |
| 前端性能 | 中 | 中 | 虚拟滚动、分页 |
| 并发控制 | 中 | 高 | 任务队列限流 |
