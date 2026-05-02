"""
运营规划生成服务

作为画像与内容生成之间的桥梁，将 Skill 的方法论（H-V-F、GEO、五段式）
贯穿到内容生成流程中。

功能：
1. 基于画像生成运营规划方案
2. 确定账号阶段和五段式配比
3. 匹配 GEO 模式与内容类型的对应关系
4. 为后续内容生成提供完整上下文

使用方式：
from services.operations_planner import OperationsPlanner, OperationsPlanContext

planner = OperationsPlanner()
plan = planner.generate_plan(
    portraits=portraits,
    business_info=business_info,
    content_stage='成长阶段'
)
"""

import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from services.llm import get_llm_service

logger = logging.getLogger(__name__)


class ContentStage(Enum):
    """账号内容阶段"""
    STARTUP = '起号阶段'      # 冷启动期
    GROWTH = '成长阶段'       # 成长期
    MATURE = '成熟阶段'       # 成熟期


class FiveStage(Enum):
    """五段式内容阶段"""
    AUDIENCE = 'audience'           # 受众锁定
    PAIN = 'pain'                   # 痛点放大
    COMPARE = 'compare'              # 方案对比
    VISION = 'vision'               # 愿景勾画
    HESITATION = 'hesitation'       # 顾虑消除


class GEOMode(Enum):
    """GEO内容模式"""
    PROBLEM_DIAGNOSIS = '问题诊断型'       # 对比类
    COMPARISON = '对比答案型'               # 答案类
    SCENE_STORY = '场景故事型'             # 场景类
    CONCERN = '顾虑消除型'                 # 顾虑类
    PROMOTION = '促销引导型'               # 促销类
    KNOWLEDGE = '知识科普型'               # 科普类
    TUTORIAL = '技巧教程型'                # 技巧类
    EMOTIONAL = '情感共鸣型'               # 故事类


# =============================================================================
# 五段式阶段配置
# =============================================================================

# 各账号阶段的内容配比
STAGE_RATIOS = {
    ContentStage.STARTUP: {
        FiveStage.AUDIENCE: 0.20,      # 20% 受众锁定 - 拉新
        FiveStage.PAIN: 0.40,          # 40% 痛点放大 - 建立痛点认知
        FiveStage.COMPARE: 0.25,        # 25% 方案对比 - 建立信任
        FiveStage.VISION: 0.10,        # 10% 愿景勾画 - 激发期待
        FiveStage.HESITATION: 0.05,     # 5% 顾虑消除 - 初步转化
    },
    ContentStage.GROWTH: {
        FiveStage.AUDIENCE: 0.15,      # 15% 受众锁定
        FiveStage.PAIN: 0.25,          # 25% 痛点放大
        FiveStage.COMPARE: 0.30,        # 30% 方案对比 - 平衡发展
        FiveStage.VISION: 0.15,        # 15% 愿景勾画
        FiveStage.HESITATION: 0.15,     # 15% 顾虑消除 - 开始转化
    },
    ContentStage.MATURE: {
        FiveStage.AUDIENCE: 0.10,      # 10% 受众锁定
        FiveStage.PAIN: 0.15,          # 15% 痛点放大
        FiveStage.COMPARE: 0.30,        # 30% 方案对比
        FiveStage.VISION: 0.20,        # 20% 愿景勾画
        FiveStage.HESITATION: 0.25,     # 25% 顾虑消除 - 重在转化
    },
}

# 五段式阶段含义和内容类型
STAGE_DEFINITIONS = {
    FiveStage.AUDIENCE: {
        'name': '受众锁定',
        'description': '让用户判断"这说的是不是我"',
        'content_types': ['人群锁定', '场景细分', '地域精准'],
        'geo_modes': [GEOMode.SCENE_STORY, GEOMode.EMOTIONAL],
    },
    FiveStage.PAIN: {
        'name': '痛点放大',
        'description': '让人意识到"现在的做法有多糟糕"',
        'content_types': ['原因分析', '避坑指南', '认知颠覆', '知识教程'],
        'geo_modes': [GEOMode.PROBLEM_DIAGNOSIS, GEOMode.KNOWLEDGE, GEOMode.TUTORIAL],
    },
    FiveStage.COMPARE: {
        'name': '方案对比',
        'description': '突出"我的方案为什么更好"',
        'content_types': ['方案对比', '效果验证', '上游科普', '行业关联'],
        'geo_modes': [GEOMode.COMPARISON, GEOMode.KNOWLEDGE],
    },
    FiveStage.VISION: {
        'name': '愿景勾画',
        'description': '期待"用之后会变多好"',
        'content_types': ['实操技巧', '季节营销', '节日营销', '情感故事'],
        'geo_modes': [GEOMode.TUTORIAL, GEOMode.EMOTIONAL, GEOMode.SCENE_STORY],
    },
    FiveStage.HESITATION: {
        'name': '顾虑消除',
        'description': '打消"用了之后有问题怎么办"',
        'content_types': ['痛点放大', '决策安心', '行情价格', '工具耗材'],
        'geo_modes': [GEOMode.CONCERN, GEOMode.PROMOTION],
    },
}

