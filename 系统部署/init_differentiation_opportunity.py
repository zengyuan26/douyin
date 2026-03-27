#!/usr/bin/env python3
"""
初始化差异化机会维度数据

在 AnalysisDimension 表中，「超级定位」-「差异化机会」二级分类下新增7个维度：
1. 产品 - 产品细分/规格/包装
2. 方法 - 使用方法/搭配方案
3. 流程 - 购买/交付流程
4. 工具 - 配件/辅助用品
5. 理念 - 价值主张/品牌故事
6. 服务 - 售后/使用指导
7. 场景 - 使用场景细分
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, AnalysisDimension


# 差异化机会维度数据
DIFFERENTIATION_OPPORTUNITY_DIMENSIONS = [
    {
        'name': '产品机会',
        'code': 'sup_diff_product',
        'description': '从产品维度挖掘差异化机会：细分规格、独特包装、产品组合等',
        'icon': 'bi-box-seam',
        'examples': '桶装水→一次性桶装水 | 奶粉→分阶段奶粉 | 家政→深度清洁套餐',
        'usage_tips': '思考：现有产品能否拆分/组合/定制规格？哪些细分规格还没人做？',
        'importance': 5
    },
    {
        'name': '方法机会',
        'code': 'sup_diff_method',
        'description': '从方法维度挖掘差异化机会：使用方式、解决方案、服务方法论',
        'icon': 'bi-lightbulb',
        'examples': '桶装水→企业饮水方案 | 家电清洗→预防性维护方案 | 护肤品→分肤质护理',
        'usage_tips': '思考：不只是卖产品，而是卖解决方案。用户真正需要的是结果，不是工具',
        'importance': 5
    },
    {
        'name': '场景机会',
        'code': 'sup_diff_scenario',
        'description': '从场景维度挖掘差异化机会：细分使用场景、精准场景需求',
        'icon': 'bi-pin-map',
        'examples': '桶装水→健身房更衣室用水 | 家政→新房开荒/老人照护 | 奶粉→断奶期/辅食期',
        'usage_tips': '思考：中国人口基数大，再小的场景也有很多人。找到被大品牌忽略的细分场景',
        'importance': 5
    },
    {
        'name': '流程机会',
        'code': 'sup_diff_process',
        'description': '从流程维度挖掘差异化机会：交付流程、购买流程、服务流程的优化',
        'icon': 'bi-diagram-3',
        'examples': '到店买→送货上门 | 统一配送→定时定量 | 事后维修→事前维护',
        'usage_tips': '思考：用户购买/使用的流程中有哪些不便？能否简化或优化？',
        'importance': 4
    },
    {
        'name': '理念机会',
        'code': 'sup_diff_philosophy',
        'description': '从理念维度挖掘差异化机会：重新定义品类价值、差异化定位、品牌故事',
        'icon': 'bi-gem',
        'examples': '卖水→卖健康饮水理念 | 卖奶粉→宝宝喂养顾问 | 卖家政→家庭健康守护者',
        'usage_tips': '思考：能否用一个新的理念重新定义你的业务？不要只说"卖XX"，而是说"提供XX方案"',
        'importance': 4
    },
    {
        'name': '服务机会',
        'code': 'sup_diff_service',
        'description': '从服务维度挖掘差异化机会：增值服务、延伸服务、售后服务',
        'icon': 'bi-headset',
        'examples': '卖产品→卖使用指导 | 一次性交易→长期顾问 | 产品销售→解决方案服务',
        'usage_tips': '思考：卖产品不如卖服务。产品只是服务的载体，服务才是建立壁垒的关键',
        'importance': 4
    },
    {
        'name': '工具机会',
        'code': 'sup_diff_tool',
        'description': '从工具维度挖掘差异化机会：配套工具、设备升级、辅助用品',
        'icon': 'bi-tools',
        'examples': '桶装水→饮水架+取水器 | 豆浆机→配套豆子套餐 | 家政→专业清洁工具展示',
        'usage_tips': '思考：用户使用产品时需要什么辅助工具？配套工具能否成为差异化卖点？',
        'importance': 3
    },
]


def init_differentiation_opportunity_dimensions():
    """初始化差异化机会维度"""
    with app.app_context():
        created_count = 0
        updated_count = 0

        for item in DIFFERENTIATION_OPPORTUNITY_DIMENSIONS:
            # 检查是否已存在
            exists = AnalysisDimension.query.filter_by(
                category='super_positioning',
                sub_category='differentiation_opportunity',
                name=item['name']
            ).first()

            if exists:
                # 更新已存在的维度
                exists.description = item['description']
                exists.icon = item.get('icon', 'bi-circle')
                exists.examples = item.get('examples', '') or None
                exists.usage_tips = item.get('usage_tips', '') or None
                exists.importance = item.get('importance', 1) or 1
                exists.is_active = True
                updated_count += 1
                print(f"  ~ 更新: {item['name']}")
            else:
                # 创建新维度
                dimension = AnalysisDimension(
                    name=item['name'],
                    code=item['code'],
                    icon=item.get('icon', 'bi-circle'),
                    description=item['description'],
                    category='super_positioning',
                    sub_category='differentiation_opportunity',
                    examples=item.get('examples', '') or None,
                    usage_tips=item.get('usage_tips', '') or None,
                    importance=item.get('importance', 1) or 1,
                    is_active=True,
                    is_default=True
                )
                db.session.add(dimension)
                created_count += 1
                print(f"  + 添加: {item['name']}")

        db.session.commit()
        print(f"\n初始化完成：新增 {created_count} 个，更新 {updated_count} 个差异化机会维度")

        # 显示所有差异化机会维度
        print("\n当前差异化机会维度:")
        dims = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='differentiation_opportunity'
        ).order_by(AnalysisDimension.importance.desc(), AnalysisDimension.id).all()

        for dim in dims:
            stars = '⭐' * dim.importance
            status = '✓' if dim.is_active else '✗'
            print(f"  [{status}] {dim.name} {stars}")


if __name__ == '__main__':
    init_differentiation_opportunity_dimensions()
