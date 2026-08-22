#!/bin/bash
# content-creator → Obsidian 知识库 同步脚本
# 源（生产端）：douyin/.cursor/skill/content-creator/
# 目标（沉淀端）：~/Obsidian/知识库/
#
# 用法：
#   bash 工具/sync-to-obsidian.sh           # 全量同步
#   bash 工具/sync-to-obsidian.sh 母系统     # 只同步母系统
#   bash 工具/sync-to-obsidian.sh 案例库     # 只同步案例库
#   bash 工具/sync-to-obsidian.sh 项目       # 只同步项目 config/档案
#   bash 工具/sync-to-obsidian.sh 方法论     # 只同步方法论（增量，不删 Obsidian 独有文件）
#   bash 工具/sync-to-obsidian.sh skill      # 只同步 skill.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OBS_VAULT="${OBSIDIAN_VAULT:-/Users/zengyuan/Obsidian/知识库}"
TARGET="${1:-all}"

echo "源: $SRC_ROOT"
echo "目标: $OBS_VAULT"
echo "模式: $TARGET"
echo "---"

sync_dir() {
  local src="$1"
  local dst="$2"
  mkdir -p "$dst"
  rsync -av --delete "$src/" "$dst/"
  echo "✓ $(basename "$dst")"
}

sync_dir_incremental() {
  local src="$1"
  local dst="$2"
  local exclude="${3:-}"
  mkdir -p "$dst"
  if [ -n "$exclude" ]; then
    rsync -av --exclude="$exclude" "$src/" "$dst/"
  else
    rsync -av "$src/" "$dst/"
  fi
  echo "✓ $(basename "$dst") (增量，保留目标独有文件)"
}

sync_file() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "✓ $(basename "$dst")"
}

case "$TARGET" in
  all)
    sync_dir "$SRC_ROOT/母系统" "$OBS_VAULT/13-内容创作/母系统"
    sync_dir "$SRC_ROOT/知识库/案例库/图文拆解" "$OBS_VAULT/13-内容创作/案例库/图文拆解"
    sync_dir_incremental "$SRC_ROOT/知识库/案例库/爆款拆解" "$OBS_VAULT/13-内容创作/案例库/爆款拆解"
    sync_dir_incremental "$SRC_ROOT/知识库/方法论库" "$OBS_VAULT/13-内容创作/方法论"
    sync_file "$SRC_ROOT/skill.md" "$OBS_VAULT/13-内容创作/skill.md"
    for proj in 备电 企业咨询 风水 职业规划; do
      if [ -d "$SRC_ROOT/项目/$proj" ]; then
        mkdir -p "$OBS_VAULT/12-项目/$proj"
        for f in config.md 个人档案.md 标杆映射表.md 选题池.md 运营规划方案.md; do
          [ -f "$SRC_ROOT/项目/$proj/$f" ] && cp "$SRC_ROOT/项目/$proj/$f" "$OBS_VAULT/12-项目/$proj/$f"
        done
        if [ -d "$SRC_ROOT/项目/$proj/输出" ]; then
          sync_dir_incremental "$SRC_ROOT/项目/$proj/输出" "$OBS_VAULT/12-项目/$proj/输出" "脚本/"
        fi
        if [ -d "$SRC_ROOT/项目/$proj/资产" ]; then
          sync_dir_incremental "$SRC_ROOT/项目/$proj/资产" "$OBS_VAULT/12-项目/$proj/资产"
        fi
        if [ -d "$SRC_ROOT/项目/$proj/素材库" ]; then
          sync_dir_incremental "$SRC_ROOT/项目/$proj/素材库" "$OBS_VAULT/12-项目/$proj/素材库"
        fi
        echo "✓ 项目/$proj"
      fi
    done
    ;;
  母系统)
    sync_dir "$SRC_ROOT/母系统" "$OBS_VAULT/13-内容创作/母系统"
    ;;
  案例库)
    sync_dir "$SRC_ROOT/知识库/案例库/图文拆解" "$OBS_VAULT/13-内容创作/案例库/图文拆解"
    sync_dir_incremental "$SRC_ROOT/知识库/案例库/爆款拆解" "$OBS_VAULT/13-内容创作/案例库/爆款拆解"
    ;;
  方法论)
    sync_dir_incremental "$SRC_ROOT/知识库/方法论库" "$OBS_VAULT/13-内容创作/方法论"
    ;;
  项目)
    for proj in 备电 企业咨询 风水 职业规划; do
      if [ -d "$SRC_ROOT/项目/$proj" ]; then
        mkdir -p "$OBS_VAULT/12-项目/$proj"
        for f in config.md 个人档案.md 标杆映射表.md 选题池.md 运营规划方案.md; do
          [ -f "$SRC_ROOT/项目/$proj/$f" ] && cp "$SRC_ROOT/项目/$proj/$f" "$OBS_VAULT/12-项目/$proj/$f"
        done
        if [ -d "$SRC_ROOT/项目/$proj/素材库" ]; then
          sync_dir_incremental "$SRC_ROOT/项目/$proj/素材库" "$OBS_VAULT/12-项目/$proj/素材库"
        fi
        echo "✓ 项目/$proj"
      fi
    done
    ;;
  skill)
    sync_file "$SRC_ROOT/skill.md" "$OBS_VAULT/13-内容创作/skill.md"
    ;;
  *)
    echo "未知模式: $TARGET"
    echo "可用: all | 母系统 | 案例库 | 方法论 | 项目 | skill"
    exit 1
    ;;
esac

echo "---"
echo "同步完成 → $OBS_VAULT"
