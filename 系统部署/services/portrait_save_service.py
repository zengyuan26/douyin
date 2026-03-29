"""
画像保存服务

整合画像保存、缓存和频率控制
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from models.models import db
from services.portrait_cache_service import portrait_cache_service
from services.portrait_frequency_controller import portrait_frequency_controller


class PortraitSaveService:
    """画像保存服务"""
    
    @classmethod
    def save_portrait(cls, user_id: int, portrait_data: Dict,
                    portrait_name: str = None, 
                    business_description: str = None,
                    industry: str = None,
                    target_customer: str = None,
                    source_session_id: int = None,
                    set_as_default: bool = False) -> Tuple[bool, str, Dict]:
        """
        保存画像
        
        Args:
            user_id: 用户ID
            portrait_data: 画像数据
            portrait_name: 画像名称
            business_description: 业务描述
            industry: 行业
            target_customer: 目标客户
            source_session_id: 来源会话ID
            set_as_default: 是否设为默认
        
        Returns:
            (success, message, saved_portrait)
        """
        # 检查保存权限
        allowed, reason, quota = portrait_frequency_controller.check_save_permission(user_id)
        if not allowed:
            return False, reason, {}
        
        # 如果设为默认，先取消其他默认
        if set_as_default:
            db.session.execute(
                text("UPDATE saved_portraits SET is_default = FALSE WHERE user_id = :user_id"),
                {'user_id': user_id}
            )
        
        # 生成画像名称
        if not portrait_name:
            portrait_name = f"画像_{datetime.now().strftime('%m%d_%H%M')}"
        
        # 插入保存记录
        result = db.session.execute(
            text("""
                INSERT INTO saved_portraits 
                (user_id, portrait_name, portrait_data, business_description,
                 industry, target_customer, is_default, source_session_id, created_at)
                VALUES (:user_id, :name, :data, :desc, :industry, :customer,
                        :is_default, :session_id, NOW())
            """),
            {
                'user_id': user_id,
                'name': portrait_name,
                'data': json.dumps(portrait_data, ensure_ascii=False),
                'desc': business_description,
                'industry': industry,
                'customer': target_customer,
                'is_default': set_as_default,
                'session_id': source_session_id
            }
        )
        
        saved_id = result.lastrowid
        db.session.commit()

        # 获取保存的画像
        saved = cls.get_saved_portrait(saved_id)

        # 后台自动生成关键词库+选题库（付费用户）
        cls._trigger_library_generation_async(saved_id, saved)

        return True, '画像保存成功', saved

    @classmethod
    def _trigger_library_generation_async(cls, portrait_id: int, portrait: Dict):
        """后台异步生成关键词库和选题库"""
        import threading
        def _generate():
            try:
                from services.keyword_library_generator import keyword_library_generator
                from services.topic_library_generator import topic_library_generator
                from models.public_models import PublicUser
                from models.models import db as app_db
                from services.portrait_frequency_controller import portrait_frequency_controller

                user_id = portrait.get('user_id', 0)
                print(f"[_trigger_library_generation_async] 开始生成画像 {portrait_id}, user_id={user_id}")

                # 检查付费状态
                user = PublicUser.query.get(user_id)
                if not user:
                    print(f"[_trigger_library_generation_async] 用户 {user_id} 不存在，跳过")
                    return
                if not user.is_paid_user():
                    print(f"[_trigger_library_generation_async] 用户 {user_id} 为免费用户，跳过专属库生成")
                    return

                plan_type = user.premium_plan or 'basic'
                print(f"[_trigger_library_generation_async] 用户 {user_id} plan={plan_type}")

                # 检查配额
                allowed, reason, quota = portrait_frequency_controller.check_library_update_permission(
                    user_id, 'keyword'
                )
                print(f"[_trigger_library_generation_async] 配额检查: allowed={allowed}, reason={reason}")

                portrait_data = portrait.get('portrait_data', {})
                business_info = {
                    'business_description': portrait.get('business_description', ''),
                    'industry': portrait.get('industry', ''),
                    'products': [],
                    'region': '',
                    'target_customer': portrait.get('target_customer', ''),
                }

                # 1. 生成关键词库
                kw_result = keyword_library_generator.generate(
                    portrait_data=portrait_data,
                    business_info=business_info,
                    plan_type=plan_type,
                )
                print(f"[_trigger_library_generation_async] 关键词库生成: {kw_result.get('success')}")
                if kw_result.get('success'):
                    keyword_library_generator.save_to_portrait(
                        portrait_id=portrait_id,
                        keyword_library=kw_result['keyword_library'],
                        user_id=user_id,
                        plan_type=plan_type,
                    )
                    portrait_frequency_controller.record_library_update(user_id, 'keyword')

                # 2. 生成选题库（依赖关键词库）
                kw_library = keyword_library_generator.get_from_portrait(portrait_id)
                topic_result = topic_library_generator.generate(
                    portrait_data=portrait_data,
                    business_info=business_info,
                    keyword_library=kw_library,
                    plan_type=plan_type,
                )
                print(f"[_trigger_library_generation_async] 选题库生成: {topic_result.get('success')}")
                if topic_result.get('success'):
                    topic_library_generator.save_to_portrait(
                        portrait_id=portrait_id,
                        topic_library=topic_result['topic_library'],
                        user_id=user_id,
                        plan_type=plan_type,
                    )
                    portrait_frequency_controller.record_library_update(user_id, 'topic')
                print(f"[_trigger_library_generation_async] 画像 {portrait_id} 关键词库+选题库生成完成")
            except Exception as e:
                print(f"[_trigger_library_generation_async] 画像 {portrait_id} 生成失败: {e}")
                import traceback
                traceback.print_exc()

        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
    
    @classmethod
    def get_saved_portrait(cls, portrait_id: int) -> Optional[Dict]:
        """获取已保存的画像"""
        result = db.session.execute(
            text("""
                SELECT id, user_id, portrait_name, portrait_data, business_description,
                       industry, target_customer, is_default, used_count,
                       last_used_at, created_at,
                       keyword_library, topic_library,
                       keyword_updated_at, keyword_update_count, keyword_cache_expires_at,
                       topic_updated_at, topic_update_count, topic_cache_expires_at
                FROM saved_portraits
                WHERE id = :id
            """),
            {'id': portrait_id}
        ).fetchone()

        if not result:
            return None

        def parse_json(val):
            if val is None:
                return None
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    return val
            return val

        def fmt_datetime(val):
            """兼容 datetime 对象和字符串"""
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return val.isoformat()

        return {
            'id': result[0],
            'user_id': result[1],
            'portrait_name': result[2],
            'portrait_data': parse_json(result[3]),
            'business_description': result[4],
            'industry': result[5],
            'target_customer': result[6],
            'is_default': result[7],
            'used_count': result[8],
            'last_used_at': fmt_datetime(result[9]),
            'created_at': fmt_datetime(result[10]),
            # 专属库
            'keyword_library': parse_json(result[11]),
            'topic_library': parse_json(result[12]),
            'keyword_updated_at': fmt_datetime(result[13]),
            'keyword_update_count': result[14] or 0,
            'keyword_cache_expires_at': fmt_datetime(result[15]),
            'topic_updated_at': fmt_datetime(result[16]),
            'topic_update_count': result[17] or 0,
            'topic_cache_expires_at': fmt_datetime(result[18]),
        }
    
    @classmethod
    def get_user_portraits(cls, user_id: int, include_data: bool = True) -> List[Dict]:
        """获取用户所有已保存的画像"""
        query = """
            SELECT id, portrait_name, portrait_data, industry, target_customer,
                   is_default, used_count, last_used_at, created_at,
                   keyword_library, topic_library,
                   keyword_updated_at, keyword_update_count, keyword_cache_expires_at,
                   topic_updated_at, topic_update_count, topic_cache_expires_at
            FROM saved_portraits
            WHERE user_id = :user_id
            ORDER BY is_default DESC, last_used_at DESC, created_at DESC
        """

        results = db.session.execute(text(query), {'user_id': user_id}).fetchall()

        def parse_json(val):
            if val is None:
                return None
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except:
                    return val
            return val

        portraits = []
        for r in results:
            portrait = {
                'id': r[0],
                'portrait_name': r[1],
                'industry': r[3],
                'target_customer': r[4],
                'is_default': r[5],
                'used_count': r[6],
                'last_used_at': r[7].isoformat() if r[7] else None,
                'created_at': r[8].isoformat() if r[8] else None,
                # 专属库（始终返回，用于卡片状态显示）
                'keyword_library': parse_json(r[9]),
                'topic_library': parse_json(r[10]),
                'keyword_updated_at': r[11].isoformat() if r[11] else None,
                'keyword_update_count': r[12] or 0,
                'keyword_cache_expires_at': r[13].isoformat() if r[13] else None,
                'topic_updated_at': r[14].isoformat() if r[14] else None,
                'topic_update_count': r[15] or 0,
                'topic_cache_expires_at': r[16].isoformat() if r[16] else None,
            }

            if include_data:
                portrait['portrait_data'] = parse_json(r[2])

            portraits.append(portrait)

        return portraits
    
    @classmethod
    def delete_portrait(cls, user_id: int, portrait_id: int) -> Tuple[bool, str]:
        """删除已保存的画像"""
        result = db.session.execute(
            text("""
                DELETE FROM saved_portraits
                WHERE id = :id AND user_id = :user_id
            """),
            {'id': portrait_id, 'user_id': user_id}
        )
        db.session.commit()
        
        if result.rowcount > 0:
            return True, '画像已删除'
        return False, '画像不存在或无权删除'
    
    @classmethod
    def set_default_portrait(cls, user_id: int, portrait_id: int) -> Tuple[bool, str]:
        """设为默认画像"""
        # 取消其他默认
        db.session.execute(
            text("UPDATE saved_portraits SET is_default = FALSE WHERE user_id = :user_id"),
            {'user_id': user_id}
        )
        
        # 设置新的默认
        result = db.session.execute(
            text("""
                UPDATE saved_portraits SET is_default = TRUE
                WHERE id = :id AND user_id = :user_id
            """),
            {'id': portrait_id, 'user_id': user_id}
        )
        db.session.commit()
        
        if result.rowcount > 0:
            return True, '已设为默认画像'
        return False, '画像不存在或无权操作'
    
    @classmethod
    def get_default_portrait(cls, user_id: int) -> Optional[Dict]:
        """获取默认画像"""
        result = db.session.execute(
            text("""
                SELECT id FROM saved_portraits
                WHERE user_id = :user_id AND is_default = TRUE
                LIMIT 1
            """),
            {'user_id': user_id}
        ).fetchone()
        
        if result:
            return cls.get_saved_portrait(result[0])
        return None
    
    @classmethod
    def use_portrait(cls, user_id: int, portrait_id: int) -> bool:
        """使用画像（更新使用次数）"""
        db.session.execute(
            text("""
                UPDATE saved_portraits
                SET used_count = used_count + 1,
                    last_used_at = NOW()
                WHERE id = :id AND user_id = :user_id
            """),
            {'id': portrait_id, 'user_id': user_id}
        )
        db.session.commit()
        return True
    
    @classmethod
    def switch_portrait(cls, user_id: int, old_portrait_id: int = None,
                      new_portrait_id: int = None,
                      new_portrait_data: Dict = None,
                      portrait_name: str = None,
                      business_description: str = None,
                      change_type: str = 'generate_new') -> Tuple[bool, str, Dict]:
        """
        切换/更换画像
        
        流程：
        1. 检查更换权限
        2. 记录更换
        3. 如果是新画像则保存
        4. 返回新画像数据
        
        Returns:
            (success, message, portrait_data)
        """
        # 检查更换权限
        allowed, reason, quota = portrait_frequency_controller.check_change_permission(
            user_id, change_type
        )
        if not allowed:
            return False, reason, {}
        
        # 如果是新画像
        if new_portrait_data:
            success, msg, saved = cls.save_portrait(
                user_id=user_id,
                portrait_data=new_portrait_data,
                portrait_name=portrait_name,
                business_description=business_description,
                set_as_default=True
            )
            if success:
                # 记录更换
                portrait_frequency_controller.record_change(
                    user_id, old_portrait_id, saved['id'], change_type
                )
                return True, '画像已保存并使用', saved
            return False, msg, {}
        
        # 如果是切换到已保存的画像
        if new_portrait_id:
            portrait = cls.get_saved_portrait(new_portrait_id)
            if not portrait:
                return False, '画像不存在', {}
            
            # 更新使用记录
            cls.use_portrait(user_id, new_portrait_id)
            
            # 记录更换
            portrait_frequency_controller.record_change(
                user_id, old_portrait_id, new_portrait_id, 'switch_saved'
            )
            
            return True, '已切换到画像：' + portrait['portrait_name'], portrait
        
        return False, '未指定要切换的画像', {}
    
    @classmethod
    def generate_with_cache(cls, user_id: int, industry: str,
                          business_desc: str, portraits: List[Dict],
                          plan_type: str = 'free') -> Tuple[Dict, bool]:
        """
        带缓存的画像生成
        
        流程：
        1. 尝试从缓存获取关键词库
        2. 如果没有缓存，生成并保存缓存
        3. 尝试从缓存获取选题库
        4. 如果没有缓存，生成并保存缓存
        
        Returns:
            (result_data, from_cache)
        """
        result = {
            'keywords': None,
            'keyword_cache_id': None,
            'topics': None,
            'from_cache': False
        }
        
        # 尝试获取关键词库缓存
        kw_cache = portrait_cache_service.get_keyword_cache(
            industry, business_desc, portraits, user_id, plan_type
        )
        
        if kw_cache:
            result['keywords'] = kw_cache['keywords']
            result['keyword_cache_id'] = kw_cache.get('id')
            result['from_cache'] = True
        else:
            # 需要生成关键词库
            result['from_cache'] = False
        
        # 尝试获取选题库缓存
        topic_cache = portrait_cache_service.get_topic_cache(
            industry, business_desc, portraits,
            result.get('keyword_cache_id'), user_id, plan_type
        )
        
        if topic_cache:
            result['topics'] = topic_cache['topics']
            result['from_cache'] = result['from_cache'] or True
        
        return result, result['from_cache']
    
    @classmethod
    def save_cache(cls, user_id: int, industry: str,
                  business_desc: str, portraits: List[Dict],
                  keywords: List, keyword_types: Dict,
                  topics: List, topic_types: Dict,
                  plan_type: str = 'free') -> bool:
        """
        保存缓存
        
        在生成完成后调用，保存结果到缓存
        """
        # 保存关键词库缓存
        kw_cache_id = portrait_cache_service.save_keyword_cache(
            industry, business_desc, portraits, user_id,
            keywords, keyword_types, plan_type
        )
        
        # 保存选题库缓存
        portrait_cache_service.save_topic_cache(
            industry, business_desc, portraits,
            kw_cache_id, user_id,
            topics, topic_types, plan_type
        )
        
        return True
    
    @classmethod
    def get_portrait_stats(cls, user_id: int) -> Dict:
        """获取画像统计"""
        return portrait_frequency_controller.get_portrait_usage_stats(user_id)


# 全局实例
portrait_save_service = PortraitSaveService()
