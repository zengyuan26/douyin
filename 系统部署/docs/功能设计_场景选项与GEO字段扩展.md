# 星系图谱增强功能 — 详细设计文档

> 文档版本：v1.2
> 日期：2026-04-09
> 状态：待确认

---

## 一、需求概述

本方案包含三个独立功能增强：

| # | 功能名称 | 核心描述 |
|---|---------|---------|
| F1 | **场景选项（scene_options）** | 选题时预置 AI 生成的多维度场景组合，客户直接选择而非自行拆解 |
| F2 | **GEO 字段扩展** | 在现有星系图谱接口上扩展地理位置相关字段，支持地域化内容分析 |
| F3 | **恒星缩略图（cover_thumb）** | 为用户画像节点提供可视化缩略图，提升星系图谱的视觉识别度 |

三者共享同一 URL 前缀（`/public/api/galaxy/*`），统一扩展现有接口字段，不新建独立 API。

---

## 二、功能一：场景选项（scene_options）

### 2.1 概念定义

#### 2.1.1 什么是"场景选项"

场景选项是 AI 在生成选题时，自动为每个选题预置的**多维度场景组合**。

客户无需理解"人群-时间-情境-痛点"这些维度，只需从预置选项中**勾选/单选**一个组合即可。

#### 2.1.2 场景选项 vs 业务场景（语义区分）

> ⚠️ **重要**：本字段与现有 `applicable_scenarios` 名称相似，但语义完全不同，两者均需保留：

| 字段 | 语义 | 示例 |
|------|------|------|
| `applicable_scenarios` | **业务场景维度**（营销策略） | `["种草", "带货", "品牌宣传"]` |
| `scene_options` | **内容场景组合**（内容策略） | `["高三家长 + 出分后 + 焦虑"]` |

```
applicable_scenarios = 选题用于什么业务目的（卖给谁）
scene_options = 内容针对什么用户场景（怎么写）
```

两者在代码中需加注释严格区分语义，避免维护时混淆。

#### 2.1.3 场景选项的生成逻辑

参考「茶艺爱好者」案例的方法论：

```
1. 确定人群（Who）   → 高三家长 / 高三学生 / 复读生家长
2. 拆解场景（When）   → 出分前 / 出分时 / 填报时 / 截止前
3. 匹配情境（How）   → 每个时间节点对应的具体心理状态
4. 验证痛点（Why）    → 所有场景都指向同一核心选题
```

**选题示例：专业调剂要不要勾**

```json
[
  {
    "id": "scene_001",
    "组合": "高三家长 + 出分后 + 勾/不勾两难 + 怕被调剂",
    "标签": "焦虑型家长",
    "风格": "情绪共鸣"
  },
  {
    "id": "scene_002",
    "组合": "高三学生 + 填报期间 + 规则不熟 + 怕报错",
    "标签": "新手学生",
    "风格": "干货科普"
  },
  {
    "id": "scene_003",
    "组合": "高三家长 + 截止前夕 + 时间紧迫 + 决策困难",
    "标签": "紧迫型",
    "风格": "犀利吐槽"
  }
]
```

### 2.2 数据模型设计

#### 2.2.1 扩展 `PublicIndustryTopic` 模型

**文件**：`系统部署/models/public_models.py`

```python
class PublicIndustryTopic(db.Model):
    """行业选题库"""
    __tablename__ = 'public_industry_topics'

    # ... 现有字段保持不变 ...

    # === 新增字段 ===
    # 【内容策略】AI 自动生成的多维度场景组合（与 applicable_scenarios 业务场景维度正交）
    # 结构：[{"id": "...", "组合": "...", "标签": "...", "风格": "..."}]
    scene_options = db.Column(JSON, default=list)

    # 风格类型（用于内容生成时的风格指导）
    # 枚举：情绪共鸣 / 干货科普 / 犀利吐槽 / 故事叙述 / 权威背书
    content_style = db.Column(db.String(50))
```

#### 2.2.2 扩展 `PublicGeneration` 模型

**文件**：`系统部署/models/public_models.py`

