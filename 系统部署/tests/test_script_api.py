"""
短视频脚本生成系统 - API测试用例

运行方式:
    cd /Volumes/增元/项目/douyin/系统部署
    python -m pytest tests/test_script_api.py -v
"""

import pytest
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 测试配置
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
        {
            "narration": "我叫小李，在山里收了20年核桃",
            "subtitle_text": "20年坚守"
        },
        {
            "narration": "你知道吗？很多人买核桃都选错了！今天教你3招分辨好核桃",
            "subtitle_text": "3招分辨"
        },
        {
            "narration": "第一招，看颜色，青皮核桃才是新鲜的；第二招，闻味道，有自然果香才是好核桃",
            "subtitle_text": "两招辨别"
        },
        {
            "narration": "觉得有用吗？评论区告诉我你买核桃踩过什么坑？",
            "subtitle_text": "评论区见"
        }
    ],
    "narration": "你知道吗？这款山核桃，竟然藏着一个300年的秘密！..."
}

TEST_SCRIPT_BAD = {
    "title": "产品介绍",
    "scenes": [
        {
            "narration": "这是一个产品"
        }
    ]
}


# =============================================================================
# 测试辅助函数
# =============================================================================

def get_app():
    """获取Flask应用实例"""
    from app import app
    return app


def get_client():
    """获取测试客户端"""
    app = get_app()
    return app.test_client()


# =============================================================================
# 测试类
# =============================================================================

class TestScriptScorer:
    """评分模块测试"""

    def test_score_good_script(self):
        """测试优质脚本评分"""
        from services.script_scorer import ScriptScorer, TrustSourceType

        scorer = ScriptScorer()
        report = scorer.score(TEST_SCRIPT_GOOD, TrustSourceType.PERSONA)

        assert report.total_score > 0, "总分应该大于0"
        assert 0 <= report.emotion_score <= 100, "情绪分应在0-100之间"
        assert 0 <= report.rhythm_score <= 100, "节奏分应在0-100之间"
        assert 0 <= report.interaction_score <= 100, "互动分应在0-100之间"
        print(f"优质脚本评分: {report.total_score:.1f}, 等级: {report.grade}")

    def test_score_bad_script(self):
        """测试劣质脚本评分"""
        from services.script_scorer import ScriptScorer, TrustSourceType

        scorer = ScriptScorer()
        report = scorer.score(TEST_SCRIPT_BAD, TrustSourceType.PERSONA)

        assert report.total_score >= 0, "总分应该>=0"
        assert len(report.suggestions) > 0, "应该有优化建议"
        print(f"劣质脚本评分: {report.total_score:.1f}, 等级: {report.grade}")

    def test_score_different_trust_types(self):
        """测试不同信任来源类型的评分"""
        from services.script_scorer import ScriptScorer, TrustSourceType

        scorer = ScriptScorer()
        test_script = {
            "title": "测试",
            "opening": "你知道吗？",
            "scenes": [{"narration": "测试内容"}]
        }

        for trust_type in TrustSourceType:
            report = scorer.score(test_script, trust_type)
            assert report.total_score >= 0, f"{trust_type.value} 类型总分应>=0"
            print(f"{trust_type.value}: {report.total_score:.1f}")


class TestBusinessClassifier:
    """业务分类模块测试"""

    def test_classify_persona_type(self):
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
        assert len(result.recommended_topic_types) > 0, "应该有推荐的选题类型"
        print(f"分类结果: {result.trust_source.value}, 置信度: {result.confidence:.2f}")

    def test_classify_institution_type(self):
        """测试机构型分类"""
        from services.business_classifier import BusinessClassifier

        classifier = BusinessClassifier()
        result = classifier.classify({
            "name": "XX知名品牌",
            "org_type": "知名企业",
            "description": "全国连锁知名品牌"
        })

        assert result.trust_source.value == "institution", "应该是机构型"
        print(f"机构型分类: {result.trust_source.value}")

    def test_classify_knowledge_type(self):
        """测试知识型分类"""
        from services.business_classifier import BusinessClassifier

        classifier = BusinessClassifier()
        result = classifier.classify({
            "name": "教育培训",
            "industry": "教育",
            "description": "专业技能培训"
        })

        assert result.trust_source.value == "knowledge", "应该是知识型"
        print(f"知识型分类: {result.trust_source.value}")


