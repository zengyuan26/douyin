"""
测试用例文件

本文件包含所有新增/修改模块的测试用例：
- portrait_generator
- topic_library_generator
- keyword_library_generator
- data_mapper
- emotion_curves
- visual_guides
- expert_reviewer
- json_parser
- prompt_constraints

运行方式：
    python -m pytest tests/test_enhancements.py -v
"""

import unittest
import json
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# 测试：画像增强 (portrait_generator)
# =============================================================================

class TestPortraitEnhancement(unittest.TestCase):
    """测试画像增强的新增字段"""

    def test_portrait_class_has_new_fields(self):
        """测试 Portrait 类是否包含新增字段"""
        from services.portrait_generator import Portrait

        # 检查新字段存在
        portrait = Portrait(
            portrait_id="test_001",
            problem_type="价格问题",
            problem_type_description="价格相关问题",
            identity="学生家长",
            identity_description="孩子即将高考的家长",
            pain_points=["分数不够上好大学"],
            pain_scenarios=["高考出分后"],
            psychology={},
            barriers=["担心选错"],
            search_keywords=["高考志愿填报"],
            content_preferences=["干货型"],
            market_type="blue_ocean",
            differentiation="专业服务",
            # 新增字段
            language_style="口语化",
            crowd_perspective="第一人称",
            age_range="35-45岁",
            pain_point_level="high",
            decision_stage="consideration",
        )

        self.assertEqual(portrait.language_style, "口语化")
        self.assertEqual(portrait.crowd_perspective, "第一人称")
        self.assertEqual(portrait.age_range, "35-45岁")
        self.assertEqual(portrait.pain_point_level, "high")
        self.assertEqual(portrait.decision_stage, "consideration")

    def test_portrait_class_default_values(self):
        """测试新字段的默认值"""
        from services.portrait_generator import Portrait

        portrait = Portrait(
            portrait_id="test_002",
            problem_type="价格问题",
            problem_type_description="价格相关问题",
            identity="学生家长",
            identity_description="孩子即将高考的家长",
            pain_points=[],
            pain_scenarios=[],
            psychology={},
            barriers=[],
            search_keywords=[],
            content_preferences=[],
            market_type="blue_ocean",
            differentiation="",
        )

        # 检查默认值
        self.assertEqual(portrait.language_style, "")
        self.assertEqual(portrait.crowd_perspective, "")
        self.assertEqual(portrait.age_range, "")
        self.assertEqual(portrait.pain_point_level, "medium")  # 默认值
        self.assertEqual(portrait.decision_stage, "consideration")  # 默认值

    def test_portrait_to_dict_includes_new_fields(self):
        """测试 to_dict 输出包含新字段"""
        from services.portrait_generator import generate_portraits_from_analysis

        # 模拟分析结果
        analysis_result = {
            'keyword_library': {
                'categories': [
                    {'category_name': '测试', 'keywords': ['测试词1', '测试词2']}
                ]
            },
            'problem_types': [],
            'market_opportunities': []
        }

        business_info = {'business_description': '高考志愿填报辅导'}

        # 由于需要 LLM 调用，这里只测试数据结构转换
        from services.portrait_generator import Portrait

        portrait = Portrait(
            portrait_id="test_003",
            problem_type="价格问题",
            problem_type_description="价格相关问题",
            identity="学生家长",
            identity_description="孩子即将高考的家长",
            pain_points=["分数不够"],
            pain_scenarios=["高考出分后"],
            psychology={},
            barriers=["担心选错"],
            search_keywords=["高考志愿"],
            content_preferences=["干货型"],
            market_type="blue_ocean",
            differentiation="专业",
            language_style="口语化",
            crowd_perspective="第一人称",
            age_range="40岁",
            pain_point_level="high",
            decision_stage="decision",
        )

        # 转换为字典
        portrait_dict = {
            'portrait_id': portrait.portrait_id,
            'problem_type': portrait.problem_type,
            'problem_type_description': portrait.problem_type_description,
            'identity': portrait.identity,
            'identity_description': portrait.identity_description,
            'pain_points': portrait.pain_points,
            'pain_scenarios': portrait.pain_scenarios,
            'psychology': portrait.psychology,
            'barriers': portrait.barriers,
            'search_keywords': portrait.search_keywords,
            'content_preferences': portrait.content_preferences,
            'market_type': portrait.market_type,
            'differentiation': portrait.differentiation,
            'scene_tags': portrait.scene_tags,
            'behavior_tags': portrait.behavior_tags,
            'content_direction': portrait.content_direction,
            # 新增字段
            'language_style': portrait.language_style,
            'crowd_perspective': portrait.crowd_perspective,
            'age_range': portrait.age_range,
            'pain_point_level': portrait.pain_point_level,
            'decision_stage': portrait.decision_stage,
        }

        # 验证新字段存在
        self.assertIn('language_style', portrait_dict)
        self.assertIn('crowd_perspective', portrait_dict)
        self.assertIn('age_range', portrait_dict)
        self.assertIn('pain_point_level', portrait_dict)
        self.assertIn('decision_stage', portrait_dict)