```python
class PublicGeneration(db.Model):
    """公开用户生成记录表"""
    __tablename__ = 'public_generations'

    # ... 现有字段保持不变 ...

    # === 新增字段 ===
    # 客户选择的具体场景组合（从 scene_options 中选取）
    selected_scenes = db.Column(JSON, default=list)
    # 例：{"scene_id": "scene_001", "组合": "高三家长 + 出分后 + ...", "标签": "焦虑型家长"}
```

#### 2.2.3 字段对比

| 模型 | 字段 | 类型 | 说明 |
|------|------|------|------|
| `PublicIndustryTopic` | `scene_options` | JSON 数组 | AI 生成的预置场景组合列表（内容策略） |
| `PublicIndustryTopic` | `content_style` | 字符串 | 风格类型 |
| `PublicIndustryTopic` | `applicable_scenarios` | JSON 数组 | **保留**，业务场景（种草/带货/引流）不变（营销策略） |
| `PublicGeneration` | `selected_scenes` | JSON 对象 | 客户选中的场景组合 |

### 2.3 API 扩展设计

#### 2.3.1 选题查询接口扩展

**端点**：`GET /public/api/topics`（现有接口扩展）

**新增返回字段**：

```json
{
  "success": true,
  "data": {
    "topics": [
      {
        "id": 1,
        "title": "云南高考500分能选哪些学校",
        "description": "...",
        "applicable_scenarios": ["新客户获取", "老客户复购"],
        "scene_options": [
          {
            "id": "scene_001",
            "组合": "高三家长 + 出分后 + 分数尴尬 + 怕浪费分",
            "标签": "焦虑型家长",
            "风格": "情绪共鸣"
          },
          {
            "id": "scene_002",
            "组合": "高三学生 + 填报期间 + 信息不足 + 选择困难",
            "标签": "迷茫学生",
            "风格": "干货科普"
          }
        ],
        "content_style": "情绪共鸣"
      }
    ]
  }
}
```

#### 2.3.2 内容生成接口扩展

**端点**：`POST /public/api/generate`（现有接口扩展）

**新增请求字段**：

```json
{
  "topic_id": 1,
  "selected_scene": {
    "scene_id": "scene_001",
    "组合": "高三家长 + 出分后 + 分数尴尬 + 怕浪费分",
    "标签": "焦虑型家长"
  },
  "content_style": "情绪共鸣",
  "geo_location": "昆明"
}
```

### 2.4 前端交互设计

#### 2.4.1 选题卡片展示

```
┌──────────────────────────────────────────────────────┐
│  云南高考500分能选哪些学校                             │
│  描述：帮500分左右的考生找到性价比最高的学校...         │
│                                                      │
│  适用场景：种草 / 带货                                 │  ← applicable_scenarios（营销策略）
│                                                      │
│  ▶ 场景选项                                          │  ← scene_options（内容策略）
│    ○ 高三家长 + 出分后 + 分数尴尬 + 怕浪费分          │
│      标签：焦虑型家长  |  风格：情绪共鸣              │
│    ● 高三学生 + 填报期间 + 信息不足 + 选择困难        │
│      标签：迷茫学生  |  风格：干货科普   ← 已选       │
│    ○ 高三家长 + 截止前夕 + 时间紧迫 + 决策困难        │
│      标签：紧迫型  |  风格：犀利吐槽                  │
│                                                      │
│  [开始生成]                                           │
└──────────────────────────────────────────────────────┘
```

#### 2.4.2 交互规则

- 场景选项默认**单选**
- 客户选择后，生成内容时自动带入场景信息
- 如果客户未选择，使用选题的第一个场景组合作为默认值
- 风格（content_style）跟随选中的场景自动带入，也可手动切换

### 2.5 场景生成时机

| 时机 | 说明 |
|------|------|
| 选题创建时 | AI 一次性生成 3-5 个场景组合 |
| 画像专属选题生成时 | AI 根据画像特征定制场景组合 |
| 管理员编辑选题时 | 可手动调整/增删场景选项 |

---

## 三、功能二：GEO 字段扩展

### 3.1 需求背景

现有星系图谱接口需要扩展地理位置信息，支持：
- 恒星（画像）关联的地域信息
- 行星（问题）的地域触发场景
- 卫星（内容）覆盖的地域范围

### 3.2 扩展字段说明

#### 3.2.1 恒星节点扩展（`/node/star/<id>`）

