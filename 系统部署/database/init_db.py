"""
数据库初始化脚本
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.models import db, User, Expert, Skill, KnowledgeCategory, Industry, Channel, Client, Keyword, Topic, Content, Monitor, MonitorReport, ExpertOutput, ChatSession, ChatMessage
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()


def init_database():
    """初始化数据库"""
    with app.app_context():
        # 创建所有表
        db.create_all()
        print("✓ 数据库表创建完成")
        
        # 创建超级管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=bcrypt.generate_password_hash('aaa111').decode('utf-8'),
                role='super_admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ 超级管理员账号创建完成 (admin / aaa111)")
        else:
            # 更新旧admin角色为super_admin
            if admin.role == 'admin':
                admin.role = 'super_admin'
                db.session.commit()
            print("✓ 超级管理员账号已存在")
        
        # 创建默认行业分类
        industries_data = [
            {'name': '食品行业', 'slug': 'food', 'description': '食品生产、销售相关', 'icon': '🍜', 'sort_order': 1},
            {'name': '本地服务', 'slug': 'local_service', 'description': '家政、维修、物流等本地服务', 'icon': '🏠', 'sort_order': 2},
            {'name': '教育培训', 'slug': 'education', 'description': '教育培训相关', 'icon': '📚', 'sort_order': 3},
            {'name': '医疗健康', 'slug': 'health', 'description': '医疗健康相关', 'icon': '🏥', 'sort_order': 4},
            {'name': '零售批发', 'slug': 'retail', 'description': '零售批发相关', 'icon': '🛒', 'sort_order': 5},
            {'name': '其他', 'slug': 'other', 'description': '其他行业', 'icon': '📦', 'sort_order': 99},
        ]
        
        for ind_data in industries_data:
            industry = Industry.query.filter_by(slug=ind_data['slug']).first()
            if not industry:
                industry = Industry(**ind_data)
                db.session.add(industry)
        
        db.session.commit()
        print("✓ 行业分类创建完成")
        
        # 创建默认专家
        experts_data = [
            {
                'name': '总控专家',
                'slug': 'master',
                'nickname': '约瑟夫·库珀',
                'title': '首席营销官',
                'description': '欢迎回来！我协调大局，实时捕捉高价值的跨渠道机会，并将其转给合适的专家。所有专家的最终输出将收集在右侧的面板中，供您查看。',
                'capabilities': ['新客户流程', '客户切换', '资料收集', '专家调度', '方案整合'],
                'command': '/总控',
                'icon': '👨‍🚀',
                'avatar_url': '/static/images/avatars/expert_cooper_avatar.png',
                'sort_order': 1,
                'is_visible': True
            },
            {
                'name': 'AI智能运营专家',
                'slug': 'ai-operations-commander',
                'nickname': '塔斯',
                'title': 'AI智能运营专家',
                'description': 'AI搜索优化、关键词策略、内容发现、市场机会发现、差异化定位、账号设计、运营规划',
                'capabilities': ['关键词库生成', '选题库生成', '运营规划方案', '差异化定位', '账号设计'],
                'command': '/塔斯',
                'icon': '🤖',
                'avatar_url': '/static/images/avatars/expert_tars_avatar.png',
                'sort_order': 3,
                'is_visible': True
            },
            {
                'name': '社交监控和市场洞察分析师',
                'slug': 'monitor',
                'nickname': '艾米莉亚·布兰德',
                'title': '市场洞察分析师',
                'description': '实时监控、舆情分析、竞品追踪、市场洞察、风险预警',
                'capabilities': ['社交监控（监控社交媒体讨论与趋势）', '深入研究（进行深入研究报告）'],
                'command': '/舆情',
                'icon': '👩‍🔬',
                'avatar_url': '/static/images/avatars/expert_brand_avatar.png',
                'sort_order': 2,
                'is_visible': True
            },
            {
                'name': 'Geo SEO 策略师',
                'slug': 'seo',
                'nickname': '墨菲',
                'title': 'Geo SEO 策略师',
                'description': 'AI搜索优化、关键词策略、内容发现、市场机会发现、差异化定位、账号设计',
                'capabilities': ['AI搜索优化', '关键词策略', '内容发现', '关键词库生成', '选题库生成', '市场分析', '账号设计', '运营规划', '差异化定位'],
                'command': '/seo',
                'icon': '👩‍💻',
                'avatar_url': '/static/images/avatars/expert_murph_avatar.png',
                'sort_order': 4,
                'is_visible': True
            },
            {
                'name': '内容创作师',
                'slug': 'content',
                'nickname': '塔斯',
                'title': '内容创作师',
                'description': '图文规划、短视频脚本、封面设计、消费心理分析、视觉设计评审',
                'capabilities': ['图文内容生成', '短视频脚本', '封面设计', '内容优化', '消费心理分析', '文案优化', '视觉设计评审', '9:16比例检查', '排版优化'],
                'command': '/内容',
                'icon': '🤖',
                'avatar_url': '/static/images/avatars/expert_tars_avatar.png',
                'sort_order': 5,
                'is_visible': True
            },
            {
                'name': '知识库专家',
                'slug': 'knowledge',
                'nickname': '伊森亨特',
                'title': '知识库',
                'description': '负责知识库的分类管理、内容存储和检索，支持纯文字/图文/短视频分类管理。',
                'capabilities': ['知识分类管理', '内容存储', '知识检索', '分类维护'],
                'command': '/知识库',
                'icon': '📚',
                'avatar_url': '/static/images/avatars/expert_ethan_avatar.png',
                'sort_order': 6,
                'is_visible': True
            }
        ]
        
        for exp_data in experts_data:
            expert = Expert.query.filter_by(slug=exp_data['slug']).first()
            if not expert:
                expert = Expert(**exp_data)
                expert.is_active = True  # 确保专家是激活状态
                db.session.add(expert)
        
        db.session.commit()
        print("✓ 专家数据创建完成")
        
        # 创建默认知识库分类
        categories_data = [
            {'name': '纯文字类', 'slug': 'pure_text', 'icon': '📄', 'sort_order': 1},
            {'name': '图文类', 'slug': 'graphic', 'icon': '🖼️', 'sort_order': 2},
            {'name': '短视频类', 'slug': 'video', 'icon': '🎬', 'sort_order': 3},
        ]
        
        for cat_data in categories_data:
            category = KnowledgeCategory.query.filter_by(slug=cat_data['slug']).first()
            if not category:
                category = KnowledgeCategory(**cat_data)
                db.session.add(category)
        
        db.session.commit()
        print("✓ 知识库分类创建完成")
        
        print("\n" + "="*50)
        print("数据库初始化完成！")
        print("="*50)
        print("\n默认账号信息：")
        print("  用户名: admin")
        print("  密码: aaa111")
        print("\n请访问 http://localhost:5000 登录管理后台")


if __name__ == '__main__':
    init_database()