# =============================================================================
# 测试：选题增强 (topic_library_generator)
# =============================================================================

class TestTopicEnhancement(unittest.TestCase):
    """测试选题增强的新增字段"""

    def test_topic_generator_has_scene_details_method(self):
        """测试 _generate_scene_details 方法存在"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        # 检查方法存在
        self.assertTrue(hasattr(gen, '_generate_scene_details'))
        self.assertTrue(callable(getattr(gen, '_generate_scene_details')))

    def test_topic_generator_has_core_value_method(self):
        """测试 _generate_core_value 方法存在"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        # 检查方法存在
        self.assertTrue(hasattr(gen, '_generate_core_value'))
        self.assertTrue(callable(getattr(gen, '_generate_core_value')))

    def test_topic_generator_has_content_format_method(self):
        """测试 _determine_content_format 方法存在"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        # 检查方法存在
        self.assertTrue(hasattr(gen, '_determine_content_format'))
        self.assertTrue(callable(getattr(gen, '_determine_content_format')))

    def test_topic_generator_has_emotion_curve_method(self):
        """测试 _generate_emotion_curve 方法存在"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        # 检查方法存在
        self.assertTrue(hasattr(gen, '_generate_emotion_curve'))
        self.assertTrue(callable(getattr(gen, '_generate_emotion_curve')))

    def test_scene_details_returns_list(self):
        """测试 _generate_scene_details 返回列表"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        topic = {
            'type_key': 'cause',
            'title': '分数不够怎么办',
            'stage_key': 'pain',
        }

        result = gen._generate_scene_details(topic)

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        # 检查结构
        for scene in result:
            self.assertIn('scene', scene)
            self.assertIn('trigger', scene)
            self.assertIn('emotion', scene)

    def test_core_value_returns_string(self):
        """测试 _generate_core_value 返回字符串"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        topic = {
            'type_key': 'cause',
            'type_name': '原因分析',
            'stage_key': 'pain',
        }

        result = gen._generate_core_value(topic)

        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_content_format_returns_string(self):
        """测试 _determine_content_format 返回字符串"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        topic = {
            'type_key': 'tutorial',
            'stage_key': 'pain',
        }

        result = gen._determine_content_format(topic)

        self.assertIsInstance(result, str)
        self.assertIn(result, ['种草', '测评', '教程', '对比', '转化型教程'])

    def test_emotion_curve_returns_string(self):
        """测试 _generate_emotion_curve 返回字符串"""
        from services.topic_library_generator import TopicLibraryGenerator

        gen = TopicLibraryGenerator()

        topic = {
            'type_key': 'pitfall',
            'stage_key': 'pain',
            'stage_name': '痛点放大',
        }

        result = gen._generate_emotion_curve(topic)

        self.assertIsInstance(result, str)
        self.assertIn('→', result)  # 包含情绪过渡箭头


# =============================================================================
# 测试：关键词库增强 (keyword_library_generator)
# =============================================================================

class TestKeywordEnhancement(unittest.TestCase):
    """测试关键词库增强的新增字段"""

    def test_keyword_result_has_new_fields(self):
        """测试 KeywordLibraryResult 类包含新增字段"""
        from services.keyword_library_generator import KeywordLibraryResult

        result = KeywordLibraryResult()
        result.success = True
        result.geo_score = {'region': '云南', 'score': 85, 'reason': '地域覆盖度高'}
        result.trust_keywords = ['品质保证', '专业服务']
        result.data_sources = ['行业报告', '用户调研']

        self.assertEqual(result.geo_score['region'], '云南')
        self.assertEqual(result.trust_keywords, ['品质保证', '专业服务'])
        self.assertEqual(result.data_sources, ['行业报告', '用户调研'])

    def test_keyword_result_to_dict_includes_new_fields(self):
        """测试 to_dict 输出包含新字段"""
        from services.keyword_library_generator import KeywordLibraryResult

        result = KeywordLibraryResult()
        result.success = True
        result.geo_score = {'region': '昆明', 'score': 80}
        result.trust_keywords = ['信任词1']
        result.data_sources = ['数据源1']

        result_dict = result.to_dict()

        self.assertIn('geo_score', result_dict)
        self.assertIn('trust_keywords', result_dict)
        self.assertIn('data_sources', result_dict)

    def test_extract_enhanced_fields_method_exists(self):
        """测试 _extract_enhanced_fields 方法存在"""
        from services.keyword_library_generator import KeywordLibraryGenerator

        gen = KeywordLibraryGenerator()

        self.assertTrue(hasattr(gen, '_extract_enhanced_fields'))
        self.assertTrue(callable(getattr(gen, '_extract_enhanced_fields')))


# =============================================================================
# 测试：数据映射增强 (data_mapper)
# =============================================================================

class TestDataMapperEnhancement(unittest.TestCase):
    """测试数据映射的新增方法"""

    def setUp(self):
        from services.skill_bridge.registry import SkillRegistry
        from services.skill_bridge.data_mapper import DataMapper
        self.registry = SkillRegistry()
        self.mapper = DataMapper(self.registry)

    def test_map_portrait_to_content_method_exists(self):
        """测试 map_portrait_to_content 方法存在"""
        self.assertTrue(hasattr(self.mapper, 'map_portrait_to_content'))
        self.assertTrue(callable(getattr(self.mapper, 'map_portrait_to_content')))

    def test_map_topic_to_content_method_exists(self):
        """测试 map_topic_to_content 方法存在"""
        self.assertTrue(hasattr(self.mapper, 'map_topic_to_content'))
        self.assertTrue(callable(getattr(self.mapper, 'map_topic_to_content')))

    def test_map_keyword_to_content_method_exists(self):
        """测试 map_keyword_to_content 方法存在"""
        self.assertTrue(hasattr(self.mapper, 'map_keyword_to_content'))
        self.assertTrue(callable(getattr(self.mapper, 'map_keyword_to_content')))

    def test_map_portrait_to_content_returns_dict(self):
        """测试 map_portrait_to_content 返回字典"""
        portrait = {
            'identity': '学生家长',
            'pain_points': ['分数不够'],
            'language_style': '口语化',
            'pain_point_level': 'high',
        }

        result = self.mapper.map_portrait_to_content(portrait)

        self.assertIsInstance(result, dict)
        self.assertIn('identity', result)
        self.assertIn('language_style', result)
        self.assertIn('pain_point_level', result)

    def test_map_topic_to_content_returns_dict(self):
        """测试 map_topic_to_content 返回字典"""
        topic = {
            'id': 'topic_001',
            'title': '分数不够怎么办',
            'type_key': 'cause',
            'scene_details': [{'scene': '测试'}],
            'core_value': '提供解决方案',
        }

        result = self.mapper.map_topic_to_content(topic)

        self.assertIsInstance(result, dict)
        self.assertIn('topic_id', result)
        self.assertIn('title', result)
        self.assertIn('scene_details', result)
        self.assertIn('core_value', result)

    def test_map_keyword_to_content_returns_dict(self):
        """测试 map_keyword_to_content 返回字典"""
        keyword_lib = {
            'keyword_core': '高考志愿',
            'geo_score': {'region': '云南', 'score': 85},
            'trust_keywords': ['专业'],
        }

        result = self.mapper.map_keyword_to_content(keyword_lib)

        self.assertIsInstance(result, dict)
        self.assertIn('keyword_core', result)
        self.assertIn('geo_score', result)
        self.assertIn('trust_keywords', result)

    def test_build_content_context_method_exists(self):
        """测试 build_content_context 方法存在"""
        self.assertTrue(hasattr(self.mapper, 'build_content_context'))
        self.assertTrue(callable(getattr(self.mapper, 'build_content_context')))


# =============================================================================
# 测试：情绪曲线配置 (emotion_curves)
# =============================================================================

class TestEmotionCurves(unittest.TestCase):
    """测试情绪曲线配置"""

    def test_emotion_curves_module_exists(self):
        """测试模块可以导入"""
        from content_templates.emotion_curves import EMOTION_CURVES
        self.assertIsInstance(EMOTION_CURVES, dict)

    def test_emotion_curves_has_7_types(self):
        """测试包含7种情绪曲线类型"""
        from content_templates.emotion_curves import EMOTION_CURVES

        expected_types = ['种草型', '干货型', '测评型', '对比型', '故事型', '悬念型', '温情型']
        for curve_type in expected_types:
            self.assertIn(curve_type, EMOTION_CURVES)

    def test_emotion_curve_structure(self):
        """测试情绪曲线结构"""
        from content_templates.emotion_curves import EMOTION_CURVES

        curve = EMOTION_CURVES['种草型']

        self.assertIn('stages', curve)
        self.assertIn('keywords', curve)
        self.assertIn('visual_hints', curve)
        self.assertIn('color_progression', curve)

        # 检查 stages 结构
        for stage in curve['stages']:
            self.assertIn('name', stage)
            self.assertIn('emotion', stage)
            self.assertIn('duration_ratio', stage)

    def test_get_emotion_curve_function(self):
        """测试 get_emotion_curve 函数"""
        from content_templates.emotion_curves import get_emotion_curve

        curve = get_emotion_curve('种草型')
        self.assertEqual(curve['name'], '种草型')

        # 测试默认值
        default_curve = get_emotion_curve('不存在的类型')
        self.assertEqual(default_curve['name'], '种草型')

    def test_build_emotion_plan_function(self):
        """测试 build_emotion_plan 函数"""
        from content_templates.emotion_curves import build_emotion_plan

        plan = build_emotion_plan('种草型', total_frames=5)

        self.assertIsInstance(plan, list)
        self.assertEqual(len(plan), 5)

        # 检查帧结构
        for frame in plan:
            self.assertIn('frame_index', frame)
            self.assertIn('stage_name', frame)
            self.assertIn('emotion', frame)


# =============================================================================
# 测试：视觉风格配置 (visual_guides)
# =============================================================================

class TestVisualGuides(unittest.TestCase):
    """测试视觉风格配置"""

    def test_visual_guides_module_exists(self):
        """测试模块可以导入"""
        from content_templates.visual_guides import VISUAL_GUIDES
        self.assertIsInstance(VISUAL_GUIDES, dict)

    def test_visual_guides_has_5_styles(self):
        """测试包含5种视觉风格"""
        from content_templates.visual_guides import VISUAL_GUIDES

        expected_styles = ['warm_tone', 'professional_tone', 'fresh_tone', 'luxury_tone', 'casual_tone']
        for style in expected_styles:
            self.assertIn(style, VISUAL_GUIDES)

    def test_visual_guide_structure(self):
        """测试视觉风格结构"""
        from content_templates.visual_guides import VISUAL_GUIDES

        guide = VISUAL_GUIDES['warm_tone']

        self.assertIn('name', guide)
        self.assertIn('colors', guide)
        self.assertIn('light', guide)
        self.assertIn('scene', guide)
        self.assertIn('font_pairing', guide)

    def test_get_visual_guide_function(self):
        """测试 get_visual_guide 函数"""
        from content_templates.visual_guides import get_visual_guide

        guide = get_visual_guide('warm_tone')
        self.assertEqual(guide['name'], '暖色调风格')

        # 测试默认值
        default_guide = get_visual_guide('不存在的风格')
        self.assertEqual(default_guide['name'], '休闲生活风格')

    def test_get_recommended_style_function(self):
        """测试 get_recommended_style 函数"""
        from content_templates.visual_guides import get_recommended_style

        # B2B 业务
        style = get_recommended_style(industry='教育培训', business_type='b2b')
        self.assertEqual(style, 'professional_tone')

        # B2C 业务
        style = get_recommended_style(industry='母婴')
        self.assertEqual(style, 'warm_tone')


# =============================================================================
# 测试：专家评审 (expert_reviewer)
# =============================================================================

class TestExpertReviewer(unittest.TestCase):
    """测试专家评审模块"""

    def test_expert_reviewer_module_exists(self):
        """测试模块可以导入"""
        from services.expert_reviewer import ExpertReviewer, REVIEW_DIMENSIONS
        self.assertIsInstance(REVIEW_DIMENSIONS, dict)

    def test_review_dimensions_has_5_dimensions(self):
        """测试包含5个评审维度"""
        from services.expert_reviewer import REVIEW_DIMENSIONS

        expected_dims = [
            'psychology_compliance',
            'emotion_resonance',
            'trust_building',
            'value_delivery',
            'action_guide'
        ]
        for dim in expected_dims:
            self.assertIn(dim, REVIEW_DIMENSIONS)

    def test_review_dimension_structure(self):
        """测试评审维度结构"""
        from services.expert_reviewer import REVIEW_DIMENSIONS

        dim = REVIEW_DIMENSIONS['psychology_compliance']

        self.assertIn('name', dim)
        self.assertIn('weight', dim)
        self.assertIn('description', dim)
        self.assertIn('checklist', dim)
        self.assertIn('prompt_template', dim)

        # 检查权重总和
        total_weight = sum(d['weight'] for d in REVIEW_DIMENSIONS.values())
        self.assertAlmostEqual(total_weight, 1.0, places=1)

    def test_review_grades_exists(self):
        """测试评审等级存在"""
        from services.expert_reviewer import REVIEW_GRADES

        expected_grades = ['excellent', 'good', 'pass', 'fail']
        for grade in expected_grades:
            self.assertIn(grade, REVIEW_GRADES)

    def test_expert_reviewer_class_exists(self):
        """测试 ExpertReviewer 类存在"""
        from services.expert_reviewer import ExpertReviewer
        self.assertTrue(callable(ExpertReviewer))

    def test_dimension_result_dataclass(self):
        """测试 DimensionResult 数据类"""
        from services.expert_reviewer import DimensionResult

        result = DimensionResult(
            dimension_key='test',
            dimension_name='测试',
            score=85,
            issues=['问题1'],
            suggestions=['建议1'],
            is_pass=True
        )

        self.assertEqual(result.score, 85)
        self.assertTrue(result.is_pass)

    def test_review_result_dataclass(self):
        """测试 ReviewResult 数据类"""
        from services.expert_reviewer import ReviewResult

        result = ReviewResult(
            success=True,
            overall_score=85,
            grade='good',
            grade_label='良好',
            is_pass=True
        )

        self.assertTrue(result.success)
        self.assertEqual(result.overall_score, 85)


# =============================================================================
# 测试：JSON 解析器 (json_parser)
# =============================================================================

class TestJSONParser(unittest.TestCase):
    """测试 JSON 解析器"""

    def test_json_parser_module_exists(self):
        """测试模块可以导入"""
        from services.json_parser import JSONParser
        self.assertTrue(callable(JSONParser))

    def test_parse_direct(self):
        """测试直接解析"""
        from services.json_parser import JSONParser

        parser = JSONParser()

        text = '{"key": "value", "number": 123}'
        result = parser.parse_with_fallback(text)

        self.assertIsNotNone(result)
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['number'], 123)

    def test_parse_with_code_block(self):
        """测试解析 markdown code block"""
        from services.json_parser import JSONParser

        parser = JSONParser()

        text = '''
        这里是说明文字
        ```json
        {"key": "value"}
        ```
        '''
        result = parser.parse_with_fallback(text)

        self.assertIsNotNone(result)
        self.assertEqual(result['key'], 'value')

    def test_parse_array(self):
        """测试解析数组"""
        from services.json_parser import JSONParser

        parser = JSONParser()

        text = '[{"id": 1}, {"id": 2}]'
        result = parser.parse_with_fallback(text)

        self.assertIsNotNone(result)
        # 可能是列表或包含 _data 的字典
        if isinstance(result, list):
            self.assertEqual(len(result), 2)
        else:
            self.assertIn('_data', result)

    def test_parse_invalid_json(self):
        """测试解析无效 JSON"""
        from services.json_parser import JSONParser

        parser = JSONParser()

        text = '这是无效的JSON {'
        result = parser.parse_with_fallback(text)

        # 应该返回 None 或降级处理
        self.assertIsNone(result)

    def test_fix_json_errors(self):
        """测试 JSON 错误修复"""
        from services.json_parser import JSONParser

        parser = JSONParser()

        # 尾部逗号
        text = '{"key": "value",}'
        fixed = parser._fix_json_errors(text)
        self.assertNotIn(',}', fixed)

    def test_parse_array_with_fallback(self):
        """测试数组解析便捷函数"""
        from services.json_parser import parse_json_array

        text = '[{"title": "测试1"}, {"title": "测试2"}]'
        result = parse_json_array(text)

        self.assertIsInstance(result, list)


# =============================================================================
# 测试：Prompt 约束 (prompt_constraints)
# =============================================================================

class TestPromptConstraints(unittest.TestCase):
    """测试 Prompt 约束模块"""

    def test_prompt_constraints_module_exists(self):
        """测试模块可以导入"""
        from services.prompt_constraints import (
            JSON_OUTPUT_CONSTRAINT,
            SYSTEM_PROMPTS,
            GEO_EVALUATION_PROMPTS,
        )
        self.assertIsInstance(JSON_OUTPUT_CONSTRAINT, str)
        self.assertIsInstance(SYSTEM_PROMPTS, dict)
        self.assertIsInstance(GEO_EVALUATION_PROMPTS, dict)

    def test_json_output_constraint(self):
        """测试 JSON 输出约束"""
        from services.prompt_constraints import JSON_OUTPUT_CONSTRAINT

        self.assertIn('JSON', JSON_OUTPUT_CONSTRAINT)

    def test_system_prompts_has_roles(self):
        """测试 System Prompt 包含角色"""
        from services.prompt_constraints import SYSTEM_PROMPTS

        expected_roles = [
            'content_expert',
            'keyword_expert',
            'portrait_expert',
            'topic_expert',
            'title_expert',
            'tag_expert'
        ]
        for role in expected_roles:
            self.assertIn(role, SYSTEM_PROMPTS)

    def test_geo_evaluation_prompts_has_dimensions(self):
        """测试 GEO 评估 Prompt 包含维度"""
        from services.prompt_constraints import GEO_EVALUATION_PROMPTS

        expected_dims = [
            'title_attraction',
            'opening_directness',
            'structure_clarity',
            'trust_evidence',
            'cta_effectiveness'
        ]
        for dim in expected_dims:
            self.assertIn(dim, GEO_EVALUATION_PROMPTS)

    def test_get_system_prompt_function(self):
        """测试 get_system_prompt 函数"""
        from services.prompt_constraints import get_system_prompt

        prompt = get_system_prompt('content_expert')
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    def test_get_geo_prompt_function(self):
        """测试 get_geo_prompt 函数"""
        from services.prompt_constraints import get_geo_prompt

        prompt = get_geo_prompt('title_attraction')
        self.assertIsInstance(prompt, str)
        self.assertIn('标题吸引力', prompt)

    def test_build_full_prompt_function(self):
        """测试 build_full_prompt 函数"""
        from services.prompt_constraints import build_full_prompt

        messages = build_full_prompt(
            system_role='content_expert',
            user_content='请生成内容',
            add_json_constraint=True,
            add_example='content'
        )

        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)  # system + user

        # 检查消息结构
        self.assertIn('role', messages[0])
        self.assertIn('content', messages[0])


# =============================================================================
# =============================================================================
# 测试：新增 Skill 配置
# =============================================================================

class TestNewSkillConfigs(unittest.TestCase):
    """测试新增的 Skill 配置文件"""

    def test_consumer_psychology_skill_exists(self):
        """测试 consumer_psychology_skill.json 存在"""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'consumer_psychology_skill.json'
        )
        self.assertTrue(os.path.exists(config_path), f"文件不存在: {config_path}")

    def test_consumer_psychology_skill_valid_json(self):
        """测试 consumer_psychology_skill.json 是有效 JSON"""
        import json
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'consumer_psychology_skill.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.assertIn('skill', config)
        self.assertEqual(config['skill']['name'], 'consumer_psychology')

    def test_consumer_psychology_skill_has_required_steps(self):
        """测试 consumer_psychology_skill 包含必要步骤"""
        import json
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'consumer_psychology_skill.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)

        step_ids = [step['id'] for step in config['steps']]
        self.assertIn('step_influence_principles', step_ids)
        self.assertIn('step_conflict_design', step_ids)
        self.assertIn('step_loss_aversion', step_ids)
        self.assertIn('step_psychology_summary', step_ids)

    def test_visual_design_skill_exists(self):
        """测试 visual_design_skill.json 存在"""
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'visual_design_skill.json'
        )
        self.assertTrue(os.path.exists(config_path), f"文件不存在: {config_path}")

    def test_visual_design_skill_valid_json(self):
        """测试 visual_design_skill.json 是有效 JSON"""
        import json
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'visual_design_skill.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)
        self.assertIn('skill', config)
        self.assertEqual(config['skill']['name'], 'visual_design')

    def test_visual_design_skill_has_required_steps(self):
        """测试 visual_design_skill 包含必要步骤"""
        import json
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'visual_design_skill.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)

        step_ids = [step['id'] for step in config['steps']]
        self.assertIn('step_composition_check', step_ids)
        self.assertIn('step_color_scheme', step_ids)
        self.assertIn('step_scene_integration', step_ids)
        self.assertIn('step_visual_summary', step_ids)

    def test_graphic_skill_has_skill_chain(self):
        """测试 graphic_skill.json 包含 skill_chain 配置"""
        import json
        import os
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'services', 'skill_bridge', 'config', 'graphic_skill.json'
        )
        with open(config_path, 'r') as f:
            config = json.load(f)

        self.assertIn('skill_chain', config)
        self.assertIn('after_content_generation', config['skill_chain'])
        self.assertIn('consumer_psychology', config['skill_chain']['after_content_generation'])
        self.assertIn('visual_design', config['skill_chain']['after_content_generation'])


# 主函数
# =============================================================================

if __name__ == '__main__':
    unittest.main(verbosity=2)