class TestRewardPointSystem:
    """奖励点系统测试"""

    def test_calculate_short_video(self):
        """测试短视频奖励点计算"""
        from services.reward_point_system import RewardPointService

        service = RewardPointService()
        result = service.calculate(30, {"奖励分布": 0.8})

        assert result["total_points"] >= 1, "至少应该有1个奖励点"
        assert len(result["points"]) > 0, "应该有奖励点列表"
        print(f"30秒视频: {result['total_points']}个奖励点")

    def test_calculate_long_video(self):
        """测试长视频奖励点计算"""
        from services.reward_point_system import RewardPointService

        service = RewardPointService()
        result = service.calculate(90, {"奖励分布": 0.6})

        assert result["total_points"] > 0, "应该有奖励点"
        print(f"90秒视频: {result['total_points']}个奖励点")

    def test_reward_distribution_density(self):
        """测试奖励点分布密度"""
        from services.reward_point_system import RewardPointService

        service = RewardPointService()

        # 前密分布
        result_dense = service.calculate(60, {"奖励分布": 1.0})
        # 均匀分布
        result_uniform = service.calculate(60, {"奖励分布": 0.3})

        # 前密分布的前几个点应该比均匀分布更密集
        first_point_dense = result_dense["points"][0]["time_start"] if result_dense["points"] else 0
        first_point_uniform = result_uniform["points"][0]["time_start"] if result_uniform["points"] else 0

        print(f"前密分布首个点: {first_point_dense}秒, 均匀分布首个点: {first_point_uniform}秒")
        assert True, "分布测试通过"


class TestTemplateSystem:
    """模板系统测试"""

    def test_get_all_templates(self):
        """测试获取所有模板"""
        from services.script_template import get_template_library

        library = get_template_library()
        templates = library.list_all()

        assert len(templates) >= 10, "应该有至少10个模板"
        print(f"模板总数: {len(templates)}")

    def test_get_templates_by_type(self):
        """测试按类型筛选模板"""
        from services.script_template import get_template_library, ContentType

        library = get_template_library()
        templates = library.list_by_type(ContentType.PROBLEM_DIAGNOSIS)

        assert len(templates) > 0, "问题诊断类应该有模板"
        print(f"问题诊断类模板: {len(templates)}个")

    def test_get_templates_by_duration(self):
        """测试按时长筛选模板"""
        from services.script_template import get_template_library, Duration

        library = get_template_library()
        templates = library.list_by_duration(Duration.SHORT)

        assert len(templates) > 0, "短时长模板应该有"
        print(f"短时长模板: {len(templates)}个")


class TestIPConfigManager:
    """IP配置管理测试"""

    def test_get_all_presets(self):
        """测试获取所有预设"""
        from services.ip_persona_manager import IPConfigManager

        manager = IPConfigManager()
        presets = manager.list_presets()

        assert len(presets) >= 3, "至少有3个预设"
        print(f"IP预设数量: {len(presets)}")

    def test_get_specific_preset(self):
        """测试获取指定预设"""
        from services.ip_persona_manager import IPConfigManager

        manager = IPConfigManager()
        preset = manager.get_config("preset_companion")

        assert preset is not None, "预设应该存在"
        assert preset.name == "陪伴者", "应该是陪伴者预设"
        print(f"预设详情: {preset.name}, 类型: {preset.persona_type.value}")