**新增返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `geo_province` | string | 主要省份 |
| `geo_city` | string | 主要城市 |
| `geo_level` | string | 地域粒度：`province` / `city` / `district` |
| `geo_coverages` | JSON 数组 | 覆盖地域列表（多地域时） |
| `geo_tags` | JSON 数组 | 地域标签，如 `["高考大省", "西南地区"]` |

**示例**：

```json
{
  "success": true,
  "data": {
    "portrait_id": 1,
    "name": "云南高考家长",
    "geo_province": "云南",
    "geo_city": "昆明",
    "geo_level": "city",
    "geo_coverages": ["昆明", "曲靖", "大理", "红河"],
    "geo_tags": ["西南地区", "高考大省"],
    "generation_count": 128
  }
}
```

#### 3.2.2 行星节点扩展（`/node/planet/<id>`）

> ⚠️ **注意**：`PersonaUserProblem` 模型定义在 `models/models.py`（第 1101 行），**不是** `models/public_models.py`。迁移脚本需分别指向不同文件。

**新增返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `geo_trigger_regions` | JSON 数组 | 触发问题的地域列表 |
| `geo_seasonal_factor` | string | 季节性因素，如 "高考出分季（6月底-7月初）" |

**示例**：

```json
{
  "success": true,
  "data": {
    "problem_id": 1,
    "name": "志愿填报焦虑",
    "geo_trigger_regions": ["云南", "贵州", "四川"],
    "geo_seasonal_factor": "高考出分季（6月底-7月初）",
    "generation_count": 89
  }
}
```

#### 3.2.3 卫星节点扩展（`/node/satellite/<id>`）

**新增返回字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `geo_target_regions` | JSON 数组 | 内容目标地域 |
| `geo_adaptation_level` | string | 地域适配度：`high` / `medium` / `low` |

**示例**：

```json
{
  "success": true,
  "data": {
    "generation_id": 1,
    "titles": ["云南高考500分能选哪些学校"],
    "geo_target_regions": ["云南"],
    "geo_adaptation_level": "high",
    "total_count": 12
  }
}
```

#### 3.2.4 星系概览扩展（`/graph`）

**节点数据新增字段**：

```json
{
  "nodes": [
    {
      "id": "star_1",
      "type": "star",
      "portrait_id": 1,
      "name": "云南高考家长",
      "geo_province": "云南",
      "geo_city": "昆明",
      "geo_level": "city",
      "cover_thumb": "https://xxx.com/portrait-thumb.png"
    },
    {
      "id": "planet_1",
      "type": "planet",
      "problem_id": 1,
      "name": "志愿填报焦虑",
      "geo_trigger_regions": ["云南", "贵州"],
      "geo_seasonal_factor": "高考出分季"
    }
  ]
}
```

### 3.3 数据来源

| 字段来源 | 说明 |
|---------|------|
| 用户画像输入 | 客户在创建画像时选择地域 |
| 内容生成参数 | 生成内容时指定目标地域 |
| AI 自动推断 | 根据行业和内容自动推断地域标签 |
| 画像专属地域库 | 画像关联的关键词/选题库中的地域信息 |

---

## 四、功能三：恒星缩略图（cover_thumb）

### 4.1 字段定义

| 属性 | 值 |
|------|-----|
| 字段名 | `cover_thumb` |
| 所属表 | `saved_portraits`（用户画像表，对应恒星节点） |
| 字段类型 | `VARCHAR(255)` |
| 默认值 | `''`（空字符串） |
| 存储内容 | 图片的网络 URL（不存储文件本身） |

### 4.2 核心作用

在「星系 - 恒星 - 行星 - 卫星」模型中：

- `saved_portraits` 表对应的是「恒星」（用户画像）
- `cover_thumb` 存储的缩略图就是「恒星节点」的视觉图标
- 前端通过该字段的 URL，在 ECharts 可视化图表中加载图片
- 让用户直观识别不同画像节点，无需看文字就能快速定位

### 4.3 应用示例

```
B 端画像（如"SaaS企业决策者"）
  → cover_thumb = https://xxx.com/logos/company-thumb.png（企业 Logo）

C 端画像（如"新手宝妈"）
  → cover_thumb = https://xxx.com/icons/mom-baby-thumb.png（场景示意图）

默认空值
  → 前端显示金色圆形占位图（与恒星节点默认样式一致）
```

