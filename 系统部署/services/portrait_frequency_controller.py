"""
画像频率控制服务

功能：
1. 画像保存权限控制
2. 画像更换频率限制
3. 配额管理
"""

import json
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from models.models import db


class PortraitFrequencyController:
    """画像频率控制器"""
    
    # 套餐配置
    PLAN_CONFIG = {
        'free': {
            'can_save': False,
            'max_saved': 0,
            'weekly_change_limit': None,      # 无限制
            'monthly_change_limit': None,
            'can_lock': False,
            'max_locked': 0,
            'enable_cache': False,
            'keyword_update_limit': 0,     # 关键词库每月更新次数
            'topic_update_limit': 0,       # 选题库每月更新次数
        },
        'basic': {
            'can_save': True,
            'max_saved': 3,
            'weekly_change_limit': None,      # 无限制
            'monthly_change_limit': 20,
            'can_lock': False,
            'max_locked': 0,
            'enable_cache': True,
            'cache_ttl': 24,
            'keyword_update_limit': 2,
            'topic_update_limit': 2,
        },
        'professional': {
            'can_save': True,
            'max_saved': 10,
            'weekly_change_limit': 3,
            'monthly_change_limit': 30,
            'can_lock': True,
            'max_locked': 1,
            'enable_cache': True,
            'cache_ttl': 168,
            'keyword_update_limit': 5,
            'topic_update_limit': 5,
        },
        'enterprise': {
            'can_save': True,
            'max_saved': None,               # 无限制
            'weekly_change_limit': None,
            'monthly_change_limit': None,
            'can_lock': True,
            'max_locked': 3,
            'enable_cache': True,
            'cache_ttl': 720,
            'keyword_update_limit': 20,
            'topic_update_limit': 20,
        }
    }
    
    @classmethod
    def get_plan_config(cls, plan_type: str) -> Dict:
        """获取套餐配置"""
        return cls.PLAN_CONFIG.get(plan_type, cls.PLAN_CONFIG['free'])
    
    @classmethod
    def get_user_quota(cls, user_id: int) -> Dict:
        """
        获取用户画像配额
        
        Returns:
            配额信息字典
        """
        # 查询配额记录
        result = db.session.execute(
            text("""
                SELECT plan_type, weekly_change_limit, weekly_changes_used, 
                       quota_week_start, monthly_change_limit, monthly_changes_used,
                       quota_month_start, total_changes, total_generations,
                       keyword_update_limit, keyword_updates_used, keyword_quota_start,
                       topic_update_limit, topic_updates_used, topic_quota_start
                FROM user_portrait_quota
                WHERE user_id = :user_id
            """),
            {'user_id': user_id}
        ).fetchone()
        
        if not result:
            # 创建新配额记录
            cls._init_user_quota(user_id, 'free')
            return cls.get_user_quota(user_id)
        
        plan_config = cls.get_plan_config(result[0])
        today = date.today()
        
        def parse_date(val):
            """解析日期，兼容 date 对象和字符串"""
            if val is None:
                return None
            if isinstance(val, str):
                return datetime.strptime(val[:10], '%Y-%m-%d').date()
            if isinstance(val, datetime):
                return val.date()
            return val

        # 检查周配额是否需要重置
        quota_week_start = parse_date(result[3])
        weekly_changes_used = result[1]
        if quota_week_start and (today - quota_week_start).days >= 7:
            weekly_changes_used = 0

        # 检查月配额是否需要重置
        quota_month_start = parse_date(result[6])
        monthly_changes_used = result[5]
        if quota_month_start and (today - quota_month_start).days >= 30:
            monthly_changes_used = 0

        # 库配额日期
        keyword_quota_start = parse_date(result[10])
        topic_quota_start = parse_date(result[13])

        return {
            'plan_type': result[0],
            'weekly_change_limit': result[1] or plan_config['weekly_change_limit'],
            'weekly_changes_used': weekly_changes_used,
            'quota_week_start': str(quota_week_start) if quota_week_start else None,
            'monthly_change_limit': result[4] or plan_config['monthly_change_limit'],
            'monthly_changes_used': monthly_changes_used,
            'quota_month_start': str(quota_month_start) if quota_month_start else None,
            'total_changes': result[7],
            'total_generations': result[8],
            'can_save': plan_config['can_save'],
            'max_saved': plan_config['max_saved'],
            'can_lock': plan_config['can_lock'],
            'max_locked': plan_config['max_locked'],
            'enable_cache': plan_config['enable_cache'],
            # 库更新配额
            'keyword_update_limit': result[9] or plan_config.get('keyword_update_limit', 0),
            'keyword_updates_used': result[10] or 0,
            'keyword_quota_start': str(keyword_quota_start) if keyword_quota_start else None,
            'topic_update_limit': result[12] or plan_config.get('topic_update_limit', 0),
            'topic_updates_used': result[13] or 0,
            'topic_quota_start': str(topic_quota_start) if topic_quota_start else None,
        }
    
    @classmethod
    def _init_user_quota(cls, user_id: int, plan_type: str = 'free'):
        """初始化用户配额记录"""
        today = date.today()
        plan_config = cls.get_plan_config(plan_type)
        
        # SQLite 用 INSERT OR IGNORE 代替 MySQL 的 ON DUPLICATE KEY UPDATE
        db.session.execute(
            text("""
                INSERT OR IGNORE INTO user_portrait_quota
                (user_id, plan_type, weekly_change_limit, monthly_change_limit,
                 quota_week_start, quota_month_start,
                 keyword_update_limit, topic_update_limit,
                 keyword_quota_start, topic_quota_start)
                VALUES (:user_id, :plan_type, :weekly_limit, :monthly_limit,
                        :week_start, :month_start,
                        :kw_limit, :topic_limit, :today, :today)
            """),
            {
                'user_id': user_id,
                'plan_type': plan_type,
                'weekly_limit': plan_config['weekly_change_limit'],
                'monthly_limit': plan_config['monthly_change_limit'],
                'week_start': today,
                'month_start': today,
                'kw_limit': plan_config.get('keyword_update_limit', 0),
                'topic_limit': plan_config.get('topic_update_limit', 0),
                'today': today,
            }
        )
        db.session.commit()
    
    @classmethod
    def update_user_plan(cls, user_id: int, plan_type: str):
        """更新用户套餐"""
        plan_config = cls.get_plan_config(plan_type)
        
        db.session.execute(
            text("""
                UPDATE user_portrait_quota
                SET plan_type = :plan_type,
                    weekly_change_limit = :weekly_limit,
                    monthly_change_limit = :monthly_limit,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {
                'user_id': user_id,
                'plan_type': plan_type,
                'weekly_limit': plan_config['weekly_change_limit'],
                'monthly_limit': plan_config['monthly_change_limit']
            }
        )
        db.session.commit()
    
    @classmethod
    def check_save_permission(cls, user_id: int) -> Tuple[bool, str, Dict]:
        """
        检查用户是否有权限保存画像
        
        Returns:
            (allowed, reason, quota_info)
        """
        quota = cls.get_user_quota(user_id)
        
        if not quota['can_save']:
            return False, '当前套餐不支持保存画像，请升级到基础版或更高版本', quota
        
        # 查询已保存的画像数量
        saved_count = db.session.execute(
            text("SELECT COUNT(*) FROM saved_portraits WHERE user_id = :user_id"),
            {'user_id': user_id}
        ).scalar()
        
        if quota['max_saved'] and saved_count >= quota['max_saved']:
            return False, f'已保存{quota["max_saved"]}个画像，请删除后再保存', quota
        
        return True, 'ok', quota

    @classmethod
    def check_library_update_permission(cls, user_id: int, library_type: str) -> Tuple[bool, str, Dict]:
        """
        检查用户是否有权限更新关键词库/选题库

        Args:
            user_id: 用户ID
            library_type: 'keyword' / 'topic'

        Returns:
            (allowed, reason, quota_info)
        """
        quota = cls.get_user_quota(user_id)
        plan_config = cls.get_plan_config(quota['plan_type'])
        today = date.today()

        limit_key = f'{library_type}_update_limit'
        used_key = f'{library_type}_updates_used'
        start_key = f'{library_type}_quota_start'

        monthly_limit = plan_config.get(limit_key, 0)
        if monthly_limit == 0:
            return False, f'当前套餐不支持更新{library_type}库，请升级套餐', quota

        used = quota.get(used_key, 0) or 0
        if used >= monthly_limit:
            return False, f'{library_type}库本月更新次数已用完（{monthly_limit}次）', quota

        return True, 'ok', quota

    @classmethod
    def record_library_update(cls, user_id: int, library_type: str) -> bool:
        """记录关键词库/选题库更新"""
        quota = cls.get_user_quota(user_id)
        today = date.today()
        used_key = f'{library_type}_updates_used'
        start_key = f'{library_type}_quota_start'

        current_used = quota.get(used_key, 0) or 0
        current_start = quota.get(start_key, None)

        new_used = 1
        new_start = today
        if current_start:
            start_date = datetime.strptime(current_start, '%Y-%m-%d').date() if isinstance(current_start, str) else current_start
            if (today - start_date).days >= 1:
                new_used = 1
                new_start = today
            else:
                new_used = current_used + 1
                new_start = current_start

        db.session.execute(
            text(f"""
                UPDATE user_portrait_quota
                SET {used_key} = :used,
                    {start_key} = :start,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {'used': new_used, 'start': new_start, 'user_id': user_id}
        )
        db.session.commit()
        return True

    @classmethod
    def get_library_quota(cls, user_id: int, library_type: str) -> Dict:
        """获取关键词库/选题库的配额信息"""
        quota = cls.get_user_quota(user_id)
        plan_config = cls.get_plan_config(quota['plan_type'])
        today = date.today()

        limit_key = f'{library_type}_update_limit'
        used_key = f'{library_type}_updates_used'
        start_key = f'{library_type}_quota_start'

        monthly_limit = int(quota.get(limit_key, 0) or 0)
        used = int(quota.get(used_key, 0) or 0)
        start = quota.get(start_key, None)
        remaining = max(0, monthly_limit - used)

        reset_at = None
        if start:
            start_date = datetime.strptime(start, '%Y-%m-%d').date() if isinstance(start, str) else start
            days_until_reset = max(0, 1 - (today - start_date).days)
            reset_at = (today + timedelta(days=days_until_reset)).isoformat()

        return {
            'limit': monthly_limit,
            'used': used,
            'remaining': remaining,
            'reset_at': reset_at,
            'plan': quota['plan_type'],
        }

    @classmethod
    def check_change_permission(cls, user_id: int, 
                               change_type: str = 'generate_new') -> Tuple[bool, str, Dict]:
        """
        检查用户是否有权限更换画像
        
        Args:
            user_id: 用户ID
            change_type: 'generate_new' / 'switch_saved' / 'reset'
        
        Returns:
            (allowed, reason, quota_info)
        """
        quota = cls.get_user_quota(user_id)
        today = date.today()
        
        # 免费用户可随时更换
        if quota['plan_type'] == 'free':
            return True, 'ok', quota
        
        # 检查周配额
        weekly_limit = quota['weekly_change_limit']
        if weekly_limit is not None:
            if quota['weekly_changes_used'] >= weekly_limit:
                # 计算重置时间
                reset_at = None
                if quota['quota_week_start']:
                    days_until_reset = 7 - (today - datetime.strptime(quota['quota_week_start'], '%Y-%m-%d').date()).days
                    reset_at = (today + timedelta(days=days_until_reset)).isoformat()
                
                return False, f'本周更换次数已用完（{weekly_limit}次），{reset_at or "下周一"}重置', quota
        
        # 检查月配额
        monthly_limit = quota['monthly_change_limit']
        if monthly_limit is not None:
            if quota['monthly_changes_used'] >= monthly_limit:
                return False, f'本月更换次数已用完（{monthly_limit}次）', quota
        
        return True, 'ok', quota
    
    @classmethod
    def record_change(cls, user_id: int, old_portrait_id: int = None,
                     new_portrait_id: int = None, change_type: str = 'generate_new',
                     change_reason: str = None) -> bool:
        """
        记录画像更换
        
        Returns:
            是否记录成功
        """
        today = date.today()
        quota = cls.get_user_quota(user_id)
        
        # 计算剩余配额
        new_weekly_used = quota['weekly_changes_used'] + 1
        new_monthly_used = quota['monthly_changes_used'] + 1
        weekly_remaining = None
        if quota['weekly_change_limit']:
            weekly_remaining = max(0, quota['weekly_change_limit'] - new_weekly_used)
        
        # 更新配额
        week_start = quota['quota_week_start']
        month_start = quota['quota_month_start']
        
        # 检查是否需要重置周配额
        if week_start:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d').date() if isinstance(week_start, str) else week_start
            if (today - week_start_date).days >= 7:
                new_weekly_used = 1
                week_start = today
        
        # 检查是否需要重置月配额
        if month_start:
            month_start_date = datetime.strptime(month_start, '%Y-%m-%d').date() if isinstance(month_start, str) else month_start
            if (today - month_start_date).days >= 30:
                new_monthly_used = 1
                month_start = today
        
        db.session.execute(
            text("""
                UPDATE user_portrait_quota
                SET weekly_changes_used = :weekly_used,
                    monthly_changes_used = :monthly_used,
                    quota_week_start = :week_start,
                    quota_month_start = :month_start,
                    total_changes = total_changes + 1,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {
                'user_id': user_id,
                'weekly_used': new_weekly_used,
                'monthly_used': new_monthly_used,
                'week_start': week_start,
                'month_start': month_start
            }
        )
        
        # 记录变更日志
        db.session.execute(
            text("""
                INSERT INTO portrait_change_logs
                (user_id, old_portrait_id, new_portrait_id, change_type, 
                 change_reason, quota_remaining)
                VALUES (:user_id, :old_id, :new_id, :change_type,
                        :reason, :remaining)
            """),
            {
                'user_id': user_id,
                'old_id': old_portrait_id,
                'new_id': new_portrait_id,
                'change_type': change_type,
                'reason': change_reason,
                'remaining': weekly_remaining
            }
        )
        
        db.session.commit()
        return True
    
    @classmethod
    def record_generation(cls, user_id: int) -> bool:
        """记录生成次数"""
        db.session.execute(
            text("""
                UPDATE user_portrait_quota
                SET total_generations = total_generations + 1,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {'user_id': user_id}
        )
        db.session.commit()
        return True
    
    @classmethod
    def get_change_history(cls, user_id: int, limit: int = 20) -> List[Dict]:
        """获取画像更换历史"""
        results = db.session.execute(
            text("""
                SELECT id, old_portrait_id, new_portrait_id, change_type,
                       change_reason, quota_remaining, created_at
                FROM portrait_change_logs
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {'user_id': user_id, 'limit': limit}
        ).fetchall()
        
        return [
            {
                'id': r[0],
                'old_portrait_id': r[1],
                'new_portrait_id': r[2],
                'change_type': r[3],
                'change_reason': r[4],
                'quota_remaining': r[5],
                'created_at': r[6].isoformat() if r[6] else None
            }
            for r in results
        ]
    
    @classmethod
    def reset_weekly_quota(cls, user_id: int) -> bool:
        """手动重置周配额（管理员用）"""
        today = date.today()
        quota = cls.get_user_quota(user_id)
        
        db.session.execute(
            text("""
                UPDATE user_portrait_quota
                SET weekly_changes_used = 0,
                    quota_week_start = :week_start,
                    updated_at = NOW()
                WHERE user_id = :user_id
            """),
            {'user_id': user_id, 'week_start': today}
        )
        db.session.commit()
        return True
    
    @classmethod
    def get_portrait_usage_stats(cls, user_id: int) -> Dict:
        """获取画像使用统计"""
        # 保存的画像数量
        saved_count = db.session.execute(
            text("SELECT COUNT(*) FROM saved_portraits WHERE user_id = :user_id"),
            {'user_id': user_id}
        ).scalar()
        
        # 被使用的画像数量
        used_count = db.session.execute(
            text("SELECT COUNT(*) FROM saved_portraits WHERE user_id = :user_id AND used_count > 0"),
            {'user_id': user_id}
        ).scalar()
        
        # 最常用的画像
        most_used = db.session.execute(
            text("""
                SELECT id, portrait_name, used_count
                FROM saved_portraits
                WHERE user_id = :user_id
                ORDER BY used_count DESC
                LIMIT 1
            """),
            {'user_id': user_id}
        ).fetchone()
        
        quota = cls.get_user_quota(user_id)
        
        return {
            'saved_count': saved_count,
            'used_count': used_count,
            'most_used_portrait': {
                'id': most_used[0] if most_used else None,
                'name': most_used[1] if most_used else None,
                'usage_count': most_used[2] if most_used else 0
            } if most_used else None,
            'quota': quota,
            'remaining_changes': {
                'weekly': max(0, (quota['weekly_change_limit'] or 999) - quota['weekly_changes_used']),
                'monthly': max(0, (quota['monthly_change_limit'] or 999) - quota['monthly_changes_used'])
            }
        }


# 全局实例
portrait_frequency_controller = PortraitFrequencyController()
