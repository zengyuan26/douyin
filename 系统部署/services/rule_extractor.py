"""
规则自动提取服务 - 从生成内容中自动提取规则
"""
import json
import logging
from typing import List, Dict, Optional
from models.models import db, RuleExtractionLog, KnowledgeRule, AnalysisDimension, ContentReplication

logger = logging.getLogger(__name__)


class RuleExtractor:
    """规则自动提取器 - 从内容中自动提取可复用的规则"""

    # 提取规则的系统提示词
    EXTRACTION_PROMPT = """你是一个内容分析专家。请分析以下内容，提取可复用的规则。

源内容信息：
- 标题：{source_title}
- 内容：{source_content}

生成的内容信息：
- 标题：{generated_title}
- 内容：{generated_content}

请分析这个内容成功的原因，提取3-5条可复用的规则。每条规则需要包含：
1. 规则标题（简明扼要）
2. 规则内容（具体的操作方法）
3. 所属分类（关键词库/选题库/内容模板/运营规划/市场分析）
4. 适用场景（种草/带货/品牌宣传/知识分享等）
5. 适用人群（年轻女性/白领/宝爸/学生等）
6. 适用平台（抖音/小红书/bilibili等）

请以JSON数组格式输出，格式如下：
[
  {{
    "rule_title": "规则标题",
    "rule_content": "规则内容",
    "category": "内容模板",
    "applicable_scenarios": ["种草", "带货"],
    "applicable_audiences": ["年轻女性", "白领"],
    "platforms": ["抖音"],
    "source_dimension": "标题/封面/选题/内容/心理/商业/爆款/结尾/标签/人物/形式/互动"
  }}
]

请确保规则具体、可操作、有价值。"""

    def __init__(self):
        """初始化规则提取器"""
        self.llm_service = None
        self._init_llm_service()

    def _init_llm_service(self):
        """初始化 LLM 服务"""
        try:
            from services.llm import LLMService
            self.llm_service = LLMService()
        except Exception as e:
            logger.warning(f"初始化 LLM 服务失败: {e}")

    def extract_rules(self, source_title: str, source_content: str,
                      generated_title: str, generated_content: str,
                      source_replication_id: int = None) -> Optional[List[Dict]]:
        """
        从生成的内容中提取规则

        Args:
            source_title: 源内容标题
            source_content: 源内容
            generated_title: 生成的内容标题
            generated_content: 生成的内容
            source_replication_id: 关联的复制记录ID

        Returns:
            提取的规则列表，失败返回 None
        """
        if not self.llm_service:
            logger.error("LLM 服务未初始化")
            return None

        try:
            # 构建提示词
            prompt = self.EXTRACTION_PROMPT.format(
                source_title=source_title or '',
                source_content=source_content or '',
                generated_title=generated_title or '',
                generated_content=generated_content or ''
            )

            # 调用 LLM
            messages = [
                {"role": "system", "content": "你是一个专业的内容分析专家，擅长提取可复用的内容创作规则。"},
                {"role": "user", "content": prompt}
            ]

            response = self.llm_service.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=2000
            )

            if not response:
                logger.error("LLM 调用返回为空")
                return None

            # 解析 JSON 响应
            rules = self._parse_llm_response(response)

            # 创建提取记录
            self._create_extraction_log(
                source_replication_id=source_replication_id,
                source_title=source_title,
                source_content=source_content,
                generated_title=generated_title,
                generated_content=generated_content,
                suggested_rules=rules
            )

            return rules

        except Exception as e:
            logger.error(f"提取规则失败: {e}")
            return None

    def _parse_llm_response(self, response: str) -> List[Dict]:
        """解析 LLM 响应，提取规则列表"""
        try:
            # 尝试提取 JSON 数组
            import re

            # 查找 JSON 数组
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                rules = json.loads(json_match.group())
                return rules

            # 如果没有找到 JSON，返回空列表
            logger.warning("LLM 响应中未找到有效的 JSON 数组")
            return []

        except json.JSONDecodeError as e:
            logger.error(f"解析 JSON 失败: {e}")
            return []
        except Exception as e:
            logger.error(f"解析 LLM 响应失败: {e}")
            return []

    def _create_extraction_log(self, source_replication_id: int,
                                source_title: str, source_content: str,
                                generated_title: str, generated_content: str,
                                suggested_rules: List[Dict]):
        """创建规则提取记录"""
        try:
            log = RuleExtractionLog(
                source_replication_id=source_replication_id,
                source_title=source_title,
                source_content=source_content,
                generated_title=generated_title,
                generated_content=generated_content,
                suggested_rules=suggested_rules,
                status='pending'
            )
            db.session.add(log)
            db.session.commit()
            logger.info(f"创建规则提取记录成功: {log.id}")
        except Exception as e:
            logger.error(f"创建规则提取记录失败: {e}")
            db.session.rollback()

    def periodic_review(self) -> Dict:
        """
        定期复盘规则库

        Returns:
            复盘结果
        """
        try:
            # 统计规则使用情况
            total_rules = KnowledgeRule.query.count()
            active_rules = KnowledgeRule.query.filter_by(status='active').count()

            # 统计自动提取的规则
            auto_extracted = KnowledgeRule.query.filter_by(is_auto_extracted=True).count()

            # 统计待审核的提取记录
            pending_extractions = RuleExtractionLog.query.filter_by(status='pending').count()

            # 找出使用次数少或成功率低的规则
            low_usage_rules = KnowledgeRule.query.filter(
                KnowledgeRule.usage_count < 5,
                KnowledgeRule.is_auto_extracted == True
            ).limit(10).all()

            return {
                'total_rules': total_rules,
                'active_rules': active_rules,
                'auto_extracted_rules': auto_extracted,
                'pending_extractions': pending_extractions,
                'low_usage_rules': [
                    {
                        'id': r.id,
                        'title': r.rule_title,
                        'usage_count': r.usage_count,
                        'success_rate': r.success_rate
                    }
                    for r in low_usage_rules
                ]
            }
        except Exception as e:
            logger.error(f"定期复盘失败: {e}")
            return {'error': str(e)}

    def update_rule_usage(self, rule_id: int, success: bool = True):
        """更新规则使用统计"""
        try:
            rule = KnowledgeRule.query.get(rule_id)
            if rule:
                rule.usage_count = (rule.usage_count or 0) + 1
                if success:
                    if rule.success_rate is None:
                        rule.success_rate = 1.0
                    else:
                        rule.success_rate = (rule.success_rate * (rule.usage_count - 1) + 1.0) / rule.usage_count
                db.session.commit()
        except Exception as e:
            logger.error(f"更新规则使用统计失败: {e}")
            db.session.rollback()


# 全局实例
_rule_extractor = None


def get_rule_extractor() -> RuleExtractor:
    """获取规则提取器实例"""
    global _rule_extractor
    if _rule_extractor is None:
        _rule_extractor = RuleExtractor()
    return _rule_extractor
