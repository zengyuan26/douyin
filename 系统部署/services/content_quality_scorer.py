"""
GEO内容质量评分服务

基于GEO内容优化自检清单(V1.0)，对生成的内容进行10项评估：
- 战略意图：标题吸引力、开篇直接性
- 结构与逻辑：结构清晰度、模块化完整
- 信任与权威：信任证据、品牌锚点
- 优化与体验：关键词密度、可读性
- 转化与潜力：行动号召、改造潜力

评估方式：
- 规则评分（6项）：毫秒级，速度快
- LLM评分（4项）：语义理解，深度评估
"""

import re
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from services.llm import get_llm_service

logger = logging.getLogger(__name__)


# =============================================================================
# GEO自检清单统一权重配置
# 所有项统一10分满分，简化计算
# =============================================================================
GEO_SELF_CHECK_WEIGHTS = {
    # 所有项统一10分满分
    "local_service": {
        "标题吸引力": 10,
        "开篇直接性": 10,
        "结构清晰度": 10,
        "模块化完整": 10,
        "信任证据": 10,
        "品牌锚点": 10,
        "关键词密度": 10,
        "可读性": 10,
        "行动号召": 10,
        "改造潜力": 10,
    },
    "product": {
        "标题吸引力": 10,
        "开篇直接性": 10,
        "结构清晰度": 10,
        "模块化完整": 10,
        "信任证据": 10,
        "品牌锚点": 10,
        "关键词密度": 10,
        "可读性": 10,
        "行动号召": 10,
        "改造潜力": 10,
    },
    "personal": {
        "标题吸引力": 10,
        "开篇直接性": 10,
        "结构清晰度": 10,
        "模块化完整": 10,
        "信任证据": 10,
        "品牌锚点": 10,
        "关键词密度": 10,
        "可读性": 10,
        "行动号召": 10,
        "改造潜力": 10,
    },
    "enterprise": {
        "标题吸引力": 10,
        "开篇直接性": 10,
        "结构清晰度": 10,
        "模块化完整": 10,
        "信任证据": 10,
        "品牌锚点": 10,
        "关键词密度": 10,
        "可读性": 10,
        "行动号召": 10,
        "改造潜力": 10,
    },
}


def get_self_check_weights(business_type: str) -> Dict[str, int]:
    """获取指定经营类型的自检权重配置"""
    return GEO_SELF_CHECK_WEIGHTS.get(business_type, GEO_SELF_CHECK_WEIGHTS.get("local_service"))


def get_pass_threshold(business_type: str) -> int:
    """获取指定经营类型的及格分数线"""
    thresholds = {
        "enterprise": 85,
        "personal": 82,
        "product": 80,
        "local_service": 80,
    }
    return thresholds.get(business_type, 80)


# =============================================================================
# GEO递进式优化引擎 - 优化组定义（严格按规格，不许修改）
# =============================================================================
# A组（最安全·结构组）：结构+模块化，最先优化
# B组（安全·骨架组）：标题+开篇，第二优化
# C组（敏感·信任转化组）：信任证据+品牌锚点+关键词+可读性+CTA+改造潜力，最后优化
GEO_OPTIMIZATION_GROUPS = {
    'A': {
        'name': '结构组',
        'label': 'A组 · 最安全 · 结构+模块化',
        'scope': '仅结构组',
        'priority': 1,  # 第1轮
        'items': ['结构清晰度', '模块化完整'],
    },
    'B': {
        'name': '骨架组',
        'label': 'B组 · 安全 · 标题+开篇',
        'scope': '仅骨架组',
        'priority': 2,  # 第2轮
        'items': ['标题吸引力', '开篇直接性'],
    },
    'C': {
        'name': '信任转化组',
        'label': 'C组 · 敏感项 · 信任+品牌+关键词+CTA',
        'scope': '敏感项',
        'priority': 3,  # 第3轮
        'items': ['信任证据', '品牌锚点', '关键词密度', '可读性', '行动号召', '改造潜力'],
    },
}

# 优化组执行顺序（严格固定）
GROUP_ORDER = ['A', 'B', 'C']

# 合格项铁律：合格项 100% 禁止改动
QUALIFIED_ITEMS_LOCKED = True

# 自动回滚：分数下降自动回滚到上一版
AUTO_ROLLBACK_ON_DECLINE = True

# 分数达标阈值
PASS_THRESHOLD_SCORE = 80


def get_failed_items_by_group(failed_items: List['ScoreItem']) -> Dict[str, List['ScoreItem']]:
    """将不合格项按组分类（A/B/C三组）"""
    result = {g: [] for g in GROUP_ORDER}
    for item in failed_items:
        for group_key, group_def in GEO_OPTIMIZATION_GROUPS.items():
            if item.name in group_def['items']:
                result[group_key].append(item)
                break
    return result