### 4.4 图片规范（建议）

| 规格 | 参数 |
|------|------|
| 尺寸 | 200×200 像素（正方形） |
| 格式 | JPG / PNG |
| 文件大小 | ≤ 3MB |
| 存储服务 | 阿里云 OSS / 七牛云 / 本地静态资源 |

---

## 五、API 接口完整规范

### 5.1 接口总览

> ⚠️ **路径规范**：所有端点统一使用 `/public/api/galaxy/*` 前缀，与现有 Blueprint 保持一致。不得新建 `/public/galaxy/*`（无 `/api`）前缀的平行路由。

| 方法 | 路径 | 功能 | 新增字段 |
|------|------|------|---------|
| GET | `/public/api/galaxy/graph` | 星系概览 | `geo_*` + `cover_thumb` |
| GET | `/public/api/galaxy/node/star/<id>` | 恒星详情 | `geo_*` + `cover_thumb` |
| GET | `/public/api/galaxy/node/planet/<id>` | 行星详情 | `geo_*` |
| GET | `/public/api/galaxy/node/satellite/<id>` | 卫星详情 | `geo_*` |
| POST | `/public/api/galaxy/generation/link` | 关联生成记录 | `selected_scenes` |
| GET | `/public/api/topics` | 选题列表 | `scene_options` + `content_style` |
| POST | `/public/api/generate` | 内容生成 | `selected_scene` |

### 5.2 端点复用说明

| 数据 | 现有端点 | 职责边界 |
|------|---------|---------|
| 内容结构（graphic / video / long_text） | `GET /public/api/content/structures` | 已存在，直接复用，无需新建 `options` 端点 |
| 场景选项（scene_options） | `GET /public/api/topics` | 扩展返回字段，带入 `scene_options` 数组 |

### 5.3 错误处理

| 错误码 | 说明 |
|-------|------|
| 400 | 参数错误（缺少必填字段） |
| 401 | 未登录 |
| 404 | 资源不存在 |
| 422 | 场景选项不存在 |
| 500 | 服务器内部错误 |

---

## 六、数据库迁移

### 6.1 迁移文件对应关系

| 表名 | 模型所在文件 | 说明 |
|------|------------|------|
| `public_industry_topics` | `models/public_models.py` | 公开端选题库 |
| `public_generations` | `models/public_models.py` | 公开端生成记录 |
| `saved_portraits` | `models/models.py` | 恒星节点（画像） |
| `persona_user_problems` | `models/models.py` | 行星节点（问题） |

> ⚠️ **注意**：`PersonaUserProblem` 和 `SavedPortrait` 在 `models/models.py`（admin 端/私域），不是 `models/public_models.py`（公开端/公域）。迁移脚本需分别指向不同文件。

### 6.2 完整迁移 SQL（共 8 个字段 + 2 个索引）

```sql
-- =============================================
-- PublicIndustryTopic 新增字段
-- 文件：models/public_models.py
-- =============================================
ALTER TABLE public_industry_topics
ADD COLUMN scene_options JSON DEFAULT '[]';

ALTER TABLE public_industry_topics
ADD COLUMN content_style VARCHAR(50);


-- =============================================
-- PublicGeneration 新增字段
-- 文件：models/public_models.py
-- =============================================
ALTER TABLE public_generations
ADD COLUMN selected_scenes JSON;


-- =============================================
-- SavedPortrait 新增字段（恒星）
-- 文件：models/models.py
-- =============================================
ALTER TABLE saved_portraits
ADD COLUMN cover_thumb VARCHAR(255) DEFAULT '';

ALTER TABLE saved_portraits
ADD COLUMN geo_province VARCHAR(50);

ALTER TABLE saved_portraits
ADD COLUMN geo_city VARCHAR(50);

ALTER TABLE saved_portraits
ADD COLUMN geo_level VARCHAR(20) DEFAULT 'city';

ALTER TABLE saved_portraits
ADD COLUMN geo_coverages JSON DEFAULT '[]';

ALTER TABLE saved_portraits
ADD COLUMN geo_tags JSON DEFAULT '[]';


-- =============================================
-- PersonaUserProblem 新增字段（行星）
-- 文件：models/models.py
-- =============================================
ALTER TABLE persona_user_problems
ADD COLUMN geo_trigger_regions JSON DEFAULT '[]';

ALTER TABLE persona_user_problems
ADD COLUMN geo_seasonal_factor VARCHAR(100);
```