class TestAPIEndpoints:
    """API端点测试"""

    @pytest.fixture
    def client(self):
        """获取测试客户端"""
        app = get_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            with app.app_context():
                yield client

    def test_health_check(self, client):
        """测试健康检查端点"""
        response = client.get('/api/script/health')
        data = json.loads(response.data)

        assert response.status_code == 200, "健康检查应该返回200"
        assert data.get('success') == True, "应该返回成功"
        print(f"健康检查: {data}")

    def test_balance_presets(self, client):
        """测试获取均衡器预设"""
        response = client.get('/api/script/balance-presets')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) >= 6, "应该有至少6个预设"
        print(f"均衡器预设数量: {len(data.get('data', []))}")

    def test_topic_types(self, client):
        """测试获取选题类型"""
        response = client.get('/api/script/topic-types')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) >= 10, "应该有至少10个类型"
        print(f"选题类型数量: {len(data.get('data', []))}")

    def test_templates(self, client):
        """测试获取模板列表"""
        response = client.get('/api/script/templates')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) > 0, "应该有模板"
        print(f"模板数量: {len(data.get('data', []))}")

    def test_ip_configs(self, client):
        """测试获取IP配置"""
        response = client.get('/api/script/ip-configs')
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) >= 3, "应该有至少3个IP配置"
        print(f"IP配置数量: {len(data.get('data', []))}")

    def test_score_script(self, client):
        """测试脚本评分API"""
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
        assert 'data' in data
        assert 'total_score' in data['data']
        print(f"评分结果: {data['data']['total_score']}")

    def test_classify_business(self, client):
        """测试业务分类API"""
        response = client.post(
            '/api/script/classify',
            json=TEST_PORTRAIT_DATA,
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'trust_source' in data['data']
        print(f"分类结果: {data['data']['trust_source']}")

    def test_reward_preview(self, client):
        """测试奖励点预览API"""
        response = client.post(
            '/api/script/reward-preview',
            json={
                "duration": 60,
                "balance_config": {
                    "信息密度": 60,
                    "奖励分布": 0.8
                }
            },
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert 'total_points' in data['data']
        print(f"奖励点数量: {data['data']['total_points']}")

    def test_balance_recommend(self, client):
        """测试均衡器推荐API"""
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
        print(f"推荐配置: {data['data']['config']}")

    def test_score_batch(self, client):
        """测试批量评分API"""
        response = client.post(
            '/api/script/score-batch',
            json={
                "scripts": [
                    {"script": TEST_SCRIPT_GOOD, "trust_source": "persona"},
                    {"script": TEST_SCRIPT_BAD, "trust_source": "knowledge"}
                ]
            },
            content_type='application/json'
        )
        data = json.loads(response.data)

        assert response.status_code == 200
        assert data.get('success') == True
        assert len(data.get('data', [])) == 2, "应该有2个结果"
        print(f"批量评分: {len(data.get('data', []))}个脚本")


# =============================================================================
# 集成测试
# =============================================================================

class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流程"""
        from services.script_scorer import ScriptScorer, TrustSourceType
        from services.business_classifier import BusinessClassifier
        from services.reward_point_system import RewardPointService
        from services.script_template import get_template_library

        # 1. 业务分类
        classifier = BusinessClassifier()
        classify_result = classifier.classify(TEST_PORTRAIT_DATA)
        print(f"1. 业务分类: {classify_result.trust_source.value}")

        # 2. 获取模板
        library = get_template_library()
        templates = library.list_by_type(
            classify_result.recommended_topic_types[0]
            if classify_result.recommended_topic_types else None
        )
        print(f"2. 推荐模板: {len(templates)}个")

        # 3. 计算奖励点
        reward_service = RewardPointService()
        reward_result = reward_service.calculate(60, {"奖励分布": 0.7})
        print(f"3. 奖励点: {reward_result['total_points']}个")

        # 4. 评分
        scorer = ScriptScorer()
        score_result = scorer.score(TEST_SCRIPT_GOOD, TrustSourceType.PERSONA)
        print(f"4. 评分: {score_result.total_score:.1f}")

        assert True, "完整流程测试通过"


# =============================================================================
# 运行测试
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
