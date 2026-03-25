#!/usr/bin/env python3
"""初始化市场洞察维度数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, AnalysisDimension
from services.market_insight_filter import get_default_dimensions


def init_market_insight_dimensions():
    """初始化市场洞察维度"""
    with app.app_context():
        created_count = 0

        for item in get_default_dimensions():
            # 检查是否已存在
            exists = AnalysisDimension.query.filter_by(
                category='super_positioning',
                sub_category='market_insight',
                name=item['name']
            ).first()

            if not exists:
                # 生成唯一编码
                import re
                import hashlib
                name_str = item['name']
                # 用名称的hash生成唯一后缀
                hash_suffix = hashlib.md5(name_str.encode()).hexdigest()[:6]
                base_code = 'sup_mar_' + hash_suffix

                # 确保编码唯一
                existing_codes = [d.code for d in AnalysisDimension.query.filter(
                    AnalysisDimension.code.like('sup_mar_%')
                ).all()]
                code = base_code
                counter = 1
                while code in existing_codes:
                    code = f"{base_code}_{counter}"
                    counter += 1

                dimension = AnalysisDimension(
                    name=item['name'],
                    code=code,
                    icon=item.get('icon', 'bi-circle'),
                    description=item.get('description', ''),
                    category='super_positioning',
                    sub_category='market_insight',
                    examples=item.get('examples', '') or None,
                    usage_tips=item.get('usage_tips', ''),
                    applicable_audience=item.get('applicable_audience', '') or None,
                    trigger_conditions=item.get('trigger_conditions', {}) or {},
                    content_template=item.get('content_template', '') or None,
                    importance=item.get('importance', 1) or 1,
                    is_active=True,
                    is_default=True
                )
                db.session.add(dimension)
                created_count += 1
                print(f"  + 添加: {item['name']}")

        db.session.commit()
        print(f"\n初始化完成，共创建 {created_count} 个市场洞察维度")

        # 显示所有市场洞察维度
        print("\n当前市场洞察维度:")
        dims = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='market_insight'
        ).all()

        for dim in dims:
            stars = '⭐' * dim.importance
            print(f"  - {dim.name} {stars}")


if __name__ == '__main__':
    init_market_insight_dimensions()
