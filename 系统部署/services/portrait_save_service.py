"""
画像保存服务

整合画像保存、缓存和频率控制
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy import text
from models.models import db
from services.portrait_cache_service import portrait_cache_service
from services.portrait_frequency_controller import portrait_frequency_controller

logger = logging.getLogger(__name__)


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
        
        try:
            # 每个客户只保留一个画像：删除旧的（先备份）
            old_portraits = cls.get_user_portraits(user_id, include_data=False)

            db.session.execute(
                text("DELETE FROM saved_portraits WHERE user_id = :user_id"),
                {'user_id': user_id}
            )

            # 如果设为默认，先取消其他默认（已删除，这里保持一致）
            if set_as_default:
                pass

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

        except Exception:
            db.session.rollback()
            # 尝试恢复旧数据（如果被删了）
            try:
                if old_portraits:
                    for op in old_portraits:
                        db.session.execute(
                            text("""
                                INSERT INTO saved_portraits
                                (user_id, portrait_name, portrait_data, business_description,
                                 industry, target_customer, is_default, source_session_id,
                                 keyword_library, topic_library, created_at)
                                VALUES (:uid, :name, :data, :desc, :industry, :customer,
                                        :is_default, :session_id, :kw, :topic, NOW())
                            """),
                            {
                                'uid': user_id,
                                'name': op.get('portrait_name', ''),
                                'data': json.dumps(op.get('portrait_data', {}), ensure_ascii=False),
                                'desc': op.get('business_description', ''),
                                'industry': op.get('industry', ''),
                                'customer': op.get('target_customer', ''),
                                'is_default': op.get('is_default', False),
                                'session_id': op.get('source_session_id'),
                                'kw': json.dumps(op.get('keyword_library'), ensure_ascii=False) if op.get('keyword_library') else None,
                                'topic': json.dumps(op.get('topic_library'), ensure_ascii=False) if op.get('topic_library') else None,
                            }
                        )
                    db.session.commit()
            except Exception:
                db.session.rollback()
                logger.exception("[portrait_save] 画像保存失败且旧数据恢复也失败，user_id=%s", user_id)

            raise

        # 获取保存的画像
        saved = cls.get_saved_portrait(saved_id)

        return True, '画像保存成功', saved
    
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
                       topic_updated_at, topic_update_count, topic_cache_expires_at,
                       generation_status, generation_error
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
            # 生成状态
            'generation_status': result[19] or 'pending',
            'generation_error': result[20],
        }
    
    @classmethod
    def get_user_portraits(cls, user_id: int, include_data: bool = True) -> List[Dict]:
        """获取用户所有已保存的画像"""
        query = """
            SELECT id, portrait_name, portrait_data, industry, target_customer,
                   is_default, used_count, last_used_at, created_at,
                   keyword_library, topic_library,
                   keyword_updated_at, keyword_update_count, keyword_cache_expires_at,
                   topic_updated_at, topic_update_count, topic_cache_expires_at,
                   generation_status, generation_error
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
                # 生成状态
                'generation_status': r[17] or 'pending',
                'generation_error': r[18],
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