# GEO模式说明
GEO_MODE_DEFINITIONS = {
    GEOMode.PROBLEM_DIAGNOSIS: {
        'name': '问题诊断型',
        'keywords': ['为什么', '原因', '怎么回事', '问题出在哪'],
        'structure': '问题描述 → 原因分析 → 解决方案',
        'suitable_for': ['痛点放大', '方案对比'],
    },
    GEOMode.COMPARISON: {
        'name': '对比答案型',
        'keywords': ['哪个好', '区别', '对比', '还是'],
        'structure': '选项A vs 选项B → 各自优缺点 → 推荐答案',
        'suitable_for': ['方案对比', '顾虑消除'],
    },
    GEOMode.SCENE_STORY: {
        'name': '场景故事型',
        'keywords': ['经历', '故事', '那天', '终于'],
        'structure': '场景引入 → 经历描述 → 转折点 → 结果',
        'suitable_for': ['受众锁定', '愿景勾画'],
    },
    GEOMode.CONCERN: {
        'name': '顾虑消除型',
        'keywords': ['放心', '靠谱', '保障', '万一'],
        'structure': '顾虑点 → 解决方案 → 保障措施 → 行动引导',
        'suitable_for': ['顾虑消除'],
    },
    GEOMode.PROMOTION: {
        'name': '促销引导型',
        'keywords': ['优惠', '活动', '限时', '特价'],
        'structure': '利益点 → 限时优惠 → 行动号召',
        'suitable_for': ['顾虑消除', '愿景勾画'],
    },
    GEOMode.KNOWLEDGE: {
        'name': '知识科普型',
        'keywords': ['原理', '为什么', '是什么', '科普'],
        'structure': '概念定义 → 原理说明 → 实际应用',
        'suitable_for': ['痛点放大', '方案对比'],
    },
    GEOMode.TUTORIAL: {
        'name': '技巧教程型',
        'keywords': ['怎么', '技巧', '方法', '步骤'],
        'structure': '目标 → 步骤1/2/3 → 注意事项 → 总结',
        'suitable_for': ['痛点放大', '愿景勾画'],
    },
    GEOMode.EMOTIONAL: {
        'name': '情感共鸣型',
        'keywords': ['终于', '没想到', '其实', '原来'],
        'structure': '情感共鸣点 → 故事/经历 → 情感升华',
        'suitable_for': ['受众锁定', '愿景勾画'],
    },
}


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class OperationsPlanContext:
    """运营规划生成上下文"""
    portraits: List[Dict[str, Any]]            # 画像列表
    business_info: Dict[str, Any]             # 业务信息
    content_stage: str = '成长阶段'           # 账号内容阶段
    target_topic_count: int = 30              # 目标选题数量


@dataclass
class StagePlan:
    """五段式阶段规划"""
    stage_key: str                             # stage key
    stage_name: str                           # 阶段名称
    ratio: float                              # 占比
    topic_count: int                          # 选题数量
    content_types: List[str]                   # 内容类型
    geo_modes: List[str]                       # 推荐GEO模式
    description: str                          # 阶段说明


@dataclass
class OperationsPlan:
    """运营规划方案"""
    # 基础信息
    plan_id: str
    business_name: str
    industry: str
    content_stage: str
    
    # 账号定位
    account_positioning: str                   # 账号定位
    ip_persona: str                           # IP人设
    content_style: str                         # 内容风格
    differentiation: str                       # 差异化方向
    
    # 五段式规划
    five_stage_plan: List[StagePlan]          # 五段式规划列表
    total_topic_count: int                    # 总选题数量
    
    # GEO模式匹配
    geo_mode_mapping: Dict[str, List[str]]     # 五段式 → GEO模式映射
    
    # 内容策略
    content_ratio: Dict[str, float]           # 内容类型配比
    content_sequence: List[str]                # 推荐内容发布顺序
    
    # 执行计划
    first_week_topics: List[Dict]              # 首周选题计划
    content_calendar: Dict[str, Any]           # 内容日历
    
    # 元信息
    created_at: str = ''
    version: str = '1.0'


