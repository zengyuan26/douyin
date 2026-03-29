"""
公开内容生成平台 - 配额管理服务

功能：
1. 检查用户生成配额
2. 更新配额使用情况
3. 计费计算
"""

from datetime import datetime, date
from typing import Tuple, Optional
from flask import current_app
from models.public_models import PublicUser, PublicGeneration, PublicLLMCallLog
from services.public_cache import public_cache


class QuotaManager:
    """配额管理器"""

    # 方案配置
    PLAN_CONFIG = {
        'free': {
            'daily_limit': 2,       # 每日2次
            'monthly_limit': None,
            'overage_price': 0,      # 免费用户不支持超量
            'ai_enhancement': False,  # 不支持AI增强内容
            'ai_target_enhancement': False,  # 不支持AI增强目标用户画像
            'save_portraits': False,  # 不支持保存画像
            'max_saved_portraits': 0,
            'weekly_portrait_changes': 0,
        },
        'basic': {
            'daily_limit': None,
            'monthly_limit': 100,   # 每月100次
            'overage_price': 3,      # 超量3元/次
            'ai_enhancement': True,
            'ai_target_enhancement': True,   # 支持AI目标用户画像
            'structure_options': 10,  # 10种内容结构
            'title_options': 5,       # 5个标题方案
            'save_portraits': True,   # 支持保存画像
            'max_saved_portraits': 5,  # 最多保存5个
            'weekly_portrait_changes': 2,  # 每周可更换2次
        },
        'professional': {
            'daily_limit': None,
            'monthly_limit': 300,   # 每月300次
            'overage_price': 2,      # 超量2元/次
            'ai_enhancement': True,
            'ai_target_enhancement': True,
            'structure_options': 15,
            'title_options': 10,
            'mixed_topics': True,    # 支持混合选题
            'precise_tags': True,    # 精准埋词方案
            'image_ratios': ['9:16', '4:3', '1:1'],  # 可选图片比例
            'save_portraits': True,
            'max_saved_portraits': 20,  # 最多保存20个
            'weekly_portrait_changes': 5,
        },
        'enterprise': {
            'daily_limit': None,
            'monthly_limit': None,  # 不限次数
            'overage_price': 0,
            'ai_enhancement': True,
            'ai_target_enhancement': True,
            'structure_options': 20,
            'title_options': 15,
            'mixed_topics': True,
            'precise_tags': True,
            'image_ratios': ['9:16', '4:3', '1:1', '16:9'],
            'save_portraits': True,
            'max_saved_portraits': 100,  # 最多保存100个
            'weekly_portrait_changes': 0,  # 不限更换
            'api_access': True,
            'priority_support': True,
        },
    }

    @classmethod
    def get_plan_config(cls, plan: str) -> dict:
        """获取方案配置"""
        return cls.PLAN_CONFIG.get(plan, cls.PLAN_CONFIG['free'])

    @classmethod
    def check_quota(cls, user: PublicUser) -> Tuple[bool, str, dict]:
        """
        检查用户是否可以生成内容

        Returns:
            (can_generate, reason, quota_info)
        """
        plan_config = cls.get_plan_config(user.premium_plan)

        # 免费用户：检查每日次数
        if plan_config['daily_limit']:
            today = date.today()

            # 重置每日次数
            if user.daily_free_reset_at != today:
                return True, 'daily_reset', {'remaining': plan_config['daily_limit']}

            if user.daily_free_count >= plan_config['daily_limit']:
                return False, 'daily_limit_exceeded', {
                    'limit': plan_config['daily_limit'],
                    'used': user.daily_free_count,
                    'reset_at': str(today + 1)
                }

            return True, 'ok', {
                'remaining': plan_config['daily_limit'] - user.daily_free_count
            }

        # 付费用户：检查月次数
        if plan_config['monthly_limit']:
            today = date.today()
            month_start = today.replace(day=1)

            # 重置月次数
            if user.monthly_reset_at != month_start:
                return True, 'monthly_reset', {'remaining': plan_config['monthly_limit']}

            if user.monthly_generation_count >= plan_config['monthly_limit']:
                return False, 'monthly_limit_exceeded', {
                    'limit': plan_config['monthly_limit'],
                    'used': user.monthly_generation_count,
                    'overage_price': plan_config['overage_price']
                }

            return True, 'ok', {
                'remaining': plan_config['monthly_limit'] - user.monthly_generation_count
            }

        # 企业版：无限制
        return True, 'ok', {'remaining': -1}

    @classmethod
    def use_quota(cls, user: PublicUser, tokens_used: int = 0) -> bool:
        """
        使用配额（生成成功后调用）

        Args:
            user: 用户
            tokens_used: 本次消耗的Token数

        Returns:
            是否成功
        """
        plan_config = cls.get_plan_config(user.premium_plan)
        today = date.today()

        # 免费用户
        if plan_config['daily_limit']:
            if user.daily_free_reset_at != today:
                user.daily_free_count = 1
                user.daily_free_reset_at = today
            else:
                user.daily_free_count += 1

        # 付费用户
        elif plan_config['monthly_limit']:
            month_start = today.replace(day=1)

            if user.monthly_reset_at != month_start:
                user.monthly_generation_count = 1
                user.monthly_token_count = tokens_used
                user.monthly_reset_at = month_start
            else:
                user.monthly_generation_count += 1
                user.monthly_token_count += tokens_used

        # 清除缓存
        public_cache.invalidate_user_quota(user.id)

        return True

    @classmethod
    def calculate_cost(cls, user: PublicUser, tokens_used: int) -> Tuple[float, str]:
        """
        计算本次生成的成本

        Returns:
            (cost, description)
        """
        plan_config = cls.get_plan_config(user.premium_plan)

        # 免费用户
        if plan_config['daily_limit']:
            return 0, '免费用户'

        # 企业版
        if user.premium_plan == 'enterprise':
            return 0, '企业版会员'

        # 基础版/专业版
        if plan_config['monthly_limit']:
            if user.monthly_generation_count > plan_config['monthly_limit']:
                cost = plan_config['overage_price']
                return cost, f'超量计费 {cost}元'
            else:
                return 0, '套餐内'

        return 0, '免费'

    @classmethod
    def get_user_quota_info(cls, user: PublicUser) -> dict:
        """获取用户配额信息"""
        plan_config = cls.get_plan_config(user.premium_plan)
        can_generate, reason, quota_info = cls.check_quota(user)

        return {
            'plan': user.premium_plan,
            'plan_name': {
                'free': '免费体验',
                'basic': '基础版',
                'professional': '专业版',
                'enterprise': '企业版'
            }.get(user.premium_plan, '未知'),

            'is_premium': user.is_premium,
            'premium_expires': user.premium_expires.isoformat() if user.premium_expires else None,

            'can_generate': can_generate,
            'reason': reason,

            'daily_limit': plan_config['daily_limit'],
            'monthly_limit': plan_config['monthly_limit'],
            'overage_price': plan_config.get('overage_price'),

            'quota': quota_info,

            'used_today': user.daily_free_count if plan_config['daily_limit'] else None,
            'used_month': user.monthly_generation_count if plan_config['monthly_limit'] else None,
        }

    @classmethod
    def get_feature_access(cls, user: PublicUser) -> dict:
        """获取用户功能权限"""
        plan_config = cls.get_plan_config(user.premium_plan)

        return {
            'ai_enhancement': plan_config.get('ai_enhancement', False),
            'structure_options': plan_config.get('structure_options', 2),
            'title_options': plan_config.get('title_options', 2),
            'mixed_topics': plan_config.get('mixed_topics', False),
            'precise_tags': plan_config.get('precise_tags', False),
            'image_ratios': plan_config.get('image_ratios', ['9:16']),
            'api_access': plan_config.get('api_access', False),
            'priority_support': plan_config.get('priority_support', False),
            # 画像保存功能
            'save_portraits': plan_config.get('save_portraits', False),
            'max_saved_portraits': plan_config.get('max_saved_portraits', 0),
            'weekly_portrait_changes': plan_config.get('weekly_portrait_changes', 0),
        }


# 全局实例
quota_manager = QuotaManager()
