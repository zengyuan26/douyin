"""
Skill 管理器

功能：
- 加载 Skill 文件内容
- 监听 Skill 文件变更，自动刷新缓存
- 提供统一的 Skill 访问接口

使用方式：
from services.skill_manager import SkillManager

manager = SkillManager()

# 获取 Skill 内容
content = manager.get_skill_content('blue-ocean-expert')

# 获取 Prompt 模板
template = manager.get_prompt_template('blue-ocean-expert')

# 获取所有 Skills 索引
skills = manager.get_skills_index()
"""

import os
import re
import json
import logging
import threading
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SkillInfo:
    """Skill 信息"""
    name: str                           # Skill 名称
    path: str                           # Skill 路径
    skill_md_path: str                   # SKILL.md 路径
    template_path: str                   # prompt_template.md 路径
    description: str = ""                # 描述
    capabilities: List[str] = field(default_factory=list)  # 能力列表
    last_modified: float = 0             # 最后修改时间
    content_cache: Optional[str] = None  # 缓存的内容


class SkillManager:
    """
    Skill 管理器

    功能：
    1. 自动扫描 .cursor/skills/ 和 .cursor/skill/ 目录
    2. 加载 Skill 内容并缓存
    3. 监听文件变更，自动刷新缓存
    4. 提供统一的 Skill 访问接口
    """

    _instance = None
    _lock = threading.Lock()

    # 缓存过期时间（秒）
    CACHE_EXPIRY = 300  # 5分钟

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

        # Skill 目录
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # 系统部署/
        self.new_skills_dir = os.path.join(self.base_dir, '.cursor', 'skills')     # .cursor/skills/
        self.legacy_skills_dir = os.path.join(self.base_dir, '.cursor', 'skill')    # .cursor/skill/

        # Skill 缓存 {name: SkillInfo}
        self._skills_cache: Dict[str, SkillInfo] = {}
        self._template_cache: Dict[str, str] = {}
        self._cache_timestamps: Dict[str, float] = {}

        # 扫描 Skills
        self._scan_skills()

        # 启动文件监听（后台线程）
        self._listener_running = False
        self._listener_thread = None

        logger.info(f"[SkillManager] 初始化完成，已加载 {len(self._skills_cache)} 个 Skills")

    def _scan_skills(self):
        """扫描 Skill 目录"""
        skills = {}

        # 扫描新版目录 (.cursor/skills/)
        if os.path.exists(self.new_skills_dir):
            for name in os.listdir(self.new_skills_dir):
                skill_path = os.path.join(self.new_skills_dir, name)
                if os.path.isdir(skill_path) and not name.startswith('_'):
                    skill_info = self._load_skill_info(name, skill_path)
                    if skill_info:
                        skills[name] = skill_info

        # 扫描旧版目录 (.cursor/skill/)
        if os.path.exists(self.legacy_skills_dir):
            for name in os.listdir(self.legacy_skills_dir):
                skill_path = os.path.join(self.legacy_skills_dir, name)
                if os.path.isdir(skill_path):
                    # 旧版名称可能带中文，转换为 slug
                    slug = self._to_slug(name)
                    if slug not in skills:  # 新版优先
                        skill_info = self._load_skill_info(slug, skill_path, is_legacy=True)
                        if skill_info:
                            skills[slug] = skill_info

        self._skills_cache = skills
        logger.info(f"[SkillManager] 扫描完成，共 {len(skills)} 个 Skills")

    def _load_skill_info(self, name: str, skill_path: str, is_legacy: bool = False) -> Optional[SkillInfo]:
        """加载 Skill 信息"""
        skill_md_path = os.path.join(skill_path, 'SKILL.md')
        template_path = os.path.join(skill_path, 'prompt_template.md')

        if not os.path.exists(skill_md_path):
            return None

        # 获取最后修改时间
        mtime = os.path.getmtime(skill_path)

        # 读取描述（从 SKILL.md 的 description 字段提取）
        description = ""
        capabilities = []
        try:
            with open(skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 提取 YAML frontmatter 中的 description
                match = re.search(r'description:\s*[">]?(.*?)["<]?\n', content)
                if match:
                    description = match.group(1).strip()
                # 提取能力列表（从角色定义的技能清单中提取）
                if '技能清单' in content or '能力清单' in content:
                    capabilities = self._extract_capabilities(content)
        except Exception as e:
            logger.warning(f"[SkillManager] 读取 Skill 描述失败: {name}, {e}")

        return SkillInfo(
            name=name,
            path=skill_path,
            skill_md_path=skill_md_path,
            template_path=template_path if os.path.exists(template_path) else "",
            description=description,
            capabilities=capabilities,
            last_modified=mtime
        )

    def _extract_capabilities(self, content: str) -> List[str]:
        """从 Skill 内容中提取能力列表"""
        capabilities = []
        patterns = [
            r'[【\[](?:技能|能力)清单[】\]]\s*[:：]?\s*([^\n]+)',
            r'[-*]\s*([A-Z][^:\n]{2,30}):',  # 匹配 "- xxx: 描述" 格式
        ]
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) > 2 and len(capabilities) < 20:  # 限制数量
                    capabilities.append(match.strip())
        return capabilities

    def _to_slug(self, name: str) -> str:
        """将名称转换为 slug 格式"""
        # 中文转拼音（简化版）
        import re
        # 移除非字母数字字符，转为小写
        slug = re.sub(r'[^\w\s-]', '', name)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.lower()

    def start_listener(self):
        """启动文件监听"""
        if self._listener_running:
            return

        self._listener_running = True
        self._listener_thread = threading.Thread(target=self._listen_changes, daemon=True)
        self._listener_thread.start()
        logger.info("[SkillManager] 文件监听已启动")

    def stop_listener(self):
        """停止文件监听"""
        self._listener_running = False
        if self._listener_thread:
            self._listener_thread.join(timeout=1)
        logger.info("[SkillManager] 文件监听已停止")

    def _listen_changes(self):
        """监听文件变更"""
        while self._listener_running:
            try:
                # 检查是否有文件变更
                changed = self._check_changes()
                if changed:
                    logger.info(f"[SkillManager] 检测到 Skill 文件变更: {changed}")
                    # 刷新缓存
                    self._refresh_cache(changed)

                # 每 10 秒检查一次
                time.sleep(10)
            except Exception as e:
                logger.error(f"[SkillManager] 监听异常: {e}")

    def _check_changes(self) -> List[str]:
        """检查文件变更"""
        changed = []
        current_time = time.time()

        for name, skill_info in self._skills_cache.items():
            # 检查 SKILL.md
            if os.path.exists(skill_info.skill_md_path):
                mtime = os.path.getmtime(skill_info.skill_md_path)
                if mtime > skill_info.last_modified:
                    changed.append(name)
                    skill_info.last_modified = mtime

            # 检查 prompt_template.md
            if skill_info.template_path and os.path.exists(skill_info.template_path):
                mtime = os.path.getmtime(skill_info.template_path)
                cache_key = f"{name}_template"
                if cache_key in self._cache_timestamps:
                    if mtime > self._cache_timestamps[cache_key]:
                        changed.append(name)
                        self._cache_timestamps[cache_key] = mtime
                else:
                    self._cache_timestamps[cache_key] = mtime

        return changed

    def _refresh_cache(self, names: List[str]):
        """刷新指定 Skill 的缓存"""
        for name in names:
            # 清除模板缓存
            if name in self._template_cache:
                del self._template_cache[name]

            # 清除内容缓存
            if name in self._cache_timestamps:
                del self._cache_timestamps[name]

            # 重新扫描
            skill_path = self._skills_cache.get(name)
            if skill_path:
                self._load_skill_info(name, skill_path.path)

        logger.info(f"[SkillManager] 缓存已刷新: {names}")

    # ============================================================
    # 公共接口
    # ============================================================

    def get_skill_content(self, name: str, use_cache: bool = True) -> Optional[str]:
        """
        获取 Skill 内容（SKILL.md）

        Args:
            name: Skill 名称
            use_cache: 是否使用缓存

        Returns:
            Skill 内容字符串，或 None
        """
        skill_info = self._skills_cache.get(name)
        if not skill_info:
            return None

        cache_key = f"{name}_content"
        current_time = time.time()

        # 检查缓存
        if use_cache and cache_key in self._cache_timestamps:
            if current_time - self._cache_timestamps[cache_key] < self.CACHE_EXPIRY:
                return self._template_cache.get(cache_key)

        # 读取文件
        try:
            with open(skill_info.skill_md_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._template_cache[cache_key] = content
                self._cache_timestamps[cache_key] = current_time
                return content
        except Exception as e:
            logger.error(f"[SkillManager] 读取 Skill 内容失败: {name}, {e}")
            return None

    def get_prompt_template(self, name: str, use_cache: bool = True) -> Optional[str]:
        """
        获取 Prompt 模板（prompt_template.md）

        Args:
            name: Skill 名称
            use_cache: 是否使用缓存

        Returns:
            Prompt 模板字符串，或 None
        """
        skill_info = self._skills_cache.get(name)
        if not skill_info:
            return None

        cache_key = f"{name}_template"
        current_time = time.time()

        # 检查缓存
        if use_cache and cache_key in self._cache_timestamps:
            if current_time - self._cache_timestamps[cache_key] < self.CACHE_EXPIRY:
                return self._template_cache.get(cache_key)

        # 读取文件
        if not skill_info.template_path or not os.path.exists(skill_info.template_path):
            return None

        try:
            with open(skill_info.template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 提取代码块内容
                match = re.search(r'```python\s*(.*?)\s*```', content, re.DOTALL)
                if match:
                    content = match.group(1).strip()

                self._template_cache[cache_key] = content
                self._cache_timestamps[cache_key] = current_time
                return content
        except Exception as e:
            logger.error(f"[SkillManager] 读取 Prompt 模板失败: {name}, {e}")
            return None

    def get_skills_index(self) -> List[Dict[str, Any]]:
        """
        获取所有 Skills 索引

        Returns:
            Skills 索引列表
        """
        result = []
        for name, skill_info in self._skills_cache.items():
            result.append({
                'name': skill_info.name,
                'path': skill_info.path,
                'description': skill_info.description,
                'capabilities': skill_info.capabilities,
                'has_template': bool(skill_info.template_path)
            })
        return result

    def get_skill_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定 Skill 的详细信息

        Args:
            name: Skill 名称

        Returns:
            Skill 信息字典
        """
        skill_info = self._skills_cache.get(name)
        if not skill_info:
            return None

        return {
            'name': skill_info.name,
            'path': skill_info.path,
            'skill_md_path': skill_info.skill_md_path,
            'template_path': skill_info.template_path,
            'description': skill_info.description,
            'capabilities': skill_info.capabilities,
            'last_modified': datetime.fromtimestamp(skill_info.last_modified).isoformat()
        }

    def reload_skill(self, name: str):
        """
        重新加载指定 Skill

        Args:
            name: Skill 名称
        """
        skill_info = self._skills_cache.get(name)
        if skill_info:
            self._load_skill_info(name, skill_info.path)
            self._refresh_cache([name])

    def reload_all(self):
        """重新加载所有 Skills"""
        self._scan_skills()
        self._template_cache.clear()
        self._cache_timestamps.clear()
        logger.info("[SkillManager] 所有 Skills 已重新加载")


# 全局单例
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取 Skill 管理器单例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.start_listener()
    return _skill_manager
