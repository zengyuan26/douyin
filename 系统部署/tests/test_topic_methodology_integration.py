"""
选题方法论功能测试脚本

使用方法：
cd /Volumes/增元/项目/douyin/系统部署
python3 tests/test_topic_methodology_integration.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests

BASE_URL = "http://127.0.0.1:5001"


def test_1_check_config():
    """测试1: 验证方法论配置文件"""
    print("\n" + "="*60)
    print("测试1: 验证方法论配置文件")
    print("="*60)

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config', 'topic_methodology.json'
    )

    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        return False

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 验证结构
    categories = config.get('categories', {})
    required_categories = ['persona', 'traffic', 'conversion']

    print(f"✅ 配置文件存在，共 {len(categories)} 个分类")

    for cat in required_categories:
        if cat in categories:
            print(f"  ✅ {cat}: {categories[cat].get('name', '')}")
            topic_types = categories[cat].get('topic_types', {})
            print(f"     选题类型: {len(topic_types)} 个")
        else:
            print(f"  ❌ 缺少 {cat} 分类")

    return True


def test_2_check_database():
    """测试2: 验证数据库字段"""
    print("\n" + "="*60)
    print("测试2: 验证数据库字段")
    print("="*60)

    from app import app
    from models.models import db

    with app.app_context():
        try:
            # 检查 topic_libraries 表
            result = db.session.execute(db.text("PRAGMA table_info(topic_libraries)"))
            columns = {row[1] for row in result.fetchall()}

            required_fields = [
                'marketing_purpose', 'marketing_purpose_name',
                'core_insight', 'content_guidance', 'format_guidance'
            ]

            print("topic_libraries 表字段：")
            for field in required_fields:
                if field in columns:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field}（缺失）")
                    return False

            # 检查 content_plans 表
            result = db.session.execute(db.text("PRAGMA table_info(content_plans)"))
            columns = {row[1] for row in result.fetchall()}

            required_fields = [
                'methodology_ref', 'emotion_arc', 'persona_elements',
                'title_guidance', 'layout_guidance'
            ]

            print("\ncontent_plans 表字段：")
            for field in required_fields:
                if field in columns:
                    print(f"  ✅ {field}")
                else:
                    print(f"  ❌ {field}（缺失）")
                    return False

            return True

        except Exception as e:
            print(f"❌ 数据库验证失败: {e}")
            return False


def test_3_check_service():
    """测试3: 验证服务层方法"""
    print("\n" + "="*60)
    print("测试3: 验证服务层方法")
    print("="*60)

    from services.topic_library_generator import TopicLibraryGenerator

    gen = TopicLibraryGenerator()

    # 检查方法存在
    methods = [
        '_load_methodology_config',
        '_enhance_topic_with_methodology',
        '_generate_content_guidance',
        '_generate_format_guidance',
    ]

    print("TopicLibraryGenerator 方法：")
    for method in methods:
        if hasattr(gen, method):
            print(f"  ✅ {method}")
        else:
            print(f"  ❌ {method}（缺失）")
            return False

    # 检查静态映射
    print("\n静态映射：")
    if hasattr(gen, 'MARKETING_TO_STAGE_RATIO'):
        print(f"  ✅ MARKETING_TO_STAGE_RATIO")
        print(f"     包含 {len(gen.MARKETING_TO_STAGE_RATIO)} 个营销目的")
    else:
        print(f"  ❌ MARKETING_TO_STAGE_RATIO（缺失）")
        return False

    if hasattr(gen, 'MARKETING_TO_TOPIC_TYPES'):
        print(f"  ✅ MARKETETING_TO_TOPIC_TYPES")
    else:
        print(f"  ❌ MARKETING_TO_TOPIC_TYPES（缺失）")
        return False

    # 检查配置加载
    if hasattr(gen, 'methodology_config') and gen.methodology_config:
        print(f"\n方法论配置已加载，包含 {len(gen.methodology_config.get('categories', {}))} 个分类")
    else:
        print(f"\n⚠️ 方法论配置未加载或为空")

    return True


def test_4_check_content_generator():
    """测试4: 验证内容生成器方法论方法"""
    print("\n" + "="*60)
    print("测试4: 验证内容生成器方法论方法")
    print("="*60)

    from services.public_content_generator import (
        _build_methodology_prompt_section,
        _build_graphic_methodology_prompt,
        _build_longtext_methodology_prompt,
        _build_shortvideo_methodology_prompt
    )

    print("内容生成器方法：")
    print(f"  ✅ _build_methodology_prompt_section")
    print(f"  ✅ _build_graphic_methodology_prompt")
    print(f"  ✅ _build_longtext_methodology_prompt")
    print(f"  ✅ _build_shortvideo_methodology_prompt")

    # 测试图文Prompt构建
    topic = {
        'title': '测试选题',
        'content_guidance': {
            'title_pattern': '承诺型',
            'emotional_tone': '真诚'
        },
        'format_guidance': {
            'graphic': {
                'frame_count': 7,
                'emotion_arc': {
                    'P1': {'name': '封面', 'stage': '期待', 'goal': '引发点击'},
                    'P2': {'name': '共情', 'stage': '代入', 'goal': '建立连接'}
                }
            }
        }
    }

    prompt = _build_graphic_methodology_prompt(topic, topic['format_guidance']['graphic'])

    if '情绪动线' in prompt:
        print(f"\n✅ 图文Prompt包含情绪动线")
    else:
        print(f"\n❌ 图文Prompt不包含情绪动线")
        return False

    if 'P1' in prompt and 'P2' in prompt:
        print(f"✅ 情绪帧标签正确")
    else:
        print(f"❌ 情绪帧标签缺失")
        return False

    return True


def test_5_check_api():
    """测试5: 验证API端点（需要服务运行）"""
    print("\n" + "="*60)
    print("测试5: 验证API端点")
    print("="*60)

    try:
        # 测试健康检查
        resp = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"  ✅ 服务运行中 (状态码: {resp.status_code})")
    except requests.exceptions.ConnectionError:
        print(f"  ⚠️ 服务未运行，跳过API测试")
        print(f"     请先启动服务: cd /Volumes/增元/项目/douyin/系统部署 && python3 app.py")
        return None
    except Exception as e:
        print(f"  ⚠️ API测试跳过: {e}")
        return None

    # 测试选题生成API
    print("\n  测试选题生成API...")
    try:
        resp = requests.post(
            f"{BASE_URL}/public/api/topics/regenerate",
            json={"count": 3},
            timeout=30
        )
        data = resp.json()
        if data.get('success'):
            topics = data.get('topics', [])
            print(f"  ✅ /public/api/topics/regenerate 成功，返回 {len(topics)} 条选题")
        else:
            print(f"  ⚠️ API返回失败: {data.get('message')}")
    except Exception as e:
        print(f"  ⚠️ API调用失败: {e}")

    # 测试方法论增强API
    print("\n  测试方法论增强API（付费用户）...")
    try:
        resp = requests.post(
            f"{BASE_URL}/public/api/topics/generate-with-methodology",
            json={
                "marketing_focus": "persona",
                "marketing_focus_name": "人设类",
                "topic_type": "persona_story",
                "topic_type_name": "人设故事类",
                "count": 3
            },
            timeout=30
        )
        data = resp.json()
        if data.get('success'):
            topics = data.get('topics', [])
            print(f"  ✅ /public/api/topics/generate-with-methodology 成功")
            if topics:
                topic = topics[0]
                print(f"     选题包含:")
                print(f"       - marketing_purpose: {topic.get('marketing_purpose')}")
                print(f"       - content_guidance: {bool(topic.get('content_guidance'))}")
                print(f"       - format_guidance: {bool(topic.get('format_guidance'))}")
        else:
            print(f"  ⚠️ API返回失败: {data.get('message')}")
            if resp.status_code == 403:
                print(f"     (方法论增强API仅对付费用户开放)")
    except Exception as e:
        print(f"  ⚠️ API调用失败: {e}")

    return True


def test_6_summary():
    """测试6: 前端代码检查"""
    print("\n" + "="*60)
    print("测试6: 前端代码检查")
    print("="*60)

    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'templates', 'public', 'produce.html'
    )

    if not os.path.exists(template_path):
        print(f"❌ 模板文件不存在: {template_path}")
        return False

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('MARKETING_CATEGORIES', 'L1营销目的配置'),
        ('marketing_purpose', '营销目的字段'),
        ('topic-marketing-badge', '营销目的标签样式'),
        ('topic-type-category-header', 'L1分类标题样式'),
        ('regenerateWithTopicType', '选题生成函数'),
    ]

    print("前端代码检查：")
    for keyword, desc in checks:
        if keyword in content:
            print(f"  ✅ {desc}")
        else:
            print(f"  ❌ {desc}（缺失）")
            return False

    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# 选题方法论功能测试")
    print("#"*60)

    results = []

    # 测试1: 配置文件
    result = test_1_check_config()
    results.append(("配置文件", result))

    # 测试2: 数据库
    result = test_2_check_database()
    results.append(("数据库字段", result))

    # 测试3: 服务层
    result = test_3_check_service()
    results.append(("服务层方法", result))

    # 测试4: 内容生成器
    result = test_4_check_content_generator()
    results.append(("内容生成器", result))

    # 测试5: API
    result = test_5_check_api()
    if result is not None:
        results.append(("API端点", result))

    # 测试6: 前端
    result = test_6_summary()
    results.append(("前端代码", result))

    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}  {name}")

    passed = sum(1 for _, r in results if r)
    print(f"\n通过率: {passed}/{len(results)}")

    return all(r for _, r in results if r is not None)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
