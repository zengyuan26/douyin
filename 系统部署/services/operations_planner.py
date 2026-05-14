"""
运营规划生成服务

作为画像与内容生成之间的桥梁，将 Skill 的方法论（H-V-F、GEO、五段式）
贯穿到内容生成流程中。

参考 Skill: .cursor/skills/operations-expert/
使用 SkillManager 加载 Prompt 模板

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
from services.skill_manager import get_skill_manager

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

    # 新增：账号设计（昵称方案、头像建议、简介、标签）
    account_design: Dict[str, Any] = None

    # 新增：IP人设打造（外在形象、内在特质、口头禅、信任路径）
    ip_build: Dict[str, Any] = None

    # 新增：变现路径（产品、定价、转化漏斗、话术）
    monetization: Dict[str, Any] = None

    # 新增：KPI目标（各阶段粉丝/咨询量/成交）
    kpi_targets: Dict[str, Any] = None

    # 新增：风险提示（季节性/竞争/政策）
    risk_alerts: Dict[str, str] = None

    # 新增：行动计划（优先级任务列表）
    action_items: List[Dict] = None

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

    使用 SkillManager 加载 Prompt 模板，实现 Skill 驱动的 Prompt 管理
    """

    def __init__(self):
        self.llm = get_llm_service()
        self._skill_manager = get_skill_manager()

    def _load_prompt(self, prompt_type: str) -> Optional[str]:
        """从 Skill 模板加载 Prompt"""
        return self._skill_manager.get_prompt_template('operations-expert')
    
    def generate_plan(
        self,
        portraits: List[Dict[str, Any]],
        business_info: Dict[str, Any],
        content_stage: str = '成长阶段',
        target_topic_count: int = 30,
        client_profile: Dict[str, Any] = None,
    ) -> OperationsPlan:
        """
        生成运营规划方案

        Args:
            portraits: 画像列表
            business_info: 业务信息
            content_stage: 账号内容阶段（起号阶段/成长阶段/成熟阶段）
            target_topic_count: 目标选题数量
            client_profile: 客户自定义信息（账号/IP/变现等信息）

        Returns:
            OperationsPlan: 运营规划方案
        """
        # 确保 client_profile 不为 None
        if client_profile is None:
            client_profile = {}

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
                client_profile=client_profile,
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

            # 9. 生成账号设计（昵称方案、头像建议等）
            account_design = self._generate_account_design(
                business_info=business_info,
                client_profile=client_profile,
            )

            # 10. 生成IP人设打造
            ip_build = self._generate_ip_build(
                client_profile=client_profile,
                business_info=business_info,
            )

            # 11. 生成变现路径
            monetization = self._generate_monetization(
                client_profile=client_profile,
                business_info=business_info,
            )

            # 12. 生成KPI目标
            kpi_targets = self._generate_kpi_targets(
                stage=stage_enum,
            )

            # 13. 生成风险提示
            risk_alerts = self._generate_risk_alerts(
                business_info=business_info,
            )

            # 14. 生成行动计划
            action_items = self._generate_action_items(
                client_profile=client_profile,
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
                account_design=account_design,
                ip_build=ip_build,
                monetization=monetization,
                kpi_targets=kpi_targets,
                risk_alerts=risk_alerts,
                action_items=action_items,
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
        client_profile: Dict[str, Any] = None,
    ) -> Dict[str, str]:
        """生成账号定位"""
        if client_profile is None:
            client_profile = {}

        # 从画像中提取核心痛点
        pain_points = []
        identities = []
        for p in portraits[:5]:
            if isinstance(p, dict):
                pain_points.extend(p.get('pain_points', [])[:2])
                identities.append(p.get('identity', ''))

        # 用户录入的信息（支持 brand_name 和 account_name 两种字段）
        user_defined_name = client_profile.get('account_name', '') or client_profile.get('brand_name', '')
        user_defined_bio = client_profile.get('account_bio', '') or client_profile.get('brand_type', '')
        user_defined_years = client_profile.get('operating_years', '')
        user_defined_advantages = client_profile.get('core_advantages', '')
        user_defined_credentials = client_profile.get('credentials', '')
        user_defined_cases = client_profile.get('case_data', '')
        user_defined_contact = client_profile.get('contact_info', '')
        user_defined_target = client_profile.get('target_audience', '')

        # 调用LLM生成账号定位
        prompt = f"""基于以下信息，生成账号定位策略：

【业务信息】
- 业务名称：{business_info.get('business_name', '')}
- 业务描述：{business_info.get('business_description', '')}
- 行业：{business_info.get('industry', '')}
- 目标客户：{user_defined_target or business_info.get('target_customer', '')}

【用户已录入的信息】
- 品牌/账号名称：{user_defined_name or '未填写'}
- 品牌类型：{user_defined_bio or '未填写'}
- 经营年限：{user_defined_years or '未填写'}
- 核心优势：{user_defined_advantages or '未填写'}
- 资质证书：{user_defined_credentials or '未填写'}
- 成功案例：{user_defined_cases or '未填写'}
- 联系方式：{user_defined_contact or '未填写'}

【目标人群画像】
{', '.join(set([i for i in identities if i]))}

【核心痛点】
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

        # 兜底：基于业务信息和用户录入信息生成
        account_name = user_defined_name or business_info.get('business_name', '')
        return {
            'positioning': f"{account_name}，专注{business_info.get('industry', '')}服务",
            'ip_persona': f"{account_name}创始人/负责人，{user_defined_advantages[:20] + '...' if user_defined_advantages else '专业可靠'}",
            'content_style': '专业可信、亲切接地气',
            'differentiation': (user_defined_advantages[:30] if user_defined_advantages else '专业经验') + ' + 本地服务',
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

    def _generate_account_design(
        self,
        business_info: Dict[str, Any],
        client_profile: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """生成账号设计（昵称方案、头像建议、简介、标签）"""
        if client_profile is None:
            client_profile = {}

        # 支持 brand_name 和 account_name
        user_account_name = client_profile.get('account_name', '') or client_profile.get('brand_name', '')
        user_brand_type = client_profile.get('brand_type', '')
        user_advantages = client_profile.get('core_advantages', '')
        user_credentials = client_profile.get('credentials', '')
        business_name = business_info.get('business_name', '')
        industry = business_info.get('industry', '')

        # 如果用户已录入名称，使用用户提供的信息
        if user_account_name:
            # 基于用户提供的信息生成简介
            bio_parts = []
            if user_brand_type:
                bio_parts.append(f"{user_brand_type}")
            if user_advantages:
                bio_parts.append(user_advantages[:20])
            if user_credentials:
                bio_parts.append(user_credentials[:15])

            return {
                'nickname_options': [
                    user_account_name,
                    f"{user_account_name.split()[0]}老师" if len(user_account_name.split()) > 1 else user_account_name,
                    user_account_name.replace('老师', '咨询'),
                ],
                'avatar_suggestion': '个人形象照（专业、亲切）',
                'bio_final': ' | '.join(bio_parts) if bio_parts else f"{industry}专家",
                'content_tags': [f"#{industry}", f"#{user_account_name}"],
            }

        # 否则调用 LLM 生成
        prompt = f"""为以下业务设计抖音账号方案：

