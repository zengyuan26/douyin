"""
短视频脚本评分服务 - 单元测试
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.script_scorer import (
    ScriptScorer,
    score_script,
    get_score_summary,
    TrustSourceType,
    ScriptScoreReport
)


class TestScriptScorer:
    """评分器测试"""

    def setup_method(self):
        self.scorer = ScriptScorer()

    def test_score_empty_script(self):
        """测试空脚本评分"""
        report = self.scorer.score({}, TrustSourceType.KNOWLEDGE)
        assert isinstance(report, ScriptScoreReport)
        assert report.total_score < 50  # 空脚本应该低分

    def test_score_good_script(self):
        """测试优质脚本评分"""
        script = {
            "title": "为什么你买的山货总是踩坑？我来告诉你真相！",
            "opening": "买山货总是被坑？那是因为你不知道这些内幕！",
            "scenes": [
                {
                    "scene_index": 1,
                    "scene_name": "痛点开场",
                    "time_range": "0-3秒",
                    "narration": "太难了！花了大价钱买的野生菌，结果全是假的！",
                    "emotion_stage": "高情绪",
                },
                {
                    "scene_index": 2,
                    "scene_name": "原因分析",
                    "time_range": "3-15秒",
                    "narration": "为什么你买的山货总是踩坑？主要是这三个原因。第一，不懂行；第二，太贪便宜；第三，不会看。",
                    "emotion_stage": "疑问",
                },
                {
                    "scene_index": 3,
                    "scene_name": "干货输出",
                    "time_range": "15-30秒",
                    "narration": "今天我教你三招辨别真假山货的技巧。第一看颜色，第二闻味道，第三摸手感。记住了吗？",
                    "emotion_stage": "中情绪",
                },
                {
                    "scene_index": 4,
                    "scene_name": "互动引导",
                    "time_range": "30-45秒",
                    "narration": "你们买山货有没有踩过坑？评论区说说你的经历，我来帮你辨别真假！",
                    "emotion_stage": "正面",
                },
                {
                    "scene_index": 5,
                    "scene_name": "CTA收尾",
                    "time_range": "45-60秒",
                    "narration": "觉得有用就点个赞，关注我，每天分享山货鉴别技巧！",
                    "emotion_stage": "高情绪",
                }
            ],
            "duration": 60
        }

        report = self.scorer.score(script, TrustSourceType.PERSONA)

        assert report.total_score > 60  # 优质脚本应该得到较高分数
        assert report.emotion_score > 0
        assert report.rhythm_score > 0
        assert report.interaction_score > 0

    def test_emotion_detection(self):
        """测试情绪词检测"""
        text = "太棒了！终于找到了秘诀！没想到这么简单，爱了爱了！"
        density = self.scorer._calc_emotion_density(text)
        assert density > 0  # 应该检测到情绪词

    def test_hook_strength(self):
        """测试钩子强度"""
        # 强钩子
        strong_hook = "崩溃！踩雷了！这个坑千万不能进！"
        scenes = [{"narration": strong_hook}]
        strength = self.scorer._calc_hook_strength("", {"scenes": scenes})
        assert strength >= 0.5

        # 弱钩子
        weak_hook = "今天给大家介绍一下这个产品。"
        scenes = [{"narration": weak_hook}]
        strength = self.scorer._calc_hook_strength("", {"scenes": scenes})
        assert strength < 0.5

    def test_reward_distribution(self):
        """测试奖励点分布"""
        # 前密后疏的分布
        scenes = [
            {"narration": "记住！这是第一个技巧！"},
            {"narration": "第二个技巧来了！"},
            {"narration": "技巧三！"},
            {"narration": "总结一下。"},
            {"narration": "好的，再见。"}
        ]
        script = {"scenes": scenes}
        text = " ".join(s["narration"] for s in scenes)

        distribution = self.scorer._calc_reward_distribution(text, script)
        assert distribution >= 0.5  # 应该符合前密后疏

    def test_question_density(self):
        """测试问句密度"""
        text = "为什么你总是失败？是不是方法不对？会不会是心态问题？"
        density = self.scorer._calc_question_density(text)
        assert density > 0  # 应该检测到问句

    def test_cta_count(self):
        """测试CTA计数"""
        text = "关注我，点赞，评论，收藏，转发！"
        script = {}
        count = self.scorer._calc_cta_count(text, script)
        assert count >= 3  # 应该检测到多个CTA

    def test_grade_calculation(self):
        """测试等级计算"""
        assert self.scorer._get_grade(98) == ("S", "神级")
        assert self.scorer._get_grade(92) == ("A+", "优秀")
        assert self.scorer._get_grade(88) == ("A", "良好")
        assert self.scorer._get_grade(75) == ("B", "一般")
        assert self.scorer._get_grade(55) == ("D", "不及格")

    def test_pass_threshold(self):
        """测试及格分数线"""
        assert self.scorer.get_threshold(TrustSourceType.KNOWLEDGE) == 75
        assert self.scorer.get_threshold(TrustSourceType.PERSONA) == 70
        assert self.scorer.get_threshold(TrustSourceType.INSTITUTION) == 75
        assert self.scorer.get_threshold(TrustSourceType.PRODUCT) == 70


class TestScoreScript:
    """便捷函数测试"""

    def test_score_script_function(self):
        """测试便捷评分函数"""
        script = {
            "title": "测试标题",
            "opening": "痛点开场：为什么你总是...",
            "scenes": [
                {"narration": "第一段口播内容，包含一些知识点和情绪词。"},
                {"narration": "第二段，这里有问句吗？你们觉得怎么样？"},
                {"narration": "第三段总结，关注点赞评论！"}
            ]
        }

        report = score_script(script)
        assert isinstance(report, dict)
        assert "total_score" in report
        assert "dimensions" in report
        assert "suggestions" in report

    def test_get_score_summary(self):
        """测试评分摘要生成"""
        report = {
            "total_score": 78.5,
            "grade": "B+",
            "passed": True,
            "emotion_score": 75.0,
            "rhythm_score": 80.0,
            "interaction_score": 80.0,
            "suggestions": ["建议1", "建议2"]
        }

        summary = get_score_summary(report)
        assert "78.5" in summary
        assert "B+" in summary
        assert "通过" in summary


class TestEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        self.scorer = ScriptScorer()

    def test_very_short_script(self):
        """测试超短视频（15秒）"""
        script = {
            "title": "快闪",
            "scenes": [
                {"narration": "3秒钩子：崩溃！"},
                {"narration": "7秒干货。"},
                {"narration": "5秒CTA：关注！"}
            ],
            "duration": 15
        }

        report = self.scorer.score(script, TrustSourceType.PRODUCT)
        assert report.total_score > 0

    def test_very_long_script(self):
        """测试超长视频（120秒）"""
        script = {
            "title": "深度讲解",
            "scenes": [
                {"narration": f"第{i}段口播内容，包含知识点{i}。" * 10}
                for i in range(1, 8)
            ],
            "duration": 120
        }

        report = self.scorer.score(script, TrustSourceType.KNOWLEDGE)
        assert report.total_score > 0

    def test_chinese_only_script(self):
        """测试纯中文脚本"""
        script = {
            "title": "中文标题",
            "opening": "你好，今天分享干货！",
            "scenes": [
                {"narration": "内容一，包含问句吗？你们觉得呢？"},
                {"narration": "内容二，关注点赞！"}
            ]
        }

        report = self.scorer.score(script)
        assert isinstance(report, ScriptScoreReport)

    def test_mixed_language_script(self):
        """测试中英混合脚本"""
        script = {
            "title": "Secret Tips",
            "opening": "揭秘！你不知道的tips！",
            "scenes": [
                {"narration": "First, 记住这个关键点。Second, CTA：关注！"}
            ]
        }

        report = self.scorer.score(script)
        assert isinstance(report, ScriptScoreReport)


class TestTrustSourceTypes:
    """信任来源类型测试"""

    def setup_method(self):
        self.scorer = ScriptScorer()

    def test_knowledge_type_threshold(self):
        """测试知识型信任"""
        script = {
            "title": "知识分享",
            "scenes": [
                {"narration": "今天讲三个技巧：第一，第二，第三。记住了吗？"},
            ]
        }

        report = self.scorer.score(script, TrustSourceType.KNOWLEDGE)
        # 知识型对节奏和互动要求较高
        assert report.rhythm_score > 0

    def test_persona_type_threshold(self):
        """测试人设型信任"""
        script = {
            "title": "我的故事",
            "scenes": [
                {"narration": "今天遇到一件奇葩的事！太离谱了！"},
            ]
        }

        report = self.scorer.score(script, TrustSourceType.PERSONA)
        assert report.emotion_score > 0

    def test_institution_type_threshold(self):
        """测试机构型信任"""
        script = {
            "title": "品牌介绍",
            "scenes": [
                {"narration": "我们的产品特点：第一，品质保证；第二，服务完善。"},
            ]
        }

        report = self.scorer.score(script, TrustSourceType.INSTITUTION)
        assert report.interaction_score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
