"""
GEO递进式内容质量优化引擎

核心策略：
- 将10项GEO自检分为4个优化组，按组序递进优化
- 每轮只修复当前组的不合格项，严格约束修改范围
- 达到80分自动停止，避免过度优化

组A（战略层）：标题吸引力、开篇直接性
组B（结构层）：结构清晰度、模块化完整
组C（信任层）：信任证据、品牌锚点、关键词密度
组D（体验转化层）：可读性、行动号召、改造潜力
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from services.llm import get_llm_service
from services.content_quality_scorer import (
    content_scorer, ScoreItem, ScoreResult,
    GEO_OPTIMIZATION_GROUPS, GROUP_ORDER,
    get_failed_items_by_group, should_start_from_group_a,
    get_pass_threshold
)

logger = logging.getLogger(__name__)


# =============================================================================
# 递进优化数据模型
# =============================================================================

@dataclass
class RoundResult:
    """单轮优化结果"""
    round_num: int           # 第几轮（1-based）
    group_key: str           # 组标识 A/B/C/D
    group_label: str         # 组标签
    items_optimized: List[str]  # 本轮优化的项
    score_before: float      # 本轮优化前分数
    score_after: float       # 本轮优化后分数
    content_snapshot: Dict    # 本轮优化后的内容快照
    quality_report_snapshot: Dict  # 本轮优化后的评分报告
    stopped: bool = False    # 是否因达到80分而停止
    message: str = ''


@dataclass
class ProgressiveOptimizationResult:
    """递进式优化最终结果"""
    success: bool
    optimized_content: Dict = None
    total_rounds: int = 0          # 总共执行了多少轮
    final_score: float = 0         # 最终分数
    first_score: float = 0         # 初始分数
    final_report: Dict = None       # 最终评分报告
    round_history: List[RoundResult] = field(default_factory=list)
    message: str = ''
    stopped_early: bool = False    # 是否提前停止（达到80分）


# =============================================================================
# 内容提取工具（兼容图文和长文两种结构）
# =============================================================================

def _extract_body(content: Dict) -> str:
    """从内容中提取正文"""
    # 长文结构
    article = content.get('article', {})
    if article:
        body = article.get('body', '')
        if body:
            return body
    # 图文结构
    return content.get('body', '') or content.get('content', '') or ''


def _extract_title(content: Dict) -> str:
    """从内容中提取标题"""
    # 长文结构
    article = content.get('article', {})
    if article:
        title = article.get('title', '')
        if title:
            return title
    # 图文结构
    return content.get('title', '') or ''


def _extract_subtitle(content: Dict) -> str:
    """从内容中提取副标题"""
    article = content.get('article', {})
    if article:
        subtitle = article.get('subtitle', '')
        if subtitle:
            return subtitle
    return content.get('subtitle', '') or ''


def _set_title(content: Dict, new_title: str) -> Dict:
    """设置标题（兼容长文结构）"""
    content = content.copy()
    article = content.get('article')
    if article:
        article = article.copy()
        article['title'] = new_title
        content['article'] = article
    else:
        content['title'] = new_title
    return content


def _set_subtitle(content: Dict, new_subtitle: str) -> Dict:
    """设置副标题（兼容长文结构）"""
    content = content.copy()
    article = content.get('article')
    if article:
        article = article.copy()
        article['subtitle'] = new_subtitle
        content['article'] = article
    else:
        content['subtitle'] = new_subtitle
    return content


def _set_body(content: Dict, new_body: str) -> Dict:
    """设置正文（兼容长文结构）"""
    content = content.copy()
    article = content.get('article')
    if article:
        article = article.copy()
        article['body'] = new_body
        content['article'] = article
    else:
        content['body'] = new_body
    return content


# =============================================================================
# 递进式优化引擎
# =============================================================================

class ProgressiveContentOptimizer:
    """GEO递进式内容优化引擎"""

    PASS_THRESHOLD = 80

    def __init__(self):
        self.llm = get_llm_service()

    def optimize(
        self,
        content: Dict,
        failed_items: List[ScoreItem],
        initial_score: float,
        brand_name: str = '',
        business_desc: str = '',
        max_rounds: int = 4,
        progress_callback=None
    ) -> ProgressiveOptimizationResult:
        """
        递进式优化入口

        Args:
            content: 当前内容
            failed_items: 不合格项列表
            initial_score: 初始分数
            brand_name: 品牌名
            business_desc: 业务描述
            max_rounds: 最大轮数（默认4轮，每组一轮）
            progress_callback: 进度回调函数，接收 (event_type, data) 参数
                             event_type: 'start' | 'round_start' | 'round_complete' | 'complete'
        """
        def _send_progress(event_type, data):
            if progress_callback:
                try:
                    progress_callback(event_type, data)
                except Exception as e:
                    logger.warning(f"[递进优化] 进度回调失败: {e}")

        if initial_score >= self.PASS_THRESHOLD:
            return ProgressiveOptimizationResult(
                success=True,
                optimized_content=content,
                total_rounds=0,
                final_score=initial_score,
                first_score=initial_score,
                final_report=None,
                round_history=[],
                message='内容已达80分，无需优化',
                stopped_early=True
            )

        if not failed_items:
            return ProgressiveOptimizationResult(
                success=True,
                optimized_content=content,
                total_rounds=0,
                final_score=initial_score,
                first_score=initial_score,
                final_report=None,
                round_history=[],
                message='无不合格项，无需优化',
                stopped_early=True
            )

        # 发送开始事件
        _send_progress('start', {
            'initial_score': initial_score,
            'failed_items_count': len(failed_items)
        })

        # 按组分类不合格项
        failed_by_group = get_failed_items_by_group(failed_items)
        logger.info(f"[递进优化] 初始分={initial_score}, 不合格项按组分类: "
                    + ", ".join(f"{k}:{[f.name for f in v]}" for k, v in failed_by_group.items() if v))

        # 确定从哪个组开始
        if should_start_from_group_a(initial_score):
            active_groups = GROUP_ORDER
            logger.info("[递进优化] 初始分<60，从组A开始执行全部4组")
        else:
            # 从第一个有不合格项的组开始
            active_groups = [g for g in GROUP_ORDER if failed_by_group.get(g, [])]
            logger.info(f"[递进优化] 初始分>=60，从第一个不合格组开始: {active_groups}")

        if not active_groups:
            return ProgressiveOptimizationResult(
                success=True,
                optimized_content=content,
                total_rounds=0,
                final_score=initial_score,
                first_score=initial_score,
                final_report=None,
                round_history=[],
                message='无需要优化的组',
                stopped_early=True
            )

        current_content = _deep_copy_content(content)
        current_score = initial_score
        round_history: List[RoundResult] = []
        stopped_early = False

        for round_idx, group_key in enumerate(active_groups):
            if round_idx >= max_rounds:
                logger.info(f"[递进优化] 已达最大轮数{max_rounds}，停止")
                break

            group_items = failed_by_group.get(group_key, [])
            if not group_items:
                logger.info(f"[递进优化] 轮{round_idx+1} {group_key}组无不合格项，跳过")
                continue

            group_def = GEO_OPTIMIZATION_GROUPS[group_key]
            round_num = len(round_history) + 1

            logger.info(f"[递进优化] === 轮次{round_num}：{group_key}组 {group_def['name']} ===")
            logger.info(f"[递进优化] 本轮优化项: {[f.name for f in group_items]}")

            # 发送轮次开始事件
            _send_progress('round_start', {
                'round_num': round_num,
                'group_key': group_key,
                'group_label': group_def['label'],
                'items': [f.name for f in group_items],
                'score_before': current_score,
                'total_groups': len(active_groups)
            })

            # 执行本轮优化
            round_result = self._optimize_single_group(
                content=current_content,
                group_key=group_key,
                group_def=group_def,
                group_items=group_items,
                brand_name=brand_name,
                business_desc=business_desc,
                round_num=round_num,
                score_before=current_score
            )

            round_history.append(round_result)
            current_content = round_result.content_snapshot
            current_score = round_result.score_after

            # 发送轮次完成事件
            _send_progress('round_complete', {
                'round_num': round_num,
                'group_key': group_key,
                'group_label': group_def['label'],
                'items_fixed': round_result.items_optimized,
                'score_before': round_result.score_before,
                'score_after': round_result.score_after,
                'score_delta': round_result.score_after - round_result.score_before,
                'total_groups': len(active_groups)
            })

            logger.info(f"[递进优化] 轮次{round_num}完成: {round_result.score_before} → {round_result.score_after}")

            # 达到80分，提前停止
            if current_score >= self.PASS_THRESHOLD:
                logger.info(f"[递进优化] 分数达到{current_score}（>={self.PASS_THRESHOLD}），提前停止")
                stopped_early = True
                break

        # 最终评分
        final_report = content_scorer.score(current_content, brand_name)
        final_score = final_report.total_score

        # 构建最终报告
        final_dict = content_scorer.to_dict(final_report)
        final_dict['optimized'] = True
        final_dict['first_score'] = initial_score
        final_dict['final_score'] = final_score
        final_dict['total_rounds'] = len(round_history)
        final_dict['round_history'] = [
            {
                'round_num': r.round_num,
                'group_key': r.group_key,
                'group_label': r.group_label,
                'items_optimized': r.items_optimized,
                'score_before': r.score_before,
                'score_after': r.score_after,
                'stopped': r.stopped,
                'message': r.message,
            }
            for r in round_history
        ]

        # 发送完成事件
        _send_progress('complete', {
            'success': True,
            'final_score': final_score,
            'total_rounds': len(round_history),
            'stopped_early': stopped_early,
            'message': f'递进优化完成，共{len(round_history)}轮，最终分数{final_score}'
        })

        return ProgressiveOptimizationResult(
            success=True,
            optimized_content=current_content,
            total_rounds=len(round_history),
            final_score=final_score,
            first_score=initial_score,
            final_report=final_dict,
            round_history=round_history,
            message=f'递进优化完成，共{len(round_history)}轮，最终分数{final_score}',
            stopped_early=stopped_early
        )

    def _optimize_single_group(
        self,
        content: Dict,
        group_key: str,
        group_def: Dict,
        group_items: List[ScoreItem],
        brand_name: str,
        business_desc: str,
        round_num: int,
        score_before: float
    ) -> RoundResult:
        """执行单轮单组优化"""
        body = _extract_body(content)
        title = _extract_title(content)
        subtitle = _extract_subtitle(content)

        # 构建组优化提示词
        prompt = self._build_group_prompt(
            group_key=group_key,
            group_def=group_def,
            group_items=group_items,
            title=title,
            subtitle=subtitle,
            body=body,
            brand_name=brand_name,
            business_desc=business_desc
        )

        try:
            response = self.llm.chat([
                {"role": "system", "content": self._get_group_system_prompt(group_key)},
                {"role": "user", "content": prompt}
            ])
        except Exception as e:
            logger.error(f"[递进优化] 轮次{round_num} LLM调用失败: {e}")
            return RoundResult(
                round_num=round_num,
                group_key=group_key,
                group_label=group_def['label'],
                items_optimized=[],
                score_before=score_before,
                score_after=score_before,
                content_snapshot=content,
                quality_report_snapshot={},
                message=f'LLM调用失败: {e}'
            )

        # 解析优化响应
        new_content, items_fixed = self._parse_group_response(
            response, content, group_items, group_key
        )

        # 重新评分
        score_after_result = content_scorer.score(new_content, brand_name)
        score_after = score_after_result.total_score
        quality_dict = content_scorer.to_dict(score_after_result)

        # 检查是否达到80分
        stopped = score_after >= self.PASS_THRESHOLD

        return RoundResult(
            round_num=round_num,
            group_key=group_key,
            group_label=group_def['label'],
            items_optimized=items_fixed,
            score_before=score_before,
            score_after=score_after,
            content_snapshot=new_content,
            quality_report_snapshot=quality_dict,
            stopped=stopped,
            message=f'优化了: {", ".join(items_fixed)}' if items_fixed else '无修改'
        )

    def _get_group_system_prompt(self, group_key: str) -> str:
        """获取各组的系统提示词"""
        prompts = {
            'A': (
                "你是一位资深内容编辑，精通SEO标题优化和文章开头写作。"
                "你只修改标题和文章开头部分，严格保留原文风格、结构、段落顺序。"
                "禁止重写正文、禁止改变文章主题、禁止修改小标题。"
                "只做最小化、精准的修改。"
            ),
            'B': (
                "你是一位专业的文案结构优化师。"
                "你只优化文章结构清晰度和模块化完整性。"
                "严格保留原文内容、标题、段落文字。"
                "只调整段落逻辑组织、小标题措辞，不得改变正文内容。"
                "禁止新增内容、禁止删除段落、禁止改变文章主题。"
            ),
            'C': (
                "你是一位内容营销专家，擅长在文章中植入品牌元素和关键词。"
                "你只在文章中适当位置植入品牌名称和关键词，不得改变文章核心内容。"
                "保持文章自然流畅，植入要恰当不过度。"
                "严格保留原文标题、结构、段落顺序。"
                "禁止新增段落、禁止重写句子、禁止改变文章主题。"
            ),
            'D': (
                "你是一位转化优化专家，擅长提升内容可读性和行动号召力。"
                "你只优化可读性、CTA和改造潜力相关内容。"
                "严格保留原文标题、结构和核心段落内容。"
                "只优化结尾CTA措辞、调整段落长度以提升可读性。"
                "禁止改变文章主题、禁止重写全文、禁止新增大量内容。"
            ),
        }
        return prompts.get(group_key, prompts['A'])

    def _build_group_prompt(
        self,
        group_key: str,
        group_def: Dict,
        group_items: List[ScoreItem],
        title: str,
        subtitle: str,
        body: str,
        brand_name: str,
        business_desc: str
    ) -> str:
        """构建各组的优化提示词"""
        suggestions_text = '\n'.join(
            f"{i+1}. 【{item.name}】{item.suggestion}"
            for i, item in enumerate(group_items)
        )

        group_intro = {
            'A': '【本轮优化任务】战略层优化（标题吸引力 + 开篇直接性）\n只修改标题和文章开头，不要动正文！',
            'B': '【本轮优化任务】结构层优化（结构清晰度 + 模块化完整）\n只调整文章结构和小标题，不要改变正文内容！',
            'C': '【本轮优化任务】信任层优化（信任证据 + 品牌锚点 + 关键词密度）\n在适当位置植入品牌信息和关键词，不要改变文章主题！',
            'D': '【本轮优化任务】体验转化优化（可读性 + 行动号召 + 改造潜力）\n优化结尾CTA和可读性，不要大改正文！',
        }

        constraints = {
            'A': (
                "【硬性约束】\n"
                "- 标题和副标题如需修改请输出，否则保持不变\n"
                "- 只修改文章开头段落（引言部分），最多重写前200字\n"
                "- 不修改任何正文主体内容\n"
                "- 不修改任何小标题\n"
                "- 不改变文章主题和风格\n"
                "- 不新增或删除段落"
            ),
            'B': (
                "【硬性约束】\n"
                "- 不修改正文文字内容\n"
                "- 不新增内容、不删除段落\n"
                "- 只调整段落顺序、小标题措辞\n"
                "- 不改变文章主题\n"
                "- 确保每个段落可独立理解"
            ),
            'C': (
                "【硬性约束】\n"
                "- 不改变文章核心观点和叙述逻辑\n"
                "- 品牌名称只自然植入1-2次，不超过3次\n"
                "- 关键词植入自然，不堆砌\n"
                "- 不新增段落\n"
                "- 不重写句子，只在适当位置补充"
            ),
            'D': (
                "【硬性约束】\n"
                "- 不修改标题\n"
                "- 不大改正文，只优化段落长度\n"
                "- CTA只放在结尾，措辞清晰具体\n"
                "- 不新增小标题\n"
                "- 保持文章主题不变"
            ),
        }

        prompt = f"""{group_intro.get(group_key, '')}

