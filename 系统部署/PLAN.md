# 改造执行计划

## 概述

将完成完整的系统改造，涵盖数据层增强、Skill Bridge优化、配置层新建和旧代码清理五个阶段。

---

## 阶段一：数据层增强（P0）

### 1. 画像增强
- **文件**：`系统部署/services/portrait_generator.py`
- **新增字段**：language_style, crowd_perspective, age_range, pain_point_level, decision_stage

### 2. 选题增强
- **文件**：`系统部署/services/topic_library_generator.py`
- **新增字段**：scene_details, core_value, content_format, emotion_curve

### 3. 关键词库增强
- **文件**：`系统部署/services/keyword_library_generator.py`
- **新增字段**：geo_score, trust_keywords, data_sources

---

## 阶段二：Skill Bridge增强（P0）

### 4. 新建 graphic_skill.json
- **文件**：`系统部署/services/skill_bridge/config/graphic_skill.json`
- **内容**：图文Skill执行配置，包含情绪动线和视觉规范

### 5. 增强 data_mapper.py
- **文件**：`系统部署/services/skill_bridge/data_mapper.py`
- **新增方法**：map_portrait_to_content, map_topic_to_content, map_keyword_to_content

---

## 阶段三：配置层新建（P1）

### 6. 新建 emotion_curves.py
- **文件**：`系统部署/content_templates/emotion_curves.py`
- **内容**：7种情绪曲线配置（种草型、干货型、测评型等）

### 7. 新建 visual_guides.py
- **文件**：`系统部署/content_templates/visual_guides.py`
- **内容**：5种视觉风格配置（暖色调、专业风、清新风等）

### 8. 新建 expert_reviewer.py
- **文件**：`系统部署/services/expert_reviewer.py`
- **内容**：5维评审体系（心理合规、情绪共鸣、信任建立、价值传递、行动引导）

---

## 阶段四：长文/短视频适配（P1）

**状态**：✅ 已完成
- `long_text_generator.json` - 已存在
- `video_script_generator.json` - 已存在

---

## 阶段五：旧代码清理（P2）

### 9. 创建 prompt_constraints.py
- **文件**：`系统部署/services/prompt_constraints.py`
- **内容**：提取公共JSON约束、角色定义、GEO评分Prompt

### 10. 统一 json_parser.py
- **文件**：`系统部署/services/json_parser.py`
- **内容**：封装7层降级解析逻辑，供所有生成器复用

### 11. 统一标题生成入口
- 确保 `title_generator.py` 是唯一标题生成入口

### 12. 统一评分逻辑入口
- 增强 `content_quality_scorer.py` 作为唯一评分入口

---

## 执行顺序

| 顺序 | 任务 | 优先级 |
|------|------|--------|
| 1 | 画像增强 | P0 |
| 2 | 选题增强 | P0 |
| 3 | 关键词库增强 | P0 |
| 4 | 新建 graphic_skill.json | P0 |
| 5 | 增强 data_mapper.py | P0 |
| 6 | 新建 emotion_curves.py | P1 |
| 7 | 新建 visual_guides.py | P1 |
| 8 | 新建 expert_reviewer.py | P1 |
| 9 | 创建 prompt_constraints.py | P2 |
| 10 | 统一 json_parser.py | P2 |
| 11 | 统一标题入口 | P2 |
| 12 | 统一评分入口 | P2 |

---

## 验收标准

1. 所有新增字段有合理默认值，不破坏现有功能
2. Skill配置文件可通过 registry 正常加载
3. 情绪曲线和视觉指南可被内容生成器引用
4. 公共模块可被其他服务正确导入使用
5. 清理后的代码功能与清理前一致