### 6.3 历史数据默认值策略

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `geo_*` 字段（GEO 地域） | `null` | 表示未分类，前端展示"全国" |
| `scene_options` | `[]`（空数组） | 选题创建时由 AI 填充 |
| `cover_thumb` | `''`（空字符串） | 前端显示默认金色圆形占位图 |
| `selected_scenes` | `null` | 客户未选择时为空 |

### 6.4 索引建议

```sql
-- GEO 字段索引（按地域查询时使用）
CREATE INDEX idx_portrait_geo ON saved_portraits(user_id, geo_province, geo_city);
CREATE INDEX idx_topic_scene ON public_industry_topics(industry, is_active);
```

---

## 七、现有系统重叠/冲突分析

### 7.1 架构现状梳理

现有系统与新需求的关系，归纳为以下五类：

| 关系 | 说明 | 涉及模块 |
|------|------|---------|
| 已完全实现 | 现有代码已完整满足需求 | ECharts 力导向图、节点详情面板 |
| 重叠可复用 | 现有功能部分重叠，稍作扩展即可 | Galaxy Graph 结构、`/graph` 接口 |
| 部分重叠需扩展 | 现有功能存在但需扩展字段/逻辑 | `public_generations`、`public_industry_topics` |
| 完全空白需新建 | 现有代码中不存在 | `galaxy_service.py`、`scene_options` 生成逻辑 |
| 存在潜在冲突 | 语义或路径可能重叠 | `applicable_scenarios` vs `scene_options` |

### 7.2 各模块详细分析

#### 7.2.1 后端路由 — Galaxy API

**文件**：`routes/galaxy_api.py`

| 现有端点 | 新需求端点 | 重叠关系 |
|---------|----------|---------|
| `GET /public/api/galaxy/graph` | 扩展字段 | 完全重叠，路径一致，仅扩展返回字段 |
| `GET /public/api/galaxy/node/star/<id>` | 扩展字段 | 功能重叠，扩展 GEO + cover_thumb |
| `GET /public/api/galaxy/node/satellite/<id>` | 扩展字段 | 功能重叠，已有 `history_list` |

**分析**：现有 Blueprint 前缀为 `/public/api/galaxy`，新需求**统一扩展现有端点**，不新建平行 Blueprint。

#### 7.2.2 数据库模型 — public_generations

**文件**：`models/public_models.py`

| 字段 | 状态 | 说明 |
|------|------|------|
| `portrait_id` | ✅ 已存在 | 通过 `migrate_galaxy_fields.py` 已迁移 |
| `problem_id` | ✅ 已存在 | 同上 |
| `geo_mode` / `selected_scenes` / `content_style` | ❌ 新增 | 低风险，可直接新增列 |

#### 7.2.3 数据库模型 — public_industry_topics

**文件**：`models/public_models.py`

| 字段 | 与现有字段关系 | 冲突风险 |
|------|--------------|---------|
| `scene_options` | 与 `applicable_scenarios` 语义**正交** | ✅ 无冲突，已在 2.1.2 节明确区分 |
| `content_style` | 独立新增 | 低 |

#### 7.2.4 服务层 — content_generator.py

**文件**：`services/content_generator.py`

- `galaxy_service.py` 作为**独立新建文件**（不存在冲突）
- GEO 模式是**新增正交维度**，与现有 20 种结构不是替代关系

#### 7.2.5 前端页面 — galaxy.html / produce.html

| 文件 | 现有能力 | 扩展需求 |
|------|---------|---------|
| `galaxy.html` | ECharts Graph、节点详情面板 | GEO 字段展示、cover_thumb 图标渲染 |
| `produce.html` | 选题列表、内容生成 | 场景选择器（注意折叠分组，避免功能堆积） |

### 7.3 服务层职责边界

> ⚠️ **重要**：服务层新建需明确职责定位，推荐**方案 A**：

