#!/usr/bin/env python3
"""
短视频脚本生成系统 - 功能测试脚本

运行方式:
    cd /Volumes/增元/项目/douyin/系统部署
    python3 tests/run_script_tests.py
"""

import sys
import os
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试数据
TEST_PORTRAIT_DATA = {
    "name": "小李土特产店",
    "industry": "食品",
    "org_type": "个体工商户",
    "tags": ["特产", "农产品", "家乡"],
    "description": "卖家乡土特产，有故事有情怀"
}

TEST_SCRIPT_GOOD = {
    "title": "这款山核桃太好吃了！",
    "opening": "你知道吗？这款山核桃，竟然藏着一个300年的秘密！",
    "scenes": [
        {"narration": "我叫小李，在山里收了20年核桃", "subtitle_text": "20年坚守"},
        {"narration": "你知道吗？很多人买核桃都选错了！今天教你3招分辨好核桃", "subtitle_text": "3招分辨"},
        {"narration": "第一招，看颜色，青皮核桃才是新鲜的；第二招，闻味道，有自然果香才是好核桃", "subtitle_text": "两招辨别"},
        {"narration": "觉得有用吗？评论区告诉我你买核桃踩过什么坑？", "subtitle_text": "评论区见"}
    ],
    "narration": "你知道吗？这款山核桃，竟然藏着一个300年的秘密！..."
}

TEST_SCRIPT_BAD = {
    "title": "产品介绍",
    "scenes": [{"narration": "这是一个产品"}]
}


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def run(self, name, test_func):
        """运行单个测试"""
        try:
            result = test_func()
            self.passed += 1
            status = "✅ PASS"
            self.results.append((name, status, str(result) if result else ""))
        except Exception as e:
            self.failed += 1
            status = f"❌ FAIL: {e}"
            self.results.append((name, status, ""))
            print(f"  ❌ {name}: {e}")

    def summary(self):
        """打印总结"""
        print("\n" + "=" * 60)
        print(f"测试结果: {self.passed} 通过, {self.failed} 失败")
        print("=" * 60)

        if self.failed == 0:
            print("🎉 所有测试通过!")
        else:
            print(f"⚠️  {self.failed} 个测试失败")


def test_score_good_script(runner):
    """测试优质脚本评分"""
    from services.script_scorer import ScriptScorer, TrustSourceType

    scorer = ScriptScorer()
    report = scorer.score(TEST_SCRIPT_GOOD, TrustSourceType.PERSONA)

    assert report.total_score > 0, "总分应该大于0"
    assert 0 <= report.emotion_score <= 100, "情绪分应在0-100之间"

    return f"总分={report.total_score:.1f}, 等级={report.grade}"


def test_score_bad_script(runner):
    """测试劣质脚本评分"""
    from services.script_scorer import ScriptScorer, TrustSourceType

    scorer = ScriptScorer()
    report = scorer.score(TEST_SCRIPT_BAD, TrustSourceType.PERSONA)

    assert report.total_score >= 0, "总分应该>=0"
    assert len(report.suggestions) > 0, "应该有优化建议"

    return f"总分={report.total_score:.1f}, 等级={report.grade}"


def test_classify_persona_type(runner):
    """测试人设型分类"""
    from services.business_classifier import BusinessClassifier

    classifier = BusinessClassifier()
    result = classifier.classify({
        "name": "家乡土特产",
        "industry": "食品",
        "description": "有故事有情怀的农产品"
    })

    assert result.trust_source.value in ["persona", "knowledge"], "应该是人设型或知识型"
    assert result.confidence > 0, "置信度应该>0"

    return f"信任来源={result.trust_source.value}, 置信度={result.confidence:.2f}"


def test_classify_institution_type(runner):
    """测试机构型分类"""
    from services.business_classifier import BusinessClassifier

    classifier = BusinessClassifier()
    result = classifier.classify({
        "name": "XX知名品牌",
        "org_type": "知名企业",
        "description": "全国连锁知名品牌"
    })

    assert result.trust_source.value == "institution", "应该是机构型"

    return f"信任来源={result.trust_source.value}"


def test_classify_knowledge_type(runner):
    """测试知识型分类"""
    from services.business_classifier import BusinessClassifier

    classifier = BusinessClassifier()
    result = classifier.classify({
        "name": "教育培训",
        "industry": "教育",
        "description": "专业技能培训"
    })

    assert result.trust_source.value == "knowledge", "应该是知识型"

    return f"信任来源={result.trust_source.value}"


def test_reward_point_calculation(runner):
    """测试奖励点计算"""
    from services.reward_point_system import RewardPointService

    service = RewardPointService()
    result = service.calculate(60, {"奖励分布": 0.8})

    assert result["total_points"] >= 1, "至少应该有1个奖励点"
    assert len(result["points"]) > 0, "应该有奖励点列表"

    return f"总点数={result['total_points']}"


def test_template_library(runner):
    """测试模板库"""
    from services.script_template import get_template_library

    library = get_template_library()
    templates = library.list_all()

    assert len(templates) >= 10, "应该有至少10个模板"

    return f"模板数量={len(templates)}"


