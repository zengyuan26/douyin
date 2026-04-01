"""
初始化公开平台模板数据

功能：
1. 将 geo-seo skill 文件中的关键词库/选题库模板导入数据库
2. 初始化预设模板变量
"""

from services.template_config_service import template_config_service
import os


def get_skill_base_path():
    """获取 skill 文件基准路径"""
    return '/Volumes/增元/项目/douyin/系统部署/'


def import_geo_seo_templates():
    """导入 geo-seo skill 中的模板文件"""
    base = get_skill_base_path()

    files = [
        {
            'path': os.path.join(base, 'skills/geo-seo/输出/关键词库/关键词库_模板.md'),
            'type': 'keyword',
            'name': '关键词库_通用_v1',
        },
        {
            'path': os.path.join(base, 'skills/geo-seo/输出/选题推荐/选题库_模板.md'),
            'type': 'topic',
            'name': '选题库_通用_v1',
        },
    ]

    results = []
    for f in files:
        if os.path.exists(f['path']):
            result = template_config_service.import_from_skill_file(
                file_path=f['path'],
                template_type=f['type'],
                template_name=f['name'],
            )
            results.append({
                'file': f['path'],
                'type': f['type'],
                'result': result,
            })
            print(f"  {'✅' if result.get('success') else '❌'} {f['name']}: {result.get('message', result)}")
        else:
            print(f"  ⚠️  文件不存在: {f['path']}")
            results.append({
                'file': f['path'],
                'type': f['type'],
                'result': {'success': False, 'message': '文件不存在'},
            })

    return results


def init_default_variables():
    """初始化预设模板变量"""
    from models.public_models import TemplateVariable, db

    # 关键词库模板变量
    keyword_vars = [
        {'name': '行业', 'label': '行业', 'type': 'text', 'required': True,
         'desc': '所属行业，如：桶装水、餐饮、教育'},
        {'name': '业务描述', 'label': '业务描述', 'type': 'text', 'required': True,
         'desc': '简要描述主营业务'},
        {'name': '产品', 'label': '核心产品', 'type': 'text', 'required': False,
         'desc': '主要产品或服务，多个用逗号分隔'},
        {'name': '地域', 'label': '服务地域', 'type': 'text', 'required': False,
         'desc': '主要服务地区'},
        {'name': '目标客户', 'label': '目标客户', 'type': 'text', 'required': True,
         'desc': '目标客户群体描述'},
        {'name': '目标客户身份', 'label': '客户身份', 'type': 'text', 'required': False,
         'desc': '用户身份特征，如：注重健康的家庭主妇'},
        {'name': '核心痛点', 'label': '核心痛点', 'type': 'text', 'required': False,
         'desc': '目标客户最关心的问题'},
        {'name': '核心顾虑', 'label': '核心顾虑', 'type': 'text', 'required': False,
         'desc': '客户购买前最大的顾虑'},
        {'name': '使用场景', 'label': '使用场景', 'type': 'text', 'required': False,
         'desc': '典型使用场景'},
        # 实时变量（自动注入，无需用户填）
        {'name': '当前季节', 'label': '当前季节', 'type': 'text', 'required': False,
         'desc': '自动注入：春/夏/秋/冬'},
        {'name': '月份名称', 'label': '月份名称', 'type': 'text', 'required': False,
         'desc': '自动注入：如五月/劳动'},
        {'name': '季节消费特点', 'label': '季节消费特点', 'type': 'text', 'required': False,
         'desc': '自动注入：当季消费习惯'},
        {'name': '月度热点前缀', 'label': '月度热点', 'type': 'text', 'required': False,
         'desc': '自动注入：当月热点关键词'},
        {'name': '当前节日', 'label': '当前节日', 'type': 'text', 'required': False,
         'desc': '自动注入：节日名称'},
        {'name': '当前节气', 'label': '当前节气', 'type': 'text', 'required': False,
         'desc': '自动注入：节气名称'},
    ]

    # 选题库模板变量
    topic_vars = [
        {'name': '行业', 'label': '行业', 'type': 'text', 'required': True,
         'desc': '所属行业'},
        {'name': '业务描述', 'label': '业务描述', 'type': 'text', 'required': True,
         'desc': '主营业务描述'},
        {'name': '产品', 'label': '核心产品', 'type': 'text', 'required': False,
         'desc': '主要产品'},
        {'name': '地域', 'label': '服务地域', 'type': 'text', 'required': False,
         'desc': '主要服务地区'},
        {'name': '目标客户', 'label': '目标客户', 'type': 'text', 'required': True,
         'desc': '目标客户群体'},
        {'name': '目标客户身份', 'label': '客户身份', 'type': 'text', 'required': False,
         'desc': '用户身份特征'},
        {'name': '核心痛点', 'label': '核心痛点', 'type': 'text', 'required': False,
         'desc': '用户核心痛点'},
        {'name': '关键词库', 'label': '关键词库', 'type': 'text', 'required': False,
         'desc': '从专属关键词库提取的关键词'},
        # 实时变量
        {'name': '当前季节', 'label': '当前季节', 'type': 'text', 'required': False,
         'desc': '自动注入'},
        {'name': '当前节日', 'label': '当前节日', 'type': 'text', 'required': False,
         'desc': '自动注入'},
        {'name': '月度热点前缀', 'label': '月度热点', 'type': 'text', 'required': False,
         'desc': '自动注入'},
    ]

    all_vars = [
        ('keyword', keyword_vars),
        ('topic', topic_vars),
    ]

    for template_type, vars_list in all_vars:
        for idx, v in enumerate(vars_list):
            # 检查是否已存在
            existing = TemplateVariable.query.filter_by(
                template_type=template_type,
                variable_name=v['name']
            ).first()
            if existing:
                continue

            var = TemplateVariable(
                template_type=template_type,
                variable_name=v['name'],
                variable_label=v['label'],
                variable_type=v['type'],
                description=v['desc'],
                is_required=v.get('required', False),
                display_order=idx,
            )
            db.session.add(var)
            print(f"  ✅ 添加变量: {template_type}.{v['name']}")

    db.session.commit()
    print(f"  变量初始化完成")


def init_keyword_library_config():
    """初始化关键词库分类配置（存储在常量中，供生成器使用）"""
    from services.keyword_library_generator import KeywordLibraryGenerator
    print(f"  关键词库分类配置: {len(KeywordLibraryGenerator.CATEGORIES)} 个分类")
    for cat in KeywordLibraryGenerator.CATEGORIES:
        print(f"    - {cat['name']}（≥{cat['min']}个）")


def init_topic_library_config():
    """初始化选题库分类配置"""
    from services.topic_library_generator import TopicLibraryGenerator
    print(f"  选题库分类配置: {len(TopicLibraryGenerator.TOPIC_TYPES)} 个分类")
    for t in TopicLibraryGenerator.TOPIC_TYPES:
        print(f"    - {t['name']}【{t['priority']}】（来源：{t['source']}）")


def run():
    """执行所有初始化"""
    print("=" * 50)
    print("公开平台模板数据初始化")
    print("=" * 50)

    print("\n📦 1. 导入 geo-seo 模板文件...")
    import_geo_seo_templates()

    print("\n📦 2. 初始化模板变量...")
    init_default_variables()

    print("\n📦 3. 初始化分类配置...")
    init_keyword_library_config()
    init_topic_library_config()

    print("\n✅ 初始化完成！")


if __name__ == '__main__':
    from app import app
    with app.app_context():
        run()
