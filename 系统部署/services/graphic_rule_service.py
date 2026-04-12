"""
图文内容规则服务
提供从数据库加载图文规则配置的接口
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GraphicRuleService:
    """图文规则服务"""

    _cache = {}  # 简单内存缓存

    @classmethod
    def get_active_rule(cls, industry: str = None, portrait_id: int = None) -> Optional[Dict[str, Any]]:
        """获取当前生效的图文规则"""
        cache_key = f"{industry}_{portrait_id}"

        # 检查缓存（5分钟）
        if cache_key in cls._cache:
            cached = cls._cache[cache_key]
            import time
            if time.time() - cached['cached_at'] < 300:
                return cached['data']

        try:
            # 延迟导入避免循环依赖
            from migrations.add_graphic_rules import (
                GraphicContentRule, ImageTemplateRule, HeadlineRule,
                DesignRule, SeoRule, PublishRule
            )
            from models.models import db

            # 查找匹配的规则
            rule = None
            if industry:
                rule = GraphicContentRule.query.filter_by(
                    industry=industry, is_active=True
                ).first()

            # 如果没有匹配的行业规则，使用默认规则
            if not rule:
                rule = GraphicContentRule.query.filter_by(
                    is_default=True, is_active=True
                ).first()

            # 如果还是没有，查找任意激活的规则
            if not rule:
                rule = GraphicContentRule.query.filter_by(is_active=True).first()

            if not rule:
                logger.warning("未找到生效的图文规则")
                return None

            # 获取关联数据
            image_templates = ImageTemplateRule.query.filter_by(
                rule_id=rule.id
            ).order_by(ImageTemplateRule.image_index).all()

            headline_rules = HeadlineRule.query.filter_by(rule_id=rule.id).all()
            design_rules = DesignRule.query.filter_by(rule_id=rule.id).all()
            seo_rule = SeoRule.query.filter_by(rule_id=rule.id).first()
            publish_rule = PublishRule.query.filter_by(rule_id=rule.id).first()

            result = {
                'id': rule.id,
                'rule_name': rule.rule_name,
                'industry': rule.industry,
                'image_count': rule.image_count,
                'image_ratio': rule.image_ratio,
                'structure_type': rule.structure_type,
                'image_templates': [{
                    'image_index': t.image_index,
                    'positioning': t.positioning,
                    'emotion': t.emotion,
                    'function': t.function,
                    'headline_requirement': t.headline_requirement,
                    'must_pain_first': t.must_pain_first,
                } for t in image_templates],
                'headline_rules': [{
                    'headline_type': h.headline_type,
                    'type_name': h.type_name,
                    'char_min': h.char_min,
                    'char_max': h.char_max,
                    'position_requirement': h.position_requirement,
                    'function_desc': h.function_desc,
                    'is_required': h.is_required,
                } for h in headline_rules],
                'design_rules': {d.design_type: d.config_data for d in design_rules},
                'seo_rule': {
                    'tag_count': seo_rule.tag_count if seo_rule else 6,
                    'tag_types': seo_rule.tag_types if seo_rule else {},
                    'keyword_types': seo_rule.keyword_types if seo_rule else {},
                } if seo_rule else None,
                'publish_rule': {
                    'schedule_config': publish_rule.schedule_config if publish_rule else [],
                    'compliance_checklist': publish_rule.compliance_checklist if publish_rule else [],
                } if publish_rule else None,
            }

            # 缓存结果
            import time
            cls._cache[cache_key] = {
                'data': result,
                'cached_at': time.time()
            }

            return result

        except Exception as e:
            logger.error(f"获取图文规则失败: {e}")
            return None

    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        cls._cache = {}

    @classmethod
    def build_rule_context(cls, rule: Dict[str, Any]) -> str:
        """将规则配置构建为提示词上下文"""
        if not rule:
            return ""

        context_parts = []

        # 图片模板
        img_templates = rule.get('image_templates', [])
        if img_templates:
            context_parts.append("【图片内容规范】")
            for tpl in img_templates:
                idx = tpl.get('image_index', '')
                pos = tpl.get('positioning', '')
                emotion = tpl.get('emotion', '')
                func = tpl.get('function', '')
                headline_req = tpl.get('headline_requirement', '')

                context_parts.append(f"图片{idx}：定位={pos}，情绪={emotion}，功能={func}")
                if headline_req:
                    context_parts.append(f"  大字要求：{headline_req}")

        # 大字金句规范
        hl_rules = rule.get('headline_rules', [])
        if hl_rules:
            context_parts.append("\n【大字金句规范】")
            for hl in hl_rules:
                name = hl.get('type_name', '')
                char_min = hl.get('char_min', '')
                char_max = hl.get('char_max', '')
                position = hl.get('position_requirement', '')
                desc = hl.get('function_desc', '')

                context_parts.append(f"{name}：{char_min}-{char_max}字，位置={position}，作用={desc}")

        # 设计规格
        design_rules = rule.get('design_rules', {})
        if design_rules:
            context_parts.append("\n【设计规格】")
            if 'color_scheme' in design_rules:
                colors = design_rules['color_scheme']
                color_str = "、".join([f"{k}({v})" for k, v in colors.items() if v])
                if color_str:
                    context_parts.append(f"色彩方案：{color_str}")

            if 'font' in design_rules:
                fonts = design_rules['font']
                if fonts.get('允许'):
                    context_parts.append(f"允许字体：{', '.join(fonts['允许'])}")
                if fonts.get('禁止'):
                    context_parts.append(f"禁止字体：{', '.join(fonts['禁止'])}")

            if 'forbidden' in design_rules:
                forbid = design_rules['forbidden']
                if forbid:
                    context_parts.append(f"禁止项：{', '.join(forbid)}")

        # SEO规则
        seo = rule.get('seo_rule')
        if seo:
            context_parts.append("\n【SEO标签规则】")
            context_parts.append(f"标签数量：{seo.get('tag_count', 6)}")
            tag_types = seo.get('tag_types', {})
            if tag_types:
                enabled_types = [k for k, v in tag_types.items() if v]
                context_parts.append(f"标签类型：{', '.join(enabled_types)}")

        return "\n".join(context_parts)


# 全局实例
graphic_rule_service = GraphicRuleService()
