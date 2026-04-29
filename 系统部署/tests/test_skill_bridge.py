"""
SkillBridge 系统测试用例

测试覆盖：
1. SkillRegistry - 配置加载
2. SkillExecutor - 技能执行
3. SkillBridge - 业务API
4. DataMapper - 数据映射
"""

import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_registry_loading():
    """测试1: SkillRegistry 配置加载"""
    print("\n" + "="*60)
    print("测试1: SkillRegistry 配置加载")
    print("="*60)

    from services.skill_bridge.registry import SkillRegistry

    registry = SkillRegistry()

    # 测试列出所有skill
    skills = registry.list_skills()
    print(f"✓ 已加载的Skills: {len(skills)} 个")
    for s in skills:
        print(f"  - {s}")

    assert len(skills) > 0, "应该有至少一个skill"
    print(f"✓ 共 {len(skills)} 个skill加载成功\n")

    # 测试获取skill元信息
    for skill_name in ['market_analyzer', 'content_generator', 'title_generator']:
        meta = registry.get_skill_meta(skill_name)
        if meta:
            print(f"✓ {skill_name}: {meta.get('display_name', 'N/A')}")
        else:
            print(f"✗ {skill_name}: 未找到")

    return True


def test_bridge_api():
    """测试2: SkillBridge API方法"""
    print("\n" + "="*60)
    print("测试2: SkillBridge API方法")
    print("="*60)

    from services.skill_bridge import SkillBridge

    bridge = SkillBridge()

    # 测试list_skills
    skills = bridge.list_skills()
    print(f"✓ Bridge.list_skills(): {len(skills)} 个skills")

    # 测试get_skill_info
    for skill_name in ['market_analyzer', 'keyword_library_generator', 'topic_library_generator']:
        info = bridge.get_skill_info(skill_name)
        if info:
            print(f"✓ {skill_name}: {info.get('display_name', 'N/A')}")
        else:
            print(f"✗ {skill_name}: 未找到")

    # 测试get_skill_steps
    steps = bridge.get_skill_steps('market_analyzer')
    print(f"✓ market_analyzer 步骤数: {len(steps)}")
    for step in steps[:3]:
        print(f"  - {step.get('id', 'N/A')}: {step.get('name', 'N/A')}")

    return True


def test_data_mapper():
    """测试3: DataMapper 数据映射"""
    print("\n" + "="*60)
    print("测试3: DataMapper 数据映射")
    print("="*60)

    from services.skill_bridge.data_mapper import DataMapper
    from services.skill_bridge.registry import SkillRegistry

    registry = SkillRegistry()
    mapper = DataMapper(registry)

    # 测试点号路径get
    test_data = {
        "step3_audience_segment": {
            "paying_equals_using": "企业采购者",
            "segments": ["CEO", "CTO"]
        },
        "step6_search_journey": {
            "keywords": ["人工智能", "AI客服"]
        }
    }

    val = mapper.get_nested(test_data, "step3_audience_segment.paying_equals_using")
    print(f"✓ get_nested: {val}")
    assert val == "企业采购者", f"期望'企业采购者', 实际{val}"

    val2 = mapper.get_nested(test_data, "step6_search_journey.keywords")
    print(f"✓ get_nested(list): {val2}")
    assert val2 == ["人工智能", "AI客服"]

    # 测试点号路径set
    new_data = {}
    mapper.set_nested(new_data, "test.nested.value", "success")
    print(f"✓ set_nested: {new_data}")
    assert new_data == {"test": {"nested": {"value": "success"}}}

    # 测试跨skill数据流映射
    market_output = {
        "step3_audience_segment": {
            "paying_equals_using": "高三家长",
            "segments": ["爸爸", "妈妈", "考生本人"]
        },
        "step6_search_journey": {
            "keywords": ["高考志愿", "医学专业"]
        }
    }

    mapped = mapper.map_output_to_input(
        from_skill="market_analyzer",
        output_data=market_output,
        to_skill="keyword_library_generator"
    )
    print(f"✓ 数据流映射结果: {json.dumps(mapped, ensure_ascii=False, indent=2)}")

    return True


def test_skill_templates():
    """测试4: Skill模板文件"""
    print("\n" + "="*60)
    print("测试4: Skill模板文件")
    print("="*60)

    templates_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "services", "skill_bridge", "skill_templates"
    )

    # 检查目录是否存在
    assert os.path.exists(templates_dir), f"模板目录不存在: {templates_dir}"
    print(f"✓ 模板目录存在: {templates_dir}")

    # 检查index.json
    index_path = os.path.join(templates_dir, "index.json")
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
        print(f"✓ index.json: {len(index.get('templates', []))} 个模板")
        for t in index.get('templates', []):
            print(f"  - {t.get('id')}: {t.get('name')}")
    else:
        print(f"✗ index.json 不存在")

    # 检查子目录
    for subdir in ['graphic', 'long_text', 'video', 'examples']:
        subdir_path = os.path.join(templates_dir, subdir)
        if os.path.exists(subdir_path):
            files = os.listdir(subdir_path)
            print(f"✓ {subdir}/: {len(files)} 个文件")
        else:
            print(f"✗ {subdir}/ 不存在")

    return True


def test_topic_generator_skill_mode():
    """测试5: TopicGenerator skill_mode参数"""
    print("\n" + "="*60)
    print("测试5: TopicGenerator skill_mode参数")
    print("="*60)

    from services.topic_generator import TopicGenerator
    import inspect

    gen = TopicGenerator()

    # 检查skill_mode参数是否存在
    sig = inspect.signature(gen.generate_topics)
    params = list(sig.parameters.keys())
    print(f"✓ generate_topics 参数: {params}")

    assert 'skill_mode' in params, "应该有skill_mode参数"
    print("✓ skill_mode 参数存在")

    return True


def test_config_json():
    """测试6: Skill配置文件验证"""
    print("\n" + "="*60)
    print("测试6: Skill配置文件验证")
    print("="*60)

    config_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "services", "skill_bridge", "config"
    )

    required_configs = [
        'market_analyzer.json',
        'keyword_library_generator.json',
        'topic_library_generator.json',
        'portrait_generator.json',
        'content_generator.json',
        'long_text_generator.json',
        'video_script_generator.json',
        'title_generator.json',
        'tag_generator.json',
    ]

    all_valid = True
    for config_file in required_configs:
        path = os.path.join(config_dir, config_file)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                skill_name = data.get('skill', {}).get('name', 'N/A')
                steps = data.get('steps', [])
                print(f"✓ {config_file}: {skill_name}, {len(steps)} 步骤")
            except json.JSONDecodeError as e:
                print(f"✗ {config_file}: JSON解析错误 - {e}")
                all_valid = False
        else:
            print(f"✗ {config_file}: 不存在")
            all_valid = False

    return all_valid


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print("# SkillBridge 系统测试")
    print("#"*60)

    tests = [
        ("配置加载", test_registry_loading),
        ("Bridge API", test_bridge_api),
        ("数据映射", test_data_mapper),
        ("Skill模板", test_skill_templates),
        ("TopicGenerator", test_topic_generator_skill_mode),
        ("配置文件", test_config_json),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "✓ PASS" if result else "✗ FAIL"))
        except Exception as e:
            print(f"\n✗ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"✗ ERROR: {e}"))

    # 汇总
    print("\n" + "="*60)
    print("测试汇总")
    print("="*60)
    for name, result in results:
        print(f"{result}  {name}")

    passed = sum(1 for _, r in results if "PASS" in r)
    print(f"\n通过: {passed}/{len(results)}")

    return all("PASS" in r for _, r in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