def test_ip_config_presets(runner):
    """测试IP配置预设"""
    from services.ip_persona_manager import IPConfigManager

    manager = IPConfigManager()
    presets = manager.list_presets()

    assert len(presets) >= 3, "至少有3个预设"

    return f"IP预设数量={len(presets)}"


def test_api_health_check():
    """测试健康检查API"""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/script/health')
        data = json.loads(response.data)

        assert response.status_code == 200, "健康检查应该返回200"
        assert data.get('success') == True, "应该返回成功"

        return f"modules={list(data.get('modules', {}).keys())}"


def test_api_balance_presets():
    """测试均衡器预设API"""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/script/balance-presets')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) >= 6, "应该有至少6个预设"

        return f"预设数量={len(data.get('data', []))}"


def test_api_topic_types():
    """测试选题类型API"""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/script/topic-types')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True

        return f"类型数量={len(data.get('data', []))}"


def test_api_templates():
    """测试模板API"""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/script/templates')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True

        return f"模板数量={len(data.get('data', []))}"


def test_api_ip_configs():
    """测试IP配置API"""
    from app import app

    with app.test_client() as client:
        response = client.get('/api/script/ip-configs')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True

        return f"IP配置数量={len(data.get('data', []))}"


def test_api_score_script():
    """测试脚本评分API"""
    from app import app

    with app.test_client() as client:
        response = client.post(
            '/api/script/score',
            json={
                "script": TEST_SCRIPT_GOOD,
                "trust_source": "persona"
            },
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'total_score' in data['data']

        return f"总分={data['data']['total_score']}"


def test_api_classify_business():
    """测试业务分类API"""
    from app import app

    with app.test_client() as client:
        response = client.post(
            '/api/script/classify',
            json=TEST_PORTRAIT_DATA,
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'trust_source' in data['data']

        return f"信任来源={data['data']['trust_source']}"


def test_api_reward_preview():
    """测试奖励点预览API"""
    from app import app

    with app.test_client() as client:
        response = client.post(
            '/api/script/reward-preview',
            json={
                "duration": 60,
                "balance_config": {"奖励分布": 0.8}
            },
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'total_points' in data['data']

        return f"奖励点={data['data']['total_points']}"


def test_api_balance_recommend():
    """测试均衡器推荐API"""
    from app import app

    with app.test_client() as client:
        response = client.post(
            '/api/script/balance-recommend',
            json={
                "trust_source": "persona",
                "topic_type": "人设价值观类"
            },
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'config' in data['data']

        return f"推荐配置项={len(data['data']['config'])}"


def test_full_workflow():
    """测试完整工作流程"""
    from services.script_scorer import ScriptScorer, TrustSourceType
    from services.business_classifier import BusinessClassifier
    from services.reward_point_system import RewardPointService
    from services.script_template import get_template_library

    # 1. 业务分类
    classifier = BusinessClassifier()
    classify_result = classifier.classify(TEST_PORTRAIT_DATA)

    # 2. 获取模板
    library = get_template_library()
    templates = library.list_all()

    # 3. 计算奖励点
    reward_service = RewardPointService()
    reward_result = reward_service.calculate(60, {"奖励分布": 0.7})

    # 4. 评分
    scorer = ScriptScorer()
    score_result = scorer.score(TEST_SCRIPT_GOOD, TrustSourceType.PERSONA)

    return f"分类={classify_result.trust_source.value}, 模板={len(templates)}, 奖励点={reward_result['total_points']}, 评分={score_result.total_score:.1f}"


def main():
    """主函数"""
    print("=" * 60)
    print("短视频脚本生成系统 - 功能测试")
    print("=" * 60)
    print()

    runner = TestRunner()

    # 单元测试
    print("📦 单元测试")
    print("-" * 40)

    runner.run("评分-优质脚本", lambda: test_score_good_script(runner))
    runner.run("评分-劣质脚本", lambda: test_score_bad_script(runner))
    runner.run("分类-人设型", lambda: test_classify_persona_type(runner))
    runner.run("分类-机构型", lambda: test_classify_institution_type(runner))
    runner.run("分类-知识型", lambda: test_classify_knowledge_type(runner))
    runner.run("奖励点计算", lambda: test_reward_point_calculation(runner))
    runner.run("模板库", lambda: test_template_library(runner))
    runner.run("IP配置预设", lambda: test_ip_config_presets(runner))

    print()

    # API测试
    print("🌐 API测试")
    print("-" * 40)

    runner.run("健康检查", test_api_health_check)
    runner.run("均衡器预设", test_api_balance_presets)
    runner.run("选题类型", test_api_topic_types)
    runner.run("模板列表", test_api_templates)
    runner.run("IP配置", test_api_ip_configs)
    runner.run("脚本评分", test_api_score_script)
    runner.run("业务分类", test_api_classify_business)
    runner.run("奖励点预览", test_api_reward_preview)
    runner.run("均衡器推荐", test_api_balance_recommend)

    print()

    # 集成测试
    print("🔗 集成测试")
    print("-" * 40)

    runner.run("完整工作流程", test_full_workflow)

    # 打印总结
    print()
    runner.summary()

    # 详细结果
    print("\n详细结果:")
    for name, status, detail in runner.results:
        print(f"  {status} {name}")
        if detail:
            print(f"      {detail}")

    # 返回退出码
    return 0 if runner.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