# =============================================================================
# 运营规划生成器
# =============================================================================

class OperationsPlanner:
    """
    运营规划生成器
    
    基于画像生成完整的运营规划方案，包含：
    1. 五段式阶段规划（起号/成长/成熟阶段的配比）
    2. GEO模式匹配（五段式各阶段适合的GEO模式）
    3. 账号定位策略
    4. 内容发布计划
    """
    
    def __init__(self):
        self.llm = get_llm_service()
    
    def generate_plan(
        self,
        portraits: List[Dict[str, Any]],
        business_info: Dict[str, Any],
        content_stage: str = '成长阶段',
        target_topic_count: int = 30,
    ) -> OperationsPlan:
        """
        生成运营规划方案
        
        Args:
            portraits: 画像列表
            business_info: 业务信息
            content_stage: 账号内容阶段（起号阶段/成长阶段/成熟阶段）
            target_topic_count: 目标选题数量
        
        Returns:
            OperationsPlan: 运营规划方案
        """
        try:
            # 1. 确定账号阶段
            stage_enum = self._parse_content_stage(content_stage)
            
            # 2. 生成五段式规划
            five_stage_plan = self._generate_five_stage_plan(
                stage=stage_enum,
                target_count=target_topic_count,
            )
            
            # 3. 生成GEO模式匹配
            geo_mode_mapping = self._generate_geo_mode_mapping(five_stage_plan)
            
            # 4. 生成账号定位
            account_positioning = self._generate_account_positioning(
                portraits=portraits,
                business_info=business_info,
            )
            
            # 5. 生成内容策略
            content_ratio = self._generate_content_ratio(
                portraits=portraits,
                stage=stage_enum,
            )
            
            # 6. 生成内容发布计划
            content_sequence = self._generate_content_sequence(
                five_stage_plan=five_stage_plan,
                geo_mode_mapping=geo_mode_mapping,
            )
            
            # 7. 生成首周选题计划
            first_week_topics = self._generate_first_week_topics(
                five_stage_plan=five_stage_plan,
                geo_mode_mapping=geo_mode_mapping,
            )
            
            # 8. 生成内容日历
            content_calendar = self._generate_content_calendar(
                five_stage_plan=five_stage_plan,
                content_sequence=content_sequence,
            )
            
            # 组装运营规划
            plan = OperationsPlan(
                plan_id=f"plan_{business_info.get('business_name', 'unknown')}_{content_stage}",
                business_name=business_info.get('business_name', ''),
                industry=business_info.get('industry', ''),
                content_stage=content_stage,
                account_positioning=account_positioning.get('positioning', ''),
                ip_persona=account_positioning.get('ip_persona', ''),
                content_style=account_positioning.get('content_style', ''),
                differentiation=account_positioning.get('differentiation', ''),
                five_stage_plan=five_stage_plan,
                total_topic_count=target_topic_count,
                geo_mode_mapping=geo_mode_mapping,
                content_ratio=content_ratio,
                content_sequence=content_sequence,
                first_week_topics=first_week_topics,
                content_calendar=content_calendar,
                created_at='',
                version='1.0',
            )
            
            logger.info(f"[OperationsPlanner] 生成运营规划: {plan.plan_id}")
            return plan
            
        except Exception as e:
            logger.exception(f"[OperationsPlanner] 生成失败: {e}")
            raise
    
    def _parse_content_stage(self, content_stage: str) -> ContentStage:
        """解析账号内容阶段"""
        stage_map = {
            '起号阶段': ContentStage.STARTUP,
            '成长阶段': ContentStage.GROWTH,
            '成熟阶段': ContentStage.MATURE,
        }
        return stage_map.get(content_stage, ContentStage.GROWTH)
    
    def _generate_five_stage_plan(
        self,
        stage: ContentStage,
        target_count: int,
    ) -> List[StagePlan]:
        """生成五段式规划"""
        ratios = STAGE_RATIOS[stage]
        five_stage_plan = []
        
        for stage_key, ratio in ratios.items():
            topic_count = int(target_count * ratio)
            if topic_count < 1:
                topic_count = 1
            
            stage_def = STAGE_DEFINITIONS[stage_key]
            
            plan = StagePlan(
                stage_key=stage_key.value,
                stage_name=stage_def['name'],
                ratio=ratio,
                topic_count=topic_count,
                content_types=stage_def['content_types'],
                geo_modes=[geo.value for geo in stage_def['geo_modes']],
                description=stage_def['description'],
            )
            five_stage_plan.append(plan)
        
        return five_stage_plan
    
    def _generate_geo_mode_mapping(
        self,
        five_stage_plan: List[StagePlan],
    ) -> Dict[str, List[str]]:
        """生成五段式 → GEO模式映射"""
        mapping = {}
        for stage_plan in five_stage_plan:
            mapping[stage_plan.stage_key] = stage_plan.geo_modes
        return mapping
    
    def _generate_account_positioning(
        self,
        portraits: List[Dict[str, Any]],
        business_info: Dict[str, Any],
    ) -> Dict[str, str]:
        """生成账号定位"""
        # 从画像中提取核心痛点
        pain_points = []
        identities = []
        for p in portraits[:5]:
            if isinstance(p, dict):
                pain_points.extend(p.get('pain_points', [])[:2])
                identities.append(p.get('identity', ''))
        
        # 调用LLM生成账号定位
        prompt = f"""基于以下信息，生成账号定位策略：

业务信息：
- 业务名称：{business_info.get('business_name', '')}
- 业务描述：{business_info.get('business_description', '')}
- 行业：{business_info.get('industry', '')}

目标人群：
{', '.join(set([i for i in identities if i]))}

核心痛点：
{', '.join(set([p for p in pain_points if p]))}

请生成JSON格式的账号定位策略：
{{
    "positioning": "一句话账号定位（突出差异化）",
    "ip_persona": "IP人设描述（年龄、背景、性格、专长）",
    "content_style": "内容风格（专业/亲切/幽默等）",
    "differentiation": "差异化方向（vs竞品的独特优势）"
}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.5, max_tokens=1500)
            
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return {
                        'positioning': data.get('positioning', ''),
                        'ip_persona': data.get('ip_persona', ''),
                        'content_style': data.get('content_style', ''),
                        'differentiation': data.get('differentiation', ''),
                    }
        except Exception as e:
            logger.warning(f"[OperationsPlanner] LLM定位生成失败: {e}")
        
        # 兜底：基于业务信息生成
        return {
            'positioning': f"{business_info.get('industry', '')}专家，专注解决{business_info.get('business_description', '')}相关问题",
            'ip_persona': f"{business_info.get('business_name', '')}创始人，深耕行业多年",
            'content_style': '专业可信、亲切接地气',
            'differentiation': '专业经验 + 本地服务',
        }
    
    def _generate_content_ratio(
        self,
        portraits: List[Dict[str, Any]],
        stage: ContentStage,
    ) -> Dict[str, float]:
        """生成内容类型配比"""
        # 基于阶段的内容类型配比
        base_ratio = {
            '痛点类': 0.30,
            '解决方案类': 0.25,
            '知识科普类': 0.20,
            '案例分享类': 0.15,
            '互动话题类': 0.10,
        }
        
        # 根据阶段调整配比
        if stage == ContentStage.STARTUP:
            base_ratio['痛点类'] = 0.35
            base_ratio['知识科普类'] = 0.25
            base_ratio['案例分享类'] = 0.10
        elif stage == ContentStage.MATURE:
            base_ratio['痛点类'] = 0.20
            base_ratio['解决方案类'] = 0.30
            base_ratio['案例分享类'] = 0.20
        
        return base_ratio
    
    def _generate_content_sequence(
        self,
        five_stage_plan: List[StagePlan],
        geo_mode_mapping: Dict[str, List[str]],
    ) -> List[str]:
        """生成内容发布顺序"""
        sequence = []
        
        # 按阶段顺序生成发布建议
        for stage_plan in five_stage_plan:
            # 首周以痛点放大为主（起号关键）
            if stage_plan.stage_key == 'pain':
                sequence.append(f"第1-2周：{stage_plan.stage_name}（痛点引爆期）")
                sequence.append(f"  → 内容方向：{', '.join(stage_plan.content_types[:2])}")
                sequence.append(f"  → 推荐GEO：{', '.join(stage_plan.geo_modes[:2])}")
            elif stage_plan.stage_key == 'audience':
                sequence.append(f"第3周：{stage_plan.stage_name}（精准触达期）")
                sequence.append(f"  → 内容方向：{', '.join(stage_plan.content_types[:2])}")
            elif stage_plan.stage_key == 'compare':
                sequence.append(f"第4周：{stage_plan.stage_name}（建立信任期）")
                sequence.append(f"  → 内容方向：{', '.join(stage_plan.content_types[:2])}")
            elif stage_plan.stage_key == 'vision':
                sequence.append(f"第5-6周：{stage_plan.stage_name}（激发期待期）")
                sequence.append(f"  → 内容方向：{', '.join(stage_plan.content_types[:2])}")
            elif stage_plan.stage_key == 'hesitation':
                sequence.append(f"第7-8周：{stage_plan.stage_name}（促进转化期）")
                sequence.append(f"  → 内容方向：{', '.join(stage_plan.content_types[:2])}")
        
        return sequence
    
    def _generate_first_week_topics(
        self,
        five_stage_plan: List[StagePlan],
        geo_mode_mapping: Dict[str, List[str]],
    ) -> List[Dict]:
        """生成首周选题计划"""
        first_week = []
        
        # 首周聚焦痛点放大
        for stage_plan in five_stage_plan:
            if stage_plan.stage_key == 'pain':
                for i, content_type in enumerate(stage_plan.content_types[:3]):
                    geo_mode = stage_plan.geo_modes[i] if i < len(stage_plan.geo_modes) else stage_plan.geo_modes[0]
                    first_week.append({
                        'day': f'周{i + 1}',
                        'stage': stage_plan.stage_name,
                        'content_type': content_type,
                        'geo_mode': geo_mode,
                        'focus': '痛点引爆，拉新用户',
                    })
        
        return first_week[:5]  # 最多5条
    
    def _generate_content_calendar(
        self,
        five_stage_plan: List[StagePlan],
        content_sequence: List[str],
    ) -> Dict[str, Any]:
        """生成内容日历"""
        calendar = {
            'week_1': {
                'theme': '痛点引爆',
                'focus': '让用户意识到问题',
                'topics': ['痛点诊断类', '原因分析类'],
                'geo_modes': ['问题诊断型', '知识科普型'],
            },
            'week_2': {
                'theme': '痛点深化',
                'focus': '强化痛点认知',
                'topics': ['避坑指南类', '认知颠覆类'],
                'geo_modes': ['问题诊断型', '对比答案型'],
            },
            'week_3': {
                'theme': '信任建立',
                'focus': '展示专业能力',
                'topics': ['方案对比类', '效果验证类'],
                'geo_modes': ['对比答案型', '知识科普型'],
            },
            'week_4': {
                'theme': '价值传递',
                'focus': '激发用户期待',
                'topics': ['实操技巧类', '情感故事类'],
                'geo_modes': ['技巧教程型', '情感共鸣型'],
            },
        }
        return calendar
    
    def to_dict(self, plan: OperationsPlan) -> Dict[str, Any]:
        """将运营规划转换为字典"""
        return {
            'plan_id': plan.plan_id,
            'business_name': plan.business_name,
            'industry': plan.industry,
            'content_stage': plan.content_stage,
            'account_positioning': plan.account_positioning,
            'ip_persona': plan.ip_persona,
            'content_style': plan.content_style,
            'differentiation': plan.differentiation,
            'five_stage_plan': [
                {
                    'stage_key': s.stage_key,
                    'stage_name': s.stage_name,
                    'ratio': s.ratio,
                    'topic_count': s.topic_count,
                    'content_types': s.content_types,
                    'geo_modes': s.geo_modes,
                    'description': s.description,
                }
                for s in plan.five_stage_plan
            ],
            'total_topic_count': plan.total_topic_count,
            'geo_mode_mapping': plan.geo_mode_mapping,
            'content_ratio': plan.content_ratio,
            'content_sequence': plan.content_sequence,
            'first_week_topics': plan.first_week_topics,
            'content_calendar': plan.content_calendar,
            'created_at': plan.created_at,
            'version': plan.version,
        }
    
    def to_markdown(self, plan: OperationsPlan) -> str:
        """将运营规划转换为Markdown格式"""
        md = f"""# {plan.business_name} 运营规划方案

