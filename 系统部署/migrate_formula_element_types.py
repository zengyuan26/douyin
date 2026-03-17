"""
数据库迁移脚本 - 添加公式要素类型表
用法: python migrate_formula_element_types.py
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models.models import db, FormulaElementType


def run_migration():
    """执行迁移"""
    with app.app_context():
        # 检查表是否已存在
        try:
            # 尝试查询，如果表不存在会报错
            count = FormulaElementType.query.count()
            print(f"表已存在，当前有 {count} 条记录")
            return
        except Exception as e:
            if 'no such table' in str(e).lower():
                print("表不存在，需要创建...")
            else:
                print(f"查询错误: {e}")
                return

        # 创建表
        try:
            db.create_all()
            print("表创建成功!")

            # 初始化默认数据
            init_default_data()
        except Exception as e:
            print(f"创建表失败: {e}")
            db.session.rollback()


def init_default_data():
    """初始化默认要素数据"""
    # 昵称分析要素（9种，移除姓氏因为不应该单独存在）
    nickname_elements = [
        {'name': '产品词', 'code': 'product_word', 'description': '具体产品/服务、业务关键词（最高优先级）', 'examples': 'AI|香肠|茶叶|手机', 'priority': 1, 'usage_tips': '如AI代表AI相关业务、香肠、茶叶、手机'},
        {'name': '身份标签', 'code': 'identity_tag', 'description': '身份/职业', 'examples': '哥|姐|老师|医生|创始人', 'priority': 2, 'usage_tips': '如哥、姐、老师、医生、创始人'},
        {'name': '人设词', 'code': 'persona_word', 'description': '人格化角色/形象', 'examples': '魔女|西施|侠客|公主', 'priority': 3, 'usage_tips': '如魔女、西施、侠客、公主'},
        {'name': '风格词', 'code': 'style_word', 'description': '外观/气质/体型描述', 'examples': '红发|金丝雀|高冷|胖|瘦|矮', 'priority': 4, 'usage_tips': '如红发、金丝雀、高冷、胖、瘦、矮'},
        {'name': '行业词', 'code': 'industry_word', 'description': '行业/技术前缀（仅当无法确定具体产品时使用）', 'examples': '数码|美食|旅游', 'priority': 5, 'usage_tips': '如数码、美食、旅游'},
        {'name': '地域词', 'code': 'region_word', 'description': '地区名称', 'examples': '南漳|北京|上海', 'priority': 6, 'usage_tips': '如南漳、北京、上海'},
        {'name': '属性词', 'code': 'attribute_word', 'description': '品质/特点', 'examples': '手工|野生|正宗', 'priority': 7, 'usage_tips': '如手工、野生、正宗'},
        {'name': '数字词', 'code': 'number_word', 'description': '年份/数量', 'examples': '20年|10年|90年', 'priority': 8, 'usage_tips': '如20年、10年、90年'},
        {'name': '行动词', 'code': 'action_word', 'description': '动作/行为', 'examples': '吃|玩|学', 'priority': 9, 'usage_tips': '如吃、玩、学'},
    ]

    # 简介分析要素（7种）
    bio_elements = [
        {'name': '身份标签', 'code': 'bio_identity', 'description': '职业背景、学历、职称、专业身份', 'examples': '10年大厂PM|苏黎世大学博士|XX创始人|XX专家', 'priority': 1, 'usage_tips': '如10年大厂PM、苏黎世大学博士、XX创始人、XX专家'},
        {'name': '价值主张', 'code': 'bio_value', 'description': '你卖什么产品/服务、提供什么具体价值', 'examples': '专注茶叶20年|只卖正宗XX|专业手工XX', 'priority': 2, 'usage_tips': '如专注茶叶20年、只卖正宗XX、专业手工XX'},
        {'name': '差异化标签', 'code': 'bio_differentiate', 'description': '为什么关注你，你和别人不一样在哪', 'examples': '只讲真话|不割韭菜|0基础也能学', 'priority': 3, 'usage_tips': '如只讲真话、不割韭菜、0基础也能学'},
        {'name': '行动号召', 'code': 'bio_action', 'description': '让粉丝做什么、关注后做什么', 'examples': '关注送XX|扫码领取|私信咨询|到店试吃', 'priority': 4, 'usage_tips': '如关注送XX、扫码领取、私信咨询、到店试吃'},
        {'name': '价格信息', 'code': 'bio_price', 'description': '具体的价格/报价', 'examples': '2.5元/斤|99元/盒', 'priority': 5, 'usage_tips': '如2.5元/斤、99元/盒'},
        {'name': '联系方式', 'code': 'bio_contact', 'description': '联系方式（微信、邮箱、电话等）', 'examples': '+V|扫码|私信', 'priority': 6, 'usage_tips': '如+V、扫码、私信'},
        {'name': '内容要素', 'code': 'bio_content', 'description': '包含哪些内容要素', 'examples': '干货|技巧|避坑', 'priority': 7, 'usage_tips': '如干货、技巧、避坑'},
    ]

    # 插入数据
    created = 0
    for item in nickname_elements:
        # 检查是否已存在
        existing = FormulaElementType.query.filter_by(
            sub_category='nickname_analysis',
            code=item['code']
        ).first()
        if not existing:
            element = FormulaElementType(
                sub_category='nickname_analysis',
                name=item['name'],
                code=item['code'],
                description=item['description'],
                examples=item['examples'],
                priority=item['priority'],
                is_active=True,
                usage_tips=item['usage_tips']
            )
            db.session.add(element)
            created += 1

    for item in bio_elements:
        existing = FormulaElementType.query.filter_by(
            sub_category='bio_analysis',
            code=item['code']
        ).first()
        if not existing:
            element = FormulaElementType(
                sub_category='bio_analysis',
                name=item['name'],
                code=item['code'],
                description=item['description'],
                examples=item['examples'],
                priority=item['priority'],
                is_active=True,
                usage_tips=item['usage_tips']
            )
            db.session.add(element)
            created += 1

    db.session.commit()
    print(f"初始化完成，共创建 {created} 条要素记录")


if __name__ == '__main__':
    run_migration()
