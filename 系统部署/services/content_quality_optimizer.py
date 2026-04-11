"""
GEO内容质量自动优化服务

当内容评分低于80分时，自动触发优化机制：
- 不达标项 ≤ 2项 → 定向优化（针对具体问题修复）
- 不达标项 > 2项 → 重新生成

优化策略：
- regenerate：重新生成该项对应内容
- fix：直接修复文本格式/结构问题
- llm_fix：LLM定向修复语义问题
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from services.llm import get_llm_service
from services.content_quality_scorer import content_scorer, ScoreItem

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool                    # 优化是否成功
    optimized_content: Dict = None    # 优化后的内容
    optimized_items: List[str] = field(default_factory=list)  # 优化了哪些项
    score_after: int = 0            # 优化后评分
    optimization_type: str = ''      # 'direct_fix' / 'regenerate'
    used_rounds: int = 1            # 消耗的优化轮次
    message: str = ''               # 提示信息


class ContentQualityOptimizer:
    """内容质量自动优化器"""

    # 优化配置
    MAX_OPTIMIZATION_ROUNDS = 2      # 最多优化2次
    DIRECT_FIX_THRESHOLD = 2          # ≤2项不达标时定向优化，否则重新生成
    PASS_THRESHOLD = 80              # 及格分数

    # 评估项ID到优化策略的映射
    OPTIMIZATION_PROMPTS = {
        1: {  # 标题吸引力
            'type': 'regenerate',
            'name': '标题吸引力',
            'prompt': """请重新撰写标题，要求：
1. 包含疑问词（为什么/怎么/是什么/如何）
2. 或包含价值承诺词（必看/收藏/揭秘/干货）
3. 标题长度10-20字
4. 标题要戳心，能引发用户点击欲望"""
        },
        2: {  # 开篇直接性
            'type': 'llm_fix',
            'name': '开篇直接性',
            'prompt': """请优化开篇段落，要求：
1. 前20字内直接给出核心结论/答案
2. 不要有任何铺垫（如"近年来"、"很多人"等）
3. 开门见山，直击要害
4. 示例开头："{核心答案}。这是因为..." """
        },
        3: {  # 结构清晰度
            'type': 'regenerate',
            'name': '结构清晰度',
            'prompt': """请重新组织文章结构，要求：
1. 添加3个以上小标题（用##标记）
2. 每个小标题下内容不超过3段
3. 使用列表（- 或 1.）展示要点
4. 确保层次分明、逻辑清晰"""
        },
        4: {  # 模块化完整
            'type': 'llm_fix',
            'name': '模块化完整',
            'prompt': """请优化文章段落，要求：
1. 每个段落要有独立的小标题
2. 每个段落开头的第一句就要概括核心观点
3. 段落内不要出现"详见上文"、"如上所述"等需要上下文的内容
4. 确保每个段落可以单独拎出来阅读而不产生歧义"""
        },
        5: {  # 信任证据
            'type': 'llm_fix',
            'name': '信任证据',
            'prompt': """请增加信任证据，要求：
1. 为核心观点添加具体数据（如：90%、3天、5000元）
2. 添加真实案例（可用"某企业/某用户"代替）
3. 添加权威引用（行业报告/专家观点）
4. 至少添加2处信任证据"""
        },
        6: {  # 品牌锚点
            'type': 'fix',
            'name': '品牌锚点',
            'prompt': """请在文章中增加品牌露出，要求：
1. 开头提到品牌
2. 中间某个要点中自然融入品牌
3. 结尾再次提及品牌
4. 共3处，分布均匀"""
        },
        7: {  # 关键词密度
            'type': 'fix',
            'name': '关键词密度',
            'prompt': """请调整关键词密度，要求：
1. 核心关键词在正文中出现2-3次
2. 关键词要自然融入，不要刻意堆砌
3. 避免关键词出现超过5次（会被判定为作弊）"""
        },
        8: {  # 可读性
            'type': 'fix',
            'name': '可读性',
            'prompt': """请优化段落长度，要求：
1. 每个段落不超过50字
2. 将长段落拆分为多个短段落
3. 使用空行分隔段落
4. 适当使用emoji缓解阅读疲劳（可选）"""
        },
        9: {  # 行动号召
            'type': 'llm_fix',
            'name': '行动号召',
            'prompt': """请优化结尾行动号召，要求：
1. 结尾必须有明确的单一行动指令
2. 行动要低门槛（如：关注、评论、收藏、私信）
3. 不要给多个选择，只给一个行动
4. 示例："觉得有用就关注我，下期更精彩" """
        },
        10: {  # 改造潜力
            'type': 'regenerate',
            'name': '改造潜力',
            'prompt': """请优化内容结构，增强改造潜力：
