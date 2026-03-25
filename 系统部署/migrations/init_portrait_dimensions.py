#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
迁移：为画像维度添加新的分类数据

画像维度体系：
1. 矛盾类型（conflict_type）- 缺失型、拥有型、冲突型、替代型、减少型
2. 转变类型（transformation_type）- 坏→好、无→有、差→好、旧→新、少→多、高→低、闲置→激活
3. 转变障碍（transformation_barrier）- 内在/他人/环境的各种障碍
4. 买用关系（buyer_user_relationship）- 买用一体、保护型、孝心型、责任型
5. 内容类型（content_type）- 科普、教程、对比、推荐、背书、案例、安慰、促销
6. 意图阶段（intent_stage）- 问题感知、信息搜索、方案评估、购买决策、购买后
7. 风险维度（risk_dimension）- 风险厌恶、财务风险、健康风险、机会风险
8. 效率维度（efficiency_dimension）- 时间敏感度、效率需求
9. 情感维度（emotional_dimension）- 焦虑型、内疚型、成就型、归属型、安全感型
10. 社交维度（social_dimension）- 社交证明、圈层特征、影响力类型

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
python migrations/init_portrait_dimensions.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, AnalysisDimension
from services.portrait_dimension_data import PORTRAIT_DIMENSIONS_DATA


# 画像维度默认数据
PORTRAIT_DIMENSIONS = PORTRAIT_DIMENSIONS_DATA


def _generate_dimension_code(name: str, category: str, sub_category: str = None) -> str:
    """生成维度编码"""
    import re
    # 取拼音首字母
    pinyin_map = {
        '缺': 'que', '失': 'shi', '拥': 'yong', '有': 'you',
        '冲': 'chong', '突': 'tu', '替': 'ti', '代': 'dai',
        '减': 'jian', '少': 'shao', '坏': 'huai', '好': 'hao',
        '无': 'wu', '旧': 'jiu', '新': 'xin', '高': 'gao',
        '低': 'di', '闲': 'xian', '置': 'zhi', '激': 'ji',
        '活': 'huo', '模': 'mo', '糊': 'hu', '清': 'qing',
        '晰': 'xi', '认': 'ren', '知': 'zhi', '资': 'zi',
        '源': 'yuan', '决': 'jue', '策': 'ce', '心': 'xin',
        '理': 'li', '代': 'dai', '理': 'li', '焦': 'jiao',
        '虑': 'lv', '反': 'fan', '对': 'dui', '口': 'kou',
        '碑': 'bei', '分': 'fen', '歧': 'qi', '社': 'she',
        '交': 'jiao', '压': 'ya', '力': 'li', '权': 'quan',
        '威': 'wei', '影': 'ying', '响': 'xiang', '渠': 'qu',
        '道': 'dao', '时': 'shi', '间': 'jian', '条': 'tiao',
        '件': 'jian', '沉': 'chen', '没': 'mo', '成': 'cheng',
        '本': 'ben', '转': 'zhuan', '变': 'bian', '前': 'qian',
        '中': 'zhong', '后': 'hou', '买': 'mai', '用': 'yong',
        '一': 'yi', '体': 'ti', '保': 'bao', '护': 'hu',
        '孝': 'xiao', '心': 'xin', '责': 'ze', '任': 'ren',
        '科': 'ke', '普': 'pu', '教': 'jiao', '程': 'cheng',
        '对': 'dui', '比': 'bi', '推': 'tui', '荐': 'jian',
        '背': 'bei', '书': 'shu', '案': 'an', '例': 'li',
        '安': 'an', '慰': 'wei', '促': 'cu', '销': 'xiao',
        '问': 'wen', '题': 'ti', '感': 'gan', '知': 'zhi',
        '搜': 'sou', '索': 'suo', '评': 'ping', '估': 'gu',
        '决': 'jue', '购': 'gou', '买': 'mai', '意': 'yi',
        '图': 'tu', '阶': 'jie', '段': 'duan', '风': 'feng',
        '险': 'yan', '厌': 'yan', '恶': 'e', '财': 'cai',
        '务': 'wu', '健': 'jian', '康': 'kang', '机': 'ji',
        '会': 'hui', '效': 'xiao', '率': 'lv', '时': 'shi',
        '间': 'jian', '敏': 'min', '感': 'gan', '投': 'tou',
        '入': 'ru', '情': 'qing', '感': 'gan', '焦': 'jiao',
        '虑': 'lv', '内': 'nei', '疚': 'jiu', '成': 'cheng',
        '就': 'jiu', '归': 'gui', '属': 'shu', '安': 'an',
        '全': 'quan', '同': 'tong', '类': 'lei', '专': 'zhuan',
        '家': 'jia', '大': 'da', '众': 'zhong', '熟': 'shu',
        '人': 'ren', '受': 'shou', '圈': 'quan', '层': 'ceng',
    }
    
    # 取第一个字
    first_char = name[0] if name else ''
    pinyin = pinyin_map.get(first_char, first_char)
    
    base_code = f"{category[:4]}_{pinyin}"
    code = re.sub(r'[^a-z0-9_]', '', base_code.lower())
    
    # 查重并追加数字
    existing = AnalysisDimension.query.filter(
        AnalysisDimension.code.like(f'{code}%')
    ).all()
    if existing:
        code = f"{code}_{len(existing) + 1}"
    
    return code


def migrate():
    """执行迁移"""
    with app.app_context():
        created_count = 0
        skip_count = 0
        
        for item in PORTRAIT_DIMENSIONS:
            # 检查是否已存在（按 category + sub_category + name 判断）
            exists = AnalysisDimension.query.filter_by(
                category=item['category'],
                sub_category=item['sub_category'],
                name=item['name']
            ).first()
            
            if exists:
                skip_count += 1
                print(f"[SKIP] 已存在: {item['category']}/{item['sub_category']}/{item['name']}")
                continue
            
            # 自动生成编码
            code = _generate_dimension_code(
                name=item['name'],
                category=item['category'],
                sub_category=item.get('sub_category')
            )
            
            dimension = AnalysisDimension(
                name=item['name'],
                code=code,
                icon=item.get('icon', 'bi-circle'),
                description=item.get('description', ''),
                category=item['category'],
                sub_category=item.get('sub_category'),
                examples=item.get('examples', '') or None,
                usage_tips=item.get('usage_tips', '') or None,
                applicable_audience=item.get('applicable_audience', '') or None,
                prompt_template=item.get('prompt_template', '') or None,
                is_active=True,
                is_default=True,
                importance=item.get('importance', 1) or 1
            )
            db.session.add(dimension)
            created_count += 1
            print(f"[OK] 创建: {item['category']}/{item['sub_category']}/{item['name']}")
        
        db.session.commit()
        print(f"\n迁移完成！创建 {created_count} 个维度，跳过 {skip_count} 个已存在的维度")


if __name__ == '__main__':
    migrate()
