#!/usr/bin/env python3
"""
直接测试蓝海分析 API
"""
import sys
import os
import requests
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.skill_bridge import SkillBridge


def test_full_pipeline():
    """执行完整的蓝海分析测试"""
    print("="*60)
    print("蓝海分析实际测试")
    print("="*60)

    bridge = SkillBridge()

    # 执行完整流水线
    start_time = time.time()

    result = bridge.execute_full_pipeline(
        business_description="卖进口奶粉",
        industry="奶粉",
        business_type="b2c",
        content_stage='成长阶段',
    )

    elapsed = time.time() - start_time

    # 打印结果摘要
    print(f"\n执行耗时: {elapsed:.1f}秒")

    # 市场分析结果
    market_result = result.get('market_analyzer')
    if market_result:
        print(f"\n[市场分析] {'✓ 成功' if market_result.success else '✗ 失败'}")
        print(f"  步骤数: {len(market_result.step_results)}")
        for sr in market_result.step_results:
            warnings = len(sr.validation_warnings) if sr.validation_warnings else 0
            print(f"    - {sr.step_id}: {'✓' if sr.success else '✗'} (警告: {warnings})")

    # 关键词库结果
    keyword_result = result.get('keyword_library')
    if keyword_result:
        print(f"\n[关键词库] {'✓ 成功' if keyword_result.success else '✗ 失败'}")
        print(f"  步骤数: {len(keyword_result.step_results)}")
        for sr in keyword_result.step_results:
            warnings = len(sr.validation_warnings) if sr.validation_warnings else 0
            # 检查输出内容
            output_keys = list(sr.output.keys()) if sr.output else []
            print(f"    - {sr.step_id}: {'✓' if sr.success else '✗'} (警告: {warnings}, 输出字段: {len(output_keys)})")

    # 选题库结果
    topic_result = result.get('topic_library')
    if topic_result:
        print(f"\n[选题库] {'✓ 成功' if topic_result.success else '✗ 失败'}")
        print(f"  步骤数: {len(topic_result.step_results)}")
        for sr in topic_result.step_results:
            warnings = len(sr.validation_warnings) if sr.validation_warnings else 0
            output_keys = list(sr.output.keys()) if sr.output else []
            print(f"    - {sr.step_id}: {'✓' if sr.success else '✗'} (警告: {warnings}, 输出字段: {len(output_keys)})")

    # 返回总体状态
    return market_result.success if market_result else False


def test_specific_steps():
    """测试特定步骤的输出长度"""
    print("\n" + "="*60)
    print("检查关键步骤的 raw_output 长度")
    print("="*60)

    bridge = SkillBridge()

    # 只执行关键词库，测试 step_blue_ocean_matrix
    print("\n执行关键词库生成...")

    # 先执行市场分析获取上下文
    market = bridge.execute_market_analyzer(
        business_description="卖进口奶粉",
        industry="奶粉",
        business_type="b2c",
    )

    if market.success:
        # 执行关键词库
        keyword = bridge.execute_keyword_library(
            business_description="卖进口奶粉",
            industry="奶粉",
            business_type="b2c",
            market_analyzer_output=market.full_output,
        )

        # 检查各步骤的 raw_output 长度
        print("\n关键词库各步骤 raw_output 长度:")
        for sr in keyword.step_results:
            raw_len = len(sr.raw_output) if sr.raw_output else 0
            print(f"  - {sr.step_id}: {raw_len} 字符")
            if sr.validation_warnings:
                for w in sr.validation_warnings:
                    print(f"      警告: {w}")


if __name__ == '__main__':
    try:
        success = test_full_pipeline()
        print("\n" + "="*60)
        print("测试完成" + (" - 成功" if success else " - 失败"))
        print("="*60)
    except Exception as e:
        print(f"\n测试异常: {e}")
        import traceback
        traceback.print_exc()