| 方案 | 职责 | 侵入程度 |
|------|------|---------|
| **方案 A（推荐）** | `galaxy_service.py` 仅做数据聚合/格式化，`galaxy_api.py` 调用服务层 | **低** — 路由层不变 |
| 方案 B（不推荐） | 将 `galaxy_api.py` 的查询逻辑搬到服务层，路由仅做转发 | **高** — 改动路由层 |

**方案 A 架构**：

```
galaxy_api.py（路由层）
    ↓ 调用
galaxy_service.py（数据聚合层，仅做查询结果的聚合和格式化）
    ↓ 查询
models.py / public_models.py（数据层）
```

---

## 八、风险评估总结

### 8.1 各维度风险等级

| 维度 | 风险等级 | 说明 |
|------|---------|------|
| 数据库 | **低** | 新增字段为主，`problem_id`/`portrait_id` 已存在，向后兼容 |
| 后端路由 | **中** | Galaxy API 端点路径与现有高度重叠，严格遵循「新增非覆盖」策略 |
| 服务层 | **低** | `galaxy_service.py` 可独立新建，**仅做数据聚合（方案 A）** |
| 前端页面 | **中-高** | `galaxy.html` 和 `produce.html` 已有，需扩展；注意 produce.html 不堆叠功能 |
| 内容生成 | **低** | GEO 是新增正交维度，与现有 20 种结构不冲突 |

### 8.2 风险矩阵（完整版）

| 风险项 | 概率 | 影响 | 应对措施 |
|-------|------|------|---------|
| `/graph` 响应结构变更破坏前端 | 中 | 中 | 严格遵循「新增字段，非覆盖」策略 |
| scene_options 生成质量不稳定 | 高 | 中 | 提供人工审核入口，Phase 5 才接入生成流程 |
| GEO 字段数据稀疏（历史数据） | 中 | 低 | 前端默认展示"全国"，降级友好 |
| produce.html 功能堆积 | 中 | 高 | 场景选择器默认折叠，不影响现有操作流 |
| cover_thumb 空值导致图标不显示 | 低 | 低 | 前端 fallback 默认金色圆形图标 |
| 端点路径命名不一致 | 中 | 高 | 统一使用 `/public/api/galaxy/*` 前缀 |
| 服务层 vs 路由层职责不清 | 高 | 高 | **明确采用方案 A**：服务层仅做数据聚合 |
| scene_options 与 applicable_scenarios 混用 | 中 | 中 | 加注释严格区分语义（见 2.1.2 节） |
| PersonaUserProblem 迁移脚本指向错误文件 | 低 | 中 | 确认 `models/models.py` 而非 `public_models.py` |

### 8.3 关键重叠发现

现有系统已实现了约 **85%** 的星系可视化功能：

```
已实现 ✅
  · Galaxy Graph 三层结构（恒星/行星/卫星）
  · ECharts 力导向图可视化
  · 节点详情面板
  · 历史记录查询
  · problem_id/portrait_id 迁移逻辑（migrate_galaxy_fields.py）
  · /graph /star /planet /satellite 接口

本次新增 ❌
  · scene_options 字段存储
  · selected_scenes 字段存储
  · GEO 地域字段（portrait / problem 层）
  · cover_thumb 缩略图字段
  · 场景选择器组件（produce.html）
  · GEO 节点属性展示（galaxy.html）
  · 内容生成 Prompt 集成 GEO 维度
  · galaxy_service.py（数据聚合层）
```

---

## 九、实施计划

### 9.1 阶段划分

| 阶段 | 内容 | 优先级 | 关键注意事项 |
|------|------|--------|------------|
| Phase 1 | 数据库迁移（8 个字段 + 2 个索引） | P0 | `PersonaUserProblem` 和 `SavedPortrait` 在 `models/models.py` |
| Phase 2 | 服务层新建 `galaxy_service.py`（仅数据聚合，方案 A） | P0 | 不搬移 `galaxy_api.py` 逻辑，仅做数据聚合 |
| Phase 3 | API 接口扩展（GEO 字段返回） | P0 | 严格「新增非覆盖」策略 |
| Phase 4 | 前端扩展 `galaxy.html`（GEO 展示 + cover_thumb 图标） | P1 | 在现有节点属性中展示，不新增节点类型 |
| Phase 5 | 前端扩展 `produce.html`（场景选择器） | P1 | 默认折叠，不影响现有操作流 |
| Phase 6 | 内容生成流程集成（scene_options + GEO 带入 Prompt） | P2 | 条件分支，不改默认生成路径 |
| Phase 7 | 测试与优化 | P2 | — |

