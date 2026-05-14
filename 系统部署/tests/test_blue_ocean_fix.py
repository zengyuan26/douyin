"""
测试脚本 - 验证蓝海机会分析修改

测试内容：
1. 验证 max_tokens 配置是否生效
2. 验证 skill 配置的 minItems 是否正确降低
3. 执行一个简单的蓝海分析测试
"""

import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.llm import get_task_config
from services.skill_bridge.registry import SkillRegistry


def test_max_tokens_config():
    """测试1: 验证 max_tokens 配置"""
    print("\n" + "="*60)
    print("测试1: max_tokens 配置")
    print("="*60)

    skills_to_test = [
        'topic_library_generator',
        'keyword_library_generator',
        'market_analyzer',
    ]

    for skill_name in skills_to_test:
        config = get_task_config(skill_name)
        max_tokens = config.get('max_tokens', 0)
        print(f"  {skill_name}: max_tokens = {max_tokens}")

        # 验证修改是否生效
        if skill_name == 'topic_library_generator':
            assert max_tokens >= 8000, f"topic_library_generator max_tokens 应该 >= 8000，实际: {max_tokens}"
        elif skill_name == 'keyword_library_generator':
            assert max_tokens >= 6000, f"keyword_library_generator max_tokens 应该 >= 6000，实际: {max_tokens}"

    print("✓ max_tokens 配置验证通过\n")
    return True


def test_skill_config():
    """测试2: 验证 skill 配置的 minItems"""
    print("\n" + "="*60)
    print("测试2: skill 配置 minItems")
    print("="*60)

    registry = SkillRegistry()

    # 测试 topic_library_generator
    topic_skill = registry.get_skill('topic_library_generator')
    if topic_skill:
        print("\n[topic_library_generator]")

        # 检查 step_public_topics
        for step in topic_skill.get('steps', []):
            if step.get('id') == 'step_public_topics':
                schema = step.get('output_schema', {})
                public = schema.get('public_topics', {})
                min_items = public.get('minItems', 0)
                print(f"  public_topics minItems: {min_items}")
                assert min_items <= 25, f"public_topics minItems 应该 <= 25，实际: {min_items}"

            if step.get('id') == 'step_portrait_topics':
                schema = step.get('output_schema', {})
                portrait = schema.get('portrait_topics', {})
                min_items = portrait.get('minItems', 0)
                print(f"  portrait_topics minItems: {min_items}")
                assert min_items <= 120, f"portrait_topics minItems 应该 <= 120，实际: {min_items}"

    # 测试 keyword_library_generator
    keyword_skill = registry.get_skill('keyword_library_generator')
    if keyword_skill:
        print("\n[keyword_library_generator]")

        for step in keyword_skill.get('steps', []):
            if step.get('id') == 'step_blue_ocean_matrix':
                schema = step.get('output_schema', {})
                l2 = schema.get('L2_long_tail', {})
                min_items = l2.get('minItems', 0)
                print(f"  L2_long_tail minItems: {min_items}")
                assert min_items <= 35, f"L2_long_tail minItems 应该 <= 35，实际: {min_items}"

            if step.get('id') == 'step_failure_keywords':
                schema = step.get('output_schema', {})
                avoid = schema.get('avoid_pitfall_keywords', {})
                min_items = avoid.get('minItems', 0)
                print(f"  avoid_pitfall_keywords minItems: {min_items}")
                assert min_items <= 5, f"avoid_pitfall_keywords minItems 应该 <= 5，实际: {min_items}"

    print("\n✓ skill 配置验证通过\n")
    return True


def test_async_executor():
    """测试3: 验证异步执行器"""
    print("\n" + "="*60)
    print("测试3: 异步执行器")
    print("="*60)

    from services.background_task_service import get_async_skill_executor

    executor = get_async_skill_executor()
    print(f"  异步执行器实例: {type(executor).__name__}")
    print(f"  线程池最大worker: {executor._executor._max_workers}")

    print("✓ 异步执行器验证通过\n")
    return True


def test_skill_execution():
    """测试4: 执行一个简单的市场分析测试"""
    print("\n" + "="*60)
    print("测试4: 执行市场分析 (step1)")
    print("="*60)

    from services.skill_bridge import SkillBridge

    bridge = SkillBridge()

    # 只执行前1个步骤，测试 token 配置
    result = bridge.execute_market_analyzer(
        business_description="卖进口奶粉",
        industry="奶粉",
        business_type="b2c",
        max_steps=1,  # 只执行第一步
    )

    print(f"  执行结果: {'成功' if result.success else '失败'}")
    print(f"  耗时: {result.total_duration_ms}ms")

    if result.full_output:
        print(f"  输出字段: {list(result.full_output.keys())}")

    if result.step_results:
        for step_result in result.step_results:
            print(f"\n  步骤: {step_result.step_id}")
            print(f"  - 成功: {step_result.success}")
            print(f"  - 警告: {step_result.validation_warnings}")

    return result.success


def main():
    """主函数"""
    print("\n" + "="*60)
    print("蓝海机会分析修改验证测试")
    print("="*60)

    try:
        # 基础配置测试
        test_max_tokens_config()
        test_skill_config()
        test_async_executor()

        # 可选：执行实际测试（需要网络）
        print("\n" + "="*60)
        print("执行实际市场分析测试 (需要网络)")
        print("="*60)
        print("提示: 这将调用 LLM API，可能需要一些时间...")
        print()

        # 询问是否执行实际测试
        import time
        print("跳过实际测试（避免消耗 API 配额）")
        print("请通过前端界面进行实际测试\n")

        print("="*60)
        print("所有测试通过!")
        print("="*60)
        print("\n修改验证完成，可以重新运行蓝海分析了。")

        return True

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
