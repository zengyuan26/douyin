#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在数据库中补充简介分析的维度配置
"""
import sqlite3

DB_PATH = '/Volumes/增元/项目/douyin/系统部署/instance/douyin_system.db'

# 要添加的简介分析维度（和代码里硬编码的 7 个维度对应）
bio_dimensions = [
    {
        'code': 'bio_identity',
        'name': '身份标签',
        'description': '是否有身份标签（如：XX创始人、XX专家）',
        'prompt_template': '''- 是否有身份标签 (has_identity): true/false
- 身份内容 (identity): 具体身份描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 1
    },
    {
        'code': 'bio_value',
        'name': '价值主张',
        'description': '是否有价值主张（如：专注XX年、只做XX）',
        'prompt_template': '''- 是否有价值主张 (has_value): true/false
- 价值主张内容 (value_proposition): 具体价值描述
- 清晰度 (clarity): 高/中/低
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 2
    },
    {
        'code': 'bio_differentiate',
        'name': '差异化标签',
        'description': '是否有差异化标签（如：XX第一人、XX冠军）',
        'prompt_template': '''- 是否有差异化 (has_differentiation): true/false
- 差异化内容 (differentiation): 具体差异化描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 3
    },
    {
        'code': 'bio_action',
        'name': '行动号召',
        'description': '是否有行动号召（如：+V、扫码等）',
        'prompt_template': '''- 是否有行动号召 (has_cta): true/false
- 行动号召内容 (cta_content): 具体的行动号召内容
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 4
    },
    {
        'code': 'bio_structure',
        'name': '结构分析',
        'description': '是否有清晰结构：身份+价值+差异化+行动号召',
        'prompt_template': '''- 是否有结构 (has_structure): true/false
- 有联系方式 (has_contact): true/false
- 有价值主张 (has_value_proposition): true/false
- 有行动号召 (has_cta): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 5
    },
    {
        'code': 'bio_content',
        'name': '内容要素',
        'description': '包含哪些内容要素',
        'prompt_template': '''- 内容要素 (content_elements): 包含的内容要素列表
- 有差异化 (has_differentiation): true/false
- 有明确报价 (has_clear_offer): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 6
    },
    {
        'code': 'bio_advantage',
        'name': '优点总结',
        'description': '简介有哪些优点和可改进点',
        'prompt_template': '''- 优点 (advantages): 简介有哪些优点
- 改进点 (improvements): 简介有哪些可以改进的地方
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'sort_order': 7
    }
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否已存在
    cursor.execute("SELECT code FROM analysis_dimensions WHERE sub_category = 'bio_analysis' AND code = ?", 
                  (bio_dimensions[0]['code'],))
    exists = cursor.fetchone()
    
    if exists:
        print("数据库中已存在 bio_analysis 维度，检查现有数据:")
        cursor.execute("SELECT code, name FROM analysis_dimensions WHERE sub_category = 'bio_analysis' ORDER BY sort_order")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}")
        
        # 检查是否有 prompt_template
        print("\n检查 prompt_template 字段:")
        cursor.execute("SELECT code, prompt_template FROM analysis_dimensions WHERE sub_category = 'bio_analysis'")
        for row in cursor.fetchall():
            has_template = "有" if row[1] else "空"
            print(f"  - {row[0]}: {has_template}")
    else:
        print("开始添加 bio_analysis 维度...")
        
        for dim in bio_dimensions:
            cursor.execute("""
                INSERT INTO analysis_dimensions 
                (code, name, description, prompt_template, category, sub_category, sort_order, is_active, is_default)
                VALUES (?, ?, ?, ?, 'account', 'bio_analysis', ?, 1, 1)
            """, (dim['code'], dim['name'], dim['description'], dim['prompt_template'], dim['sort_order']))
            print(f"  添加: {dim['code']} - {dim['name']}")
        
        conn.commit()
        print("\n✅ 添加完成!")
    
    conn.close()

if __name__ == '__main__':
    main()