业务名称：{business_name}
行业：{industry}

请生成JSON格式：
{{
    "nickname_options": ["方案1", "方案2", "方案3"],
    "avatar_suggestion": "头像建议",
    "bio_final": "最终简介",
    "content_tags": ["#标签1", "#标签2", "#标签3"]
}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.5, max_tokens=800)
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[OperationsPlanner] 账号设计生成失败: {e}")

        # 兜底
        return {
            'nickname_options': [business_name, f"{business_name}老师", f"{business_name}咨询"],
            'avatar_suggestion': '个人形象照（专业、亲切）',
            'bio_final': f"{industry}专家，为您提供专业服务",
            'content_tags': [f"#{industry}", '#服务'],
        }

    def _generate_ip_build(
        self,
        client_profile: Dict[str, Any] = None,
        business_info: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """生成IP人设打造"""
        if client_profile is None:
            client_profile = {}
        if business_info is None:
            business_info = {}

        # 支持 brand_name 和 account_name
        brand_name = client_profile.get('brand_name', '') or client_profile.get('account_name', '')
        operating_years = client_profile.get('operating_years', '')
        core_advantages = client_profile.get('core_advantages', '')
        credentials = client_profile.get('credentials', '')
        case_data = client_profile.get('case_data', '')
        contact_info = client_profile.get('contact_info', '')
        industry = business_info.get('industry', '')

        # 拼接年龄信息（如果有经营年限）
        ip_age = ''
        if operating_years:
            try:
                years = int(operating_years)
                if years >= 1:
                    ip_age = f"{20 + years}-{30 + years}岁"
            except:
                pass

        # 调用 LLM 生成
        prompt = f"""基于以下信息，生成IP人设设定：

品牌名称：{brand_name or '待填写'}
核心优势：{core_advantages or '待填写'}
经营年限：{operating_years or '待填写'}
资质证书：{credentials or '待填写'}
成功案例：{case_data or '待填写'}
联系方式：{contact_info or '待填写'}
行业：{industry}

请生成JSON格式：
{{
    "outer_appearance": "外在形象描述（年龄、穿着、语气）",
    "inner_traits": ["特质1", "特质2", "特质3"],
    "catchphrases": ["口头禅1", "口头禅2"],
    "trust_path": ["Step 1: ...", "Step 2: ...", "Step 3: ...", "Step 4: ..."]
}}"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.chat(messages, temperature=0.5, max_tokens=1000)
            if response:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[OperationsPlanner] IP人设生成失败: {e}")

        # 兜底
        return {
            'outer_appearance': f'年龄：{ip_age or "30-40岁"}，形象：专业但不刻板，亲切但不随意',
            'inner_traits': [
                f'专业：{core_advantages[:50] if core_advantages else "深耕行业"}{operating_years + "年" if operating_years else ""}',
                '真诚：不夸大、不忽悠、实话实说',
                '负责：把每个客户当自己家人对待',
            ],
            'catchphrases': ['专业服务，值得信赖'],
            'trust_path': ['Step 1: 展示专业 - 免费知识输出，展示专业能力', 'Step 2: 建立信任 - 真实案例分享，口碑传播', 'Step 3: 获取咨询 - 提供价值后，自然转化', 'Step 4: 服务成交 - 专业服务 + 口碑推荐'],
        }

    def _generate_monetization(
        self,
        client_profile: Dict[str, Any] = None,
        business_info: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """生成变现路径"""
        if client_profile is None:
            client_profile = {}

        user_products = client_profile.get('monetization_products', [])
        industry = business_info.get('industry', '') if business_info else ''

        # 如果用户已录入变现产品，直接使用
        if user_products:
            products = []
            for p in user_products:
                products.append({
                    'name': p.get('name', ''),
                    'price': p.get('price', ''),
                    'description': f"{p.get('name', '')}服务详情",
                })
            return {
                'products': products,
                'conversion_funnel': '免费内容吸引 → 私信咨询 → 免费解答 → 推荐服务 → 成交转化',
                'sample_scripts': {
                    '评论区': f"感谢关注！想了解更多可以私信我~ {industry}相关问题都可以问！",
                    '私域': "您好，感谢您的信任！方便的话可以简单描述一下您的情况，我帮您分析一下~",
                },
            }

        # 兜底：基于行业生成
        return {
            'products': [
                {'name': '基础咨询', 'price': '待定', 'description': '单次咨询'},
                {'name': '深度服务', 'price': '待定', 'description': '全程服务'},
            ],
            'conversion_funnel': '免费内容吸引 → 私信咨询 → 免费解答 → 推荐服务 → 成交转化',
            'sample_scripts': {
                '评论区': f"感谢关注！{industry}相关问题都可以私信问我~",
                '私域': "您好，感谢您的信任！请问有什么可以帮到您的？",
            },
        }

    def _generate_kpi_targets(
        self,
        stage: ContentStage = None,
    ) -> Dict[str, Any]:
        """生成KPI目标"""
        return {
            'startup': {
                'fans': 500,
                'consults': 10,
                'deals': 1,
                'description': '启动期（1个月）：建立账号基础，获取初始粉丝',
            },
            'growth': {
                'fans': 5000,
                'consults': 30,
                'deals': 5,
                'description': '测试期（2-3个月）：优化内容方向，建立信任',
            },
            'scale': {
                'fans': 10000,
                'consults': 100,
                'deals': 15,
                'description': '放大期（4-6个月）：冲刺旺季，实现变现',
            },
            'stable': {
                'fans': 30000,
                'consults': 200,
                'deals': 30,
                'description': '稳定期（6个月后）：持续运营，稳定变现',
            },
        }

    def _generate_risk_alerts(
        self,
        business_info: Dict[str, Any] = None,
    ) -> Dict[str, str]:
        """生成风险提示"""
        industry = business_info.get('industry', '') if business_info else ''

        return {
            'seasonal': f'{industry}业务存在季节性特征，需要在旺季前积累足够粉丝和信任',
            'competition': '行业竞争激烈，需要用差异化定位+个人IP建立竞争壁垒',
            'policy': f'需要持续关注相关政策变化，第一时间解读，增加用户信任',
        }

    def _generate_action_items(
        self,
        client_profile: Dict[str, Any] = None,
    ) -> List[Dict]:
        """生成行动计划"""
        if client_profile is None:
            client_profile = {}

        brand_name = client_profile.get('brand_name', '')

        return [
            {
                'priority': 'P0',
                'task': '完善客户详细资料（服务内容、定价、成功案例）',
                'owner': brand_name or '负责人',
                'deadline': '立即',
            },
            {
                'priority': 'P0',
                'task': '账号基础搭建（头像、简介、背景图）',
                'owner': brand_name or '负责人',
                'deadline': '3天内',
            },
            {
                'priority': 'P1',
                'task': '拍摄10条科普视频储备',
                'owner': brand_name or '负责人',
                'deadline': '1周内',
            },
            {
                'priority': 'P1',
                'task': '确定前20条选题内容',
                'owner': brand_name or '负责人',
                'deadline': '1周内',
            },
            {
                'priority': 'P2',
                'task': '开始发布第一条视频',
                'owner': brand_name or '负责人',
                'deadline': '3天内',
            },
        ]

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
            # 新增字段
            'account_design': plan.account_design,
            'ip_build': plan.ip_build,
            'monetization': plan.monetization,
            'kpi_targets': plan.kpi_targets,
            'risk_alerts': plan.risk_alerts,
            'action_items': plan.action_items,
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
    client_profile: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    便捷函数：生成运营规划方案

    Args:
        portraits: 画像列表
        business_info: 业务信息
        content_stage: 账号内容阶段
        target_topic_count: 目标选题数量
        client_profile: 客户自定义信息（账号/IP/变现等）

    Returns:
        运营规划字典
    """
    planner = OperationsPlanner()
    plan = planner.generate_plan(
        portraits=portraits,
        business_info=business_info,
        content_stage=content_stage,
        target_topic_count=target_topic_count,
        client_profile=client_profile,
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
