"""
画像缓存服务

功能：
1. 关键词库缓存
2. 选题库缓存
3. 缓存命中/失效统计
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import text


class PortraitCacheService:
    """画像缓存服务"""
    
    # 缓存级别
    CACHE_LEVEL_INDUSTRY = 'industry'   # 行业级缓存（所有用户共享）
    CACHE_LEVEL_USER = 'user'           # 用户级缓存
    CACHE_LEVEL_SESSION = 'session'      # 会话级缓存
    
    # 缓存TTL配置（小时）
    DEFAULT_TTL = {
        'free': 0,           # 免费用户不缓存
        'basic': 24,         # 基础版 24小时
        'professional': 168, # 专业版 7天
        'enterprise': 720    # 企业版 30天
    }
    
    @classmethod
    def _generate_cache_key(cls, industry: str, business_desc: str,
                            portraits: List[Dict], cache_type: str,
                            user_id: int = None) -> str:
        """生成缓存key（含 user_id 隔离，防止跨用户数据泄露）"""
        data = {
            'user_id': user_id if user_id else 0,
            'industry': industry,
            'business_desc': business_desc,
            'portraits': portraits[:3] if portraits else [],
            'type': cache_type
        }
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(json_str.encode('utf-8')).hexdigest()
    
    @classmethod
    def _generate_portrait_hash(cls, portraits: List[Dict]) -> str:
        """生成画像指纹"""
        if not portraits:
            return ''
        json_str = json.dumps(portraits[:5], sort_keys=True, ensure_ascii=False)
        return hashlib.md5(json_str.encode('utf-8')).hexdigest()[:16]
    
    @classmethod
    def get_keyword_cache(cls, industry: str, business_desc: str,
                          portraits: List[Dict], user_id: int, 
                          plan_type: str) -> Optional[Dict]:
        """
        获取关键词库缓存
        
        Returns:
            缓存数据 或 None
        """
        # 免费用户不缓存
        if plan_type == 'free':
            return None
        
        cache_key = cls._generate_cache_key(industry, business_desc, portraits, 'keyword', user_id)
        portrait_hash = cls._generate_portrait_hash(portraits)
        
        # 查询缓存
        result = db.session.execute(
            text("""
                SELECT id, keywords, keyword_types, hit_count, expires_at
                FROM keyword_cache
                WHERE cache_key = :cache_key
                AND portrait_hash = :portrait_hash
                AND (expires_at IS NULL OR expires_at > NOW())
                AND is_stale = FALSE
            """),
            {'cache_key': cache_key, 'portrait_hash': portrait_hash}
        ).fetchone()
        
        if result:
            # 更新命中统计
            db.session.execute(
                text("""
                    UPDATE keyword_cache 
                    SET hit_count = hit_count + 1, 
                        last_hit_at = NOW()
                    WHERE id = :id
                """),
                {'id': result[0]}
            )
            db.session.commit()
            
            return {
                'keywords': json.loads(result[1]) if isinstance(result[1], str) else result[1],
                'keyword_types': json.loads(result[2]) if result[2] and isinstance(result[2], str) else result[2],
                'hit_count': result[3],
                'from_cache': True
            }
        
        return None
    
    @classmethod
    def save_keyword_cache(cls, industry: str, business_desc: str,
                          portraits: List[Dict], user_id: int,
                          keywords: List, keyword_types: Dict,
                          plan_type: str) -> bool:
        """
        保存关键词库缓存
        """
        # 免费用户不缓存
        if plan_type == 'free':
            return False
        
        cache_key = cls._generate_cache_key(industry, business_desc, portraits, 'keyword', user_id)
        portrait_hash = cls._generate_portrait_hash(portraits)
        ttl = cls.DEFAULT_TTL.get(plan_type, 24)
        
        # 判断缓存级别
        cache_level = cls.CACHE_LEVEL_USER if user_id else cls.CACHE_LEVEL_INDUSTRY
        expires_at = datetime.now() + timedelta(hours=ttl) if ttl > 0 else None
        
        # 先删除旧缓存
        db.session.execute(
            text("""
                DELETE FROM keyword_cache 
                WHERE cache_key = :cache_key AND portrait_hash = :portrait_hash
            """),
            {'cache_key': cache_key, 'portrait_hash': portrait_hash}
        )
        
        # 插入新缓存
        db.session.execute(
            text("""
                INSERT INTO keyword_cache 
                (cache_key, industry, portrait_hash, keywords, keyword_types, 
                 cache_level, user_id, expires_at)
                VALUES (:cache_key, :industry, :portrait_hash, :keywords, 
                        :keyword_types, :cache_level, :user_id, :expires_at)
            """),
            {
                'cache_key': cache_key,
                'industry': industry,
                'portrait_hash': portrait_hash,
                'keywords': json.dumps(keywords, ensure_ascii=False),
                'keyword_types': json.dumps(keyword_types, ensure_ascii=False) if keyword_types else None,
                'cache_level': cache_level,
                'user_id': user_id,
                'expires_at': expires_at
            }
        )
        
        db.session.commit()
        return True
    
    @classmethod
    def get_topic_cache(cls, industry: str, business_desc: str,
                       portraits: List[Dict], keyword_cache_id: int,
                       user_id: int, plan_type: str) -> Optional[Dict]:
        """
        获取选题库缓存
        """
        # 免费用户不缓存
        if plan_type == 'free':
            return None
        
        cache_key = cls._generate_cache_key(industry, business_desc, portraits, 'topic', user_id)
        
        # 查询缓存
        result = db.session.execute(
            text("""
                SELECT id, topics, topic_types, hit_count, expires_at
                FROM topic_cache
                WHERE cache_key = :cache_key
                AND (keyword_cache_id = :keyword_cache_id OR :keyword_cache_id IS NULL)
                AND (expires_at IS NULL OR expires_at > NOW())
            """),
            {'cache_key': cache_key, 'keyword_cache_id': keyword_cache_id}
        ).fetchone()
        
        if result:
            # 更新命中统计
            db.session.execute(
                text("""
                    UPDATE topic_cache 
                    SET hit_count = hit_count + 1, 
                        last_hit_at = NOW()
                    WHERE id = :id
                """),
                {'id': result[0]}
            )
            db.session.commit()
            
            return {
                'topics': json.loads(result[1]) if isinstance(result[1], str) else result[1],
                'topic_types': json.loads(result[2]) if result[2] and isinstance(result[2], str) else result[2],
                'hit_count': result[3],
                'from_cache': True
            }
        
        return None
    
    @classmethod
    def save_topic_cache(cls, industry: str, business_desc: str,
                        portraits: List[Dict], keyword_cache_id: int,
                        user_id: int, topics: List, topic_types: Dict,
                        plan_type: str) -> bool:
        """
        保存选题库缓存
        """
        # 免费用户不缓存
        if plan_type == 'free':
            return False
        
        cache_key = cls._generate_cache_key(industry, business_desc, portraits, 'topic', user_id)
        ttl = cls.DEFAULT_TTL.get(plan_type, 24)
        
        cache_level = cls.CACHE_LEVEL_USER if user_id else cls.CACHE_LEVEL_INDUSTRY
        expires_at = datetime.now() + timedelta(hours=ttl) if ttl > 0 else None
        
        # 先删除旧缓存
        db.session.execute(
            text("""
                DELETE FROM topic_cache 
                WHERE cache_key = :cache_key
            """),
            {'cache_key': cache_key}
        )
        
        # 插入新缓存
        db.session.execute(
            text("""
                INSERT INTO topic_cache 
                (cache_key, keyword_cache_id, topics, topic_types, 
                 cache_level, user_id, expires_at)
                VALUES (:cache_key, :keyword_cache_id, :topics, 
                        :topic_types, :cache_level, :user_id, :expires_at)
            """),
            {
                'cache_key': cache_key,
                'keyword_cache_id': keyword_cache_id,
                'topics': json.dumps(topics, ensure_ascii=False),
                'topic_types': json.dumps(topic_types, ensure_ascii=False) if topic_types else None,
                'cache_level': cache_level,
                'user_id': user_id,
                'expires_at': expires_at
            }
        )
        
        db.session.commit()
        return True
    
    @classmethod
    def invalidate_cache(cls, cache_type: str = 'all', 
                        industry: str = None, user_id: int = None) -> int:
        """
        手动刷新缓存
        
        Args:
            cache_type: 'keyword' / 'topic' / 'all'
            industry: 可选，指定行业
            user_id: 可选，指定用户
            
        Returns:
            删除的缓存数量
        """
        conditions = []
        params = {}
        
        if cache_type in ['keyword', 'all']:
            conditions.append("1=1")
        if cache_type in ['topic', 'all']:
            conditions.append("1=1")
        
        where_clause = " OR ".join([f"table_name = '{t}'" for t in 
                                    ['keyword_cache', 'topic_cache'] 
                                    if cache_type == 'all' or cache_type in t])
        
        # 标记为过期而非直接删除
        query = f"""
            UPDATE keyword_cache SET is_stale = TRUE, updated_at = NOW() 
            WHERE 1=1
        """
        if industry:
            query += f" AND industry = :industry"
            params['industry'] = industry
        if user_id:
            query += f" AND user_id = :user_id"
            params['user_id'] = user_id
            
        db.session.execute(text(query), params)
        db.session.execute(
            text(f"""
                UPDATE topic_cache SET expires_at = NOW() WHERE 1=1
                {'AND industry = :industry' if industry else ''}
                {'AND user_id = :user_id' if user_id else ''}
            """),
            params
        )
        
        db.session.commit()
        return 0
    
    @classmethod
    def cleanup_expired_cache(cls) -> int:
        """
        清理过期缓存
        
        Returns:
            删除的缓存数量
        """
        # 删除过期关键词缓存
        result1 = db.session.execute(
            text("DELETE FROM keyword_cache WHERE expires_at < NOW()")
        )
        
        # 删除过期选题缓存
        result2 = db.session.execute(
            text("DELETE FROM topic_cache WHERE expires_at < NOW()")
        )
        
        db.session.commit()
        
        return result1.rowcount + result2.rowcount
    
    @classmethod
    def get_cache_stats(cls, plan_type: str = None) -> Dict:
        """
        获取缓存统计
        """
        stats = {
            'keyword_cache': {'total': 0, 'hits': 0, 'avg_hits': 0},
            'topic_cache': {'total': 0, 'hits': 0, 'avg_hits': 0}
        }
        
        # 关键词缓存统计
        kw_result = db.session.execute(
            text("""
                SELECT COUNT(*) as total, SUM(hit_count) as total_hits
                FROM keyword_cache
                WHERE expires_at > NOW() OR expires_at IS NULL
            """)
        ).fetchone()
        
        if kw_result:
            stats['keyword_cache']['total'] = kw_result[0] or 0
            stats['keyword_cache']['hits'] = kw_result[1] or 0
            if kw_result[0]:
                stats['keyword_cache']['avg_hits'] = round(kw_result[1] / kw_result[0], 2)
        
        # 选题缓存统计
        topic_result = db.session.execute(
            text("""
                SELECT COUNT(*) as total, SUM(hit_count) as total_hits
                FROM topic_cache
                WHERE expires_at > NOW() OR expires_at IS NULL
            """)
        ).fetchone()
        
        if topic_result:
            stats['topic_cache']['total'] = topic_result[0] or 0
            stats['topic_cache']['hits'] = topic_result[1] or 0
            if topic_result[0]:
                stats['topic_cache']['avg_hits'] = round(topic_result[1] / topic_result[0], 2)
        
        return stats


# 全局实例
portrait_cache_service = PortraitCacheService()
