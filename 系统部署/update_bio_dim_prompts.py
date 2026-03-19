#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新简介分析维度的 prompt_template 字段
"""
import sqlite3

DB_PATH = '/Volumes/增元/项目/douyin/系统部署/instance/douyin_system.db'

# 每个维度的详细分析说明（prompt_template）
bio_dim_prompts = {
    'bio_identity': {
        'section': '''### 维度: {code} ({name})
- 是否有身份标签 (has_identity): true/false
- 身份内容 (identity): 具体身份描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "has_identity": true,
        "identity": "XX品牌创始人",
        "score": 85,
        "reason": "包含明确身份标签",
        "conclusion": "身份明确，有专业背书"
    }}'''
    },
    'bio_value': {
        'section': '''### 维度: {code} ({name})
- 是否有价值主张 (has_value): true/false
- 价值主张内容 (value_proposition): 具体价值描述
- 清晰度 (clarity): 高/中/低
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "has_value": true,
        "value_proposition": "专注茶叶20年",
        "clarity": "高",
        "score": 80,
        "reason": "价值主张清晰",
        "conclusion": "明确传达核心价值"
    }}'''
    },
    'bio_differentiate': {
        'section': '''### 维度: {code} ({name})
- 是否有差异化 (has_differentiation): true/false
- 差异化内容 (differentiation): 具体差异化描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "has_differentiation": true,
        "differentiation": "XX第一人",
        "score": 75,
        "reason": "有差异化但不够突出",
        "conclusion": "具备一定差异化"
    }}'''
    },
    'bio_action': {
        'section': '''### 维度: {code} ({name})
- 是否有行动号召 (has_cta): true/false
- 行动号召内容 (cta_content): 具体的行动号召内容
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "has_cta": true,
        "cta_content": "关注后私信领取",
        "score": 70,
        "reason": "有行动号召但不够明确",
        "conclusion": "有引导意识"
    }}'''
    },
    'bio_structure': {
        'section': '''### 维度: {code} ({name})
- 是否有结构 (has_structure): true/false
- 有联系方式 (has_contact): true/false
- 有价值主张 (has_value_proposition): true/false
- 有行动号召 (has_cta): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "has_structure": true,
        "has_contact": false,
        "has_value_proposition": true,
        "has_cta": true,
        "score": 80,
        "reason": "结构清晰有价值主张",
        "conclusion": "结构完整，缺少联系方式"
    }}'''
    },
    'bio_content': {
        'section': '''### 维度: {code} ({name})
- 内容要素 (content_elements): 包含的内容要素列表
- 有差异化 (has_differentiation): true/false
- 有明确报价 (has_clear_offer): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "content_elements": ["身份标签", "价值主张"],
        "has_differentiation": true,
        "has_clear_offer": false,
        "score": 75,
        "reason": "有身份和价值主张",
        "conclusion": "内容要素基本完整"
    }}'''
    },
    'bio_advantage': {
        'section': '''### 维度: {code} ({name})
- 优点 (advantages): 简介有哪些优点
- 改进点 (improvements): 简介有哪些可以改进的地方
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结''',
        'json_example': '''    "{code}": {{
        "advantages": ["结构清晰", "价值主张明确"],
        "improvements": ["缺少联系方式"],
        "score": 70,
        "reason": "整体不错但缺少联系方式",
        "conclusion": "有提升空间，建议添加联系方式"
    }}'''
    }
}

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("更新 bio_analysis 维度的 prompt_template 字段...")
    
    for code, prompt_data in bio_dim_prompts.items():
        # 使用 | 分隔 section 和 json_example
        template_value = prompt_data['section'] + '|' + prompt_data['json_example']
        
        cursor.execute("""
            UPDATE analysis_dimensions 
            SET prompt_template = ?
            WHERE sub_category = 'bio_analysis' AND code = ?
        """, (template_value, code))
        
        print(f"  更新: {code}")
    
    conn.commit()
    
    # 验证
    print("\n验证更新结果:")
    cursor.execute("SELECT code, name, prompt_template FROM analysis_dimensions WHERE sub_category = 'bio_analysis' ORDER BY sort_order")
    for row in cursor.fetchall():
        has_template = "有" if row[2] else "空"
        print(f"  - {row[0]} ({row[1]}): prompt_template {has_template}")
    
    conn.close()
    print("\n✅ 更新完成!")

if __name__ == '__main__':
    main()