1. 使用清晰的数字编号（如1、2、3）
2. 每个要点单独成段
3. 核心观点用简短金句总结
4. 确保内容可以被轻松提炼为思维导图或短视频脚本"""
        },
    }

    # 可直接修复的类型
    FIXABLE_TYPES = {'fix', 'llm_fix'}

    def __init__(self):
        self.llm = get_llm_service()

    def optimize(self, content: Dict, failed_items: List[ScoreItem],
                 brand_name: str = '', business_desc: str = '',
                 max_rounds: int = None) -> OptimizationResult:
        """
        优化入口

        Args:
            content: 原始内容
            failed_items: 不达标项列表
            brand_name: 品牌名
            business_desc: 业务描述
            max_rounds: 最大优化轮次（默认2轮）

        Returns:
            OptimizationResult: 优化结果
        """
        if max_rounds is None:
            max_rounds = self.MAX_OPTIMIZATION_ROUNDS

        # 如果没有不达标项，直接返回
        if not failed_items:
            return OptimizationResult(
                success=True,
                optimized_content=content,
                optimized_items=[],
                score_after=100,
                optimization_type='none',
                used_rounds=0,
                message='内容已达标，无需优化'
            )

        # 记录已优化的项
        all_optimized_items = []
        current_content = content.copy()

        for round_num in range(1, max_rounds + 1):
            logger.info(f"[ContentQualityOptimizer] 第{round_num}轮优化开始，不达标项: {[item.name for item in failed_items]}")

            # 决策：定向优化还是重新生成
            if len(failed_items) <= self.DIRECT_FIX_THRESHOLD:
                optimization_type = 'direct_fix'
            else:
                optimization_type = 'regenerate'

            # 执行优化
            if optimization_type == 'direct_fix':
                optimized_content, optimized_names = self._fix_items(
                    current_content, failed_items, brand_name
                )
            else:
                optimized_content, optimized_names = self._regenerate_content(
                    current_content, brand_name, business_desc, failed_items
                )

            all_optimized_items.extend(optimized_names)
            current_content = optimized_content

            # 重新评分
            score_result = content_scorer.score(current_content, brand_name)
            new_score = score_result.total_score

            logger.info(f"[ContentQualityOptimizer] 第{round_num}轮优化后评分: {new_score}")

            # 达到及格线，停止优化
            if new_score >= self.PASS_THRESHOLD:
                return OptimizationResult(
                    success=True,
                    optimized_content=current_content,
                    optimized_items=all_optimized_items,
                    score_after=new_score,
                    optimization_type=optimization_type,
                    used_rounds=round_num,
                    message=f'优化成功，评分从{100-new_score+score_result.total_score}提升至{new_score}'
                )

            # 未达标，更新不达标项列表，准备下一轮
            failed_items = score_result.failed_items
            if not failed_items:
                break

        # 优化轮次耗尽，返回最后结果
        final_score = content_scorer.score(current_content, brand_name).total_score
        return OptimizationResult(
            success=final_score >= self.PASS_THRESHOLD,
            optimized_content=current_content,
            optimized_items=all_optimized_items,
            score_after=final_score,
            optimization_type='max_rounds',
            used_rounds=max_rounds,
            message=f'已达到最大优化次数({max_rounds}轮)，最终评分{final_score}'
        )

    def _fix_items(self, content: Dict, failed_items: List[ScoreItem],
                   brand_name: str) -> tuple:
        """
        定向修复不达标项

        Returns:
            (优化后的内容, 被优化的项名称列表)
        """
        optimized_names = []

        for item in failed_items:
            strategy = self.OPTIMIZATION_PROMPTS.get(item.id)
            if not strategy:
                continue

            opt_type = strategy['type']
            opt_name = strategy['name']

            if opt_type == 'fix':
                # 直接修复格式/结构问题
                content = self._apply_fix(content, item.id, strategy['prompt'])
                optimized_names.append(opt_name)

            elif opt_type == 'llm_fix':
                # LLM修复语义问题
                content = self._apply_llm_fix(content, item.id, strategy['prompt'])
                optimized_names.append(opt_name)

        return content, optimized_names

    def _apply_fix(self, content: Dict, item_id: int, prompt: str) -> Dict:
        """应用直接修复"""
        body = content.get('body', '')
        title = content.get('title', '')

        if item_id == 6:  # 品牌锚点
            if brand_name and brand_name not in body:
                # 在开头、中间、结尾插入品牌
                paragraphs = body.split('\n\n')
                if len(paragraphs) >= 2:
                    paragraphs[0] = f'我是{brand_name}，' + paragraphs[0]
                    paragraphs[-1] = paragraphs[-1] + f'\n\n我是{brand_name}，专注XX领域。'
                    content['body'] = '\n\n'.join(paragraphs)
                else:
                    content['body'] = f'我是{brand_name}，{body}\n\n我是{brand_name}。'

        elif item_id == 7:  # 关键词密度
            # 关键词密度问题较难自动修复，返回原内容
            pass

        elif item_id == 8:  # 可读性
            # 拆分长段落
            lines = body.split('\n')
            new_lines = []
            for line in lines:
                if len(line) > 100 and '\n' not in line:
                    # 拆分长行
                    sentences = re.split(r'([。！？])', line)
                    current = ''
                    for i, part in enumerate(sentences):
                        current += part
                        if i % 2 == 1:  # 在句号后检查长度
                            if len(current) > 50:
                                new_lines.append(current)
                                current = ''
                    if current:
                        new_lines.append(current)
                else:
                    new_lines.append(line)
            content['body'] = '\n'.join(new_lines)

        return content

    def _apply_llm_fix(self, content: Dict, item_id: int, prompt: str) -> Dict:
        """应用LLM修复"""
        title = content.get('title', '')
        subtitle = content.get('subtitle', '')
        body = content.get('body', '')
        slides = content.get('slides', [])

        # 根据不同项选择要优化的内容部分
        if item_id == 2:  # 开篇直接性
            target_content = body[:500]  # 只优化开篇
        elif item_id == 4:  # 模块化
            target_content = body
        elif item_id == 5:  # 信任证据
            target_content = body
        elif item_id == 9:  # 行动号召
            target_content = body[-500:]  # 只优化结尾
        else:
            target_content = body

        fix_prompt = f"""{prompt}

