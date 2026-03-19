#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新简介分析要素的区分技巧，解决行动号召和联系方式混淆的问题
直接使用 SQL 更新，无需启动 Flask app
"""
import sqlite3
import os

DB_PATH = '/Volumes/增元/项目/douyin/系统部署/instance/douyin_system.db'

def update_bio_elements():
    """更新简介分析的公式要素"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 更新行动号召 (cta)
    print("=" * 50)
    print("更新行动号召 (cta) 要素")
    print("=" * 50)
    
    # 查看当前
    cursor.execute("""
        SELECT id, name, description, examples, usage_tips 
        FROM formula_element_type 
        WHERE sub_category = 'bio_analysis' AND code = 'cta'
    """)
    row = cursor.fetchone()
    if row:
        print(f"当前:")
        print(f"  - 名称: {row[1]}")
        print(f"  - 描述: {row[2]}")
        print(f"  - 示例: {row[3]}")
        print(f"  - 区分技巧: {row[4]}")
        
        # 更新
        new_examples = '关注送XX|扫码领取|私信咨询|到店试吃|关注我|点我头像'
        new_usage_tips = '【动作指令】引导粉丝做具体动作。关键词：关注、扫码、加微、领取、咨询、到店、私信、点我。注意：只是"提到送东西"但没有明确动作不算CTA，只有"关注送"、"扫码领"等明确动作才算'
        
        cursor.execute("""
            UPDATE formula_element_type 
            SET examples = ?, usage_tips = ?
            WHERE sub_category = 'bio_analysis' AND code = 'cta'
        """, (new_examples, new_usage_tips))
        
        print(f"\n更新后:")
        print(f"  - 示例: {new_examples}")
        print(f"  - 区分技巧: {new_usage_tips}")
    else:
        print("未找到行动号召要素")
    
    # 2. 更新联系方式 (contact)
    print("\n" + "=" * 50)
    print("更新联系方式 (contact) 要素")
    print("=" * 50)
    
    cursor.execute("""
        SELECT id, name, description, examples, usage_tips 
        FROM formula_element_type 
        WHERE sub_category = 'bio_analysis' AND code = 'contact'
    """)
    row = cursor.fetchone()
    if row:
        print(f"当前:")
        print(f"  - 名称: {row[1]}")
        print(f"  - 描述: {row[2]}")
        print(f"  - 示例: {row[3]}")
        print(f"  - 区分技巧: {row[4]}")
        
        # 更新
        new_examples = '微信号|电话|地址|卫星号|VX|+V|关注私信领'
        new_usage_tips = '【可直接联系】明确的联系方式，特点是可以直接加/打/联系。关键词：微信号（wx后直接是数字）、电话（11位数字）、地址（XX路XX号）、卫星号、VX、+V、关注后私信领(有"私信领"三个字才算联系方式)'
        
        cursor.execute("""
            UPDATE formula_element_type 
            SET examples = ?, usage_tips = ?
            WHERE sub_category = 'bio_analysis' AND code = 'contact'
        """, (new_examples, new_usage_tips))
        
        print(f"\n更新后:")
        print(f"  - 示例: {new_examples}")
        print(f"  - 区分技巧: {new_usage_tips}")
    else:
        print("未找到联系方式要素")
    
    # 提交保存
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 50)
    print("✅ 更新完成！")
    print("=" * 50)

if __name__ == '__main__':
    update_bio_elements()
