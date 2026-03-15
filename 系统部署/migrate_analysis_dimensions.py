#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析维度数据初始化脚本
初始化默认的分析维度数据
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db, AnalysisDimension


# 默认分析维度数据
DEFAULT_DIMENSIONS = [
    # 账号分析维度
    {
        'name': '账号定位',
        'code': 'account_positioning',
        'icon': 'bi-person-badge',
        'description': '分析账号的定位策略，包括昵称、个人简介、头像、背景图等元素的设计思路',
        'category': 'account',
        'sub_category': 'account_positioning',
        'category_group': 'account',
        'related_material_type': None,
        'is_active': True,
        'is_default': True,
        'sort_order': 1
    },
    {
        'name': '目标人群',
        'code': 'target_audience',
        'icon': 'bi-people',
        'description': '分析目标人群画像，包括年龄、性别、职业、兴趣等特征',
        'category': 'account',
        'sub_category': 'market_analysis',
        'category_group': 'account',
        'related_material_type': None,
        'is_active': True,
        'is_default': True,
        'sort_order': 2
    },
    {
        'name': '核心关键词',
        'code': 'core_keywords',
        'icon': 'bi-key',
        'description': '分析账号的核心关键词和长尾关键词策略',
        'category': 'account',
        'sub_category': 'keyword_library',
        'category_group': 'account',
        'related_material_type': 'tags',
        'is_active': True,
        'is_default': True,
        'sort_order': 3
    },
    {
        'name': '内容策略',
        'code': 'content_strategy',
        'icon': 'bi-journal-text',
        'description': '分析账号的内容规划、发布频率、内容形式等策略',
        'category': 'account',
        'sub_category': 'operation_planning',
        'category_group': 'account',
        'related_material_type': None,
        'is_active': True,
        'is_default': True,
        'sort_order': 4
    },

    # 内容分析维度
    {
        'name': '标题',
        'code': 'title',
        'icon': 'bi-card-heading',
        'description': '分析标题的撰写技巧，包括结构、关键词、情绪词等',
        'category': 'content',
        'sub_category': 'title',
        'category_group': 'content',
        'related_material_type': 'title',
        'is_active': True,
        'is_default': True,
        'sort_order': 10
    },
    {
        'name': '开头钩子',
        'code': 'hook',
        'icon': 'bi-lightning',
        'description': '分析视频/内容开头的钩子设计，悬念型、痛点型、收益型等',
        'category': 'content',
        'sub_category': 'hook',
        'category_group': 'content',
        'related_material_type': 'hook',
        'is_active': True,
        'is_default': True,
        'sort_order': 11
    },
    {
        'name': '封面',
        'code': 'cover',
        'icon': 'bi-image',
        'description': '分析封面的设计技巧，包括构图、配色、文字等',
        'category': 'content',
        'sub_category': 'visual_design',
        'category_group': 'content',
        'related_material_type': 'cover',
        'is_active': True,
        'is_default': True,
        'sort_order': 12
    },
    {
        'name': '选题',
        'code': 'topic',
        'icon': 'bi-lightbulb',
        'description': '分析选题的方向和逻辑，热门话题、痛点需求等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'topic',
        'is_active': True,
        'is_default': True,
        'sort_order': 13
    },
    {
        'name': '内容结构',
        'code': 'content',
        'icon': 'bi-text-paragraph',
        'description': '分析内容的框架结构、逻辑顺序、节奏把控',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'structure',
        'is_active': True,
        'is_default': True,
        'sort_order': 14
    },
    {
        'name': '情绪',
        'code': 'emotion',
        'icon': 'bi-heart',
        'description': '分析内容中的情绪渲染技巧，如何引发用户情感共鸣',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'psychology',
        'is_active': True,
        'is_default': False,
        'sort_order': 15
    },
    {
        'name': '节奏',
        'code': 'rhythm',
        'icon': 'bi-speedometer2',
        'description': '分析内容的节奏把控，包括快节奏、慢节奏、起伏设计',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': None,
        'is_active': True,
        'is_default': False,
        'sort_order': 16
    },
    {
        'name': '心理',
        'code': 'psychology',
        'icon': 'bi-brain',
        'description': '分析内容运用的消费心理学原理，如恐惧、贪婪、从众等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'psychology',
        'is_active': True,
        'is_default': True,
        'sort_order': 17
    },
    {
        'name': '商业',
        'code': 'commercial',
        'icon': 'bi-currency-dollar',
        'description': '分析商业变现模式，如种草、带货、品牌宣传等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'commercial',
        'is_active': True,
        'is_default': True,
        'sort_order': 18
    },
    {
        'name': '爆款',
        'code': 'why_popular',
        'icon': 'bi-fire',
        'description': '分析内容成为爆款的原因和规律',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'why_popular',
        'is_active': True,
        'is_default': True,
        'sort_order': 19
    },
    {
        'name': '结尾',
        'code': 'ending',
        'icon': 'bi-flag',
        'description': '分析结尾的行动号召设计，引导互动和转化',
        'category': 'content',
        'sub_category': 'ending',
        'category_group': 'content',
        'related_material_type': 'ending',
        'is_active': True,
        'is_default': True,
        'sort_order': 20
    },
    {
        'name': '标签',
        'code': 'tags',
        'icon': 'bi-tags',
        'description': '分析内容标签的设置技巧，话题、关键词等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'tags',
        'is_active': True,
        'is_default': False,
        'sort_order': 21
    },
    {
        'name': '人物',
        'code': 'character',
        'icon': 'bi-person',
        'description': '分析人物形象设计，人设、角色、语气等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'character',
        'is_active': True,
        'is_default': False,
        'sort_order': 22
    },
    {
        'name': '形式',
        'code': 'content_form',
        'icon': 'bi-layout-text-window-reverse',
        'description': '分析内容形式，口播、剧情、Vlog、测评等',
        'category': 'content',
        'sub_category': 'visual_design',
        'category_group': 'content',
        'related_material_type': 'content_form',
        'is_active': True,
        'is_default': False,
        'sort_order': 23
    },
    {
        'name': '互动',
        'code': 'interaction',
        'icon': 'bi-chat-dots',
        'description': '分析互动设计，问答、投票、挑战等',
        'category': 'content',
        'sub_category': 'content_body',
        'category_group': 'content',
        'related_material_type': 'interaction',
        'is_active': True,
        'is_default': False,
        'sort_order': 24
    },

    # 方法论维度
    {
        'name': '适用场景',
        'code': 'applicable_scenario',
        'icon': 'bi-geo-alt',
        'description': '方法论的适用场景，如职场、生活、学习等',
        'category': 'methodology',
        'sub_category': 'applicable_scenario',
        'category_group': 'methodology',
        'related_material_type': None,
        'is_active': True,
        'is_default': True,
        'sort_order': 30
    },
    {
        'name': '适用人群',
        'code': 'applicable_audience',
        'icon': 'bi-person-check',
        'description': '方法论的目标人群，如白领、宝爸、学生等',
        'category': 'methodology',
        'sub_category': 'applicable_audience',
        'category_group': 'methodology',
        'related_material_type': None,
        'is_active': True,
        'is_default': True,
        'sort_order': 31
    }
]


def init_dimensions():
    """初始化分析维度数据"""
    with app.app_context():
        # 检查是否已有数据
        existing_count = AnalysisDimension.query.count()
        if existing_count > 0:
            print(f"数据库中已有 {existing_count} 个分析维度，跳过初始化。")
            print("如需重新初始化，请先清空 analysis_dimensions 表。")
            return

        # 插入默认维度
        for dim_data in DEFAULT_DIMENSIONS:
            dimension = AnalysisDimension(**dim_data)
            db.session.add(dimension)

        db.session.commit()
        print(f"成功初始化 {len(DEFAULT_DIMENSIONS)} 个分析维度。")


def clear_dimensions():
    """清空分析维度数据"""
    with app.app_context():
        count = AnalysisDimension.query.delete()
        db.session.commit()
        print(f"已清空 {count} 个分析维度。")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='分析维度数据初始化脚本')
    parser.add_argument('--clear', action='store_true', help='清空现有数据')

    args = parser.parse_args()

    if args.clear:
        confirm = input("确定要清空所有分析维度数据吗？此操作不可恢复！(y/n): ")
        if confirm.lower() == 'y':
            clear_dimensions()
        else:
            print("取消操作。")
    else:
        init_dimensions()