def get_starting_groups(initial_score: float) -> List[str]:
    """根据初始分数确定起始轮次（严格固定：始终从A组开始）"""
    # 铁律：第1轮必须跑A组（结构+模块化），最安全必提分
    return GROUP_ORDER


def should_start_from_group_a(initial_score: float) -> bool:
    """始终返回True：第1轮必须从A组开始"""
    return True


@dataclass
class ScoreItem:
    """单项评分结果"""
    id: int
    category: str           # 所属分类
    name: str               # 评估项名称
    score: int              # 得分 0-10
    max_score: int = 10     # 满分
    weight: float = 1.0     # 权重
    passed: bool = False    # 是否通过（≥10分）
    detail: str = ''       # 评分理由
    suggestion: str = ''    # 改进建议
    icon: str = '✅'        # 状态图标


@dataclass
class ScoreResult:
    """综合评分结果"""
    total_score: float = 0.0           # 总分 0-100
    grade: str = 'D'               # 等级 A/B/C/D
    grade_label: str = ''           # 等级标签
    passed: bool = False            # 是否≥80分
    pass_threshold: float = 0.0      # 通过阈值
    items: List[ScoreItem] = field(default_factory=list)  # 各项评分
    failed_items: List[ScoreItem] = field(default_factory=list)  # 不达标项
    summary: str = ''               # 整体评价
    suggestions: List[str] = field(default_factory=list)  # 改进建议
    business_type: str = 'local_service'  # 经营类型