【本轮需要修复的问题及建议】
{suggestions_text}

【品牌信息】（如需植入，请使用）
品牌名：{brand_name}
业务描述：{business_desc}

【当前文章标题】
{title}

【当前文章副标题】
{subtitle}

【当前文章正文】
{body}

{constraints.get(group_key, '')}

【输出格式】
```json
{{
  "title_modified": true/false,
  "new_title": "如需修改标题则填写，否则填null",
  "subtitle_modified": true/false,
  "new_subtitle": "如需修改副标题则填写，否则填null",
  "body_modified": true/false,
  "new_body": "如需修改则填写完整正文（包含所有未修改的部分），否则填null",
  "items_fixed": ["实际修复的项名称列表"],
  "fix_summary": "本轮修改的简要说明（20字内）"
}}
```
"""
        return prompt

    def _parse_group_response(
        self,
        response: str,
        content: Dict,
        group_items: List[ScoreItem],
        group_key: str
    ) -> tuple:
        """解析组优化响应，返回（新内容, 已修复项列表）"""
        if not response:
            logger.warning(f"[递进优化] 组{group_key}响应为空，保持原内容")
            return content, []

        result = content.copy()
        items_fixed = []

        # 尝试JSON解析
        json_text = self._extract_json(response)
        if not json_text:
            logger.warning(f"[递进优化] 组{group_key}无法解析JSON，保持原内容")
            return content, []

        try:
            import json as _json
            data = _json.loads(json_text)

            # 处理标题修改
            if data.get('title_modified') and data.get('new_title'):
                result = _set_title(result, data['new_title'])
                items_fixed.append('标题吸引力')

            # 处理副标题修改
            if data.get('subtitle_modified') and data.get('new_subtitle'):
                result = _set_subtitle(result, data['new_subtitle'])

            # 处理正文修改
            if data.get('body_modified') and data.get('new_body'):
                result = _set_body(result, data['new_body'])

            # 处理已修复项
            if data.get('items_fixed'):
                items_fixed.extend(data['items_fixed'])

            if items_fixed:
                logger.info(f"[递进优化] 组{group_key}已修复: {items_fixed}")
            else:
                logger.info(f"[递进优化] 组{group_key}标记无修改")

        except Exception as e:
            logger.error(f"[递进优化] 组{group_key}JSON解析失败: {e}，保持原内容")
            return content, []

        return result, list(set(items_fixed))

    def _extract_json(self, text: str) -> Optional[str]:
        """从响应文本中提取JSON"""
        # 优先找 ```json ... ```
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # 其次找第一个 {...}
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return None


def _deep_copy_content(content: Dict) -> Dict:
    """深拷贝内容，保留长文结构"""
    import copy
    return copy.deepcopy(content)


# =============================================================================
# 全局实例
# =============================================================================
progressive_optimizer = ProgressiveContentOptimizer()
