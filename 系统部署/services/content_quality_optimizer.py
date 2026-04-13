"""
GEO 内容智能修补引擎 v2.0

核心铁律（100%严格执行）：
1. 绝对禁止 LLM 重写全文
2. 合格项目 100% 禁止改动，LLM 无权触碰
3. 只修复当前不合格项目
4. 不改变：标题结构、段落顺序、核心观点、原文风格
5. 只做最小改动，不扩写、不跑题、不新增无关内容
6. 优化后分数 ↓ 则自动回滚到上一版，只接受分数上涨的版本

固定优化顺序（不许修改）：
第1轮：只跑 A 组（结构+模块化）→ 最安全，必提分
第2轮：只跑 B 组（标题+开篇）
第3轮：只跑 C 组（剩余不合格项）
达到 80 分自动停止
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from services.llm import get_llm_service
from services.content_quality_scorer import (
    content_scorer, ScoreItem, ScoreResult,
    GEO_OPTIMIZATION_GROUPS, GROUP_ORDER,
    get_failed_items_by_group,
    QUALIFIED_ITEMS_LOCKED, AUTO_ROLLBACK_ON_DECLINE,
    PASS_THRESHOLD_SCORE,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class RoundResult:
    """单轮优化结果"""
    round_num: int           # 第几轮（1-based）
    group_key: str           # 组标识 A/B/C
    group_label: str         # 组标签
    group_scope: str         # 优化范围描述
    items_in_round: List[str]  # 本轮要优化的项（仅不合格项）
    items_fixed: List[str]    # 实际修复的项
    score_before: float      # 本轮优化前分数
    score_after: float       # 本轮优化后分数
    content_snapshot: Dict   # 本轮优化后的内容快照
    quality_report_snapshot: Dict  # 本轮优化后的评分报告
    rollback: bool = False   # 是否发生了回滚
    stopped: bool = False   # 是否因达到80分而停止
    message: str = ''


@dataclass
class ProgressiveOptimizationResult:
    """递进式优化最终结果"""
    success: bool
    optimized_content: Dict = None
    total_rounds: int = 0
    final_score: float = 0
    first_score: float = 0
    final_report: Dict = None
    round_history: List[RoundResult] = field(default_factory=list)
    message: str = ''
    stopped_early: bool = False
    rollback_count: int = 0  # 回滚次数


# =============================================================================
# 内容提取工具（兼容图文和长文两种结构）
# =============================================================================

def _extract_body(content: Dict) -> str:
    """从内容中提取正文"""
    article = content.get('article', {})
    if article:
        body = article.get('body', '')
        if body:
            return body
    return content.get('body', '') or content.get('content', '') or ''


def _extract_title(content: Dict) -> str:
    """从内容中提取标题"""
    article = content.get('article', {})
    if article:
        title = article.get('title', '')
        if title:
            return title
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
    content = dict(content)
    article = content.get('article')
    if article:
        article = dict(article)
        article['title'] = new_title
        content['article'] = article
    else:
        content['title'] = new_title
    return content


def _set_subtitle(content: Dict, new_subtitle: str) -> Dict:
    """设置副标题（兼容长文结构）"""
    content = dict(content)
    article = content.get('article')
    if article:
        article = dict(article)
        article['subtitle'] = new_subtitle
        content['article'] = article
    else:
        content['subtitle'] = new_subtitle
    return content


def _set_body(content: Dict, new_body: str) -> Dict:
    """设置正文（兼容长文结构）"""
    content = dict(content)
    article = content.get('article')
    if article:
        article = dict(article)
        article['body'] = new_body
        content['article'] = article
    else:
        content['body'] = new_body
    return content


def _deep_copy_content(content: Dict) -> Dict:
    """深拷贝内容"""
    import copy
    return copy.deepcopy(content)


# =============================================================================
# 修补式 Prompt 构建
# =============================================================================

FIX_PROMPT_TEMPLATE = """你是GEO内容修补师，只做修补，不重写。

【硬性约束 - 必须100%遵守】
1. 只修复以下不合格项，其他内容完全不动
2. 不动标题、不动段落顺序、不改变核心观点
3. 不扩写、不跑题、不换风格
4. 只做最小改动，达标即可
5. 合格项目绝对不改动

【本轮优化范围】
{group_scope}

【本轮不合格项】
{bad_items}

【本轮优化建议】
{suggestions}

【品牌信息】
品牌名：{brand_name}
业务描述：{business_desc}

