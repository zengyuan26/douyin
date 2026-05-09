"""
搜索增强集成器

将搜索服务集成到脚本生成流程
"""

import logging
from typing import List, Dict, Any, Optional
import asyncio

from services.search import (
    SearchService,
    SearchReference,
    SearchConfig,
    SearchTriggerDecider,
    AsyncSearchTask,
    get_task_queue,
    TavilySearchClient,
    ReferenceType,
)

logger = logging.getLogger(__name__)


class SearchEnhancementIntegrator:
    """
    搜索增强集成器

    将实时搜索能力集成到脚本生成流程
    """

    def __init__(
        self,
        config: Optional[SearchConfig] = None,
        search_service: Optional[SearchService] = None,
    ):
        """
        初始化集成器

        Args:
            config: 搜索配置
            search_service: 搜索服务实例
        """
        self.config = config or SearchConfig()
        self.search_service = search_service or SearchService(config=self.config)
        self.trigger_decider = SearchTriggerDecider(self.config)

    def should_enhance(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
        force: bool = False,
    ) -> bool:
        """
        判断是否应该启用搜索增强

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长
            force: 强制启用

        Returns:
            是否启用搜索增强
        """
        if not self.config.enabled:
            return False

        return self.trigger_decider.should_search(
            topic=topic,
            topic_type=topic_type,
            duration=duration,
            force=force,
        )

    async def enhance_script_prompt(
        self,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
        style: str = "",
    ) -> Dict[str, Any]:
        """
        增强脚本生成提示词

        分析需求，搜索参考资料，并返回增强后的提示词

        Args:
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长
            style: 风格要求

        Returns:
            包含增强提示词和引用的字典
        """
        # 1. 判断是否需要搜索
        if not self.should_enhance(topic, topic_type, duration):
            return {
                "enhanced_prompt": None,
                "references": [],
                "search_used": False,
                "message": "不适合添加搜索引用",
            }

        # 2. 执行搜索
        try:
            references = await self.search_service.analyze_and_search(
                topic=topic,
                topic_type=topic_type,
                duration=duration,
            )

            if not references:
                return {
                    "enhanced_prompt": None,
                    "references": [],
                    "search_used": False,
                    "message": "未找到相关引用",
                }

            # 3. 构建增强提示词
            enhanced_prompt = self._build_enhanced_prompt(
                topic=topic,
                references=references,
                style=style,
            )

            return {
                "enhanced_prompt": enhanced_prompt,
                "references": references,
                "search_used": True,
                "message": f"已添加 {len(references)} 条引用",
            }

        except Exception as e:
            logger.error(f"搜索增强失败: {e}")
            return {
                "enhanced_prompt": None,
                "references": [],
                "search_used": False,
                "message": f"搜索失败: {str(e)}",
            }

    def _build_enhanced_prompt(
        self,
        topic: str,
        references: List[SearchReference],
        style: str = "",
    ) -> str:
        """
        构建增强后的提示词

        Args:
            topic: 选题主题
            references: 引用列表
            style: 风格要求

        Returns:
            增强后的提示词
        """
        # 引用上下文
        ref_context = "\n\n【参考资料】\n"

        for i, ref in enumerate(references[:5], 1):
            ref_context += f"{i}. {ref.content[:200]}"
            if ref.source_name:
                ref_context += f"\n   来源：{ref.source_name}"
            if ref.source_url:
                ref_context += f"\n   网址：{ref.source_url}"
            ref_context += "\n\n"

        # 引用要求
        ref_requirement = """
【引用要求】
1. 适当融入上述参考资料的内容，增强说服力
2. 引用名言、数据、案例时，在脚本中标注来源
3. 保持脚本的流畅性和自然感，不要生硬堆砌引用
"""

        # 组装提示词
        enhanced_prompt = f"""{ref_context}{ref_requirement}"""

        return enhanced_prompt

    def format_references_for_display(
        self,
        references: List[SearchReference],
    ) -> List[Dict[str, Any]]:
        """
        格式化引用用于前端展示

        Args:
            references: 引用列表

        Returns:
            格式化后的引用列表
        """
        formatted = []

        for ref in references:
            formatted.append({
                "id": id(ref),
                "type": ref.type.value,
                "type_name": self._get_type_name(ref.type),
                "content": ref.content[:100] + "..." if len(ref.content) > 100 else ref.content,
                "source": ref.source_name,
                "url": ref.source_url,
                "author": ref.author,
                "score": f"{ref.score:.0%}",
                "formatted": ref.format_for_script(),
            })

        return formatted

    def _get_type_name(self, ref_type: ReferenceType) -> str:
        """获取引用类型的中文名称"""
        type_names = {
            ReferenceType.QUOTE: "名言引用",
            ReferenceType.DATA: "数据引用",
            ReferenceType.CASE: "案例引用",
            ReferenceType.HOT: "热点引用",
            ReferenceType.TERM: "术语解释",
        }
        return type_names.get(ref_type, "其他引用")

    async def trigger_async_enhancement(
        self,
        script_id: int,
        topic: str,
        topic_type: str = "",
        duration: int = 60,
    ) -> str:
        """
        触发异步搜索增强

        适用于异步模式，先返回脚本，后台补充引用

        Args:
            script_id: 脚本ID
            topic: 选题主题
            topic_type: 话题类型
            duration: 视频时长

        Returns:
            任务ID
        """
        if not self.config.async_mode:
            logger.warning("异步模式未启用，使用同步模式")
            return ""

        # 判断是否需要搜索
        if not self.should_enhance(topic, topic_type, duration):
            logger.info(f"不需要搜索增强: script_id={script_id}")
            return ""

        # 创建并添加异步任务
        task = AsyncSearchTask(
            script_id=script_id,
            topic=topic,
            topic_type=topic_type,
            duration=duration,
            search_service=self.search_service,
        )

        task_queue = get_task_queue()
        task_id = await task_queue.add(task)

        logger.info(f"异步搜索任务已添加: task_id={task_id}")

        return task_id

    def get_async_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取异步任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态
        """
        task_queue = get_task_queue()
        return task_queue.get_status(task_id)


# 全局实例
_search_integrator: Optional[SearchEnhancementIntegrator] = None


def get_search_integrator() -> SearchEnhancementIntegrator:
    """获取搜索增强集成器实例"""
    global _search_integrator
    if _search_integrator is None:
        _search_integrator = SearchEnhancementIntegrator()
    return _search_integrator
