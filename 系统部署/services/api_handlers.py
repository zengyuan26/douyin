"""
短视频脚本生成API接口层

提供统一的RESTful接口，供前端调用

接口列表：
- POST /api/script/generate     - 生成脚本
- POST /api/script/evaluate     - 评估脚本
- GET  /api/topics             - 获取选题列表
- POST /api/topics             - 创建选题
- GET  /api/ip-presets         - 获取IP预设
- POST /api/ab-test            - 创建A/B测试
- GET  /api/ab-test/{id}       - 获取测试结果
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json


# =============================================================================
# 请求/响应数据结构
# =============================================================================

@dataclass
class GenerateScriptRequest:
    """生成脚本请求"""
    topic: str
    topic_type: str
    duration: int
    ip_config: Dict[str, Any]
    balance_config: Dict[str, Any]
    trust_source: str
    template_id: Optional[str] = None


@dataclass
class EvaluateScriptRequest:
    """评估脚本请求"""
    script: Dict[str, Any]
    trust_source: str


@dataclass
class ApiResponse:
    """统一API响应"""
    success: bool
    data: Any = None
    error: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.message:
            result["message"] = self.message
        return result


# =============================================================================
# API路由处理器
# =============================================================================

class ScriptApiHandler:
    """脚本生成API处理器"""

    def __init__(self):
        self._init_services()

    def _init_services(self):
        """初始化服务"""
        from services.script_generator import ScriptGenerator
        from services.script_scorer import ScriptScorer, TrustSourceType
        from services.topic_system import TopicLibrary, TopicClassifier
        from services.ip_persona_manager import IPConfigManager
        from services.ab_test_engine import ABTestEngine

        self.generator = ScriptGenerator()
        self.scorer = ScriptScorer()
        self.topic_library = TopicLibrary()
        self.topic_classifier = TopicClassifier()
        self.ip_manager = IPConfigManager()
        self.ab_engine = ABTestEngine()

    # =========================================================================
    # 脚本生成接口
    # =========================================================================

    def generate_script(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/script/generate

        生成短视频脚本
        """
        try:
            # 验证参数
            required_fields = ["topic", "topic_type", "duration", "balance_config", "trust_source"]
            for field in required_fields:
                if field not in request:
                    return ApiResponse(
                        success=False,
                        error=f"Missing required field: {field}"
                    )

            # 构建IP配置
            ip_config = request.get("ip_config", {})
            if not ip_config.get("name"):
                ip_config["name"] = "默认IP"

            # 生成脚本
            from services.script_generator import generate_script

            result = generate_script(
                topic=request["topic"],
                topic_type=request["topic_type"],
                duration=request["duration"],
                ip_config=ip_config,
                balance_config=request["balance_config"],
                trust_source=request["trust_source"]
            )

            return ApiResponse(
                success=True,
                data=result,
                message="脚本生成成功"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def evaluate_script(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/script/evaluate

        评估脚本质量
        """
        try:
            script = request.get("script", {})
            trust_source = request.get("trust_source", "知识型")

            if not script:
                return ApiResponse(
                    success=False,
                    error="Script data is required"
                )

            from services.script_scorer import TrustSourceType

            type_mapping = {
                "知识型": TrustSourceType.KNOWLEDGE,
                "人设型": TrustSourceType.PERSONA,
                "机构型": TrustSourceType.INSTITUTION,
                "产品型": TrustSourceType.PRODUCT
            }

            trust_type = type_mapping.get(trust_source, TrustSourceType.KNOWLEDGE)
            report = self.scorer.score(script, trust_type)

            return ApiResponse(
                success=True,
                data=report.to_dict(),
                message="评估完成"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def optimize_script(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/script/optimize

        根据评分建议优化脚本
        """
        try:
            script = request.get("script", {})
            target_score = request.get("target_score", 80)

            # 先评分
            trust_source = request.get("trust_source", "知识型")
            from services.script_scorer import TrustSourceType

            type_mapping = {
                "知识型": TrustSourceType.KNOWLEDGE,
                "人设型": TrustSourceType.PERSONA,
                "机构型": TrustSourceType.INSTITUTION,
                "产品型": TrustSourceType.PRODUCT
            }
            trust_type = type_mapping.get(trust_source, TrustSourceType.KNOWLEDGE)

            report = self.scorer.score(script, trust_type)

            # 如果已达标，直接返回
            if report.total_score >= target_score:
                return ApiResponse(
                    success=True,
                    data={
                        "original_score": report.total_score,
                        "optimized": False,
                        "suggestions": report.suggestions,
                        "message": "脚本已达目标分数"
                    }
                )

            # 生成优化建议
            suggestions = self._generate_optimization_suggestions(report)

            return ApiResponse(
                success=True,
                data={
                    "original_score": report.total_score,
                    "target_score": target_score,
                    "suggestions": suggestions,
                    "optimized": True
                }
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def _generate_optimization_suggestions(self, report) -> List[Dict[str, Any]]:
        """生成优化建议"""
        suggestions = []

        # 情绪评分优化
        if report.emotion_score < 70:
            suggestions.append({
                "dimension": "情绪",
                "current_score": report.emotion_score,
                "target_score": 80,
                "tips": [
                    "增加情绪词密度，每15秒至少1个情绪词",
                    "使用强情绪词如：太棒了、崩溃、救命",
                    "增加情绪转折，制造情绪波动"
                ]
            })

        # 节奏评分优化
        if report.rhythm_score < 70:
            suggestions.append({
                "dimension": "节奏",
                "current_score": report.rhythm_score,
                "target_score": 80,
                "tips": [
                    "强化前3秒钩子，使用痛点/悬念/反差开头",
                    "确保每个场景有1个节奏峰值",
                    "检查奖励点分布，遵循前密后疏原则"
                ]
            })

        # 互动评分优化
        if report.interaction_score < 70:
            suggestions.append({
                "dimension": "互动",
                "current_score": report.interaction_score,
                "target_score": 80,
                "tips": [
                    "增加问句密度，每20-30秒设置一个问句",
                    "结尾必须有CTA：关注、点赞、评论",
                    "增加互动引导，如'评论区说说'"
                ]
            })

        return suggestions

    # =========================================================================
    # 选题管理接口
    # =========================================================================

    def list_topics(self, params: Dict[str, Any]) -> ApiResponse:
        """
        GET /api/topics

        获取选题列表
        """
        try:
            topic_type = params.get("topic_type")
            status = params.get("status")
            limit = params.get("limit", 20)

            topics = self.topic_library.list_topics(
                topic_type=self._parse_topic_type(topic_type) if topic_type else None,
                limit=limit
            )

            return ApiResponse(
                success=True,
                data={"topics": [t.to_dict() for t in topics]},
                message=f"获取到{len(topics)}个选题"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def create_topic(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/topics

        创建选题
        """
        try:
            from services.topic_system import Topic, TopicType, TopicStatus

            required_fields = ["title", "topic_type"]
            for field in required_fields:
                if field not in request:
                    return ApiResponse(
                        success=False,
                        error=f"Missing required field: {field}"
                    )

            topic = Topic(
                id="",
                title=request["title"],
                topic_type=TopicType(request["topic_type"]),
                content_summary=request.get("content_summary", ""),
                target_keywords=request.get("keywords", []),
                status=TopicStatus.DRAFT
            )

            topic_id = self.topic_library.add_topic(topic)

            return ApiResponse(
                success=True,
                data={"topic_id": topic_id},
                message="选题创建成功"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def search_topics(self, params: Dict[str, Any]) -> ApiResponse:
        """
        GET /api/topics/search

        搜索选题
        """
        try:
            keyword = params.get("keyword", "")
            limit = params.get("limit", 20)

            topics = self.topic_library.search_topics(keyword, limit)

            return ApiResponse(
                success=True,
                data={"topics": [t.to_dict() for t in topics]},
                message=f"搜索到{len(topics)}个选题"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def recommend_topics(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/topics/recommend

        推荐选题
        """
        try:
            business_type = request.get("business_type", "mixed")
            limit = request.get("limit", 5)

            topic_types = self.topic_classifier.classify(business_type)
            recommendations = self.topic_classifier.recommend_topics(
                topic_types,
                self.topic_library,
                limit
            )

            return ApiResponse(
                success=True,
                data={
                    "recommendations": [
                        {
                            "topic": r.topic.to_dict(),
                            "match_score": r.match_score,
                            "reasons": r.reasons,
                            "balance_config": r.balance_config
                        }
                        for r in recommendations
                    ]
                },
                message=f"推荐了{len(recommendations)}个选题"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    # =========================================================================
    # IP预设接口
    # =========================================================================

    def list_ip_presets(self) -> ApiResponse:
        """
        GET /api/ip-presets

        获取IP预设列表
        """
        try:
            presets = self.ip_manager.list_presets()

            return ApiResponse(
                success=True,
                data={
                    "presets": [p.to_dict() for p in presets]
                },
                message=f"获取到{len(presets)}个IP预设"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def decide_speaking_mode(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/ip/speaking-mode

        决定出镜方式
        """
        try:
            from services.ip_persona_manager import IPSpeakingModeDecider

            decider = IPSpeakingModeDecider()

            result = decider.decide(
                topic_type=request.get("topic_type", ""),
                trust_source=request.get("trust_source", ""),
                user_preference=request.get("user_preference")
            )

            return ApiResponse(
                success=True,
                data=result,
                message="出镜方式决策完成"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    # =========================================================================
    # 均衡器接口
    # =========================================================================

    def get_balance_presets(self) -> ApiResponse:
        """
        GET /api/balance-presets

        获取均衡器预设模式
        """
        try:
            presets = {
                "沉稳型": {
                    "name": "沉稳型",
                    "description": "适合B端、企业服务、专业咨询",
                    "config": {
                        "信息密度": 0.80,
                        "问题悬念": 0.50,
                        "情绪波动": 0.40,
                        "互动频率": 0.40,
                        "奖励分布": 0.50,
                        "难度递进": 0.60
                    }
                },
                "活力型": {
                    "name": "活力型",
                    "description": "适合快消品、年轻品牌、促销引流",
                    "config": {
                        "信息密度": 0.60,
                        "问题悬念": 0.80,
                        "情绪波动": 0.90,
                        "互动频率": 0.80,
                        "奖励分布": 0.90,
                        "难度递进": 0.40
                    }
                },
                "专业型": {
                    "name": "专业型",
                    "description": "适合知识付费、教育、培训",
                    "config": {
                        "信息密度": 0.90,
                        "问题悬念": 0.60,
                        "情绪波动": 0.50,
                        "互动频率": 0.60,
                        "奖励分布": 0.70,
                        "难度递进": 0.80
                    }
                },
                "情感型": {
                    "name": "情感型",
                    "description": "适合母婴、情感、心理咨询",
                    "config": {
                        "信息密度": 0.40,
                        "问题悬念": 0.50,
                        "情绪波动": 0.95,
                        "互动频率": 0.50,
                        "奖励分布": 0.60,
                        "难度递进": 0.40
                    }
                },
                "犀利型": {
                    "name": "犀利型",
                    "description": "适合吐槽、对比、避坑类内容",
                    "config": {
                        "信息密度": 0.70,
                        "问题悬念": 0.90,
                        "情绪波动": 0.85,
                        "互动频率": 0.70,
                        "奖励分布": 0.85,
                        "难度递进": 0.60
                    }
                },
                "温情型": {
                    "name": "温情型",
                    "description": "适合陪伴、治愈、暖心内容",
                    "config": {
                        "信息密度": 0.40,
                        "问题悬念": 0.40,
                        "情绪波动": 0.80,
                        "互动频率": 0.60,
                        "奖励分布": 0.50,
                        "难度递进": 0.30
                    }
                }
            }

            return ApiResponse(
                success=True,
                data={"presets": presets},
                message="获取均衡器预设成功"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    # =========================================================================
    # A/B测试接口
    # =========================================================================

    def create_ab_test(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/ab-test

        创建A/B测试
        """
        try:
            test_id = request.get("test_id")
            variants = request.get("variants", [])

            if not test_id or not variants:
                return ApiResponse(
                    success=False,
                    error="test_id and variants are required"
                )

            result = self.ab_engine.create_test(test_id, variants)

            return ApiResponse(
                success=True,
                data={
                    "test_id": result.test_id,
                    "variants": [v.to_dict() for v in result.variants]
                },
                message="A/B测试创建成功"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def get_ab_test(self, test_id: str) -> ApiResponse:
        """
        GET /api/ab-test/{test_id}

        获取A/B测试结果
        """
        try:
            result = self.ab_engine.get_test(test_id)

            if not result:
                return ApiResponse(
                    success=False,
                    error=f"Test not found: {test_id}"
                )

            return ApiResponse(
                success=True,
                data={
                    "test_id": result.test_id,
                    "variants": [v.to_dict() for v in result.variants],
                    "winner_id": result.winner_id,
                    "confidence": result.confidence,
                    "recommendations": result.recommendations
                }
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    def update_ab_metrics(self, request: Dict[str, Any]) -> ApiResponse:
        """
        POST /api/ab-test/{test_id}/metrics

        更新A/B测试指标
        """
        try:
            test_id = request.get("test_id")
            variant_id = request.get("variant_id")
            metrics = request.get("metrics", {})

            if not all([test_id, variant_id, metrics]):
                return ApiResponse(
                    success=False,
                    error="test_id, variant_id and metrics are required"
                )

            self.ab_engine.update_metrics(test_id, variant_id, metrics)

            return ApiResponse(
                success=True,
                message="指标更新成功"
            )

        except Exception as e:
            return ApiResponse(
                success=False,
                error=str(e)
            )

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _parse_topic_type(self, topic_type: str):
        """解析选题类型"""
        from services.topic_system import TopicType
        try:
            return TopicType(topic_type)
        except ValueError:
            return None


# =============================================================================
# Flask路由定义（示例）
# =============================================================================

def register_routes(app):
    """注册Flask路由"""
    handler = ScriptApiHandler()

    # 脚本生成
    app.add_url_rule(
        "/api/script/generate",
        "generate_script",
        lambda: handler.generate_script(request.json).to_dict(),
        methods=["POST"]
    )

    app.add_url_rule(
        "/api/script/evaluate",
        "evaluate_script",
        lambda: handler.evaluate_script(request.json).to_dict(),
        methods=["POST"]
    )

    app.add_url_rule(
        "/api/script/optimize",
        "optimize_script",
        lambda: handler.optimize_script(request.json).to_dict(),
        methods=["POST"]
    )

    # 选题管理
    app.add_url_rule(
        "/api/topics",
        "list_topics",
        lambda: handler.list_topics(request.args).to_dict(),
        methods=["GET"]
    )

    app.add_url_rule(
        "/api/topics",
        "create_topic",
        lambda: handler.create_topic(request.json).to_dict(),
        methods=["POST"]
    )

    # IP预设
    app.add_url_rule(
        "/api/ip-presets",
        "list_ip_presets",
        lambda: handler.list_ip_presets().to_dict(),
        methods=["GET"]
    )

    # 均衡器预设
    app.add_url_rule(
        "/api/balance-presets",
        "get_balance_presets",
        lambda: handler.get_balance_presets().to_dict(),
        methods=["GET"]
    )

    # A/B测试
    app.add_url_rule(
        "/api/ab-test",
        "create_ab_test",
        lambda: handler.create_ab_test(request.json).to_dict(),
        methods=["POST"]
    )


# =============================================================================
# 便捷调用函数
# =============================================================================

def handle_api_request(
    endpoint: str,
    method: str,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    处理API请求的便捷函数

    Args:
        endpoint: API端点
        method: HTTP方法
        data: 请求数据
        params: URL参数

    Returns:
        dict: API响应
    """
    handler = ScriptApiHandler()

    # 路由映射
    routes = {
        ("POST", "/api/script/generate"): lambda: handler.generate_script(data),
        ("POST", "/api/script/evaluate"): lambda: handler.evaluate_script(data),
        ("POST", "/api/script/optimize"): lambda: handler.optimize_script(data),
        ("GET", "/api/topics"): lambda: handler.list_topics(params or {}),
        ("POST", "/api/topics"): lambda: handler.create_topic(data),
        ("GET", "/api/topics/search"): lambda: handler.search_topics(params or {}),
        ("POST", "/api/topics/recommend"): lambda: handler.recommend_topics(data),
        ("GET", "/api/ip-presets"): lambda: handler.list_ip_presets(),
        ("POST", "/api/ip/speaking-mode"): lambda: handler.decide_speaking_mode(data),
        ("GET", "/api/balance-presets"): lambda: handler.get_balance_presets(),
        ("POST", "/api/ab-test"): lambda: handler.create_ab_test(data),
    }

    # 处理带路径参数的路由
    if endpoint.startswith("/api/ab-test/") and method == "GET":
        test_id = endpoint.split("/")[-1]
        return handler.get_ab_test(test_id).to_dict()

    # 查找匹配的路由
    key = (method.upper(), endpoint)
    if key in routes:
        return routes[key]().to_dict()

    return ApiResponse(
        success=False,
        error=f"Unknown endpoint: {method} {endpoint}"
    ).to_dict()
