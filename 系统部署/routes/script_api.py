"""
短视频脚本生成增强API

提供：
1. 脚本评分
2. 业务分类
3. 均衡器预设
4. 模板列表
5. IP配置
6. 奖励点预览
7. 脚本生成增强

蓝图前缀：/api/script
"""

import logging
from flask import Blueprint, request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

# 创建蓝图
script_bp = Blueprint('script', __name__, url_prefix='/api/script')


# =============================================================================
# 辅助函数
# =============================================================================

def require_params(*required_fields):
    """参数验证装饰器"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json() or {}
            missing = [f for f in required_fields if f not in data]
            if missing:
                return jsonify({
                    'success': False,
                    'message': f'缺少必要参数: {", ".join(missing)}'
                }), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_current_user():
    """获取当前用户（从session）"""
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            return current_user
    except:
        pass
    return None


# =============================================================================
# 1. 脚本评分 API
# =============================================================================

@script_bp.route('/score', methods=['POST'])
def api_score_script():
    """
    对短视频脚本进行多维度评分

    请求体：
    {
        "script": {
            "title": "标题",
            "opening": "开场钩子",
            "scenes": [
                {
                    "narration": "口播文案",
                    "subtitle_text": "字幕"
                }
            ],
            "duration": 60,
            "narration": "完整口播"
        },
        "trust_source": "knowledge|persona|institution|product"
    }

    响应：
    {
        "success": true,
        "data": {
            "total_score": 85,
            "grade": "A(良好)",
            "passed": true,
            "emotion_score": 80,
            "rhythm_score": 85,
            "interaction_score": 90,
            "dimensions": [...],
            "suggestions": [...]
        }
    }
    """
    try:
        data = request.get_json() or {}
        script = data.get('script', {})
        trust_source = data.get('trust_source', 'knowledge')

        if not script:
            return jsonify({
                'success': False,
                'message': '缺少脚本内容'
            }), 400

        # 调用评分服务
        from services.script_scorer import ScriptScorer, TrustSourceType

        # 映射信任来源类型
        trust_mapping = {
            'knowledge': TrustSourceType.KNOWLEDGE,
            'persona': TrustSourceType.PERSONA,
            'institution': TrustSourceType.INSTITUTION,
            'product': TrustSourceType.PRODUCT
        }
        trust_type = trust_mapping.get(trust_source, TrustSourceType.KNOWLEDGE)

        # 评分
        scorer = ScriptScorer()
        report = scorer.score(script, trust_type)

        return jsonify({
            'success': True,
            'data': report.to_dict()
        })

    except Exception as e:
        logger.error(f"评分失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'评分失败: {str(e)}'
        }), 500


@script_bp.route('/score-batch', methods=['POST'])
def api_score_batch():
    """
    批量评分

    请求体：
    {
        "scripts": [
            {"script": {...}, "trust_source": "knowledge"},
            {"script": {...}, "trust_source": "persona"}
        ]
    }
    """
    try:
        data = request.get_json() or {}
        scripts = data.get('scripts', [])

        if not scripts:
            return jsonify({
                'success': False,
                'message': '缺少脚本列表'
            }), 400

        from services.script_scorer import ScriptScorer, TrustSourceType

        trust_mapping = {
            'knowledge': TrustSourceType.KNOWLEDGE,
            'persona': TrustSourceType.PERSONA,
            'institution': TrustSourceType.INSTITUTION,
            'product': TrustSourceType.PRODUCT
        }

        scorer = ScriptScorer()
        results = []

        for item in scripts:
            script = item.get('script', {})
            trust_source = item.get('trust_source', 'knowledge')
            trust_type = trust_mapping.get(trust_source, TrustSourceType.KNOWLEDGE)

            try:
                report = scorer.score(script, trust_type)
                results.append({
                    'success': True,
                    'data': report.to_dict()
                })
            except Exception as e:
                results.append({
                    'success': False,
                    'message': str(e)
                })

        return jsonify({
            'success': True,
            'data': results
        })

    except Exception as e:
        logger.error(f"批量评分失败: {e}")
        return jsonify({
            'success': False,
            'message': f'批量评分失败: {str(e)}'
        }), 500


# =============================================================================
# 2. 业务分类 API
# =============================================================================

@script_bp.route('/classify', methods=['POST'])
def api_classify_business():
    """
    根据业务特征判断信任来源类型

    请求体：
    {
        "name": "客户名称",
        "industry": "行业",
        "org_type": "机构类型",
        "tags": ["标签1", "标签2"],
        "description": "描述"
    }

    响应：
    {
        "success": true,
        "data": {
            "trust_source": "persona",
            "trust_source_label": "人设型",
            "business_type": "low_cognition_story",
            "confidence": 0.85,
            "recommended_topic_types": ["人设价值观类", "人设故事类"],
            "recommended_balance_config": {
                "信息密度": 0.4,
                "问题悬念": 0.7,
                "情绪波动": 0.8
            },
            "reasoning": "...",
            "warnings": []
        }
    }
    """
    try:
        data = request.get_json() or {}

        # 调用分类服务
        from services.business_classifier import BusinessClassifier, TrustSourceType

        classifier = BusinessClassifier()
        result = classifier.classify(data)

        # 转换枚举值为字符串
        trust_source_map = {
            TrustSourceType.KNOWLEDGE: 'knowledge',
            TrustSourceType.PERSONA: 'persona',
            TrustSourceType.INSTITUTION: 'institution',
            TrustSourceType.PRODUCT: 'product'
        }

        trust_label_map = {
            TrustSourceType.KNOWLEDGE: '知识型',
            TrustSourceType.PERSONA: '人设型',
            TrustSourceType.INSTITUTION: '机构型',
            TrustSourceType.PRODUCT: '产品型'
        }

        return jsonify({
            'success': True,
            'data': {
                'trust_source': trust_source_map.get(result.trust_source, 'knowledge'),
                'trust_source_label': trust_label_map.get(result.trust_source, '知识型'),
                'business_type': result.business_type.value,
                'confidence': result.confidence,
                'recommended_topic_types': result.recommended_topic_types,
                'recommended_balance_config': result.recommended_balance_config,
                'reasoning': result.reasoning,
                'warnings': result.warnings
            }
        })

    except Exception as e:
        logger.error(f"业务分类失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'业务分类失败: {str(e)}'
        }), 500


# =============================================================================
# 3. 均衡器预设 API
# =============================================================================

@script_bp.route('/balance-presets', methods=['GET'])
def api_get_balance_presets():
    """
    获取均衡器预设列表

    响应：
    {
        "success": true,
        "data": [
            {
                "name": "沉稳型",
                "code": "calm",
                "info_density": 80,
                "question_suspense": 50,
                "emotion_wave": 40,
                "interaction_freq": 40,
                "reward_distribution": 50,
                "difficulty_progression": 60,
                "description": "适合B端、企业服务、专业咨询"
            },
            ...
        ]
    }
    """
    try:
        presets = [
            {
                "name": "沉稳型",
                "code": "calm",
                "info_density": 80,
                "question_suspense": 50,
                "emotion_wave": 40,
                "interaction_freq": 40,
                "reward_distribution": 50,
                "difficulty_progression": 60,
                "description": "适合B端、企业服务、专业咨询"
            },
            {
                "name": "活力型",
                "code": "energetic",
                "info_density": 60,
                "question_suspense": 80,
                "emotion_wave": 90,
                "interaction_freq": 80,
                "reward_distribution": 90,
                "difficulty_progression": 40,
                "description": "适合快消品、年轻品牌、促销引流"
            },
            {
                "name": "专业型",
                "code": "professional",
                "info_density": 90,
                "question_suspense": 60,
                "emotion_wave": 50,
                "interaction_freq": 60,
                "reward_distribution": 70,
                "difficulty_progression": 80,
                "description": "适合知识付费、教育、培训"
            },
            {
                "name": "情感型",
                "code": "emotional",
                "info_density": 40,
                "question_suspense": 50,
                "emotion_wave": 95,
                "interaction_freq": 50,
                "reward_distribution": 60,
                "difficulty_progression": 40,
                "description": "适合母婴、情感、心理咨询"
            },
            {
                "name": "犀利型",
                "code": "sharp",
                "info_density": 70,
                "question_suspense": 90,
                "emotion_wave": 85,
                "interaction_freq": 70,
                "reward_distribution": 85,
                "difficulty_progression": 60,
                "description": "适合吐槽、对比、避坑类内容"
            },
            {
                "name": "温情型",
                "code": "warm",
                "info_density": 40,
                "question_suspense": 40,
                "emotion_wave": 80,
                "interaction_freq": 60,
                "reward_distribution": 50,
                "difficulty_progression": 30,
                "description": "适合陪伴、治愈、暖心内容"
            }
        ]

        return jsonify({
            'success': True,
            'data': presets
        })

    except Exception as e:
        logger.error(f"获取均衡器预设失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取均衡器预设失败: {str(e)}'
        }), 500


@script_bp.route('/balance-recommend', methods=['POST'])
def api_recommend_balance():
    """
    根据业务特征推荐均衡器配置

    请求体：
    {
        "trust_source": "persona",
        "topic_type": "人设价值观类"
    }

    响应：
    {
        "success": true,
        "data": {
            "config": {...},
            "reasoning": "..."
        }
    }
    """
    try:
        data = request.get_json() or {}
        trust_source = data.get('trust_source', 'knowledge')
        topic_type = data.get('topic_type', '')

        # 根据信任来源和选题类型推荐配置
        if trust_source == 'persona':
            base_config = {
                "信息密度": 40,
                "问题悬念": 70,
                "情绪波动": 85,
                "互动频率": 70,
                "奖励分布": 60,
                "难度递进": 60
            }
            reasoning = "人设型内容需要高情绪波动和高问题悬念来建立信任"
        elif trust_source == 'knowledge':
            base_config = {
                "信息密度": 80,
                "问题悬念": 60,
                "情绪波动": 50,
                "互动频率": 60,
                "奖励分布": 70,
                "难度递进": 80
            }
            reasoning = "知识型内容需要高信息密度和高难度递进来展示专业性"
        elif trust_source == 'institution':
            base_config = {
                "信息密度": 70,
                "问题悬念": 40,
                "情绪波动": 50,
                "互动频率": 50,
                "奖励分布": 60,
                "难度递进": 50
            }
            reasoning = "机构型内容以产品/服务信息为主，信任由品牌背书"
        else:  # product
            base_config = {
                "信息密度": 60,
                "问题悬念": 60,
                "情绪波动": 70,
                "互动频率": 60,
                "奖励分布": 70,
                "难度递进": 50
            }
            reasoning = "产品型内容需要平衡信息展示和情绪引导"

        # 根据选题类型微调
        if '人设价值观' in topic_type or '人设故事' in topic_type:
            base_config["情绪波动"] = max(base_config["情绪波动"], 85)
            base_config["奖励分布"] = min(base_config["奖励分布"], 55)
        elif '知识' in topic_type or '科普' in topic_type:
            base_config["信息密度"] = max(base_config["信息密度"], 80)
            base_config["难度递进"] = max(base_config["难度递进"], 75)
        elif '热点' in topic_type or '问题诊断' in topic_type:
            base_config["问题悬念"] = max(base_config["问题悬念"], 80)
            base_config["奖励分布"] = max(base_config["奖励分布"], 80)

        return jsonify({
            'success': True,
            'data': {
                'config': base_config,
                'reasoning': reasoning
            }
        })

    except Exception as e:
        logger.error(f"推荐均衡器配置失败: {e}")
        return jsonify({
            'success': False,
            'message': f'推荐均衡器配置失败: {str(e)}'
        }), 500


# =============================================================================
# 4. 模板 API
# =============================================================================

@script_bp.route('/templates', methods=['GET'])
def api_get_templates():
    """
    获取脚本模板列表

    Query参数：
    - type: 内容类型 (problem_diagnosis, solution, etc.)
    - duration: 时长 (short, medium, long)

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "problem_diagnosis_short",
                "name": "问题诊断·15秒快剪",
                "content_type": "problem_diagnosis",
                "content_type_label": "问题诊断类",
                "duration": "short",
                "duration_label": "15-30秒",
                "description": "快速戳中痛点，引发共鸣",
                "scenes": [...],
                "balance_config": {...},
                "trust_source": "知识型",
                "ip_required": false,
                "tips": [...]
            },
            ...
        ]
    }
    """
    try:
        from services.script_template import get_template_library, ContentType, Duration

        content_type_filter = request.args.get('type')
        duration_filter = request.args.get('duration')

        library = get_template_library()

        templates = library.list_all()

        # 筛选
        if content_type_filter:
            try:
                ct = ContentType(content_type_filter)
                templates = [t for t in templates if t.content_type == ct]
            except:
                pass

        if duration_filter:
            try:
                d = Duration(duration_filter)
                templates = [t for t in templates if t.duration == d]
            except:
                pass

        # 类型标签映射
        type_labels = {
            ContentType.PROBLEM_DIAGNOSIS: "问题诊断类",
            ContentType.SOLUTION: "解决方案类",
            ContentType.CASE_SHARE: "案例分享类",
            ContentType.PRODUCT_RECOMMEND: "产品推荐类",
            ContentType.KNOWLEDGE: "知识科普类",
            ContentType.HOT_TOPIC: "热点关联类",
            ContentType.PERSONA_STORY: "人设故事类",
            ContentType.PERSONA_VALUE: "人设价值观类",
            ContentType.VIEWPOINT: "观点输出类",
            ContentType.INSTITUTION_PRODUCT: "机构产品类"
        }

        duration_labels = {
            Duration.SHORT: "15-30秒",
            Duration.MEDIUM: "30-60秒",
            Duration.LONG: "60-90秒",
            Duration.EXTRA_LONG: "90秒以上"
        }

        result = []
        for t in templates:
            result.append({
                "id": t.id,
                "name": t.name,
                "content_type": t.content_type.value,
                "content_type_label": type_labels.get(t.content_type, t.content_type.value),
                "duration": t.duration.value,
                "duration_label": duration_labels.get(t.duration, t.duration.value),
                "description": t.description,
                "scenes": [
                    {
                        "index": s.index,
                        "name": s.name,
                        "time_range": s.time_range,
                        "emotion": s.emotion,
                        "content_type": s.content_type,
                        "visual_guide": s.visual_guide,
                        "narration_guide": s.narration_guide,
                        "hook_type": s.hook_type,
                        "reward_type": s.reward_type
                    }
                    for s in t.scenes
                ],
                "balance_config": t.balance_config,
                "trust_source": t.trust_source,
                "ip_required": t.ip_required,
                "tips": t.tips
            })

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"获取模板列表失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取模板列表失败: {str(e)}'
        }), 500


@script_bp.route('/templates/<template_id>', methods=['GET'])
def api_get_template(template_id):
    """获取单个模板详情"""
    try:
        from services.script_template import get_template

        template = get_template(template_id)
        if not template:
            return jsonify({
                'success': False,
                'message': '模板不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': template
        })

    except Exception as e:
        logger.error(f"获取模板详情失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取模板详情失败: {str(e)}'
        }), 500


@script_bp.route('/topic-types', methods=['GET'])
def api_get_topic_types():
    """
    获取选题类型列表

    响应：
    {
        "success": true,
        "data": [
            {
                "code": "problem_diagnosis",
                "name": "问题诊断类",
                "structure": "痛点前置→问题展开→原因揭示",
                "emotion_curve": "高→中→低",
                "recommended_duration": "15-30秒",
                "hook_density": "高密度",
                "trust_requirement": "低",
                "conversion_power": "中",
                "trust_source": "知识型"
            },
            ...
        ]
    }
    """
    try:
        topic_types = [
            {
                "code": "problem_diagnosis",
                "name": "问题诊断类",
                "structure": "痛点前置→问题展开→原因揭示",
                "emotion_curve": "高→中→低",
                "recommended_duration": "15-30秒",
                "hook_density": "高密度",
                "trust_requirement": "低",
                "conversion_power": "中",
                "trust_source": "知识型",
                "description": "快速戳中痛点，引发共鸣，适合涨粉"
            },
            {
                "code": "solution",
                "name": "解决方案类",
                "structure": "痛点引入→方案→验证",
                "emotion_curve": "低→中→高",
                "recommended_duration": "30-60秒",
                "hook_density": "中密度",
                "trust_requirement": "中",
                "conversion_power": "高",
                "trust_source": "知识型",
                "description": "提供解决方案，转化力强"
            },
            {
                "code": "case_share",
                "name": "案例分享类",
                "structure": "背景→冲突→转折→结果",
                "emotion_curve": "平→高→平",
                "recommended_duration": "60-90秒",
                "hook_density": "低密度",
                "trust_requirement": "高",
                "conversion_power": "高",
                "trust_source": "知识型+人设型",
                "description": "真实案例分享，高信任要求"
            },
            {
                "code": "product_recommend",
                "name": "产品推荐类",
                "structure": "痛点→产品→优势→CTA",
                "emotion_curve": "平→高→平",
                "recommended_duration": "15-30秒",
                "hook_density": "高密度",
                "trust_requirement": "低",
                "conversion_power": "最高",
                "trust_source": "知识型/机构型",
                "description": "产品种草，需要出镜展示"
            },
            {
                "code": "knowledge",
                "name": "知识科普类",
                "structure": "提问→揭秘→应用→总结",
                "emotion_curve": "低→中→中→高",
                "recommended_duration": "30-60秒",
                "hook_density": "低密度",
                "trust_requirement": "低",
                "conversion_power": "中",
                "trust_source": "知识型",
                "description": "知识干货输出，建立专业形象"
            },
            {
                "code": "hot_topic",
                "name": "热点关联类",
                "structure": "热点切入→观点→价值",
                "emotion_curve": "高→平→高",
                "recommended_duration": "15-30秒",
                "hook_density": "高密度",
                "trust_requirement": "低",
                "conversion_power": "低",
                "trust_source": "知识型",
                "description": "蹭热点，快速获取流量"
            },
            {
                "code": "persona_story",
                "name": "人设故事类",
                "structure": "故事导入→观点表达→价值观输出",
                "emotion_curve": "平→高→高",
                "recommended_duration": "60-90秒",
                "hook_density": "低密度",
                "trust_requirement": "高",
                "conversion_power": "中",
                "trust_source": "人设型",
                "description": "必须出镜，通过人设建立信任"
            },
            {
                "code": "persona_value",
                "name": "人设价值观类",
                "structure": "话题→观点→冲突→价值观",
                "emotion_curve": "中高→高→更高",
                "recommended_duration": "30-90秒",
                "hook_density": "中密度",
                "trust_requirement": "高",
                "conversion_power": "中高",
                "trust_source": "人设型",
                "description": "必须出镜，通过价值观认同建立信任"
            },
            {
                "code": "viewpoint",
                "name": "观点输出类",
                "structure": "现象→观点→论证→结论",
                "emotion_curve": "平→高→高",
                "recommended_duration": "30-180秒",
                "hook_density": "中密度",
                "trust_requirement": "中",
                "conversion_power": "中",
                "trust_source": "均可",
                "description": "输出观点，可出镜可不出"
            },
            {
                "code": "institution_product",
                "name": "机构产品类",
                "structure": "产品→规格→对比→保障",
                "emotion_curve": "平→中→平",
                "recommended_duration": "15-60秒",
                "hook_density": "中密度",
                "trust_requirement": "低",
                "conversion_power": "高",
                "trust_source": "机构型",
                "description": "不需要出镜，信任由机构承担"
            }
        ]

        return jsonify({
            'success': True,
            'data': topic_types
        })

    except Exception as e:
        logger.error(f"获取选题类型失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取选题类型失败: {str(e)}'
        }), 500


# =============================================================================
# 5. IP配置 API
# =============================================================================

@script_bp.route('/ip-configs', methods=['GET'])
def api_get_ip_configs():
    """
    获取IP人设配置列表

    响应：
    {
        "success": true,
        "data": [
            {
                "id": "preset_companion",
                "name": "陪伴者",
                "persona_type": "陪伴者",
                "speaking_mode": "数字人出镜",
                "digital_style": "邻家姐姐",
                "appearance_desc": "25-30岁邻家姐姐形象...",
                "voice_desc": "温柔、语速适中...",
                "speech_style": "温暖共情，像朋友聊天..."
            },
            ...
        ]
    }
    """
    try:
        from services.ip_persona_manager import IPConfigManager

        manager = IPConfigManager()
        configs = manager.list_presets()

        result = []
        for config in configs:
            result.append({
                "id": config.id,
                "name": config.name,
                "persona_type": config.persona_type.value,
                "speaking_mode": config.speaking_mode.value,
                "digital_style": config.digital_style.value if config.digital_style else None,
                "appearance_desc": config.appearance_desc,
                "voice_desc": config.voice_desc,
                "gesture_desc": config.gesture_desc,
                "speech_style": config.speech_style,
                "personality_tags": config.personality_tags,
                "backstory": config.backstory,
                "values": config.values
            })

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"获取IP配置失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'获取IP配置失败: {str(e)}'
        }), 500


@script_bp.route('/ip-configs/<config_id>', methods=['GET'])
def api_get_ip_config(config_id):
    """获取单个IP配置详情"""
    try:
        from services.ip_persona_manager import IPConfigManager

        manager = IPConfigManager()
        config = manager.get_config(config_id)

        if not config:
            return jsonify({
                'success': False,
                'message': 'IP配置不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': config.to_dict()
        })

    except Exception as e:
        logger.error(f"获取IP配置详情失败: {e}")
        return jsonify({
            'success': False,
            'message': f'获取IP配置详情失败: {str(e)}'
        }), 500


# =============================================================================
# 6. 奖励点预览 API
# =============================================================================

@script_bp.route('/reward-preview', methods=['POST'])
def api_reward_preview():
    """
    预览奖励点分布

    请求体：
    {
        "duration": 60,
        "balance_config": {
            "信息密度": 0.6,
            "问题悬念": 0.5,
            "情绪波动": 0.75,
            "互动频率": 0.5,
            "奖励分布": 0.8,
            "难度递进": 0.5
        }
    }

    响应：
    {
        "success": true,
        "data": {
            "total_points": 4,
            "points": [
                {"time": 3, "time_range": "0-5秒", "type": "知识奖励", "description": "抛出数据/事实"},
                {"time": 12, "time_range": "10-15秒", "type": "思考奖励", "description": "提出问题"},
                ...
            ],
            "chart": "●●●────●─────●───────○",
            "density_by_period": {
                "0-10秒": 3.0,
                "10-30秒": 1.5,
                "30-60秒": 1.0,
                "60秒+": 0.8
            },
            "summary": "前10秒奖励密集，后续逐渐拉长，符合即时反馈递减原则"
        }
    }
    """
    try:
        data = request.get_json() or {}
        duration = data.get('duration', 60)
        balance_config = data.get('balance_config', {})

        if duration < 5 or duration > 300:
            return jsonify({
                'success': False,
                'message': '时长必须在5-300秒之间'
            }), 400

        # 调用奖励点服务
        from services.reward_point_system import RewardPointService

        service = RewardPointService()
        result = service.calculate(duration, balance_config)

        # 生成可视化图表
        chart = service.generate_visual_chart(duration, result['points'])

        # 计算各时间段密度
        density = result.get('density_by_period', {})

        return jsonify({
            'success': True,
            'data': {
                'total_points': result['total_points'],
                'points': [
                    {
                        'time': p.get('time_start', 0),
                        'time_range': f"{int(p.get('time_start', 0))}-{int(p.get('time_end', 0))}秒",
                        'type': p.get('reward_type', '知识奖励'),
                        'description': p.get('content_guidance', '')
                    }
                    for p in result['points']
                ],
                'chart': chart,
                'density_by_period': density,
                'summary': _generate_reward_summary(result, balance_config)
            }
        })

    except Exception as e:
        logger.error(f"奖励点预览失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'奖励点预览失败: {str(e)}'
        }), 500


def _generate_reward_summary(result, balance_config):
    """生成奖励点总结"""
    total = result.get('total_points', 0)
    reward_dist = balance_config.get('奖励分布', 0.6)

    if reward_dist >= 0.8:
        style = "前密后疏"
    elif reward_dist >= 0.5:
        style = "适度前密"
    else:
        style = "均匀分布"

    return f"共{total}个奖励点，{style}分布，符合即时反馈递减原则"


# =============================================================================
# 7. 脚本生成增强 API
# =============================================================================

@script_bp.route('/generate', methods=['POST'])
def api_generate_script():
    """
    生成短视频脚本（增强版）

    请求体：
    {
        "portrait_id": 123,           // 可选，从画像获取配置
        "topic": "宝宝拉肚子怎么办",
        "topic_type": "问题诊断类",
        "duration": 30,
        "ip_config": {                 // 可选，使用指定IP配置
            "name": "小李妈妈",
            "speaking_mode": "数字人出镜",
            "digital_style": "知性妈妈"
        },
        "balance_config": {           // 可选，使用指定均衡器
            "信息密度": 60,
            "问题悬念": 50,
            "情绪波动": 70
        },
        "enable_evaluation": true,    // 是否生成后评分
        "enable_reward_preview": true  // 是否显示奖励点预览
    }

    响应：
    {
        "success": true,
        "data": {
            "meta": {
                "topic": "宝宝拉肚子怎么办",
                "topic_type": "问题诊断类",
                "duration": 30
            },
            "style_guide": {
                "visual_style": "...",
                "tone": "..."
            },
            "equalizer": {...},
            "scenes": [...],
            "quality_report": {...},     // 评分报告
            "reward_preview": {...}      // 奖励点预览
        }
    }
    """
    try:
        data = request.get_json() or {}

        topic = data.get('topic')
        topic_type = data.get('topic_type', '问题诊断类')
        duration = data.get('duration', 30)
        portrait_id = data.get('portrait_id')
        ip_config = data.get('ip_config', {})
        balance_config = data.get('balance_config', {})
        enable_evaluation = data.get('enable_evaluation', True)
        enable_reward_preview = data.get('enable_reward_preview', True)

        if not topic:
            return jsonify({
                'success': False,
                'message': '缺少选题'
            }), 400

        # 如果有画像ID，获取画像数据
        portrait_data = {}
        if portrait_id:
            try:
                from models.public_models import SavedPortrait
                portrait = SavedPortrait.query.get(portrait_id)
                if portrait:
                    portrait_data = portrait.portrait_data or {}
            except Exception as e:
                logger.warning(f"获取画像失败: {e}")

        # 如果没有指定配置，使用画像中的配置
        if not ip_config and portrait_data:
            ip_config = portrait_data.get('ip_config', {})

        if not balance_config and portrait_data:
            # 尝试从运营规划获取均衡器配置
            operations_plan = portrait_data.get('operations_plan', {})
            balance_config = operations_plan.get('balance_config', {})

        # 获取模板
        from services.script_template import recommend_template
        template = recommend_template(
            content_type=_topic_type_to_template_type(topic_type),
            duration=_duration_to_level(duration)
        )

        # 构建生成请求
        from services.script_generator import GenerationRequest
        request_obj = GenerationRequest(
            topic=topic,
            topic_type=topic_type,
            duration=duration,
            ip_config=ip_config,
            balance_config=balance_config,
            trust_source=_infer_trust_source(topic_type, portrait_data)
        )

        # 生成脚本
        from services.script_generator import ScriptGenerator
        generator = ScriptGenerator()
        output = generator.generate(request_obj)

        result = {
            'meta': output.meta,
            'style_guide': output.style_guide,
            'equalizer': output.equalizer,
            'scenes': output.scenes,
            'script_info': output.script_info,
            'generated_at': output.generated_at
        }

        # 评分
        if enable_evaluation:
            from services.script_scorer import ScriptScorer, TrustSourceType
            scorer = ScriptScorer()
            trust_type = _infer_trust_source_type(topic_type, portrait_data)
            report = scorer.score({
                'title': output.meta.get('title', ''),
                'scenes': output.scenes,
                'narration': output.script_info.get('narration', '')
            }, trust_type)
            result['quality_report'] = report.to_dict()

        # 奖励点预览
        if enable_reward_preview:
            from services.reward_point_system import RewardPointService
            reward_service = RewardPointService()
            reward_data = reward_service.calculate(duration, balance_config)
            chart = reward_service.generate_visual_chart(duration, reward_data.get('points', []))

            result['reward_preview'] = {
                'total_points': reward_data.get('total_points', 0),
                'points': reward_data.get('points', []),
                'chart': chart,
                'density_by_period': reward_data.get('density_by_period', {})
            }

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"脚本生成失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'脚本生成失败: {str(e)}'
        }), 500


def _topic_type_to_template_type(topic_type):
    """选题类型转模板类型"""
    mapping = {
        "问题诊断类": "problem_diagnosis",
        "解决方案类": "solution",
        "案例分享类": "case_share",
        "产品推荐类": "product_recommend",
        "知识科普类": "knowledge",
        "热点关联类": "hot_topic",
        "人设故事类": "persona_story",
        "人设价值观类": "persona_value",
        "观点输出类": "viewpoint",
        "机构产品类": "institution_product"
    }
    return mapping.get(topic_type, "problem_diagnosis")


def _duration_to_level(duration):
    """时长转等级"""
    if duration <= 30:
        return "short"
    elif duration <= 60:
        return "medium"
    elif duration <= 90:
        return "long"
    else:
        return "extra_long"


def _infer_trust_source(topic_type, portrait_data):
    """推断信任来源"""
    if '人设' in topic_type or '故事' in topic_type:
        return 'persona'
    elif '机构' in topic_type or '产品' in topic_type:
        return 'institution'
    elif portrait_data:
        # 尝试从画像推断
        business_type = portrait_data.get('business_type', '')
        if '知识' in business_type or '教育' in business_type:
            return 'knowledge'
        elif '人设' in business_type:
            return 'persona'
        elif '机构' in business_type:
            return 'institution'
    return 'knowledge'


def _infer_trust_source_type(topic_type, portrait_data):
    """推断信任来源类型枚举"""
    from services.script_scorer import TrustSourceType

    source = _infer_trust_source(topic_type, portrait_data)
    mapping = {
        'knowledge': TrustSourceType.KNOWLEDGE,
        'persona': TrustSourceType.PERSONA,
        'institution': TrustSourceType.INSTITUTION,
        'product': TrustSourceType.PRODUCT
    }
    return mapping.get(source, TrustSourceType.KNOWLEDGE)


# =============================================================================
# 8. 辅助API
# =============================================================================

@script_bp.route('/health', methods=['GET'])
def api_health():
    """健康检查"""
    try:
        # 测试各模块导入
        from services.script_scorer import ScriptScorer
        from services.business_classifier import BusinessClassifier
        from services.reward_point_system import RewardPointService
        from services.script_template import get_template_library
        from services.ip_persona_manager import IPConfigManager

        # 测试实例化
        ScriptScorer()
        BusinessClassifier()
        RewardPointService()
        get_template_library()
        IPConfigManager()

        return jsonify({
            'success': True,
            'message': '所有模块正常',
            'modules': {
                'script_scorer': 'OK',
                'business_classifier': 'OK',
                'reward_point_system': 'OK',
                'script_template': 'OK',
                'ip_persona_manager': 'OK'
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'模块检查失败: {str(e)}',
            'error': str(e)
        }), 500


# =============================================================================
# 注册蓝图（供 app.py 调用）
# =============================================================================

def register_script_blueprint(app):
    """注册蓝图到Flask应用"""
    from routes.script_api import script_bp
    app.register_blueprint(script_bp)
