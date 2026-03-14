#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
昵称分析维度数据初始化脚本
初始化昵称分析的4个分析维度
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db, AnalysisDimension


# 昵称分析维度数据
NICKNAME_ANALYSIS_DIMENSIONS = [
    {
        'name': '核心关键词检测',
        'code': 'nickname_keyword',
        'icon': 'bi-key',
        'description': '检测昵称中是否包含行业关键词、产品关键词、地域关键词、品牌关键词等',
        'category': 'account',
        'sub_category': 'nickname_analysis',
        'category_group': 'account',
        'related_material_type': None,
        'rule_category': 'operation',
        'rule_type': 'account_design_nickname',
        'is_active': True,
        'is_default': True,
        'sort_order': 1
    },
    {
        'name': '易记性分析',
        'code': 'nickname_memorability',
        'icon': 'bi-memory',
        'description': '分析昵称的字符长度、重复字符、规律性、是否易读易记',
        'category': 'account',
        'sub_category': 'nickname_analysis',
        'category_group': 'account',
        'related_material_type': None,
        'rule_category': 'operation',
        'rule_type': 'account_design_nickname',
        'is_active': True,
        'is_default': True,
        'sort_order': 2
    },
    {
        'name': '特征分析',
        'code': 'nickname_feature',
        'icon': 'bi-person-badge',
        'description': '分析昵称中包含的身体特征、情绪特征、专业特征、人设特征',
        'category': 'account',
        'sub_category': 'nickname_analysis',
        'category_group': 'account',
        'related_material_type': None,
        'rule_category': 'operation',
        'rule_type': 'account_design_nickname',
        'is_active': True,
        'is_default': True,
        'sort_order': 3
    },
    {
        'name': '优点总结',
        'code': 'nickname_advantage',
        'icon': 'bi-star',
        'description': '总结昵称的优点，如节奏感、押韵、结构、画面感等',
        'category': 'account',
        'sub_category': 'nickname_analysis',
        'category_group': 'account',
        'related_material_type': None,
        'rule_category': 'operation',
        'rule_type': 'account_design_nickname',
        'is_active': True,
        'is_default': True,
        'sort_order': 4
    },
]


def run_migration():
    """执行迁移"""
    with app.app_context():
        try:
            # 检查是否已存在
            existing = AnalysisDimension.query.filter_by(
                code='nickname_keyword'
            ).first()
            if existing:
                print("昵称分析维度已存在，跳过")
                return

            # 批量创建
            for dim_data in NICKNAME_ANALYSIS_DIMENSIONS:
                dim = AnalysisDimension(**dim_data)
                db.session.add(dim)

            db.session.commit()
            print(f"成功创建 {len(NICKNAME_ANALYSIS_DIMENSIONS)} 个昵称分析维度")

        except Exception as e:
            db.session.rollback()
            print(f"迁移失败: {e}")
            raise


if __name__ == '__main__':
    run_migration()