【当前文章标题】
{title}

【当前文章副标题】
{subtitle}

【当前文章正文】
{body}

【输出格式】严格返回JSON：
{{
  "title_modified": false,
  "new_title": null,
  "subtitle_modified": false,
  "new_subtitle": null,
  "body_modified": true/false,
  "new_body": "只修改不合格项相关的句子，其他内容原样保留",
  "items_fixed": ["实际修复的项名称"],
  "fix_summary": "本轮修改的简要说明（20字内）"
}}

关键：body_modified=true 时必须返回完整正文（包含未修改的部分）"""


def build_fix_prompt(
    group_key: str,
    group_items: List[ScoreItem],
    title: str,
    subtitle: str,
    body: str,
    brand_name: str,
    business_desc: str
) -> str:
    """构建修补式Prompt"""
    group_def = GEO_OPTIMIZATION_GROUPS[group_key]

    # 本轮不合格项列表
    bad_items = '\n'.join(
        f"- 【{item.name}】{item.suggestion}"
        for item in group_items
    )

    # 本轮优化建议
    suggestions = '\n'.join(
        f"{i+1}. 【{item.name}】{item.suggestion}"
        for i, item in enumerate(group_items)
    )

    return FIX_PROMPT_TEMPLATE.format(
        group_scope=group_def.get('scope', ''),
        bad_items=bad_items,
        suggestions=suggestions,
        brand_name=brand_name or '未提供',
        business_desc=business_desc or '未提供',
        title=title,
        subtitle=subtitle,
        body=body,
    )


# =============================================================================
# 智能修补引擎
# =============================================================================

class ProgressiveContentOptimizer:
    """GEO内容智能修补引擎 v2.0"""

    PASS_THRESHOLD = PASS_THRESHOLD_SCORE  # 80分

    def __init__(self):
        self.llm = get_llm_service()

    def optimize(
        self,
        content: Dict,
        failed_items: List[ScoreItem],
        initial_score: float,
        brand_name: str = '',
        business_desc: str = '',
        max_rounds: int = 3,
        progress_callback=None
    ) -> ProgressiveOptimizationResult:
        """
        递进式修补优化入口

        核心逻辑：
        1. 按 ABC 三组顺序递进优化
        2. 每轮只给 LLM 本组的不合格项
        3. 优化后重新评分
        4. 分数下降 → 自动回滚，不更新内容
        5. 达到80分 → 立即停止
        """
        def _send(event_type, data):
            if progress_callback:
                try:
                    progress_callback(event_type, data)
                except Exception as e:
                    logger.warning(f"[修补引擎] 进度回调失败: {e}")

        # 铁律1：已达80分不优化
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

        # 铁律2：无不合格项不优化
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
        _send('start', {
            'initial_score': initial_score,
            'failed_items_count': len(failed_items),
            'total_groups': len(GROUP_ORDER),
        })

        # 按组分类不合格项
        failed_by_group = get_failed_items_by_group(failed_items)

        logger.info(f"[修补引擎] 初始分={initial_score}, 不合格项按组分类: "
                    + ", ".join(f"{k}:{[f.name for f in v]}" for k, v in failed_by_group.items() if v))

        # 确定要执行的轮次（每组只执行一次，除非无不合格项）
        rounds_to_execute = []
        for group_key in GROUP_ORDER:
            group_items = failed_by_group.get(group_key, [])
            if group_items:
                group_def = GEO_OPTIMIZATION_GROUPS[group_key]
                rounds_to_execute.append({
                    'group_key': group_key,
                    'group_def': group_def,
                    'group_items': group_items,
                })

        if not rounds_to_execute:
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

        logger.info(f"[修补引擎] 将执行 {len(rounds_to_execute)} 轮: {[r['group_key'] for r in rounds_to_execute]}")

        # 核心状态变量
        best_content = _deep_copy_content(content)  # 最佳版本（用于回滚）
        best_score = initial_score
        current_content = _deep_copy_content(content)
        current_score = initial_score
        round_history: List[RoundResult] = []
        rollback_count = 0
        stopped_early = False

        # 开始逐轮优化
        for round_idx, round_info in enumerate(rounds_to_execute):
            if round_idx >= max_rounds:
                logger.info(f"[修补引擎] 已达最大轮数{max_rounds}，停止")
                break

            group_key = round_info['group_key']
            group_def = round_info['group_def']
            group_items = round_info['group_items']
            round_num = len(round_history) + 1

            group_label = group_def['label']
            group_scope = group_def.get('scope', '')
            items_in_round = [f.name for f in group_items]

            logger.info(f"[修补引擎] === 第{round_num}轮：{group_key}组 {group_def['name']} ===")
            logger.info(f"[修补引擎] 本轮优化项: {items_in_round}")
            logger.info(f"[修补引擎] 当前基准分: {current_score:.1f}")

            # 发送轮次开始事件
            _send('round_start', {
                'round_num': round_num,
                'group_key': group_key,
                'group_label': group_label,
                'group_scope': group_scope,
                'items': items_in_round,
                'score_before': current_score,
                'total_groups': len(rounds_to_execute),
            })

            # 执行本轮修补优化
            round_result = self._fix_single_round(
                content=current_content,
                group_key=group_key,
                group_def=group_def,
                group_items=group_items,
                brand_name=brand_name,
                business_desc=business_desc,
                round_num=round_num,
                score_before=current_score,
            )

            # ========== 核心：分数对比与回滚 ==========
            # 回滚时需要恢复到上一轮的内容，暂存上一轮内容用于记录
            previous_content = current_content
            if round_result.score_after > current_score:
                # 分数上涨 → 保留
                logger.info(f"[修补引擎] 第{round_num}轮：{round_result.score_before} → {round_result.score_after} ✓ 分数上涨，保留")
                current_content = round_result.content_snapshot
                current_score = round_result.score_after
                round_result.rollback = False
            elif round_result.score_after == current_score:
                # 分数持平 → 保留但不计入成功轮
                logger.info(f"[修补引擎] 第{round_num}轮：{round_result.score_before} → {round_result.score_after} = 分数持平，保留")
                current_content = round_result.content_snapshot
                round_result.rollback = False
            else:
                # 分数下降 → 自动回滚
                rollback_count += 1
                round_result.rollback = True
                # current_content 保持不变（已指向上一轮的 snapshot，无需额外操作）
                # round_result.content_snapshot = bad content (本轮优化后的内容)，不更新 current_content
                logger.warning(f"[修补引擎] 第{round_num}轮：{round_result.score_before} → {round_result.score_after} ✗ 分数下降，自动回滚到 {current_score:.1f}，内容保留上一轮版本")
                round_result.score_after = current_score  # 报告显示原始分数
                round_result.items_fixed = []
                round_result.message = f'分数下降（{round_result.score_after:.1f}→{current_score:.1f}），已自动回滚'

            round_history.append(round_result)

            # 发送轮次完成事件
            _send('round_complete', {
                'round_num': round_num,
                'group_key': group_key,
                'group_label': group_label,
                'group_scope': group_scope,
                'items_fixed': round_result.items_fixed,
                'items_in_round': items_in_round,
                'score_before': round_result.score_before,
                'score_after': round_result.score_after,
                'score_delta': round_result.score_after - round_result.score_before,
                'rollback': round_result.rollback,
                'total_groups': len(rounds_to_execute),
                'reached80': current_score >= self.PASS_THRESHOLD,
            })

            # 达到80分，提前停止
            if current_score >= self.PASS_THRESHOLD:
                logger.info(f"[修补引擎] 分数达到{current_score}（>={self.PASS_THRESHOLD}），提前停止")
                stopped_early = True
                break

        # 最终评分（使用最佳版本）
        final_report_dict = content_scorer.to_dict(content_scorer.score(current_content, brand_name))
        final_report_dict['optimized'] = True
        final_report_dict['first_score'] = initial_score
        final_report_dict['final_score'] = current_score
        final_report_dict['total_rounds'] = len(round_history)
        final_report_dict['rollback_count'] = rollback_count

        # 轮次历史（只保留未回滚的轮次用于显示）
        display_round_history = [
            {
                'round_num': r.round_num,
                'group_key': r.group_key,
                'group_label': r.group_label,
                'group_scope': r.group_scope,
                'items_in_round': r.items_in_round,
                'items_optimized': r.items_fixed if not r.rollback else [],
                'score_before': r.score_before,
                'score_after': r.score_after,
                'rollback': r.rollback,
                'stopped': r.stopped,
                'message': r.message,
            }
            for r in round_history
        ]
        final_report_dict['round_history'] = display_round_history

        # 【注意】不发送 complete 事件，由 SSE endpoint 统一发送
        # SSE endpoint 会在优化完成后构建包含 quality_report、round_history 的完整 complete 事件

        return ProgressiveOptimizationResult(
            success=True,
            optimized_content=current_content,
            total_rounds=len(round_history),
            final_score=current_score,
            first_score=initial_score,
            final_report=final_report_dict,
            round_history=round_history,
            message=f'修补完成，共{len(round_history)}轮，最终分数{current_score}',
            stopped_early=stopped_early,
            rollback_count=rollback_count,
        )

    def _fix_single_round(
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
        """执行单轮修补优化"""
        body = _extract_body(content)
        title = _extract_title(content)
        subtitle = _extract_subtitle(content)

        # 构建修补式提示词
        prompt = build_fix_prompt(
            group_key=group_key,
            group_items=group_items,
            title=title,
            subtitle=subtitle,
            body=body,
            brand_name=brand_name,
            business_desc=business_desc,
        )

        # 调用 LLM 修补
        try:
            response = self.llm.chat([
                {"role": "system", "content": "你是GEO内容修补师。严格遵守规则：只修补不合格项，不重写全文，不改变合格项。"},
                {"role": "user", "content": prompt}
            ])
        except Exception as e:
            logger.error(f"[修补引擎] 第{round_num}轮 LLM调用失败: {e}")
            return RoundResult(
                round_num=round_num,
                group_key=group_key,
                group_label=group_def['label'],
                group_scope=group_def.get('scope', ''),
                items_in_round=[f.name for f in group_items],
                items_fixed=[],
                score_before=score_before,
                score_after=score_before,
                content_snapshot=content,
                quality_report_snapshot={},
                message=f'LLM调用失败: {e}'
            )

        # 解析 LLM 响应
        new_content, items_fixed = self._parse_fix_response(
            response, content, group_items, group_key
        )

        # 重新评分
        score_after_result = content_scorer.score(new_content, brand_name)
        score_after = score_after_result.total_score
        quality_dict = content_scorer.to_dict(score_after_result)

        # 是否达到80分
        stopped = score_after >= self.PASS_THRESHOLD

        return RoundResult(
            round_num=round_num,
            group_key=group_key,
            group_label=group_def['label'],
            group_scope=group_def.get('scope', ''),
            items_in_round=[f.name for f in group_items],
            items_fixed=items_fixed,
            score_before=score_before,
            score_after=score_after,
            content_snapshot=new_content,
            quality_report_snapshot=quality_dict,
            rollback=False,
            stopped=stopped,
            message=f'修补了: {", ".join(items_fixed)}' if items_fixed else '无修改'
        )

    def _parse_fix_response(
        self,
        response: str,
        content: Dict,
        group_items: List[ScoreItem],
        group_key: str
    ) -> tuple:
        """解析修补响应，返回（新内容, 已修复项列表）"""
        if not response:
            logger.warning(f"[修补引擎] 组{group_key}响应为空，保持原内容")
            return content, []

        result = content.copy() if isinstance(content, dict) else dict(content)
        items_fixed = []

        json_text = self._extract_json(response)
        if not json_text:
            logger.warning(f"[修补引擎] 组{group_key}无法解析JSON，保持原内容")
            return content, []

        try:
            import json as _json
            data = _json.loads(json_text)

            # 只处理 body_modified=true 的情况
            if data.get('body_modified') and data.get('new_body'):
                result = _set_body(result, data['new_body'])

            # 处理标题修改（谨慎）
            if data.get('title_modified') and data.get('new_title'):
                result = _set_title(result, data['new_title'])
                items_fixed.append('标题吸引力')

            # 处理副标题修改
            if data.get('subtitle_modified') and data.get('new_subtitle'):
                result = _set_subtitle(result, data['new_subtitle'])

            # 处理已修复项
            if data.get('items_fixed'):
                for item in data['items_fixed']:
                    if item not in items_fixed:
                        items_fixed.append(item)

            if items_fixed:
                logger.info(f"[修补引擎] 组{group_key}已修复: {items_fixed}")
            else:
                logger.info(f"[修补引擎] 组{group_key}标记无修改")

        except Exception as e:
            logger.error(f"[修补引擎] 组{group_key} JSON解析失败: {e}，保持原内容")
            return content, []

        return result, list(set(items_fixed))

    def _extract_json(self, text: str) -> Optional[str]:
        """从响应文本中提取JSON"""
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return None


# =============================================================================
# 全局实例
# =============================================================================
progressive_optimizer = ProgressiveContentOptimizer()
