"""
Knowledge Base Service - 查询知识库内容用于AI上下文
"""
import logging
from typing import List, Dict, Optional
from models.models import KnowledgeCategory, KnowledgeArticle

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库查询服务"""
    
    def __init__(self):
        self.max_articles = 5  # 最多返回5篇文章
        self.max_content_length = 2000  # 每篇文章最大字符数
    
    def search(self, query: str, category_slug: str = None, limit: int = None) -> List[Dict]:
        """
        搜索知识库文章
        
        Args:
            query: 搜索关键词
            category_slug: 分类slug（可选）
            limit: 返回数量限制
        
        Returns:
            文章列表，每篇包含 title, content, category, tags, url 等
        """
        limit = limit or self.max_articles
        
        # 构建查询
        articles_query = KnowledgeArticle.query.filter_by(is_published=True)
        
        if category_slug:
            category = KnowledgeCategory.query.filter_by(slug=category_slug).first()
            if category:
                articles_query = articles_query.filter_by(category_id=category.id)
        
        # 关键词搜索（标题、内容、标签）
        if query:
            search_pattern = f"%{query}%"
            articles_query = articles_query.filter(
                (KnowledgeArticle.title.ilike(search_pattern)) |
                (KnowledgeArticle.content.ilike(search_pattern)) |
                (KnowledgeArticle.tags.ilike(search_pattern))
            )
        
        articles = articles_query.order_by(KnowledgeArticle.view_count.desc(), KnowledgeArticle.created_at.desc()).limit(limit).all()
        
        results = []
        for article in articles:
            results.append({
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'content': self._truncate_content(article.content),
                'category': article.category.name if article.category else None,
                'category_slug': article.category.slug if article.category else None,
                'content_type': article.content_type,
                'tags': article.tags or [],
                'author': article.author,
                'source': article.source,
                'view_count': article.view_count,
                'created_at': article.created_at.strftime('%Y-%m-%d') if article.created_at else None
            })
        
        logger.info(f"Knowledge base search: query='{query}', category='{category_slug}', found {len(results)} articles")
        return results
    
    def get_by_category(self, category_slug: str, limit: int = None) -> List[Dict]:
        """获取指定分类下的文章"""
        return self.search(query='', category_slug=category_slug, limit=limit)
    
    def get_recent(self, limit: int = None) -> List[Dict]:
        """获取最新文章"""
        return self.search(query='', limit=limit)
    
    def get_all_categories(self) -> List[Dict]:
        """获取所有分类"""
        categories = KnowledgeCategory.query.order_by(KnowledgeCategory.sort_order).all()
        return [{
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'article_count': c.articles.count()
        } for c in categories]
    
    def format_for_context(self, articles: List[Dict], max_articles: int = None) -> str:
        """
        将文章格式化为 LLM 上下文
        
        Args:
            articles: 文章列表
            max_articles: 最大文章数
        
        Returns:
            格式化后的字符串
        """
        max_articles = max_articles or self.max_articles
        articles = articles[:max_articles]
        
        if not articles:
            return "## 知识库\n暂无相关知识库内容。"
        
        lines = ["## 知识库参考\n"]
        
        for i, article in enumerate(articles, 1):
            lines.append(f"### {i}. {article['title']}")
            if article.get('category'):
                lines.append(f"**分类**: {article['category']}")
            if article.get('tags'):
                lines.append(f"**标签**: {', '.join(article['tags'])}")
            if article.get('content'):
                lines.append(f"\n{article['content']}\n")
            lines.append("---\n")
        
        return '\n'.join(lines)
    
    def _truncate_content(self, content: str) -> str:
        """截断内容"""
        if not content:
            return ""
        if len(content) <= self.max_content_length:
            return content
        return content[:self.max_content_length] + "..."
    
    def auto_search(self, user_message: str) -> str:
        """
        根据用户消息自动搜索知识库
        
        智能分析用户消息，提取关键词并搜索相关知识库内容
        
        Args:
            user_message: 用户消息
        
        Returns:
            格式化后的知识库上下文
        """
        # 提取关键词（简单实现：取消息中的重要词汇）
        keywords = self._extract_keywords(user_message)
        
        if not keywords:
            # 如果无法提取关键词，尝试全文搜索
            articles = self.search(user_message)
        else:
            # 使用关键词搜索
            articles = self.search(' '.join(keywords))
        
        return self.format_for_context(articles)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """
        从文本中提取关键词
        
        简单实现：去除常见停用词，保留有意义的词汇
        """
        if not text:
            return []
        
        # 常见停用词
        stop_words = {
            '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '那', '什么', '怎么', '如何', '为什么', '能', '可以', '请', '帮我',
            '给', '让', '把', '用', '从', '对', '这个', '那个', '因为', '所以', '但是',
            '如果', '只是', '还是', '或者', '而且', '然后', '还', '再', '已', '已经',
            '请', '请问', '问一下', '想问一下', '麻烦', '帮忙', '帮助'
        }
        
        # 分词（简单按字符分割）
        words = text.replace('？', ' ').replace('?', ' ').replace('！', ' ').replace('!', ' ')
        words = words.replace('，', ' ').replace(',', ' ').replace('。', ' ').replace('.', ' ')
        words = words.replace('、', ' ').replace('；', ' ').replace(';', ' ').replace('：', ' ')
        
        # 过滤停用词和短词
        keywords = [w.strip() for w in words.split() if w.strip() and len(w.strip()) >= 2 and w.strip() not in stop_words]
        
        # 返回前5个关键词
        return keywords[:5]


# 全局实例
_knowledge_base_service: Optional[KnowledgeBaseService] = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """获取知识库服务实例"""
    global _knowledge_base_service
    if _knowledge_base_service is None:
        _knowledge_base_service = KnowledgeBaseService()
    return _knowledge_base_service
