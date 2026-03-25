#!/usr/bin/env python3
"""测试市场洞察维度筛选"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置 Flask 应用上下文
from app import app
from services.market_insight_filter import MarketInsightFilter

with app.app_context():
    filter = MarketInsightFilter()

    business_info = {
        'business_type': 'product',
        'description': '婴儿奶粉代购，直邮澳洲',
        'keywords': ['奶粉', '婴儿', '代购']
    }

    print("=" * 60)
    print("业务信息:")
    print(f"  业务类型: {business_info['business_type']}")
    print(f"  业务描述: {business_info['description']}")
    print(f"  关键词: {business_info['keywords']}")
    print("=" * 60)

    # 分析业务特征
    features = filter.analyze_business_features(business_info)
    print("\n业务特征分析:")
    for k, v in features.items():
        print(f"  {k}: {v}")
    print("-" * 60)

    # 筛选维度
    dimensions = filter.filter_dimensions(business_info)
    print(f"\n筛选结果: {len(dimensions)} 个相关维度")

    for i, dim in enumerate(dimensions, 1):
        print(f"\n{i}. {dim['name']} (重要性: {'⭐' * dim['importance']})")
        print(f"   代码: {dim['code']}")
        print(f"   内容预览:\n{dim['content'][:100]}...")

    print("\n" + "=" * 60)
    print("完整提示词:")
    print("=" * 60)
    prompt = filter.build_prompt(business_info, dimensions)
    print(prompt)