class ContentQualityScorer:
    """GEO内容质量评分器"""

    # 评估项配置
    SCORING_ITEMS = [
        # 第一部分：战略意图
        {
            'id': 1,
            'category': '战略意图',
            'name': '标题吸引力',
            'description': '标题是否清晰的问题句或包含强烈价值承诺',
            'method': 'rule',
        },
        {
            'id': 2,
            'category': '战略意图',
            'name': '开篇直接性',
            'description': '文章前三句话内是否给出核心答案',
            'method': 'llm',
        },
        # 第二部分：结构与逻辑
        {
            'id': 3,
            'category': '结构与逻辑',
            'name': '结构清晰度',
            'description': '是否有清晰的层级结构和列表',
            'method': 'rule',
        },
        {
            'id': 4,
            'category': '结构与逻辑',
            'name': '模块化完整',
            'description': '每个主要段落是否可单独成为完整答案',
            'method': 'llm',
        },
        # 第三部分：信任与权威
        {
            'id': 5,
            'category': '信任与权威',
            'name': '信任证据',
            'description': '是否为观点提供信任证据（案例、数据、引用）',
            'method': 'llm',
        },
        {
            'id': 6,
            'category': '信任与权威',
            'name': '品牌锚点',
            'description': '文章中是否清晰、一致地植入品牌/IP',
            'method': 'rule',
        },
        # 第四部分：优化与体验
        {
            'id': 7,
            'category': '优化与体验',
            'name': '关键词密度',
            'description': '核心关键词是否自然出现2-3次',
            'method': 'rule',
        },
        {
            'id': 8,
            'category': '优化与体验',
            'name': '可读性',
            'description': '段落是否简短、排版是否清爽',
            'method': 'rule',
        },
        # 第五部分：转化与潜力
        {
            'id': 9,
            'category': '转化与潜力',
            'name': '行动号召',
            'description': '结尾是否给出唯一、明确、低门槛的下一步行动',
            'method': 'llm',
        },
        {
            'id': 10,
            'category': '转化与潜力',
            'name': '改造潜力',
            'description': '内容是否具备被改造的潜力（结构图、短视频）',
            'method': 'llm',
        },
    ]

    # 规则项IDs
    RULE_ITEM_IDS = [1, 3, 6, 7, 8]
    # LLM项IDs
    LLM_ITEM_IDS = [2, 4, 5, 9, 10]

    # 标题疑问词
    TITLE_QUESTION_WORDS = [
        '为什么', '怎么', '如何', '是什么', '是不是', '是不是',
        '哪个', '哪些', '多少', '几', '是不是', '可否', '能否',
        '为何', '怎办', '怎樣', '怎样', '怎麼'
    ]

    # 标题价值承诺词
    TITLE_VALUE_WORDS = [
        '必看', '收藏', '揭秘', '攻略', '指南', '干货', '分享',
        '建议', '技巧', '方法', '秘诀', '绝招', '神器', '必备',
        '收藏备用', '赶紧', '速看', '限时', '内部'
    ]

    # 行动号召关键词
    CTA_KEYWORDS = [
        '关注', '私信', '评论', '留言', '点赞', '转发', '收藏',
        '领取', '获取', '下载', '扫码', '联系', '咨询', '预约',
        '购买', '下单', '参与', '加入', '注册', '申请'
    ]

    def __init__(self):
        self.llm = get_llm_service()

    def score(self, content: Dict, brand_name: str = '', business_type: str = 'local_service') -> ScoreResult:
        """
        评分入口

        Args:
            content: 内容数据，结构如下：
                - title: 主标题
                - subtitle: 副标题
                - body: 正文内容（Markdown格式）
                - slides: 图片结构列表
                - seo_keywords: SEO关键词
                - tags: 标签列表
                - hashtags: 话题标签
            brand_name: 品牌名/IP名
            business_type: 经营类型，用于动态权重

        Returns:
            ScoreResult: 评分结果
        """
        # 获取动态权重配置
        weights = get_self_check_weights(business_type)
        pass_threshold = get_pass_threshold(business_type)

        # 提取内容文本
        title = content.get('title', '')
        subtitle = content.get('subtitle', '')
        body = content.get('body', '')
        slides = content.get('slides', [])
        seo_keywords = content.get('seo_keywords', {})
        tags = content.get('tags', [])
        hashtags = content.get('hashtags', [])

        # 合并所有文本用于规则检测
        full_text = self._build_full_text(title, subtitle, body, tags, hashtags)

        # 第一阶段：规则评分
        rule_results = self._score_by_rules(
            title, full_text, body, brand_name, seo_keywords, slides
        )

        # 第二阶段：LLM评分
        llm_results = self._score_by_llm(title, body, brand_name)

        # 合并结果
        all_results = {**rule_results, **llm_results}

        # 构建评分项列表（统一10分满分，80%及格=8分）
        items = []
        for item_config in self.SCORING_ITEMS:
            item_id = item_config['id']
            if item_id in all_results:
                result = all_results[item_id]
                item_weight = 10  # 统一10分满分
                raw_score = result['score']  # LLM返回的原始分（0-10）

                items.append(ScoreItem(
                    id=item_id,
                    category=item_config['category'],
                    name=item_config['name'],
                    score=round(raw_score, 1),
                    max_score=item_weight,
                    passed=raw_score >= 8,  # 统一80%及格线 = 8分
                    detail=result.get('detail', ''),
                    suggestion=result.get('suggestion', ''),
                    icon='✅' if raw_score >= 6 else '⚠️'  # 6分以上显示✅
                ))

        # 计算加权总分
        total_score = sum(item.score for item in items)

        # 确定等级
        grade, grade_label = self._calculate_grade(total_score)

        # 提取不达标项
        failed_items = [item for item in items if not item.passed]

        # 生成改进建议
        suggestions = self._generate_suggestions(failed_items)

        # 生成整体评价
        summary = self._generate_summary(total_score, items)

        return ScoreResult(
            total_score=round(total_score, 1),
            grade=grade,
            grade_label=grade_label,
            passed=total_score >= pass_threshold,
            items=items,
            failed_items=failed_items,
            summary=summary,
            suggestions=suggestions,
            business_type=business_type
        )

    def _build_full_text(self, title: str, subtitle: str, body: str,
                         tags: List, hashtags: List) -> str:
        """构建完整文本用于规则检测"""
        parts = [title, subtitle, body]
        if tags:
            if isinstance(tags, list):
                parts.extend(tags)
            else:
                parts.append(str(tags))
        if hashtags:
            if isinstance(hashtags, list):
                parts.extend(hashtags)
            else:
                parts.append(str(hashtags))
        return '\n'.join(filter(None, parts))

    # ==================== 规则评分 ====================

    def _score_by_rules(self, title: str, full_text: str, body: str,
                        brand_name: str, seo_keywords: Dict,
                        slides: List) -> Dict[int, Dict]:
        """规则评分（6项）"""
        results = {}

        # 1. 标题吸引力
        results[1] = self._check_title_attraction(title)

        # 3. 结构清晰度
        results[3] = self._check_structure(body)

        # 6. 品牌锚点
        results[6] = self._check_brand_anchor(full_text, brand_name)

        # 7. 关键词密度
        core_keywords = seo_keywords.get('core', []) if isinstance(seo_keywords, dict) else []
        results[7] = self._check_keyword_density(full_text, core_keywords)

        # 8. 可读性
        results[8] = self._check_readability(body)

        return results

    def score_text(self, text: str, brand_name: str = '', content_type: str = 'graphic',
                   business_type: str = 'local_service') -> ScoreResult:
        """
        对文本内容评分（用于长文等纯文本内容）。

        统一使用完整 10 项评估流程，与 score() 方法保持一致。
        5 项规则评分 + 5 项 LLM 评分，满分 100。

        Args:
            text: 文本内容（可能是 Markdown 或纯文本）
            brand_name: 品牌名
            content_type: 内容类型（graphic/long_text/video）
            business_type: 经营类型，用于动态权重和及格分数线

        Returns:
            ScoreResult: 评分结果
        """
        # 解析文本结构
        title = ''
        body = text

        # 尝试从 Markdown 中提取标题
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# ') and not title:
                title = line[2:].strip()
                break

        # 构建完整文本
        full_text = text

        # 阶段一：规则评分（5项）
        rule_results = self._score_by_rules(
            title, full_text, body, brand_name, {}, []
        )

        # 阶段二：LLM 评分（5项），截取前 3000 字控制 token
        llm_results = self._score_by_llm(title, body[:3000], brand_name)

        # 合并结果
        all_results = {**rule_results, **llm_results}

        # 构建评分项列表（统一10分满分，80%及格=8分）
        items = []
        for item_config in self.SCORING_ITEMS:
            item_id = item_config['id']
            if item_id in all_results:
                result = all_results[item_id]
                raw_score = result['score']

                items.append(ScoreItem(
                    id=item_id,
                    category=item_config['category'],
                    name=item_config['name'],
                    score=round(raw_score, 1),
                    max_score=10,
                    passed=raw_score >= 8,
                    detail=result.get('detail', ''),
                    suggestion=result.get('suggestion', ''),
                    icon='✅' if raw_score >= 6 else '⚠️'
                ))

        # 计算加权总分
        total_score = sum(item.score for item in items)

        # 确定等级
        grade, grade_label = self._calculate_grade(total_score)

        # 提取不达标项
        failed_items = [item for item in items if not item.passed]

        # 生成改进建议
        suggestions = self._generate_suggestions(failed_items)

        # 生成整体评价
        summary = self._generate_summary(total_score, items)

        pass_threshold = get_pass_threshold(business_type)

        return ScoreResult(
            total_score=round(total_score, 1),
            grade=grade,
            grade_label=grade_label,
            passed=total_score >= pass_threshold,
            pass_threshold=pass_threshold,
            items=items,
            failed_items=failed_items,
            summary=summary,
            suggestions=suggestions
        )

    def _get_grade(self, percentage: float) -> str:
        """根据百分比获取等级"""
        if percentage >= 90:
            return 'A'
        elif percentage >= 75:
            return 'B'
        elif percentage >= 60:
            return 'C'
        else:
            return 'D'

    def _get_grade_label(self, percentage: float) -> str:
        """根据百分比获取等级标签"""
        if percentage >= 90:
            return '优秀'
        elif percentage >= 75:
            return '良好'
        elif percentage >= 60:
            return '及格'
        else:
            return '需改进'

    # 情绪词列表（高情绪词加分）
    TITLE_EMOTION_WORDS = [
        '终于', '后悔', '崩溃', '哭死', '救命', '绝了', '太牛了',
        '后悔', '扎心', '破防', '泪目', '笑死', '炸裂', '必看',
        '千万别', '一定要', '收藏', '赶紧', '速看', '曝光',
        '揭秘', '内幕', '真相', '套路', '坑', '血亏',
        '强推', '安利', '种草', '测评', '实测',
    ]

    # 差异化检测词（扣分词：模板化、泛滥标题党）
    TITLE_TRASH_WORDS = [
        '怎么办', '大全', '收藏', '必看', '最全',
        '建议收藏', '建议收藏备用', '抓紧收藏',
    ]

    def _check_title_attraction(self, title: str) -> Dict:
        """
        检查标题吸引力（多维度综合评分）。

        维度：
        1. 疑问词（+3）：是搜索类标题的核心
        2. 情绪词（+2）：高情绪词增加点击率
        3. 价值承诺词（+1）：辅助加分
        4. 长度适中（+1/-1）
        5. 情绪钩子多样性（+1）：有数字/对比/反问等结构
        6. 扣分项（-2）：模板化泛滥标题党
        """
        if not title:
            return {
                'score': 3,
                'detail': '标题为空',
                'suggestion': '请输入一个有吸引力的标题'
            }

        title_lower = title.lower()
        title_len = len(title)
        score = 5  # 基础分

        # 1. 疑问词（核心搜索特征）
        has_question = any(word in title_lower for word in self.TITLE_QUESTION_WORDS)
        if has_question:
            score += 3

        # 2. 情绪词（高点击率词）
        has_emotion = any(word in title_lower for word in self.TITLE_EMOTION_WORDS)
        if has_emotion:
            score += 2

        # 3. 价值承诺词
        has_value = any(word in title_lower for word in self.TITLE_VALUE_WORDS)
        if has_value:
            score += 1

        # 4. 长度适中（10-30字最优）
        if 10 <= title_len <= 30:
            score += 1
        elif title_len < 10:
            score -= 1
        elif title_len > 40:
            score -= 1

        # 5. 情绪钩子多样性（有数字/对比/反问等结构）
        has_number = bool(re.search(r'\d+', title))
        has_comparison = any(word in title_lower for word in ['vs', '还是', '对比', '比较', '哪个', '不如', '比'])
        has_negation = any(word in title_lower for word in ['不是', '千万别', '别再', '别以为', '别再', '不要'])
        if has_number or has_comparison or has_negation:
            score += 1

        # 6. 扣分：检测模板化泛滥标题党
        trash_count = sum(1 for word in self.TITLE_TRASH_WORDS if word in title_lower)
        if trash_count > 0:
            score -= 2 * trash_count

        # 特殊扣分：单独出现的"怎么办"（无上下文）
        if '怎么办' in title and not has_question:
            score -= 1

        # 标题太短直接低分
        if title_len < 5:
            return {
                'score': 2,
                'detail': '标题太短，无法清晰表达',
                'suggestion': '标题建议10-20字，包含核心关键词'
            }

        score = max(0, min(10, score))

        if score >= 8:
            detail = '标题质量优秀，包含搜索词+情绪钩子，点击率高'
        elif score >= 6:
            detail = '标题基本合格，有搜索特征，可进一步加入情绪词'
        else:
            detail = '标题缺乏吸引力，建议增加疑问词或情绪词，避免模板化表达'

        return {
            'score': score,
            'detail': detail,
            'suggestion': '建议：加入情绪词或数字钩子，避免「大全/必看/怎么办」等泛滥词' if score < 8 else ''
        }

    def _check_structure(self, body: str) -> Dict:
        """检查结构清晰度"""
        if not body:
            return {
                'score': 4,
                'detail': '正文内容为空',
                'suggestion': '请添加正文内容'
            }

        # 统计标题标记
        h2_count = len(re.findall(r'^#{2}\s', body, re.MULTILINE))
        h3_count = len(re.findall(r'^#{3}\s', body, re.MULTILINE))
        total_headers = h2_count + h3_count

        # 统计列表
        ul_count = len(re.findall(r'^[-*]\s', body, re.MULTILINE))
        ol_count = len(re.findall(r'^\d+\.\s', body, re.MULTILINE))
        total_lists = ul_count + ol_count

        score = 5  # 基础分

        # 有小标题加分
        if total_headers >= 3:
            score += 3
        elif total_headers >= 1:
            score += 1

        # 有列表加分
        if total_lists >= 3:
            score += 2
        elif total_lists >= 1:
            score += 1

        score = max(0, min(10, score))

        if score >= 8:
            detail = f'结构清晰，有{total_headers}个小标题，{total_lists}个列表项'
        elif score >= 5:
            detail = f'结构基本完整，有{total_headers}个小标题'
        else:
            detail = '结构较为松散，建议增加小标题分隔'

        return {
            'score': score,
            'detail': detail,
            'suggestion': '建议添加3个以上小标题，并使用列表展示要点' if score < 8 else ''
        }

    def _check_brand_anchor(self, full_text: str, brand_name: str) -> Dict:
        """检查品牌锚点"""
        if not brand_name:
            return {
                'score': 7,
                'detail': '未提供品牌名，跳过品牌锚点检查',
                'suggestion': ''
            }

        # 统计品牌名出现次数
        brand_count = full_text.lower().count(brand_name.lower())

        if brand_count >= 3:
            score = 10
            detail = f'品牌「{brand_name}」出现{brand_count}次，植入到位'
        elif brand_count >= 2:
            score = 8
            detail = f'品牌「{brand_name}」出现{brand_count}次，符合要求'
        elif brand_count == 1:
            score = 6
            detail = f'品牌「{brand_name}」出现{brand_count}次，建议增加露出'
        else:
            score = 3
            detail = f'未发现品牌「{brand_name}」露出'

        return {
            'score': score,
            'detail': detail,
            'suggestion': f'建议在开头、结尾和中间各植入一次品牌「{brand_name}」' if score < 8 else ''
        }

    def _check_keyword_density(self, full_text: str, core_keywords: List) -> Dict:
        """检查关键词密度"""
        if not core_keywords:
            return {
                'score': 6,
                'detail': '未配置核心关键词，跳过密度检查',
                'suggestion': ''
            }

        full_text_lower = full_text.lower()
        keyword_scores = []

        for keyword in core_keywords:
            if not keyword:
                continue
            count = full_text_lower.count(keyword.lower())
            # 2-3次为最佳，1次或4次可接受，0次或5次以上不合格
            if 2 <= count <= 3:
                keyword_scores.append(10)
            elif count == 1 or count == 4:
                keyword_scores.append(7)
            elif count == 0:
                keyword_scores.append(0)
            else:  # 5次以上
                keyword_scores.append(4)

        if not keyword_scores:
            return {
                'score': 6,
                'detail': '核心关键词列表为空',
                'suggestion': ''
            }

        avg_score = sum(keyword_scores) / len(keyword_scores)
        score = int(avg_score)

        # 统计详情
        good_count = sum(1 for s in keyword_scores if s >= 7)
        total = len(keyword_scores)

        detail = f'核心关键词密度良好（{good_count}/{total}达标）'

        return {
            'score': score,
            'detail': detail,
            'suggestion': '确保核心关键词自然出现2-3次，不要堆砌' if score < 8 else ''
        }

    def _check_readability(self, body: str) -> Dict:
        """检查可读性"""
        if not body:
            return {
                'score': 5,
                'detail': '正文为空',
                'suggestion': '请添加正文内容'
            }

        # 分割段落
        paragraphs = re.split(r'\n\n+', body)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if not paragraphs:
            return {
                'score': 5,
                'detail': '无法识别段落',
                'suggestion': '请使用空行分隔段落'
            }

        # 计算每段平均长度
        total_len = sum(len(p) for p in paragraphs)
        avg_len = total_len / len(paragraphs)

        # 统计超长段落数量
        long_paragraphs = sum(1 for p in paragraphs if len(p) > 100)

        score = 8  # 基础分

        # 平均长度适中
        if avg_len <= 50:
            score += 2
        elif avg_len <= 80:
            score += 1
        elif avg_len > 150:
            score -= 3

        # 超长段落扣分
        if long_paragraphs > len(paragraphs) * 0.5:
            score -= 2

        score = max(0, min(10, score))

        if score >= 8:
            detail = f'段落简短适中（平均{avg_len:.0f}字），阅读体验好'
        elif score >= 5:
            detail = f'段落长度基本合理（平均{avg_len:.0f}字）'
        else:
            detail = f'段落偏长（平均{avg_len:.0f}字），阅读压力大'

        return {
            'score': score,
            'detail': detail,
            'suggestion': '建议将长段落拆分为50字以内的短段落' if score < 8 else ''
        }

    # ==================== LLM评分 ====================

    def _score_by_llm(self, title: str, body: str, brand_name: str) -> Dict[int, Dict]:
        """LLM评分（5项）：开篇直接性、模块化完整、信任证据、行动号召、改造潜力"""
        results = {}

        # 构建评估文本
        content_for_eval = f"""标题：{title}

正文：
{body[:3000]}  # 限制长度避免token过多
"""

        if brand_name:
            content_for_eval += f"\n品牌名：{brand_name}"

        # 并行评估4个LLM项
        try:
            results[2] = self._llm_check_opening_directness(content_for_eval)
            results[4] = self._llm_check_modularity(content_for_eval)
            results[5] = self._llm_check_trust_evidence(content_for_eval)
            results[9] = self._llm_check_call_to_action(content_for_eval)
            results[10] = self._llm_check_potential(content_for_eval)
        except Exception as e:
            logger.error("[ContentQualityScorer] LLM评分异常: %s", e)
            # 异常时给默认值（5分，及格线以下）
            for item_id in self.LLM_ITEM_IDS:
                results[item_id] = {
                    'score': 5,
                    'detail': 'LLM评估异常，使用默认值',
                    'suggestion': ''
                }

        return results

    def _llm_check_opening_directness(self, content: str) -> Dict:
        """检查开篇直接性 - LLM评估（带重试）"""
        prompt = f"""你是一位GEO内容优化专家。请评估以下内容的「开篇直接性」。

评分标准：
- 10分：开篇前20字内直接给出核心结论/答案，无任何铺垫
- 7-9分：开篇1-3句内给出核心答案，有简短过渡
- 4-6分：开篇4-5句才给出答案，有一定铺垫
- 1-3分：需要读到一半才知道核心内容

请分析并给出评分和理由：

{content}

请以JSON格式返回：
{{"score": 分数(0-10), "detail": "评分理由", "suggestion": "改进建议（如果需要）"}}
"""
        return self._llm_eval_with_retry(
            '开篇直接性', prompt, default_score=5, max_retries=3
        )

    def _llm_check_modularity(self, content: str) -> Dict:
        """检查模块化完整 - LLM评估（带重试）"""
        prompt = f"""你是一位GEO内容优化专家。请评估以下内容的「模块化完整性」。

评分标准：
- 10分：每个段落都逻辑完整、可独立成文，AI引用任意一段都能被理解
- 7-9分：大部分段落独立完整，少量需要上下文
- 4-6分：部分段落需要上下文才能理解
- 1-3分：段落高度依赖上下文，无法独立理解

请分析并给出评分和理由：

{content}

请以JSON格式返回：
{{"score": 分数(0-10), "detail": "评分理由", "suggestion": "改进建议（如果需要）"}}
"""
        return self._llm_eval_with_retry(
            '模块化完整', prompt, default_score=5, max_retries=3
        )

    def _llm_check_trust_evidence(self, content: str) -> Dict:
        """检查信任证据 - LLM评估（带重试）"""
        prompt = f"""你是一位GEO内容优化专家。请评估以下内容的「信任证据」。

评分标准：
- 10分：为每个核心观点都提供了具体数据/案例/权威引用
- 7-9分：为大部分观点提供了信任证据
- 4-6分：有信任证据但数量不足或质量一般
- 1-3分：几乎没有信任证据，全是主观陈述

请分析并给出评分和理由：

{content}

请以JSON格式返回：
{{"score": 分数(0-10), "detail": "评分理由", "suggestion": "改进建议（如果需要）"}}
"""
        return self._llm_eval_with_retry(
            '信任证据', prompt, default_score=5, max_retries=3
        )

    def _llm_check_call_to_action(self, content: str) -> Dict:
        """检查行动号召 - LLM评估（带重试）"""
        prompt = f"""你是一位GEO内容优化专家。请评估以下内容的「行动号召(CTA)」。

评分标准：
- 10分：结尾有唯一、明确、低门槛的下一步行动指令
- 7-9分：结尾有CTA，但可以更明确或更单一
- 4-6分：有引导但不够明确，或门槛较高
- 1-3分：完全没有CTA，或指令不清晰

请分析并给出评分和理由：

{content}

请以JSON格式返回：
{{"score": 分数(0-10), "detail": "评分理由", "suggestion": "改进建议（如果需要）"}}
"""
        return self._llm_eval_with_retry(
            '行动号召', prompt, default_score=5, max_retries=3
        )

    def _llm_check_potential(self, content: str) -> Dict:
        """检查改造潜力 - LLM评估（带重试）"""
        prompt = f"""你是一位GEO内容优化专家。请评估以下内容的「多形式改造潜力」。

评分标准：
- 10分：核心逻辑清晰，可轻松提炼为结构图、短视频脚本、思维导图
- 7-9分：有改造潜力，但需要一定调整
- 4-6分：改造难度较大，主要是内容本身适合图文
- 1-3分：内容结构固化，难以改造为其他形式

请分析并给出评分和理由：

{content}

请以JSON格式返回：
{{"score": 分数(0-10), "detail": "评分理由", "suggestion": "改进建议（如果需要）"}}
"""
        return self._llm_eval_with_retry(
            '改造潜力', prompt, default_score=5, max_retries=3
        )

    def _llm_eval_with_retry(
        self, item_name: str, prompt: str, default_score: int = 5, max_retries: int = 3
    ) -> Dict:
        """LLM 评估统一重试封装

        最多重试 max_retries 次。每次解析失败后继续重试，
        全部失败才返回 default_score（5分，及格线以下）。
        """
        for attempt in range(max_retries):
            try:
                response = self.llm.chat([
                    {"role": "system", "content": "你是一位严格的内容质量评审专家。"},
                    {"role": "user", "content": prompt}
                ])
                result = self._parse_llm_response(response, default_score=default_score)
                # 如果解析成功（非默认分），直接返回
                if result.get('detail') != 'LLM响应解析失败，使用默认分':
                    logger.info("[LLM评估] %s成功（尝试%d），得分=%s",
                                item_name, attempt + 1, result.get('score'))
                    return result
                # 解析失败，记录日志后重试
                logger.warning("[LLM评估] %s解析失败（尝试%d），重试中...", item_name, attempt + 1)
            except Exception as e:
                logger.warning("[LLM评估] %s异常（尝试%d）: %s，重试中...", item_name, attempt + 1, str(e))

        # 全部重试失败
        logger.error("[LLM评估] %s全部重试失败，使用默认分 %d", item_name, default_score)
        return {
            'score': default_score,
            'detail': f'{item_name}评估全部重试失败，使用默认分',
            'suggestion': ''
        }

    def _parse_llm_response(self, response: str, default_score: int = 5) -> Dict:
        """
        解析 LLM 响应，支持多层降级解析。

        降级策略：
        1. 提取 JSON 对象（兼容多层嵌套）
        2. 提取 JSON 数组元素
        3. 从文本中提取 score 字段
        4. 从文本中提取纯数字分数
        """
        if not response:
            logger.debug("[LLM解析] 响应为空，使用默认分 %d", default_score)
            return {
                'score': default_score,
                'detail': 'LLM响应为空，使用默认分',
                'suggestion': ''
            }
        try:
            # ── 降级层 1：完整 JSON 对象解析 ──
            import json as _json

            # 去除 markdown 代码块
            clean = response.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            elif clean.startswith('```'):
                clean = clean[3:]
            if clean.endswith('```'):
                clean = clean[:-3]
            clean = clean.strip()

            # 尝试直接解析
            try:
                data = _json.loads(clean)
                if isinstance(data, dict):
                    score = int(data.get('score', default_score))
                    return {
                        'score': max(0, min(10, score)),
                        'detail': data.get('detail', 'LLM评估结果'),
                        'suggestion': data.get('suggestion', '')
                    }
                elif isinstance(data, list) and len(data) > 0:
                    # 取第一个元素
                    item = data[0] if isinstance(data[0], dict) else {}
                    score = int(item.get('score', default_score))
                    return {
                        'score': max(0, min(10, score)),
                        'detail': item.get('detail', 'LLM评估结果'),
                        'suggestion': item.get('suggestion', '')
                    }
            except _json.JSONDecodeError:
                pass

            # ── 降级层 2：查找 JSON 对象边界 ──
            start = clean.find('{')
            if start != -1:
                for end in range(len(clean), start, -1):
                    candidate = clean[start:end].replace('{{', '{').replace('}}', '}')
                    try:
                        data = _json.loads(candidate)
                        if isinstance(data, dict) and 'score' in data:
                            score = int(data.get('score', default_score))
                            return {
                                'score': max(0, min(10, score)),
                                'detail': data.get('detail', 'LLM评估结果'),
                                'suggestion': data.get('suggestion', '')
                            }
                    except _json.JSONDecodeError:
                        continue

            # ── 降级层 3：从文本提取 "score": N ──
            score_match = re.search(r'["\s]score["\s]*[:=]\s*(\d+)', response)
            if score_match:
                score = int(score_match.group(1))
                return {
                    'score': max(0, min(10, score)),
                    'detail': '从文本提取分数',
                    'suggestion': ''
                }

            # ── 降级层 4：提取纯数字分数（中文响应兼容）──
            num_match = re.search(r'(?:得分?|评分?|分数)[：:\s]*(\d+)', response)
            if num_match:
                score = int(num_match.group(1))
                return {
                    'score': max(0, min(10, score)),
                    'detail': '从文本提取数字分数',
                    'suggestion': ''
                }

        except Exception as e:
            logger.debug("[LLM解析] 解析异常: %s", str(e))

        return {
            'score': default_score,
            'detail': 'LLM响应解析失败，使用默认分',
            'suggestion': ''
        }

    # ==================== 辅助方法 ====================

    def _calculate_grade(self, score: int) -> tuple:
        """计算等级"""
        if score >= 90:
            return 'A', '卓越'
        elif score >= 80:
            return 'B', '良好'
        elif score >= 70:
            return 'C', '及格'
        else:
            return 'D', '待优化'

    def _generate_suggestions(self, failed_items: List[ScoreItem]) -> List[str]:
        """生成改进建议"""
        suggestions = []
        for item in failed_items:
            if item.suggestion:
                suggestions.append(f"【{item.name}】{item.suggestion}")
        return suggestions

    def _generate_summary(self, score: int, items: List[ScoreItem]) -> str:
        """生成整体评价"""
        passed_count = sum(1 for item in items if item.passed)
        total_count = len(items)

        if score >= 90:
            return f"内容质量卓越，{passed_count}/{total_count}项全优，GEO收录潜力极高。"
        elif score >= 80:
            return f"内容质量良好，{passed_count}/{total_count}项达标，GEO收录潜力较高。"
        elif score >= 70:
            return f"内容基本合格，{passed_count}/{total_count}项达标，建议针对性优化。"
        else:
            return f"内容有待优化，{passed_count}/{total_count}项达标，建议重点改进不达标项。"

    def to_dict(self, result: ScoreResult) -> Dict:
        """将评分结果转换为字典"""
        return {
            'total_score': result.total_score,
            'grade': result.grade,
            'grade_label': result.grade_label,
            'passed': result.passed,
            'items': [
                {
                    'id': item.id,
                    'category': item.category,
                    'name': item.name,
                    'score': item.score,
                    'max_score': item.max_score,
                    'passed': item.passed,
                    'detail': item.detail,
                    'suggestion': item.suggestion,
                    'icon': item.icon
                }
                for item in result.items
            ],
            'failed_items': [
                {
                    'id': item.id,
                    'name': item.name,
                    'score': item.score,
                    'detail': item.detail,
                    'suggestion': item.suggestion
                }
                for item in result.failed_items
            ],
            'summary': result.summary,
            'suggestions': result.suggestions
        }


# 全局实例
content_scorer = ContentQualityScorer()