**版本：{plan.version}**
**账号阶段：{plan.content_stage}**
**生成时间：{plan.created_at or '自动生成'}**

---

## 一、账号定位

### 核心定位
{plan.account_positioning}

### IP人设
{plan.ip_persona}

### 内容风格
{plan.content_style}

### 差异化方向
{plan.differentiation}

---

## 二、五段式内容规划

| 阶段 | 名称 | 占比 | 选题数量 | 内容类型 | 推荐GEO模式 |
|------|------|------|----------|----------|------------|
"""
        
        for s in plan.five_stage_plan:
            md += f"| {s.stage_key} | {s.stage_name} | {int(s.ratio * 100)}% | {s.topic_count} | {', '.join(s.content_types[:2])} | {', '.join(s.geo_modes[:2])} |\n"
        
        md += f"""
**说明**：
"""
        
        for s in plan.five_stage_plan:
            md += f"- **{s.stage_name}**：{s.description}\n"
        
        md += f"""
---

## 三、GEO模式匹配

| 五段式阶段 | 推荐GEO模式 | 模式说明 |
|------------|------------|----------|
"""
        
        for stage_key, geo_modes in plan.geo_mode_mapping.items():
            stage_name = next((s.stage_name for s in plan.five_stage_plan if s.stage_key == stage_key), stage_key)
            for geo_mode in geo_modes:
                geo_def = GEO_MODE_DEFINITIONS.get(GEOMode(geo_mode), {})
                md += f"| {stage_name} | {geo_mode} | {geo_def.get('structure', '')} |\n"
        
        md += f"""
