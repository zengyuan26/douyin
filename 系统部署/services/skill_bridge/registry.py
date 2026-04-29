"""
Skill Registry — 注册中心
负责所有 skill 配置的加载、查询、版本控制和热重载。

配置目录结构：
  skill_bridge/
  ├── config/
  │   ├── market_analyzer.json      # 市场分析配置
  │   ├── keyword_library.json      # 关键词库配置
  │   └── ...
  └── registry.py                  # 本文件
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Skill 注册中心（单例）

    职责：
    - 自动扫描 config/ 目录加载所有 .json 配置文件
    - 提供 skill/step/约束/数据流向的查询接口
    - 支持热重载：修改 JSON 配置后无需重启服务
    """

    _instance: Optional['SkillRegistry'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_dir = Path(__file__).parent / "config"
        self._skills: Dict[str, dict] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------

    def _load_all(self):
        """扫描 config/ 目录，加载所有 .json 文件"""
        if not self._config_dir.exists():
            logger.warning(f"[SkillRegistry] 配置目录不存在: {self._config_dir}")
            return

        for config_file in self._config_dir.glob("*.json"):
            skill_name = config_file.stem
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    self._skills[skill_name] = json.load(f)
                logger.info(f"[SkillRegistry] 加载配置: {skill_name}")
            except Exception as e:
                logger.error(f"[SkillRegistry] 加载配置失败 {config_file}: {e}")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> Optional[dict]:
        """获取整个 skill 配置"""
        return self._skills.get(name)

    def get_step(self, skill_name: str, step_id: str) -> Optional[dict]:
        """获取特定步骤配置"""
        skill = self.get_skill(skill_name)
        if not skill:
            return None
        for step in skill.get("steps", []):
            if step["id"] == step_id:
                return step
        return None

    def get_steps_ordered(self, skill_name: str) -> List[dict]:
        """获取按 order 排序的步骤列表"""
        skill = self.get_skill(skill_name)
        if not skill:
            return []
        return sorted(skill.get("steps", []), key=lambda x: x.get("order", 0))

    def get_data_flow(self, skill_name: str) -> dict:
        """获取 data_flow.outputs 配置"""
        skill = self.get_skill(skill_name)
        if not skill:
            return {}
        return skill.get("data_flow", {}).get("outputs", {})

    def get_constraints(self, skill_name: str) -> dict:
        """获取 constraints 配置"""
        skill = self.get_skill(skill_name)
        if not skill:
            return {}
        return skill.get("constraints", {})

    def get_input_schema(self, skill_name: str) -> dict:
        """获取 input_schema 配置"""
        skill = self.get_skill(skill_name)
        if not skill:
            return {}
        return skill.get("input_schema", {})

    def list_skills(self) -> List[str]:
        """列出所有已加载的 skill 名称"""
        return list(self._skills.keys())

    def get_skill_meta(self, name: str) -> Optional[dict]:
        """获取 skill 元信息（不含 steps）"""
        skill = self.get_skill(name)
        if not skill:
            return None
        meta = skill.get("skill", {})
        return {
            "name": meta.get("name"),
            "display_name": meta.get("display_name"),
            "description": meta.get("description"),
            "version": meta.get("version"),
            "skill_md_path": meta.get("skill_md_path"),
            "step_count": len(skill.get("steps", [])),
        }

    # ------------------------------------------------------------------
    # 热重载
    # ------------------------------------------------------------------

    def reload(self, skill_name: Optional[str] = None):
        """
        热重载配置。

        - skill_name 为 None：重载所有
        - skill_name 指定名称：只重载单个
        """
        if skill_name:
            config_file = self._config_dir / f"{skill_name}.json"
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        self._skills[skill_name] = json.load(f)
                    logger.info(f"[SkillRegistry] 热重载: {skill_name}")
                except Exception as e:
                    logger.error(f"[SkillRegistry] 热重载失败 {skill_name}: {e}")
            else:
                self._skills.pop(skill_name, None)
                logger.info(f"[SkillRegistry] 移除: {skill_name}")
        else:
            self._skills.clear()
            self._load_all()
            logger.info("[SkillRegistry] 全量重载完成")