需要优化的内容：
标题：{title}
{subtitle}

正文：
{target_content}

请直接输出优化后的内容，不要解释。
"""

        try:
            response = self.llm.chat([
                {"role": "system", "content": "你是一位专业的内容编辑。直接输出优化后的内容，不要任何解释。"},
                {"role": "user", "content": fix_prompt}
            ])

            # 提取纯文本响应
            fixed_text = self._extract_text_response(response)

            # 更新内容
            if item_id == 2:  # 开篇直接性
                content['body'] = fixed_text + '\n\n' + body[500:]
            elif item_id == 9:  # 行动号召
                content['body'] = body[:-500] + '\n\n' + fixed_text
            else:
                content['body'] = fixed_text

        except Exception as e:
            logger.error(f"[ContentQualityOptimizer] LLM修复失败 item_id={item_id}: {e}")

        return content

    def _regenerate_content(self, content: Dict, brand_name: str,
                            business_desc: str, failed_items: List[ScoreItem]) -> tuple:
        """
        重新生成内容

        Returns:
            (新内容, 被优化的项名称列表)
        """
        # 获取不达标项的优化提示
        failed_item_ids = [item.id for item in failed_items]
        regenerate_names = []

        regeneration_notes = []
        for item_id in failed_item_ids:
            strategy = self.OPTIMIZATION_PROMPTS.get(item_id)
            if strategy and strategy['type'] == 'regenerate':
                regeneration_notes.append(f"- {strategy['name']}：{strategy['prompt']}")
                regenerate_names.append(strategy['name'])

        # 如果没有需要重新生成的项，使用定向修复
        if not regeneration_notes:
            return self._fix_items(content, failed_items, brand_name)

        # 构建重新生成的Prompt
        regenerate_prompt = f"""你是一位GEO内容优化专家。原始内容未通过质量检测，需要重点优化以下方面：

需要重点优化的项：
{chr(10).join(regeneration_notes)}

业务背景：{business_desc}
品牌：{brand_name}

原始内容标题：{content.get('title', '')}

请重新生成优化后的完整内容，要求：
1. 必须解决上述所有不达标的项
2. 保持原有的核心观点和数据
3. 保持原有的结构框架
4. 直接输出内容，不要解释

输出格式：Markdown
"""

        try:
            response = self.llm.chat([
                {"role": "system", "content": "你是一位专业的内容创作专家。直接输出优化后的Markdown内容。"},
                {"role": "user", "content": regenerate_prompt}
            ])

            # 提取文本响应
            new_body = self._extract_text_response(response)

            # 更新内容
            new_content = content.copy()
            new_content['body'] = new_body

            return new_content, regenerate_names

        except Exception as e:
            logger.error(f"[ContentQualityOptimizer] 重新生成失败: {e}")
            return content, []

    def _extract_text_response(self, response: str) -> str:
        """从LLM响应中提取纯文本"""
        # 去掉可能的代码块标记
        text = re.sub(r'^```(?:markdown)?\s*', '', response, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        return text.strip()

    def to_dict(self, result: OptimizationResult) -> Dict:
        """将优化结果转换为字典"""
        return {
            'success': result.success,
            'optimized_content': result.optimized_content,
            'optimized_items': result.optimized_items,
            'score_after': result.score_after,
            'optimization_type': result.optimization_type,
            'used_rounds': result.used_rounds,
            'message': result.message
        }


# 全局实例
content_optimizer = ContentQualityOptimizer()