---

## 四、内容类型配比

"""
        
        for content_type, ratio in plan.content_ratio.items():
            md += f"- {content_type}：{int(ratio * 100)}%\n"
        
        md += f"""
---

## 五、内容发布顺序

"""
        
        for item in plan.content_sequence:
            md += f"{item}\n"
        
        md += f"""
---

## 六、首周选题计划

| 日期 | 阶段 | 内容类型 | GEO模式 | 重点 |
|------|------|----------|---------|------|
"""
        
        for topic in plan.first_week_topics:
            md += f"| {topic['day']} | {topic['stage']} | {topic['content_type']} | {topic['geo_mode']} | {topic['focus']} |\n"
        
        md += f"""
---

## 七、内容日历

"""
        
        for week, info in plan.content_calendar.items():
            md += f"### {week.upper()}：{info['theme']}\n"
            md += f"- 重点：{info['focus']}\n"
            md += f"- 选题：{', '.join(info['topics'])}\n"
            md += f"- GEO：{', '.join(info['geo_modes'])}\n\n"
        
        md += f"""
---

*本方案由运营规划生成器自动生成*
*方法论：五段式内容框架 + GEO模式匹配*
"""
        
        return md


# =============================================================================
# 便捷函数
# =============================================================================

def generate_operations_plan(
    portraits: List[Dict[str, Any]],
    business_info: Dict[str, Any],
    content_stage: str = '成长阶段',
    target_topic_count: int = 30,
) -> Dict[str, Any]:
    """
    便捷函数：生成运营规划方案
    
    Args:
        portraits: 画像列表
        business_info: 业务信息
        content_stage: 账号内容阶段
        target_topic_count: 目标选题数量
    
    Returns:
        运营规划字典
    """
    planner = OperationsPlanner()
    plan = planner.generate_plan(
        portraits=portraits,
        business_info=business_info,
        content_stage=content_stage,
        target_topic_count=target_topic_count,
    )
    return planner.to_dict(plan)


def get_stage_ratio(content_stage: str) -> Dict[str, float]:
    """获取指定阶段的内容配比"""
    stage_map = {
        '起号阶段': ContentStage.STARTUP,
        '成长阶段': ContentStage.GROWTH,
        '成熟阶段': ContentStage.MATURE,
    }
    stage = stage_map.get(content_stage, ContentStage.GROWTH)
    ratios = STAGE_RATIOS[stage]
    return {k.value: v for k, v in ratios.items()}


def get_geo_modes_for_stage(stage_key: str) -> List[str]:
    """获取指定五段式阶段推荐的GEO模式"""
    stage_enum = FiveStage(stage_key)
    stage_def = STAGE_DEFINITIONS.get(stage_enum, {})
    return [geo.value for geo in stage_def.get('geo_modes', [])]
