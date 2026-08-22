# Cursor 内容创作系统 ↔ Obsidian 知识库 打通说明

> v1.0 | 2026-08-18

---

## 一、三个知识位置，各管什么

```
┌─────────────────────────────────────────────────────────────┐
│  ① douyin 仓库（生产端 · 源）                                │
│  .cursor/skill/content-creator/                             │
│  → Cursor/Claude 直接读写                                   │
│  → 完整产出：skill、config、脚本、设计稿、台账、案例库        │
└──────────────────────────┬──────────────────────────────────┘
                           │ sync-to-obsidian.sh（批量镜像）
                           │ Step 4.6（定稿后沉淀）
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ② Obsidian 知识库（沉淀端 · 检索）                          │
│  ~/Obsidian/知识库/                                         │
│  → 你在 Obsidian 里浏览、链接、搜索                          │
│  → 提取的概念/判断/定稿归档                                  │
└──────────────────────────┬──────────────────────────────────┘
                           │ config.素材库路径 读取
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  ③ 项目素材库（弹药 · 输入）                                 │
│  content-creator/项目/<项目名>/素材库/                        │
│  → 常识/ 搜索来的知识 + 独家/ 一手对话判断                   │
│  → Step 2.4 独家价值确认时检索                               │
└─────────────────────────────────────────────────────────────┘
```

**没有实时 API 打通。** 本质是 **文件系统级** 的读写 + 同步脚本。

---

## 二、Cursor 这边怎么连 Obsidian

| 时机 | 机制 | 方向 |
|------|------|------|
| **创作前** | config 里 `素材库路径` → 读 `项目/<项目名>/素材库/` | douyin 仓库 → Cursor |
| **创作中** | skill.md 知识库路由 → 读 `知识库/` 方法论/案例 | douyin 仓库 → Cursor |
| **定稿后 Step 4.6** | 手动/Agent 提取概念 → 写入 Obsidian 对应目录 | Cursor → Obsidian |
| **批量同步** | `bash 工具/sync-to-obsidian.sh` | douyin → Obsidian 镜像 |
| **快速捕捉** | `echo "内容" \| bash ~/Obsidian/知识库/.scripts/obsidian-sync.sh` | 任意 → Obsidian 收件箱 |

---

## 三、Obsidian 目录映射

| Obsidian 路径 | 来源 | 内容 |
|---------------|------|------|
| `13-内容创作/母系统/` | douyin 母系统/ | 治理文档镜像 |
| `13-内容创作/skill.md` | douyin skill.md | 引擎镜像 |
| `13-内容创作/方法论/` | douyin 知识库/方法论库/ | 方法论镜像 |
| `13-内容创作/案例库/图文拆解/` | douyin 知识库/案例库/图文拆解/ | 自有图文案例 |
| `13-内容创作/案例库/爆款拆解/` | douyin 知识库/案例库/爆款拆解/ | 对标拆解 |
| `12-项目/<项目名>/` | douyin 项目/<项目名>/ | config + 输出 + 资产 |
| `15-财富与认知/` | Step 4.6 提取 | 核心概念 |
| `11-行业与公司/` | Step 4.6 提取 | 行业判断 |
| `00-收件箱/` | 快速捕捉 | 待整理 |

---

## 四、同步命令

在 content-creator 目录下：

```bash
# 全量同步（推荐改完系统后跑一遍）
bash 工具/sync-to-obsidian.sh

# 只同步某一块
bash 工具/sync-to-obsidian.sh 母系统
bash 工具/sync-to-obsidian.sh 案例库
bash 工具/sync-to-obsidian.sh 项目
bash 工具/sync-to-obsidian.sh 方法论
bash 工具/sync-to-obsidian.sh skill
```

**源 = 真源（douyin 仓库）。** Obsidian 是镜像 + 提取层，Obsidian 里独有的笔记（如阅读笔记）不会被删。

---

## 五、维护建议

1. **改 skill / 母系统 / 案例库后** → 跑 `sync-to-obsidian.sh`
2. **每篇定稿后** → Step 4.6 沉淀到 Obsidian（概念/行业/方法论）
3. **随手想法** → Obsidian 收件箱或项目素材库/独家/
4. **不要在 Obsidian 改母系统镜像** → 改了也会被同步覆盖。要改就去 douyin 仓库改

---

## 六、和 Git 的关系

- douyin 仓库：Git 版本控制（生产端）
- Obsidian 知识库：独立 Git 仓库（`/Users/zengyuan/Obsidian/知识库/.git`）
- 两者通过 sync 脚本保持镜像，不是 symlink