### 9.2 改动范围

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `系统部署/models/public_models.py` | 修改 | 扩展 `PublicIndustryTopic`、`PublicGeneration` |
| `系统部署/models/models.py` | 修改 | 扩展 `SavedPortrait`、`PersonaUserProblem`（⚠️ 不是 public_models.py） |
| `系统部署/routes/galaxy_api.py` | 修改 | 扩展 `/graph`、`/node/star`、`/node/planet`、`/node/satellite` 返回字段 |
| `系统部署/routes/public_api.py` | 修改 | 扩展 `/topics`、`/generate` 接口 |
| `系统部署/services/galaxy_service.py` | **新建** | 数据聚合服务（仅做查询结果聚合，不侵入路由层） |
| `系统部署/static/public/js/galaxy-universe.js` | 修改 | 新增 GEO 字段展示、cover_thumb 图标渲染、场景选择器 |
| `系统部署/templates/public/galaxy.html` | 修改 | 新增地域信息展示区域、恒星缩略图展示 |
| `系统部署/templates/public/produce.html` | 修改 | 新增场景选择器组件（注意折叠分组） |
| 数据库 | 修改 | 新增 8 个字段 + 2 个索引 |

---

## 十、附录

### 10.1 场景选项数据结构

```json
// scene_options 完整结构
[
  {
    "id": "scene_001",                            // 场景唯一ID（UUID）
    "组合": "人群 + 时间 + 情境 + 痛点",            // 完整组合描述
    "标签": "焦虑型家长",                           // 短标签
    "风格": "情绪共鸣",                             // 内容风格
    "优先级": 1,                                    // 显示顺序
    "使用次数": 0                                   // 统计
  }
]
```

### 10.2 风格类型枚举

| 风格 | 说明 | 适用场景 |
|------|------|---------|
| 情绪共鸣 | 引发情感共鸣，温暖陪伴 | 焦虑型、迷茫型场景 |
| 干货科普 | 专业知识输出，逻辑清晰 | 新手型、信息不足场景 |
| 犀利吐槽 | 直击痛点，引发讨论 | 紧迫型、拖延型场景 |
| 故事叙述 | 讲述真实案例，引发代入 | 转折型、决策型场景 |
| 权威背书 | 数据支撑，专家推荐 | 犹豫型、比较型场景 |

### 10.3 GEO 地域粒度

| 粒度 | geo_level 值 | 说明 |
|------|-------------|------|
| 省份级 | `province` | 覆盖全省 |
| 城市级 | `city` | 覆盖特定城市（默认） |
| 区县级 | `district` | 覆盖特定区县 |
| 全国级 | `nationwide` | 无地域限制 |

### 10.4 cover_thumb 字段说明

| 属性 | 值 |
|------|-----|
| 字段名 | `cover_thumb` |
| 所属表 | `saved_portraits` |
| 字段类型 | `VARCHAR(255)` |
| 默认值 | `''` |
| 存储内容 | 图片 URL |
| 用途 | ECharts 恒星节点图标 + 详情卡片封面 |
| 图片规格 | 200×200px，JPG/PNG，≤3MB |
| 空值处理 | 前端显示默认金色圆形占位图 |

### 10.5 字段语义对照表

| 字段 | 所属表 | 语义维度 | 说明 |
|------|--------|---------|------|
| `applicable_scenarios` | `public_industry_topics` | 营销策略 | 业务场景：种草/带货/品牌 |
| `scene_options` | `public_industry_topics` | 内容策略 | 内容场景：人群+时间+情境+痛点 |
| `selected_scenes` | `public_generations` | 内容策略 | 客户选择的场景组合 |
| `content_style` | `public_industry_topics` | 内容策略 | 内容风格：情绪共鸣/干货科普... |
| `geo_*` | `saved_portraits` / `persona_user_problems` | 地域策略 | 地域信息：省/市/标签 |
| `cover_thumb` | `saved_portraits` | 视觉展示 | 恒星节点缩略图 URL |
