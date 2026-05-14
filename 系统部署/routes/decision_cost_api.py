from flask import Blueprint, jsonify, request
import os
import sys
import re
from datetime import datetime

# 尝试导入LLM服务
LLM_AVAILABLE = False
try:
    from services.llm import chat_with_llm
    LLM_AVAILABLE = True
    print("✓ LLM服务导入成功: chat_with_llm")
except ImportError as e:
    print(f"✗ LLM服务导入失败: {e}")

decision_cost_bp = Blueprint('decision_cost', __name__, url_prefix='/api/decision-cost')

def get_current_public_user():
    """获取当前登录用户"""
    try:
        from routes.public_api import get_current_user
        return get_current_user()
    except:
        return {"id": 1, "username": "test"}  # 测试用


# ==================== 第一阶段：分析接口 ====================

@decision_cost_bp.route('/step1-analyze', methods=['POST'])
def step1_analyze():
    """
    第一阶段分析：业务诊断 + 生成可复制选项供用户选择

    请求体：
    {
        "business": "心理咨询",
        "scope": "national",
        "resources": ["knowledge", "experience"]
    }

    返回：
    {
        "success": true,
        "data": {
            "step": 1,
            "modules": {
                "M1": { /* 业务本质诊断 */ },
                "M2": { /* 决策成本评估 */ },
                "M3": { /* 资产盘点 */ },
                "M4": { /* AI机遇分析 */ }
            },
            "replicable_options": [
                { "id": "course", "name": "在线课程", "icon": "📚", "summary": "...", "match_score": 95 }
            ]
        }
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    data = request.get_json() or {}
    business = data.get('business', '').strip()
    scope = data.get('scope', 'local')
    resources = data.get('resources', [])

    if not business:
        return jsonify({"success": False, "message": "请输入业务类型"}), 400

    # 调用LLM进行深度分析
    analysis_result = _llm_analyze_business(business, scope, resources)

    # 生成可复制方向选项
    replicable_options = _generate_replicable_options(business, scope, resources)

    return jsonify({
        "success": True,
        "data": {
            "step": 1,
            "modules": {
                "M1": analysis_result.get("M1", {}),
                "M2": analysis_result.get("M2", {}),
                "M3": analysis_result.get("M3", {}),
                "M4": analysis_result.get("M4", {})
            },
            "replicable_options": replicable_options,
            "llm_summary": analysis_result.get("summary", "")
        }
    })


def _llm_analyze_business(business: str, scope: str, resources: list) -> dict:
    """调用LLM进行业务深度分析"""

    # 构建资源描述
    resource_desc = "无" if not resources else "、".join([
        {"knowledge": "专业知识", "experience": "行业经验", "technique": "技术工艺",
         "brand": "品牌口碑", "customers": "客户资源", "capital": "资金支持"}.get(r, r)
        for r in resources
    ])

    # 范围描述
    scope_desc = {"local": "本地客户", "national": "全国客户", "global": "全球客户"}.get(scope, "本地客户")

    # LLM分析提示词 - 简化版
    prompt = f"""请分析这个业务，输出JSON：
业务：{business}
范围：{scope_desc}
资源：{resource_desc}

输出格式（纯JSON，不要任何其他文字）：
{{
  "summary": "一句话诊断",
  "M1": {{"title":"业务本质诊断","icon":"🔍","items":[{{"label":"卖什么","value":"xxx"}}],"summary":"xxx"}},
  "M2": {{"title":"决策成本评估","icon":"⏰","items":[{{"label":"瓶颈","value":"xxx"}}],"summary":"xxx"}},
  "M3": {{"title":"资产盘点","icon":"📦","items":[{{"label":"资产","value":"xxx"}}],"summary":"xxx"}},
  "M4": {{"title":"AI机遇分析","icon":"🤖","summary":"xxx","recommendations":["建议1","建议2"]}}
}}

直接输出JSON，不要解释。"""

    # 调用LLM
    if LLM_AVAILABLE:
        try:
            print(f"正在调用LLM分析: {business}")
            response = chat_with_llm([
                {"role": "system", "content": "你是一个专业的商业诊断顾问，擅长分析各类业务的商业模式、复制可能性和发展机遇。"},
                {"role": "user", "content": prompt}
            ])
            print(f"LLM响应长度: {len(response)}")
            print(f"LLM原始响应: {response[:500]}...")

            # 尝试提取JSON
            import json

            def fix_json(text):
                """尝试修复常见的JSON格式问题"""
                # 移除代码块标记
                if '```json' in text:
                    text = re.sub(r'```json\s*', '', text)
                if '```' in text:
                    text = re.sub(r'```\s*', '', text)

                # 移除多余的中文引号
                text = text.replace('"', '"').replace('"', '"')
                text = text.replace(''', "'").replace(''', "'")

                # 提取JSON部分
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1:
                    text = text[start:end+1]

                return text

            # 尝试直接解析
            try:
                result = json.loads(response)
            except:
                # 尝试修复后解析
                try:
                    fixed = fix_json(response)
                    result = json.loads(fixed)
                except:
                    # 打印详细错误信息
                    print(f"JSON解析失败，尝试修复...")
                    print(f"修复后内容: {fixed[:500] if 'fixed' in dir() else response[:500]}...")
                    raise ValueError("无法解析JSON")

            print(f"LLM解析成功")
            return result
        except Exception as e:
            print(f"LLM分析失败: {e}")
            import traceback
            traceback.print_exc()
            # LLM失败时使用备用规则
            return _fallback_analysis(business, scope, resources)
    else:
        # 没有LLM时使用备用规则
        print("LLM不可用，使用备用分析")
        return _fallback_analysis(business, scope, resources)


def _fallback_analysis(business: str, scope: str, resources: list) -> dict:
    """备用分析：当LLM不可用时使用规则分析"""
    business_lower = business.lower()
    is_local = _is_local_service_business(business_lower)

    summary = f"你的{business}需要根据具体情况进行深度分析。"

    # M1 - 业务本质
    m1 = {
        "title": "业务本质诊断",
        "icon": "🔍",
        "items": [
            {"label": "业务类型", "value": business, "detail": "待LLM深度分析"},
            {"label": "服务范围", "value": scope, "detail": "目标市场范围"}
        ],
        "summary": f"请配置LLM服务以获得更精准的分析",
        "expandable": True,
        "details": {"提示": "建议启用LLM服务以获得针对性分析"}
    }

    # M2 - 决策成本
    m2 = {
        "title": "决策成本评估",
        "icon": "⏰",
        "items": [
            {"label": "分析状态", "value": "待分析", "detail": "请配置LLM服务"}
        ],
        "summary": "请启用LLM获取详细分析"
    }

    # M3 - 资产盘点
    m3 = {
        "title": "资产盘点",
        "icon": "📦",
        "items": [
            {"label": "分析状态", "value": "待分析", "detail": "请配置LLM服务"}
        ],
        "summary": "请启用LLM获取详细分析"
    }

    # M4 - AI机遇
    m4 = {
        "title": "AI机遇分析",
        "icon": "🤖",
        "summary": "请启用LLM获取详细分析",
        "recommendations": ["启用LLM服务以获得AI机遇分析"]
    }

    return {
        "summary": summary,
        "M1": m1,
        "M2": m2,
        "M3": m3,
        "M4": m4
    }


# ==================== 第二阶段：路线规划接口 ====================

@decision_cost_bp.route('/step2-route', methods=['POST'])
def step2_route():
    """
    第二阶段：用户选择方向后，生成详细执行路线

    请求体：
    {
        "business": "心理咨询",
        "selected_options": ["course", "handbook"],
        "scope": "national",
        "resources": ["knowledge", "experience"]
    }

    返回：
    {
        "success": true,
        "data": {
            "step": 2,
            "routes": {
                "course": { /* 详细路线 */ },
                "handbook": { /* 详细路线 */ }
            }
        }
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    data = request.get_json() or {}
    business = data.get('business', '').strip()
    selected_options = data.get('selected_options', [])
    scope = data.get('scope', 'local')
    resources = data.get('resources', [])

    if not business or not selected_options:
        return jsonify({"success": False, "message": "缺少必要参数"}), 400

    # 构建资源描述
    resource_desc = "无" if not resources else "、".join([
        {"knowledge": "专业知识", "experience": "行业经验", "technique": "技术工艺",
         "brand": "品牌口碑", "customers": "客户资源", "capital": "资金支持"}.get(r, r)
        for r in resources
    ])

    scope_desc = {"local": "本地客户", "national": "全国客户", "global": "全球客户"}.get(scope, "本地客户")

    # 定义方向名称映射
    option_names = {
        "course": "在线课程",
        "handbook": "实操手册",
        "template": "模板工具",
        "membership": "社群会员",
        "franchise": "加盟授权",
        "saas": "SaaS工具",
        "content_marketing": "内容营销",
        "productize": "技艺产品化",
        "diaspora_service": "同乡服务",
        "deepen_local": "深耕本地"
    }

    # 生成各方向的详细路线
    routes = {}
    for option_id in selected_options:
        option_name = option_names.get(option_id, option_id)

        # 构建LLM提示词 - 简化版
        prompt = f"""业务：{business}
目标方向：{option_name}

输出JSON格式（纯JSON，不要任何其他文字）：
{{
  "name": "{option_name}",
  "icon": "📋",
  "core_insight": "为什么这个方向适合",
  "steps": [
    {{"phase":"准备期","title":"xxx","duration":"x周","deliverables":["交付物1"]}},
    {{"phase":"启动期","title":"xxx","duration":"x周","deliverables":["交付物2"]}},
    {{"phase":"成长期","title":"xxx","duration":"x周","deliverables":["交付物3"]}},
    {{"phase":"稳定期","title":"xxx","duration":"x周","deliverables":["交付物4"]}}
  ],
  "investment": "投入估算",
  "risks": [{{"type":"风险","level":"high/medium/low"}}]
}}

直接输出JSON，不要解释。"""

        # 调用LLM生成路线
        if LLM_AVAILABLE:
            try:
                print(f"正在调用LLM生成路线: {option_name}")
                response = chat_with_llm([
                    {"role": "system", "content": "你是一个专业的商业规划顾问，擅长设计可复制的商业模式和执行路线。"},
                    {"role": "user", "content": prompt}
                ])
                print(f"LLM路线响应: {response[:300]}...")

                import json

                def fix_json(text):
                    """尝试修复常见的JSON格式问题"""
                    if '```json' in text:
                        text = re.sub(r'```json\s*', '', text)
                    if '```' in text:
                        text = re.sub(r'```\s*', '', text)
                    text = text.replace('"', '"').replace('"', '"')
                    start = text.find('{')
                    end = text.rfind('}')
                    if start != -1 and end != -1:
                        text = text[start:end+1]
                    return text

                try:
                    route = json.loads(response)
                except:
                    fixed = fix_json(response)
                    route = json.loads(fixed)

                route["id"] = option_id
                routes[option_id] = route
                print(f"路线生成成功: {option_name}")
            except Exception as e:
                print(f"LLM路线生成失败: {e}")
                import traceback
                traceback.print_exc()
                # 失败时使用备用
                route = _generate_route_detail(option_id, business, scope, resources)
                if route:
                    routes[option_id] = route
        else:
            # 没有LLM时使用备用规则
            print("LLM不可用，使用备用路线")
            route = _generate_route_detail(option_id, business, scope, resources)
            if route:
                routes[option_id] = route

    return jsonify({
        "success": True,
        "data": {
            "step": 2,
            "routes": routes
        }
    })


# ==================== M1: 业务本质诊断 ====================

def _analyze_business_essence(business: str, scope: str, resources: list) -> dict:
    """M1: 分析业务本质"""
    business_lower = business.lower()

    # 判断是否是本地服务型业务（核心判断）
    is_local_service = _is_local_service_business(business_lower)

    # 判断卖什么
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "培训", "咨询", "教练"]):
        what = "知识服务"
        what_detail = "出售专业知识和经验"
    elif any(k in business_lower for k in ["装修", "设计", "工程", "机械", "IT", "技术", "厨"]):
        what = "技术服务"
        what_detail = "提供专业技术交付"
    elif any(k in business_lower for k in ["美容", "健身", "理发", "餐饮", "家政", "保洁", "按摩"]):
        what = "体验服务"
        what_detail = "提供线下体验和手工服务"
    elif any(k in business_lower for k in ["中介", "代理", "贸易", "供应", "房产", "猎头"]):
        what = "撮合服务"
        what_detail = "连接供需双方赚取差价或佣金"
    elif any(k in business_lower for k in ["零售", "电商", "批发", "超市"]):
        what = "商品销售"
        what_detail = "买卖商品赚取差价"
    elif any(k in business_lower for k in ["制造", "生产", "加工"]):
        what = "生产制造"
        what_detail = "生产产品销售"
    else:
        what = "服务/产品"
        what_detail = "需要进一步明确定位"

    # 判断卖给谁（考虑本地服务特性）
    customer_map = {
        "local": "本地C端客户",
        "national": "全国C端/B端客户",
        "global": "全球客户"
    }
    who = customer_map.get(scope, "本地客户")

    # 判断价格区间
    if "心理" in business or "法律" in business or "医" in business:
        price_range = "500-5000元/次（高端）"
    elif "设计" in business or "装修" in business:
        price_range = "1000-50000元/单"
    elif "培训" in business or "教育" in business:
        price_range = "100-10000元/人"
    elif "中介" in business or "代理" in business:
        price_range = "佣金制（5%-30%）"
    elif any(k in business_lower for k in ["美容", "健身", "家政"]):
        price_range = "100-2000元/次"
    else:
        price_range = "待评估"

    # 判断收入模式
    if "心理" in business or "法律" in business or "咨询" in business:
        revenue_model = "按次收费 + 长期顾问"
    elif "培训" in business or "教育" in business:
        revenue_model = "课程销售 + 持续复购"
    elif "中介" in business or "代理" in business:
        revenue_model = "佣金/差价"
    elif any(k in business_lower for k in ["美容", "健身"]):
        revenue_model = "会员卡 + 单次消费"
    else:
        revenue_model = "一次性销售/服务"

    # 信任机制分析（核心新增）
    trust_analysis = _analyze_trust_mechanism(business_lower, scope, is_local_service)

    # 竞争要素分析（考虑本地vs跨区域）
    competition_factors = _get_competition_factors(business_lower, scope, is_local_service)

    return {
        "title": "业务本质诊断",
        "icon": "🔍",
        "items": [
            {"label": "卖什么", "value": what, "detail": what_detail},
            {"label": "卖给谁", "value": who, "detail": "目标客户群体"},
            {"label": "价格区间", "value": price_range, "detail": "市场定价范围"},
            {"label": "收入模式", "value": revenue_model, "detail": "主要盈利方式"}
        ],
        "summary": f"你的{business}属于{what}，主要面向{who}，采用{revenue_model}模式。",
        "expandable": True,
        "details": {
            "核心价值": _get_core_value(business_lower),
            "商业模式": revenue_model,
            "竞争要素": competition_factors,
            "信任机制": trust_analysis["summary"]
        },
        # 新增：特殊分析结果
        "trust_analysis": trust_analysis,
        "is_local_service": is_local_service,
        "is_hard_to_replicate": is_local_service and scope == "local"
    }


def _is_local_service_business(business_lower: str) -> bool:
    """判断是否是本地服务型业务"""
    # 需要亲自到场、依赖本地口碑人情、难以标准化的服务
    local_service_keywords = [
        "餐饮", "饭店", "餐厅", "小吃", "早餐", "外卖",  # 餐饮类
        "美容", "美发", "理发", "理发店", "化妆",          # 美业
        "健身", "瑜伽", "舞蹈", "培训中心",               # 健身培训
        "家政", "保洁", "搬家", "清洗", "疏通",           # 家政类
        "维修", "电器", "手机", "电脑", "汽车", "洗车",   # 维修类
        "装修", "木工", "水电", "油漆",                   # 装修类（部分）
        "按摩", "足疗", "推拿", "理疗",                   # 保健类
        "摄影", "摄像", "婚庆", "主持",                   # 摄影主持
        "培训", "家教", "托管",                           # 教育培训
        "诊所", "药店", "医院",                           # 医疗类
        "法律", "财税", "公证",                           # 专业服务（部分）
    ]

    # 本地制造的关键词
    local_manufacturing = [
        "灌香肠", "腊肉", "腊肠", "腌菜", "酱料",        # 食品加工
        "豆腐", "豆芽", "面条", "馒头", "糕点",          # 食品加工
        "服装", "裁缝", "定制",                           # 裁缝定制
    ]

    # 检查是否是本地服务或本地制造
    for kw in local_service_keywords + local_manufacturing:
        if kw in business_lower:
            return True

    return False


def _analyze_trust_mechanism(business_lower: str, scope: str, is_local_service: bool) -> dict:
    """分析信任获取机制"""

    # 本地服务的信任机制
    if is_local_service and scope == "local":
        return {
            "summary": "本地人情型：靠口碑、关系介绍、回头客",
            "type": "人情口碑型",
            "description": "你的业务依赖本地社会关系网络，客户信任建立在长期接触、他人推荐和人情往来上。",
            "key_factors": ["邻里口碑", "关系介绍", "长期回头客", "老板本人"],
            "challenge": "这种信任很难'复制'到外地——外地客户不认识你，也没有共同的社会网络背书。",
            "implication": "如果要扩张外地市场，需要用'内容'建立新的信任背书，而不是简单复制模式。"
        }

    # 跨区域服务的信任机制
    elif is_local_service and scope in ["national", "global"]:
        return {
            "summary": "跨区域信任型：靠品牌、内容、私域",
            "type": "内容品牌型",
            "description": "你需要通过内容输出（抖音、小红书等）建立专业形象，用作品和案例说服陌生客户。",
            "key_factors": ["内容影响力", "作品展示", "客户评价", "专业资质"],
            "challenge": "没有本地社会网络背书，需要更强的内容营销能力。",
            "implication": "先把本地成功案例做成内容，吸引外地客户/同乡。"
        }

    # 知识服务型（天然可跨区域）
    elif any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "培训", "咨询"]):
        return {
            "summary": "专业资质型：靠证书、案例、平台背书",
            "type": "专业背书型",
            "description": "你的专业资质本身就是信任背书，可以通过远程方式服务全国客户。",
            "key_factors": ["专业资质", "成功案例", "平台认证", "行业口碑"],
            "challenge": "需要持续积累案例和口碑，线上获客成本较高。",
            "implication": "适合做线上课程/咨询，边际成本低，可规模化。"
        }

    # 技术服务型
    elif any(k in business_lower for k in ["设计", "装修", "IT", "软件", "开发"]):
        return {
            "summary": "作品驱动型：靠作品集、口碑案例",
            "type": "作品案例型",
            "description": "客户通过你的作品和案例判断能力，可以通过线上展示触达全国客户。",
            "key_factors": ["作品质量", "案例数量", "客户评价", "服务效率"],
            "challenge": "交付质量高度依赖个人/团队，可复制性有限。",
            "implication": "考虑标准化流程+培养团队，降低对个人的依赖。"
        }

    #撮合服务型
    elif any(k in business_lower for k in ["中介", "代理", "猎头", "房产"]):
        return {
            "summary": "资源撮合型：靠信息差、资源整合能力",
            "type": "资源整合型",
            "description": "你的核心价值是连接供需双方，消除信息差。",
            "key_factors": ["资源丰富度", "匹配效率", "服务态度", "行业人脉"],
            "challenge": "AI正在消灭信息差，平台化是威胁也是机会。",
            "implication": "考虑建立数据壁垒，向平台化方向演进。"
        }

    else:
        return {
            "summary": "综合型：混合多种信任机制",
            "type": "混合型",
            "description": "需要结合线上线下多种方式建立客户信任。",
            "key_factors": ["产品质量", "服务态度", "价格竞争力", "渠道覆盖"],
            "challenge": "需要平衡多方面的竞争要素。",
            "implication": "找出你最独特的竞争力，集中资源打造。"
        }


def _get_core_value(business_lower: str) -> str:
    if "心理" in business_lower: return "专业陪伴 + 信任关系"
    if "法律" in business_lower: return "专业保障 + 风险规避"
    if "教育" in business_lower: return "知识传递 + 能力提升"
    if "设计" in business_lower: return "创意方案 + 美学呈现"
    if "装修" in business_lower: return "空间规划 + 施工落地"
    if "中介" in business_lower: return "信息差消除 + 资源匹配"
    if "美容" in business_lower: return "形象提升 + 体验享受"
    if "健身" in business_lower: return "健康改善 + 形体塑造"
    return "专业价值 + 客户信任"


def _get_competition_factors(business_lower: str, scope: str = "local", is_local_service: bool = False) -> str:
    """获取竞争要素（根据服务类型和范围调整）"""

    # 本地服务型业务的竞争要素
    if is_local_service and scope == "local":
        return "口碑评价 > 价格 > 便利程度 > 服务态度 > 地理位置"

    # 跨区域服务型
    if is_local_service and scope in ["national", "global"]:
        return "内容影响力 > 作品案例 > 专业资质 > 价格 > 服务态度"

    # 各行业的竞争要素
    if "心理" in business_lower: return "专业资质 > 口碑评价 > 服务态度"
    if "法律" in business_lower: return "胜诉案例 > 专业资质 > 服务价格"
    if "教育" in business_lower: return "提分效果 > 师资力量 > 服务体验"
    if "设计" in business_lower: return "作品质量 > 创意能力 > 沟通效率"
    if "装修" in business_lower: return "施工质量 > 价格透明 > 售后保障"
    if "中介" in business_lower: return "资源丰富 > 匹配效率 > 服务态度"
    if "美容" in business_lower: return "技术效果 > 口碑 > 价格 > 环境"
    if "健身" in business_lower: return "效果明显 > 教练专业 > 价格 > 便利性"
    return "专业能力 > 服务质量 > 价格因素"


# ==================== M2: 决策成本评估 ====================

def _analyze_decision_cost(business: str, scope: str, resources: list) -> dict:
    """M2: 分析决策成本"""

    business_lower = business.lower()
    is_local_service = _is_local_service_business(business_lower)

    # 本地服务型业务的特殊分析
    if is_local_service:
        return _analyze_local_service(business, scope)

    # 判断时间陷阱类型
    if any(k in business_lower for k in ["心理", "法律", "财税", "咨询", "教练"]):
        trap_type = "时间换钱型"
        trap_desc = "每做一单都需要你亲自参与，无法规模化"
        can_scale = False
    elif any(k in business_lower for k in ["装修", "设计", "工程", "厨"]):
        trap_type = "规模诅咒型"
        trap_desc = "做大了反而更累，人力瓶颈明显"
        can_scale = False
    elif any(k in business_lower for k in ["美容", "健身", "家政", "保洁"]):
        trap_type = "人力依赖型"
        trap_desc = "极度依赖员工质量，难以标准化"
        can_scale = False
    elif any(k in business_lower for k in ["中介", "代理", "猎头"]):
        trap_type = "资源瓶颈型"
        trap_desc = "业绩取决于人脉和资源，难以复制"
        can_scale = False
    else:
        trap_type = "待诊断"
        trap_desc = "需要进一步分析"
        can_scale = None

    # 判断没你能否运转
    if "心理" in business_lower:
        without_you = "较难自动运转，需要专业背景"
        autonomy_score = 30
    elif "法律" in business_lower:
        without_you = "需要资质，替代性低"
        autonomy_score = 25
    elif "设计" in business_lower or "装修" in business_lower:
        without_you = "设计部分可部分外包，但核心仍需你把关"
        autonomy_score = 40
    elif "中介" in business_lower:
        without_you = "可以培养经纪人，逐步放手"
        autonomy_score = 50
    elif any(k in business_lower for k in ["美容", "健身"]):
        without_you = "可以培训技师，但质量控制难"
        autonomy_score = 35
    else:
        without_you = "需要评估具体情况"
        autonomy_score = 50

    # 计算可复制指数
    if any(k in business_lower for k in ["心理", "法律", "财税", "医"]):
        replication_score = 45
        replication_level = "中等"
    elif any(k in business_lower for k in ["培训", "教育", "咨询"]):
        replication_score = 55
        replication_level = "中等偏高"
    elif any(k in business_lower for k in ["设计", "装修", "中介"]):
        replication_score = 50
        replication_level = "中等"
    elif any(k in business_lower for k in ["美容", "健身", "家政"]):
        replication_score = 40
        replication_level = "较低"
    else:
        replication_score = 50
        replication_level = "中等"

    # 核心痛点
    pain_points = _get_pain_points(business_lower)

    return {
        "title": "决策成本评估",
        "icon": "⏰",
        "trap_type": trap_type,
        "trap_desc": trap_desc,
        "can_scale": can_scale,
        "items": [
            {"label": "时间陷阱", "value": trap_type, "detail": trap_desc},
            {"label": "没你能否转", "value": autonomy_score < 40 and "难" or "可", "detail": without_you},
            {"label": "可复制指数", "value": f"{replication_score}/100", "detail": f"复制难度{replication_level}"},
            {"label": "核心痛点", "value": pain_points[0], "detail": "最急需解决的问题"}
        ],
        "summary": f"你的业务属于{trap_type}，{trap_desc}。可复制指数{replication_score}分，还有提升空间。",
        "expandable": True,
        "details": {
            "自运转能力": f"{autonomy_score}%（{without_you}）",
            "可复制指数": f"{replication_score}/100",
            "核心痛点": "、".join(pain_points)
        }
    }


def _analyze_local_service(business: str, scope: str) -> dict:
    """分析本地服务型业务的核心问题"""

    business_lower = business.lower()

    # 判断具体类型
    if any(k in business_lower for k in ["灌香肠", "腊肉", "腊肠", "腌菜", "酱料", "豆腐", "豆芽", "面条", "馒头", "糕点"]):
        service_type = "本地食品加工"
        examples = "如：灌香肠、腊肉、豆腐坊等"
        replication_difficulty = "极高"
        replication_reason = "依赖本地口味、原料渠道、人情关系，无法标准化复制"
    elif any(k in business_lower for k in ["餐饮", "饭店", "餐厅", "小吃", "早餐"]):
        service_type = "本地餐饮"
        examples = "如：小饭店、面馆、早餐店等"
        replication_difficulty = "极高"
        replication_reason = "极度依赖厨师手艺、地理位置、本地口碑，人力密集"
    elif any(k in business_lower for k in ["美容", "美发", "理发"]):
        service_type = "本地美发美容"
        examples = "如：理发店、美容院等"
        replication_difficulty = "高"
        replication_reason = "依赖技师手艺、客户关系，难以标准化和快速扩张"
    elif any(k in business_lower for k in ["家政", "保洁", "搬家"]):
        service_type = "本地家政服务"
        examples = "如：家政公司、搬家公司等"
        replication_difficulty = "高"
        replication_reason = "人工成本高、管理难度大、标准化困难"
    elif any(k in business_lower for k in ["维修", "电器", "手机", "电脑", "汽车"]):
        service_type = "本地维修服务"
        examples = "如：手机维修店、汽车修理厂等"
        replication_difficulty = "中高"
        replication_reason = "依赖技师手艺和工具设备，有一定标准化可能"
    elif any(k in business_lower for k in ["培训", "家教", "托管"]):
        service_type = "本地教育培训"
        examples = "如：培训班、家教中心等"
        replication_difficulty = "中高"
        replication_reason = "师资是关键瓶颈，教学质量难以快速复制"
    else:
        service_type = "本地服务"
        examples = ""
        replication_difficulty = "高"
        replication_reason = "依赖本地社会关系，难以复制到外地"

    # 根据选择的服务范围给出不同的分析
    if scope == "local":
        return {
            "title": "决策成本评估",
            "icon": "⏰",
            "trap_type": "本地人情型",
            "trap_desc": "你的业务靠本地口碑和人情关系，复制到外地很难！",
            "can_scale": False,
            "items": [
                {"label": "业务类型", "value": service_type, "detail": examples},
                {"label": "复制难度", "value": replication_difficulty, "detail": replication_reason},
                {"label": "服务范围", "value": "本地", "detail": "专注本地市场，靠口碑生存"},
                {"label": "核心瓶颈", "value": "人情网络", "detail": "外地客户不认识你，无法复制本地信任"}
            ],
            "summary": f"⚠️ {service_type}的复制难度'{replication_difficulty}'！你的核心竞争力是本地口碑，这在人情社会尤其明显。盲目扩张外地市场往往会失败。",
            "expandable": True,
            "details": {
                "为什么不建议盲目复制": "本地服务的核心竞争力是'人情'——老客户信任你、愿意转介绍、认你这个老板。这套逻辑在外地不成立，因为外地客户没有共同的社会网络背书。",
                "正确策略": "本地深耕 + 内容杠杆：把你在本地的成功案例、服务过程、用户故事做成内容（抖音/小红书），吸引外地同乡和认可你价值的新客户。",
                "真正可复制的": "不是'再开一家店'，而是'把你的方法论、产品、知识变成可销售的数字内容'。"
            },
            # 特殊标记：这是一类需要特别建议的业务
            "special_case": True,
            "recommendation_type": "local_service",
            "recommendation": {
                "directive": "建议继续深耕本地，而非盲目扩张",
                "reason": "你的核心竞争力是本地社会关系网络，这在外地无法复制",
                "strategy": "本地口碑 + 内容杠杆 + 产品化",
                "action_items": [
                    "继续做好本地服务，维护老客户关系",
                    "把本地成功案例做成内容（抖音/小红书）",
                    "考虑把技术/配方产品化（课程、教程、工具）",
                    "服务在外地的本地人或认同你价值的客户"
                ]
            }
        }
    else:
        # 选择全国/全球的分析
        return {
            "title": "决策成本评估",
            "icon": "⏰",
            "trap_type": "内容品牌型",
            "trap_desc": "想服务外地客户？你需要用内容建立新的信任背书！",
            "can_scale": True,
            "items": [
                {"label": "业务类型", "value": service_type, "detail": examples},
                {"label": "复制难度", "value": replication_difficulty, "detail": "线下扩张难，但可以内容扩张"},
                {"label": "服务范围", "value": "全国/全球", "detail": "需要建立线上影响力"},
                {"label": "核心挑战", "value": "内容获客", "detail": "没有本地社会网络背书，需要内容建立信任"}
            ],
            "summary": f"你想把{service_type}服务外地客户？这需要从'人情获客'转变为'内容获客'。",
            "expandable": True,
            "details": {
                "核心转变": "从'等客户上门'到'用内容吸引客户'",
                "关键动作": "把你的技艺、服务过程、用户见证做成内容",
                "目标人群": "在外地的本地人 + 认同你价值的远方客户"
            },
            "special_case": True,
            "recommendation_type": "local_service_expand",
            "recommendation": {
                "directive": "用内容杠杆服务外地客户",
                "reason": "外地客户无法体验你的线下服务，但可以通过内容建立信任",
                "strategy": "内容矩阵 + 本地服务 + 产品化",
                "action_items": [
                    "拍摄服务过程、技艺展示、用户见证",
                    "在抖音/小红书建立内容矩阵",
                    "把核心技能产品化（课程/教程/工具）",
                    "服务在外地务工的本地同乡"
                ]
            }
        }


def _get_pain_points(business_lower: str) -> list:
    if "心理" in business_lower:
        return ["客户来源不稳定", "咨询效率低", "收费难提升", "职业倦怠"]
    if "法律" in business_lower:
        return ["获客成本高", "案件周期长", "竞争激烈", "回款难"]
    if "教育" in business_lower or "培训" in business_lower:
        return ["师资难管控", "续费率不稳定", "场地成本高", "同质化竞争"]
    if "设计" in business_lower:
        return ["改稿耗时", "客户压价", "交付质量难保证", "时间不可控"]
    if "装修" in business_lower:
        return ["工期不可控", "材料浪费", "工人难管理", "售后纠纷多"]
    if "中介" in business_lower:
        return ["资源依赖强", "跳单风险大", "佣金下滑", "人才流失"]
    if "美容" in business_lower:
        return ["拓客成本高", "员工流失", "产品耗材", "价格战"]
    if "健身" in business_lower:
        return ["拉新难", "留存低", "教练流失", "场地利用率"]
    return ["获客难", "效率低", "难复制", "增长慢"]


# ==================== M3: 资产盘点 ====================

def _analyze_assets(business: str, scope: str, resources: list) -> dict:
    """M3: 盘点用户资产"""

    business_lower = business.lower()
    is_local_service = _is_local_service_business(business_lower)

    # 本地服务型业务的资产盘点（特殊逻辑）
    if is_local_service:
        return _analyze_local_service_assets(business, scope)

    # 可产品化的资产
    digital_assets = []
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "咨询"]):
        digital_assets = [
            {"name": "专业知识体系", "status": "已整理/待整理", "value": "高"},
            {"name": "案例库", "status": "有积累/需整理", "value": "高"},
            {"name": "方法论", "status": "有经验/待提炼", "value": "高"}
        ]
    elif any(k in business_lower for k in ["设计", "装修", "IT"]):
        digital_assets = [
            {"name": "设计方案库", "status": "有积累/可复用", "value": "高"},
            {"name": "素材模板", "status": "待整理", "value": "中"},
            {"name": "工具流程", "status": "有经验/可标准化", "value": "高"}
        ]
    else:
        digital_assets = [
            {"name": "行业经验", "status": "有积累/待整理", "value": "中"},
            {"name": "操作流程", "status": "待标准化", "value": "中"}
        ]

    # 可复制潜力评估
    if any(k in business_lower for k in ["心理", "法律", "教育", "咨询"]):
        replicable_potential = {
            "score": 85,
            "level": "高",
            "reason": "知识密集型，最适合产品化"
        }
    elif any(k in business_lower for k in ["设计", "装修"]):
        replicable_potential = {
            "score": 70,
            "level": "较高",
            "reason": "可建立标准流程和模板"
        }
    elif any(k in business_lower for k in ["美容", "健身", "中介"]):
        replicable_potential = {
            "score": 55,
            "level": "中等",
            "reason": "部分环节可标准化"
        }
    else:
        replicable_potential = {
            "score": 60,
            "level": "中等",
            "reason": "需要挖掘可标准化环节"
        }

    # 资源匹配度
    resource_match = _analyze_resource_match(resources, business_lower)

    return {
        "title": "资产盘点",
        "icon": "📦",
        "items": [
            {"label": "可产品化资产", "value": f"{len(digital_assets)}项", "detail": "可转化为数字产品"},
            {"label": "复制潜力", "value": replicable_potential["level"], "detail": replicable_potential["reason"]},
            {"label": "资源匹配", "value": f"{resource_match['score']}%", "detail": resource_match["strength"]}
        ],
        "digital_assets": digital_assets,
        "replicable_potential": replicable_potential,
        "resource_match": resource_match,
        "summary": f"你的业务有{len(digital_assets)}项可产品化资产，复制潜力{replicable_potential['level']}（{replicable_potential['score']}分）。",
        "expandable": True,
        "details": {
            "可产品化资产": [a["name"] for a in digital_assets],
            "复制潜力评分": f"{replicable_potential['score']}/100",
            "资源匹配度": f"{resource_match['score']}%"
        }
    }


def _analyze_local_service_assets(business: str, scope: str) -> dict:
    """分析本地服务型业务的资产"""

    business_lower = business.lower()

    # 区分不可复制的资产和可以复制的资产
    non_replicable_assets = []
    replicable_assets = []

    # 本地口碑（不可复制）
    non_replicable_assets.append({
        "name": "本地口碑",
        "status": "本地积累",
        "value": "极高（本地）",
        "note": "在本地很有价值，但在外地无法使用"
    })

    # 人情关系（不可复制）
    non_replicable_assets.append({
        "name": "人情关系网络",
        "status": "长期积累",
        "value": "极高（本地）",
        "note": "依赖共同社会网络，外地客户无法使用"
    })

    # 地理位置（不可复制）
    non_replicable_assets.append({
        "name": "地理位置",
        "status": "已占据",
        "value": "高（本地）",
        "note": "只服务周边客户，扩张外地无效"
    })

    # 可复制的资产
    if any(k in business_lower for k in ["灌香肠", "腊肉", "腊肠", "腌菜", "酱料", "豆腐", "豆芽", "面条", "馒头", "糕点"]):
        replicable_assets = [
            {"name": "配方/工艺", "status": "核心资产", "value": "可产品化", "action": "整理成教程/课程"},
            {"name": "制作经验", "status": "可提炼", "value": "可产品化", "action": "写成电子书/手册"},
            {"name": "产品本身", "status": "可邮寄", "value": "可产品化", "action": "做成可邮寄的产品"}
        ]
    elif any(k in business_lower for k in ["美容", "美发", "理发", "按摩", "健身"]):
        replicable_assets = [
            {"name": "服务技术", "status": "核心资产", "value": "可产品化", "action": "录制教学视频"},
            {"name": "经验方法", "status": "可提炼", "value": "可产品化", "action": "写成教程"},
            {"name": "客户见证", "status": "可展示", "value": "内容素材", "action": "做成内容吸引外地客户"}
        ]
    elif any(k in business_lower for k in ["餐饮", "饭店", "餐厅", "小吃"]):
        replicable_assets = [
            {"name": "招牌菜/特色", "status": "核心资产", "value": "可产品化", "action": "考虑做成预制菜/产品"},
            {"name": "服务流程", "status": "可提炼", "value": "可标准化", "action": "写成运营手册"},
            {"name": "口碑故事", "status": "可展示", "value": "内容素材", "action": "做成内容吸引外地同乡"}
        ]
    elif any(k in business_lower for k in ["维修", "电器", "手机", "电脑", "汽车"]):
        replicable_assets = [
            {"name": "维修技术", "status": "核心资产", "value": "可产品化", "action": "录制教学视频"},
            {"name": "故障排除经验", "status": "可提炼", "value": "可产品化", "action": "写成教程/手册"},
            {"name": "工具和方法", "status": "可标准化", "value": "可工具化", "action": "开发成工具/模板"}
        ]
    else:
        replicable_assets = [
            {"name": "技艺/技术", "status": "核心资产", "value": "可产品化", "action": "考虑录制教程"},
            {"name": "行业经验", "status": "可提炼", "value": "可产品化", "action": "整理成文档/课程"},
            {"name": "客户见证", "status": "可展示", "value": "内容素材", "action": "做成内容吸引外地客户"}
        ]

    # 判断复制潜力（基于资产类型）
    replicable_potential = {
        "score": 50,
        "level": "有限",
        "reason": "你的核心资产（口碑、人情）无法复制，但技艺和产品可以"
    }

    return {
        "title": "资产盘点",
        "icon": "📦",
        "items": [
            {"label": "不可复制资产", "value": f"{len(non_replicable_assets)}项", "detail": "本地专属，外地无效"},
            {"label": "可复制资产", "value": f"{len(replicable_assets)}项", "detail": "技艺、产品、经验可以产品化"},
            {"label": "复制策略", "value": "内容杠杆", "detail": "不是开分店，是做内容"}
        ],
        "non_replicable_assets": non_replicable_assets,
        "replicable_assets": replicable_assets,
        "replicable_potential": replicable_potential,
        "summary": "⚠️ 你的核心资产（口碑、人情关系）是本地专属，无法复制到外地！但你的技艺和经验可以产品化。",
        "expandable": True,
        "details": {
            "为什么本地资产难复制": "外地客户不认识你，没有共同的社会网络，也没有在你这里消费过的体验。口碑无法随身携带。",
            "什么可以复制": "你的技艺、经验、配方、产品本身 - 这些可以通过内容展示给别人。",
            "正确的复制方式": "不是'再开一家店'，而是'把你的技艺变成内容/产品，卖给更多人'。"
        },
        "special_case": True,
        "recommendation_type": "local_service_assets"
    }


def _analyze_resource_match(resources: list, business_lower: str) -> dict:
    score = 50
    strength = "基础资源"
    match_items = []

    if "knowledge" in resources or "专业知识" in resources:
        score += 20
        match_items.append("专业知识 ✓")
    if "experience" in resources or "行业经验" in resources:
        score += 15
        match_items.append("行业经验 ✓")
    if "technique" in resources or "技术/工艺" in resources:
        score += 15
        match_items.append("技术工艺 ✓")
    if "brand" in resources or "品牌口碑" in resources:
        score += 10
        match_items.append("品牌口碑 ✓")
    if "customers" in resources or "客户资源" in resources:
        score += 10
        match_items.append("客户资源 ✓")
    if "capital" in resources or "资金" in resources:
        score += 15
        match_items.append("资金支持 ✓")

    if score >= 80:
        strength = "资源丰富，适合扩张"
    elif score >= 60:
        strength = "资源良好，需补充弱项"
    elif score >= 40:
        strength = "资源一般，需重点建设"
    else:
        strength = "资源有限，需从头积累"

    return {
        "score": min(score, 100),
        "strength": strength,
        "match_items": match_items
    }


# ==================== M4: AI机遇分析 ====================

def _analyze_ai_opportunity(business: str, scope: str, resources: list) -> dict:
    """M4: AI机遇分析"""

    business_lower = business.lower()
    is_local_service = _is_local_service_business(business_lower)

    # 本地服务型业务的AI分析（特殊逻辑）
    if is_local_service:
        return _analyze_local_service_ai(business, scope)

    # 核心洞察
    core_insight = {
        "title": "AI = 智力平权，让经验可复制",
        "description": "AI正在把以前需要多年经验积累的技能变得可量化、可复制。就像修车师傅的补漆技术，AI机器人+调色软件可以替代多年经验，加速产业复制速度。"
    }

    # 判断行业类型和AI机遇
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "咨询", "教练"]):
        industry_type = "知识密集型"
        opportunities = [
            {"type": "replace", "task": "标准化问答", "ai_action": "AI快速解答常见问题", "impact": "减少70%重复咨询"},
            {"type": "enhance", "task": "案例分析", "ai_action": "AI辅助分析相似案例", "impact": "提升决策质量"},
            {"type": "automate", "task": "文档生成", "ai_action": "自动生成报告/方案", "impact": "效率提升10倍"},
            {"type": "create", "task": "个性化内容", "ai_action": "AI生成定制化课程", "impact": "开发周期缩短80%"}
        ]
        ceiling_level = 85
        ceiling_desc = "知识密集型行业AI赋能潜力极高，课程化、标准化最容易"
        risk_level = "medium"
        risk_desc = "你的核心竞争力在于人际连接和深度洞察，AI是辅助工具而非替代者。尽快将知识产品化，建立护城河。"
        recommendations = [
            "立即开始：把核心知识整理成文档/课程，这是抵抗AI替代的最佳护城河",
            "工具升级：用AI辅助撰写报告、生成案例分析",
            "产品化思维：思考如何把你的经验变成可复制的产品/服务",
            "关注趋势：持续关注AI在本行业的应用进展"
        ]

    elif any(k in business_lower for k in ["装修", "设计", "工程", "机械", "厨"]):
        industry_type = "技术设计型"
        opportunities = [
            {"type": "replace", "task": "效果图制作", "ai_action": "AI快速生成设计方案", "impact": "设计师效率提升5倍"},
            {"type": "enhance", "task": "成本估算", "ai_action": "AI自动精准报价", "impact": "减少人为误差"},
            {"type": "automate", "task": "图纸审核", "ai_action": "AI自动检查规范", "impact": "审核效率提升10倍"},
            {"type": "create", "task": "智能推荐", "ai_action": "AI根据用户需求推荐方案", "impact": "成单率提升30%"}
        ]
        ceiling_level = 80
        ceiling_desc = "设计和技术型行业AI替代风险中等，但辅助工具将大幅提升效率"
        risk_level = "medium"
        risk_desc = "AI可以处理标准化设计工作，但创意和客户关系仍需要人工。尽快建立自己的方法论体系。"
        recommendations = [
            "立即开始：用AI工具提升设计效率，如Midjourney、Stable Diffusion",
            "流程标准化：把设计流程拆解，找出可AI化的环节",
            "模板积累：建立自己的素材库和模板体系",
            "关注工具：CAD+AI、设计AI工具的发展"
        ]

    elif any(k in business_lower for k in ["中介", "代理", "猎头", "贸易", "供应"]):
        industry_type = "撮合交易型"
        opportunities = [
            {"type": "replace", "task": "信息匹配", "ai_action": "AI自动匹配合适资源", "impact": "匹配效率提升10倍"},
            {"type": "enhance", "task": "市场分析", "ai_action": "AI实时分析市场趋势", "impact": "决策更精准"},
            {"type": "automate", "task": "合同流程", "ai_action": "AI辅助审核合同", "impact": "风险降低80%"},
            {"type": "create", "task": "信息平台", "ai_action": "AI驱动的垂直平台", "impact": "边际成本趋近于零"}
        ]
        ceiling_level = 90
        ceiling_desc = "中介/代理业务数字化+AI化后，天花板极高"
        risk_level = "high"
        risk_desc = "中介业务面临较大被AI替代风险，因为核心价值是消除信息差。尽快向撮合平台转型。"
        recommendations = [
            "警惕风险：中介业务正在被平台替代，需要尽快转型",
            "数据积累：建立自己的供需数据库",
            "平台化思维：思考如何从中介变成平台",
            "AI赋能：用AI提升匹配效率，降低运营成本"
        ]

    else:
        industry_type = "通用型"
        opportunities = [
            {"type": "automate", "task": "日常运营", "ai_action": "AI处理重复性工作", "impact": "效率大幅提升"},
            {"type": "enhance", "task": "数据分析", "ai_action": "AI分析业务数据", "impact": "洞察更精准"},
            {"type": "enhance", "task": "客户服务", "ai_action": "AI辅助客服解答", "impact": "响应速度提升"},
            {"type": "create", "task": "内容营销", "ai_action": "AI生成营销内容", "impact": "获客成本降低"}
        ]
        ceiling_level = 65
        ceiling_desc = "各行业+AI都能带来效率提升，具体效果取决于执行深度"
        risk_level = "medium"
        risk_desc = "AI应用程度决定了你的竞争优势。尽快了解并尝试AI工具。"
        recommendations = [
            "立即开始：尝试AI写作工具（如ChatGPT）",
            "效率提升：用AI处理日常文案、数据整理",
            "客户洞察：用AI分析客户反馈和数据",
            "内容营销：用AI辅助创作营销内容"
        ]

    # 时间窗口评估
    if any(k in business_lower for k in ["法律", "财税", "医"]):
        time_window = "medium"
        time_window_desc = "监管较严，AI渗透需要时间"
    elif any(k in business_lower for k in ["设计", "装修"]):
        time_window = "short"
        time_window_desc = "设计领域AI发展很快，需快速跟进"
    else:
        time_window = "medium"
        time_window_desc = "3-5年内AI将显著改变行业"

    return {
        "title": "AI机遇分析",
        "icon": "🤖",
        "core_insight": core_insight,
        "industry_type": industry_type,
        "opportunities": opportunities,
        "ceiling": {
            "level": ceiling_level,
            "desc": ceiling_desc
        },
        "risk": {
            "level": risk_level,
            "desc": risk_desc
        },
        "time_window": {
            "value": time_window,
            "desc": time_window_desc
        },
        "recommendations": recommendations,
        "summary": f"你的{business}属于{industry_type}行业，AI+天花板{ceiling_level}%。{risk_desc[:30]}...",
        "expandable": True
    }


def _analyze_local_service_ai(business: str, scope: str) -> dict:
    """分析本地服务型业务的AI机遇"""

    business_lower = business.lower()

    # 判断具体业务类型，给出针对性分析
    if any(k in business_lower for k in ["灌香肠", "腊肉", "腊肠", "腌菜", "酱料", "豆腐", "豆芽", "面条", "馒头", "糕点"]):
        ai_type = "食品加工型"
        risk_level = "low"
        risk_desc = "AI替代不了你的手艺和口感，但可以帮你做营销和内容"
        opportunities = [
            {
                "type": "create",
                "task": "内容营销",
                "ai_action": "AI辅助生成短视频脚本、文案",
                "impact": "内容创作效率提升80%",
                "priority": "最高"
            },
            {
                "type": "enhance",
                "task": "配方优化",
                "ai_action": "AI分析用户反馈，优化配方",
                "impact": "产品改进更有方向",
                "priority": "中"
            },
            {
                "type": "create",
                "task": "教程产品化",
                "ai_action": "AI辅助写教程、录制课程",
                "impact": "把技艺变成可销售的内容",
                "priority": "高"
            },
            {
                "type": "automate",
                "task": "客户管理",
                "ai_action": "AI管理客户信息、订单",
                "impact": "提升运营效率",
                "priority": "低"
            }
        ]
        core_insight = {
            "title": "AI帮不了你的手艺，但能帮你卖",
            "description": "你的核心竞争力（手艺、口感）是AI替代不了的。但AI可以帮你：1）做内容营销；2）把技艺产品化；3）管理客户。"
        }
        ceiling_level = 40
        ceiling_desc = "AI直接赋能空间有限，但内容营销和产品化的机遇很大"
        recommendations = [
            "内容创作：用AI辅助写短视频脚本（展示制作过程、讲述用户故事）",
            "产品化：把你的配方和经验整理成教程/电子书，AI可以帮你写",
            "外地获客：拍抖音/小红书，让在外地的本地人也能看到你",
            "不要做的事：不要指望AI帮你做核心产品，把精力放在内容上"
        ]

    elif any(k in business_lower for k in ["美容", "美发", "理发"]):
        ai_type = "美业服务型"
        risk_level = "low"
        risk_desc = "AI替代不了你的手艺和审美，但可以帮你获客"
        opportunities = [
            {
                "type": "create",
                "task": "内容获客",
                "ai_action": "AI生成前后对比图、发型设计灵感",
                "impact": "小红书/抖音内容产量翻倍",
                "priority": "最高"
            },
            {
                "type": "enhance",
                "task": "客户分析",
                "ai_action": "AI分析客户偏好，推荐服务",
                "impact": "提升客户满意度和复购",
                "priority": "高"
            },
            {
                "type": "automate",
                "task": "预约管理",
                "ai_action": "AI智能预约、排期",
                "impact": "减少空档，提升利用率",
                "priority": "中"
            },
            {
                "type": "create",
                "task": "线上课程",
                "ai_action": "AI辅助录制教学视频",
                "impact": "把你的技术卖给想学的人",
                "priority": "高"
            }
        ]
        core_insight = {
            "title": "AI帮你展示手艺，不是替代手艺",
            "description": "你的剪刀和手艺是AI替代不了的。但AI可以帮你：1）拍出更好看的内容；2）吸引外地客户；3）把技术变现。"
        }
        ceiling_level = 50
        ceiling_desc = "AI主要在获客和内容方面赋能，技术本身难以替代"
        recommendations = [
            "内容展示：用AI生成精美的前后对比图/视频",
            "外地获客：在抖音/小红书展示你的技艺，吸引在外地的本地人",
            "技术变现：录制发型教程，AI帮你写脚本和字幕",
            "客户管理：用AI分析客户偏好，提供个性化服务"
        ]

    elif any(k in business_lower for k in ["餐饮", "饭店", "餐厅", "小吃", "早餐"]):
        ai_type = "餐饮服务型"
        risk_level = "medium"
        risk_desc = "预制菜和AI厨师是威胁，但你的口味和体验难以复制"
        opportunities = [
            {
                "type": "create",
                "task": "内容营销",
                "ai_action": "AI生成探店视频脚本、美食文案",
                "impact": "让更多人知道你的店",
                "priority": "最高"
            },
            {
                "type": "create",
                "task": "产品化",
                "ai_action": "AI帮你把招牌菜做成预制菜/半成品",
                "impact": "突破地理限制，卖给外地客户",
                "priority": "高"
            },
            {
                "type": "automate",
                "task": "运营管理",
                "ai_action": "AI帮你点餐、库存管理、数据分析",
                "impact": "降低运营成本",
                "priority": "中"
            },
            {
                "type": "enhance",
                "task": "用户调研",
                "ai_action": "AI分析点评和反馈",
                "impact": "了解客户真实需求",
                "priority": "低"
            }
        ]
        core_insight = {
            "title": "预制菜可能是威胁，但你的体验不是",
            "description": "预制菜正在抢走餐饮店的生意。但你的堂食体验、锅气、人情味是预制菜替代不了的。关键是：把'体验'做成内容，把'招牌菜'做成产品。"
        }
        ceiling_level = 55
        ceiling_desc = "餐饮+AI主要在获客和产品化方面机遇大"
        recommendations = [
            "内容突围：在抖音/小红书展示你的特色和人情味",
            "产品化思路：考虑把招牌菜做成预制菜，卖给外地同乡",
            "差异化竞争：强调'现做'、'有锅气'、'有温度'，这是AI做不来的",
            "私域运营：用AI管理老客户，做社群运营"
        ]

    elif any(k in business_lower for k in ["按摩", "足疗", "理疗"]):
        ai_type = "健康保健型"
        risk_level = "low"
        risk_desc = "AI替代不了你的手法和触觉，但可以帮你获客和留存"
        opportunities = [
            {
                "type": "create",
                "task": "内容营销",
                "ai_action": "AI生成养生知识、放松技巧内容",
                "impact": "吸引新客户，尤其是年轻人",
                "priority": "最高"
            },
            {
                "type": "enhance",
                "task": "客户管理",
                "ai_action": "AI分析客户偏好，推荐服务",
                "impact": "提升复购率和客单价",
                "priority": "高"
            },
            {
                "type": "automate",
                "task": "预约管理",
                "ai_action": "AI智能预约、提醒",
                "impact": "减少空档，提升效率",
                "priority": "中"
            },
            {
                "type": "create",
                "task": "知识变现",
                "ai_action": "AI辅助录制按摩/养生教程",
                "impact": "把技术卖给想学的人",
                "priority": "中"
            }
        ]
        core_insight = {
            "title": "你的双手是AI替代不了的",
            "description": "按摩的力度、穴位、手法需要真实的触觉反馈，这是AI做不到的。但AI可以帮你：1）做内容获客；2）管理客户；3）把技术变现。"
        }
        ceiling_level = 45
        ceiling_desc = "AI在获客和管理方面机遇大，但核心服务难以替代"
        recommendations = [
            "内容获客：拍抖音/小红书，展示按摩手法和养生知识",
            "外地客户：吸引在外地的本地人，回老家时来消费",
            "技术变现：录制教程，教别人按摩手法",
            "客户留存：用AI管理客户，做会员体系"
        ]

    elif any(k in business_lower for k in ["维修", "电器", "手机", "电脑", "汽车"]):
        ai_type = "维修技术型"
        risk_level = "medium"
        risk_desc = "AI诊断越来越强，但实际动手和经验判断仍需要人"
        opportunities = [
            {
                "type": "enhance",
                "task": "故障诊断",
                "ai_action": "AI辅助诊断故障原因",
                "impact": "提升诊断效率和准确率",
                "priority": "高"
            },
            {
                "type": "create",
                "task": "知识变现",
                "ai_action": "AI辅助写教程、整理故障案例",
                "impact": "把经验变成可销售的内容",
                "priority": "高"
            },
            {
                "type": "automate",
                "task": "报价管理",
                "ai_action": "AI辅助生成报价单",
                "impact": "减少报价时间，提升专业感",
                "priority": "中"
            },
            {
                "type": "create",
                "task": "内容获客",
                "ai_action": "AI生成维修教程、故障排除视频",
                "impact": "吸引外地客户和爱好者",
                "priority": "中"
            }
        ]
        core_insight = {
            "title": "AI诊断 + 你的手艺 = 最强组合",
            "description": "AI越来越擅长诊断问题，但动手解决问题仍需要你的经验和手艺。用好AI诊断工具，可以大幅提升效率。"
        }
        ceiling_level = 60
        ceiling_desc = "AI在诊断和知识变现方面机遇大"
        recommendations = [
            "诊断工具：使用AI辅助诊断故障原因，提升效率",
            "知识变现：把你遇到的典型故障整理成教程，AI帮你写",
            "内容获客：拍维修教程视频，吸引外地客户和学习者",
            "标准化：把常见故障的处理方法标准化，降低对个人依赖"
        ]

    else:
        # 通用本地服务
        ai_type = "本地服务型"
        risk_level = "low"
        risk_desc = "你的服务难以被AI替代，但AI可以帮你获客和运营"
        opportunities = [
            {
                "type": "create",
                "task": "内容获客",
                "ai_action": "AI生成推广文案、视频脚本",
                "impact": "降低获客成本",
                "priority": "最高"
            },
            {
                "type": "automate",
                "task": "客户管理",
                "ai_action": "AI管理客户信息和预约",
                "impact": "提升运营效率",
                "priority": "高"
            },
            {
                "type": "enhance",
                "task": "服务优化",
                "ai_action": "AI分析客户反馈",
                "impact": "持续改进服务",
                "priority": "中"
            },
            {
                "type": "create",
                "task": "知识变现",
                "ai_action": "AI辅助整理经验",
                "impact": "把经验变成可销售的内容",
                "priority": "中"
            }
        ]
        core_insight = {
            "title": "AI是获客工具，不是替代工具",
            "description": "你的服务手艺/体验是本地积累的，AI替代不了。但AI可以帮你：1）做内容获客；2）管理客户；3）把经验变现。"
        }
        ceiling_level = 50
        ceiling_desc = "AI主要在获客和运营方面赋能"
        recommendations = [
            "内容营销：用AI辅助创作内容（抖音/小红书/朋友圈）",
            "外地获客：让在外地的本地人也能看到你",
            "产品化：把技艺/经验整理成教程或工具",
            "客户运营：用AI管理老客户，提升复购"
        ]

    return {
        "title": "AI机遇分析",
        "icon": "🤖",
        "special_case": True,
        "ai_type": ai_type,
        "core_insight": core_insight,
        "opportunities": opportunities,
        "ceiling": {
            "level": ceiling_level,
            "desc": ceiling_desc
        },
        "risk": {
            "level": risk_level,
            "desc": risk_desc
        },
        "time_window": {
            "value": "short",
            "desc": "内容营销和获客工具已经成熟，立即可用"
        },
        "recommendations": recommendations,
        "summary": f"⚠️ AI替代不了你的手艺，但能帮你卖！{risk_desc}。重点：用AI做内容获客，把技艺产品化。",
        "expandable": True
    }


# ==================== 可复制方向选项 ====================

def _generate_replicable_options(business: str, scope: str, resources: list) -> list:
    """生成可复制方向选项供用户选择"""

    business_lower = business.lower()
    is_local_service = _is_local_service_business(business_lower)

    # 所有可复制方向
    all_options = [
        {
            "id": "course",
            "name": "在线课程",
            "icon": "📚",
            "summary": "将专业知识制作成系统课程，在各大平台销售",
            "marginal_cost": "趋近于零",
            "initial_investment": "低（录制设备）",
            "difficulty": "低",
            "time_estimate": "1-3个月",
            "best_for": ["有专业知识积累"],
            "match_keywords": ["心理", "法律", "财税", "医", "教育", "培训", "咨询", "教练"]
        },
        {
            "id": "handbook",
            "name": "实操手册",
            "icon": "📖",
            "summary": "把经验整理成标准化手册/电子书销售",
            "marginal_cost": "趋近于零",
            "initial_investment": "极低",
            "difficulty": "低",
            "time_estimate": "2-4周",
            "best_for": ["有实操经验", "想快速验证"],
            "match_keywords": ["装修", "设计", "培训", "机械", "工程", "灌香肠", "腊肉", "豆腐", "面条"]
        },
        {
            "id": "template",
            "name": "模板工具",
            "icon": "📋",
            "summary": "开发行业模板/工具，按订阅或按次收费",
            "marginal_cost": "趋近于零",
            "initial_investment": "中（开发成本）",
            "difficulty": "中",
            "time_estimate": "1-2个月",
            "best_for": ["有技术能力", "有模板积累"],
            "match_keywords": ["设计", "装修", "财务", "法律", "工程"]
        },
        {
            "id": "membership",
            "name": "社群会员",
            "icon": "👥",
            "summary": "建立付费社群，提供持续价值和资源对接",
            "marginal_cost": "低",
            "initial_investment": "极低",
            "difficulty": "低",
            "time_estimate": "1-2周",
            "best_for": ["有客户资源", "有人脉网络"],
            "match_keywords": ["中介", "代理", "培训", "咨询"]
        },
        {
            "id": "franchise",
            "name": "加盟授权",
            "icon": "🏪",
            "summary": "建立标准体系，授权他人复制你的模式",
            "marginal_cost": "低",
            "initial_investment": "高（体系搭建）",
            "difficulty": "高",
            "time_estimate": "6-12个月",
            "best_for": ["有品牌", "有资金", "有可复制模式"],
            "match_keywords": ["餐饮", "美容", "健身", "教育", "零售"]
        },
        {
            "id": "saas",
            "name": "SaaS工具",
            "icon": "💻",
            "summary": "开发行业专用软件，按订阅制收费",
            "marginal_cost": "趋近于零",
            "initial_investment": "高（技术开发）",
            "difficulty": "高",
            "time_estimate": "3-6个月起",
            "best_for": ["有技术团队", "有资金支持"],
            "match_keywords": ["管理", "运营", "数据", "分析"]
        }
    ]

    # 本地服务型业务的特殊方向
    local_service_options = [
        {
            "id": "content_marketing",
            "name": "本地内容营销",
            "icon": "🎬",
            "summary": "用抖音/小红书展示技艺，吸引外地同乡客户",
            "marginal_cost": "趋近于零",
            "initial_investment": "极低（一部手机）",
            "difficulty": "低",
            "time_estimate": "持续运营",
            "best_for": ["有独特技艺", "有本地口碑"],
            "match_keywords": ["灌香肠", "腊肉", "豆腐", "餐饮", "美容", "美发", "维修", "按摩", "摄影"]
        },
        {
            "id": "productize",
            "name": "技艺产品化",
            "icon": "🎁",
            "summary": "把核心技能/配方变成可销售的产品（教程、工具包）",
            "marginal_cost": "趋近于零",
            "initial_investment": "极低",
            "difficulty": "低",
            "time_estimate": "2-4周",
            "best_for": ["有独特配方", "有标准流程"],
            "match_keywords": ["灌香肠", "腊肉", "酱料", "豆腐", "面条", "糕点"]
        },
        {
            "id": "diaspora_service",
            "name": "同乡服务",
            "icon": "🌏",
            "summary": "服务在外地的本地人，通过内容建立信任，提供远程/邮寄服务",
            "marginal_cost": "低",
            "initial_investment": "低",
            "difficulty": "中",
            "time_estimate": "1-2个月起",
            "best_for": ["有特色产品", "能远程交付"],
            "match_keywords": ["灌香肠", "腊肉", "酱料", "特产", "美食"]
        },
        {
            "id": "deepen_local",
            "name": "深耕本地",
            "icon": "🏠",
            "summary": "不扩张，专注提升本地服务质量和口碑，做精做透",
            "marginal_cost": "无",
            "initial_investment": "低",
            "difficulty": "无",
            "time_estimate": "持续",
            "best_for": ["本地根基稳", "不想扩张"],
            "match_keywords": ["餐饮", "美容", "美发", "家政", "维修", "培训"]
        }
    ]

    # 根据业务类型选择选项
    if is_local_service:
        # 本地服务型：优先展示本地化选项
        options = local_service_options + all_options
    else:
        options = all_options

    # 计算每个选项的匹配度
    scored_options = []
    for opt in options:
        score = 30  # 基础分

        # 关键词匹配
        if any(k in business_lower for k in opt["match_keywords"]):
            score += 40

        # 资源匹配
        if opt["id"] == "course" and ("knowledge" in resources or "专业知识" in resources):
            score += 15
        if opt["id"] == "handbook" and ("experience" in resources or "行业经验" in resources):
            score += 15
        if opt["id"] == "template" and ("technique" in resources or "技术/工艺" in resources):
            score += 15
        if opt["id"] == "membership" and ("customers" in resources or "客户资源" in resources or "品牌" in resources):
            score += 15
        if opt["id"] == "franchise" and ("brand" in resources or "品牌口碑" in resources or "capital" in resources):
            score += 15
        if opt["id"] == "saas" and ("technique" in resources or "技术/工艺" in resources):
            score += 15
        if opt["id"] == "content_marketing" and ("experience" in resources or "行业经验" in resources):
            score += 20
        if opt["id"] == "productize" and ("knowledge" in resources or "experience" in resources):
            score += 20
        if opt["id"] == "deepen_local":
            score += 10  # 总是有参考价值
        if opt["id"] == "diaspora_service":
            score += 15 if any(k in business_lower for k in ["灌香肠", "腊肉", "特产", "美食", "酱料"]) else 0

        # 本地服务型降低加盟的分数
        if is_local_service and opt["id"] == "franchise":
            score -= 30  # 本地服务加盟很难

        # 难度调整（太难的方向降低推荐）
        if opt.get("difficulty") == "高":
            score -= 10

        scored_options.append({
            **opt,
            "match_score": min(score, 98)
        })

    # 按匹配度排序
    scored_options.sort(key=lambda x: x["match_score"], reverse=True)

    # 返回前8个（本地服务可能需要更多选项）
    return scored_options[:8]


# ==================== 第二阶段：路线详情 ====================

def _generate_route_detail(option_id: str, business: str, scope: str, resources: list) -> dict:
    """生成选定方向的详细执行路线"""

    business_lower = business.lower()

    routes = {
        "course": {
            "name": "在线课程",
            "icon": "📚",
            "description": "将你的专业知识制作成系统课程，在各大平台销售",
            "steps": [
                {
                    "phase": "准备期",
                    "title": "知识梳理",
                    "description": "整理核心知识点，制作课程大纲",
                    "duration": "1-2周",
                    "deliverables": ["课程大纲", "知识点清单", "案例素材"]
                },
                {
                    "phase": "制作期",
                    "title": "内容录制",
                    "description": "录制课程视频，可使用AI辅助",
                    "duration": "2-4周",
                    "deliverables": ["视频课程", "课件PPT", "配套文档"]
                },
                {
                    "phase": "上线期",
                    "title": "平台上线",
                    "description": "在多平台发布课程，设置定价",
                    "duration": "1周",
                    "deliverables": ["上线课程", "定价策略", "推广计划"]
                },
                {
                    "phase": "运营期",
                    "title": "迭代优化",
                    "description": "根据反馈优化课程，持续更新",
                    "duration": "持续",
                    "deliverables": ["课程更新", "学员社群", "口碑积累"]
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "几乎不需要资金"},
                "technique": {"level": "partial", "desc": "需要基础录制能力"},
                "time": {"level": "yes", "desc": "需要投入制作时间"},
                "network": {"level": "no", "desc": "不需要人脉"}
            },
            "timeline": "1-3个月",
            "investment": "极低（几百元设备）",
            "risks": [
                {"type": "市场风险", "level": "medium", "desc": "市场竞争激烈，需要差异化"},
                {"type": "技术风险", "level": "low", "desc": "录制和剪辑可学习"},
                {"type": "运营风险", "level": "medium", "desc": "需要持续运营和更新"}
            ],
            "milestones": [
                {"week": 1, "milestone": "完成课程大纲"},
                {"week": 4, "milestone": "完成50%内容录制"},
                {"week": 8, "milestone": "课程上线"},
                {"week": 12, "milestone": "获得第一批付费学员"}
            ]
        },
        "handbook": {
            "name": "实操手册",
            "icon": "📖",
            "description": "把经验整理成标准化手册/电子书销售",
            "steps": [
                {
                    "phase": "整理期",
                    "title": "经验萃取",
                    "description": "系统整理实操经验和流程",
                    "duration": "1-2周",
                    "deliverables": ["经验清单", "流程图", "案例库"]
                },
                {
                    "phase": "编写期",
                    "title": "内容编写",
                    "description": "撰写完整手册，使用AI辅助",
                    "duration": "1-2周",
                    "deliverables": ["完整手册", "配套清单", "案例集"]
                },
                {
                    "phase": "包装期",
                    "title": "设计排版",
                    "description": "专业排版设计，制作电子书",
                    "duration": "3-5天",
                    "deliverables": ["PDF电子书", "打印版", "在线版"]
                },
                {
                    "phase": "销售期",
                    "title": "多渠道销售",
                    "description": "在多平台发布销售",
                    "duration": "持续",
                    "deliverables": ["销售渠道", "推广素材", "客服话术"]
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "几乎零成本"},
                "technique": {"level": "no", "desc": "写作能力即可"},
                "time": {"level": "yes", "desc": "需要时间整理经验"},
                "network": {"level": "no", "desc": "不需要人脉"}
            },
            "timeline": "2-4周",
            "investment": "极低（排版费用可选）",
            "risks": [
                {"type": "市场风险", "level": "medium", "desc": "同质化内容多，需要差异化"},
                {"type": "技术风险", "level": "low", "desc": "写作门槛低"},
                {"type": "定价风险", "level": "medium", "desc": "电子书定价需要策略"}
            ],
            "milestones": [
                {"week": 1, "milestone": "完成经验整理"},
                {"week": 2, "milestone": "完成初稿"},
                {"week": 3, "milestone": "完成排版设计"},
                {"week": 4, "milestone": "正式发布销售"}
            ]
        },
        "template": {
            "name": "模板工具",
            "icon": "📋",
            "description": "开发行业模板/工具，按订阅或按次收费",
            "steps": [
                {
                    "phase": "调研期",
                    "title": "需求调研",
                    "description": "确定核心模板需求和使用场景",
                    "duration": "1周",
                    "deliverables": ["需求文档", "竞品分析", "功能清单"]
                },
                {
                    "phase": "开发期",
                    "title": "模板开发",
                    "description": "开发高质量模板/工具",
                    "duration": "2-4周",
                    "deliverables": ["模板库", "使用说明", "在线工具"]
                },
                {
                    "phase": "上线期",
                    "title": "平台搭建",
                    "description": "搭建销售平台，设置定价",
                    "duration": "1周",
                    "deliverables": ["销售网站", "支付系统", "客服系统"]
                },
                {
                    "phase": "运营期",
                    "title": "持续迭代",
                    "description": "根据用户反馈持续更新",
                    "duration": "持续",
                    "deliverables": ["模板更新", "新功能开发", "用户社群"]
                }
            ],
            "requirements": {
                "capital": {"level": "partial", "desc": "网站/平台费用"},
                "technique": {"level": "yes", "desc": "需要模板制作能力"},
                "time": {"level": "yes", "desc": "需要持续投入"},
                "network": {"level": "no", "desc": "不需要人脉"}
            },
            "timeline": "1-2个月",
            "investment": "中等（平台开发）",
            "risks": [
                {"type": "市场风险", "level": "medium", "desc": "需要持续更新保持竞争力"},
                {"type": "技术风险", "level": "medium", "desc": "模板质量很关键"},
                {"type": "运营风险", "level": "medium", "desc": "需要持续运营"}
            ],
            "milestones": [
                {"week": 1, "milestone": "完成需求调研"},
                {"week": 3, "milestone": "完成核心模板"},
                {"week": 6, "milestone": "平台上线"},
                {"week": 10, "milestone": "获得第一批付费用户"}
            ]
        },
        "membership": {
            "name": "社群会员",
            "icon": "👥",
            "description": "建立付费社群，提供持续价值和资源对接",
            "steps": [
                {
                    "phase": "策划期",
                    "title": "社群定位",
                    "description": "确定社群定位、价值主张、定价",
                    "duration": "3-5天",
                    "deliverables": ["定位文档", "价值清单", "定价方案"]
                },
                {
                    "phase": "招募期",
                    "title": "种子用户",
                    "description": "从现有客户/粉丝中招募",
                    "duration": "1-2周",
                    "deliverables": ["招募文案", "种子用户群", "入群流程"]
                },
                {
                    "phase": "运营期",
                    "title": "持续运营",
                    "description": "提供持续价值，维护社群活跃",
                    "duration": "持续",
                    "deliverables": ["内容输出", "活动组织", "资源对接"]
                },
                {
                    "phase": "扩张期",
                    "title": "口碑传播",
                    "description": "通过口碑吸引更多会员",
                    "duration": "持续",
                    "deliverables": ["口碑素材", "推荐机制", "增长策略"]
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "几乎零成本"},
                "technique": {"level": "no", "desc": "运营能力即可"},
                "time": {"level": "yes", "desc": "需要持续投入时间"},
                "network": {"level": "partial", "desc": "有客户基础更好"}
            },
            "timeline": "1-2周启动",
            "investment": "极低（社群工具费用）",
            "risks": [
                {"type": "市场风险", "level": "low", "desc": "定位清晰就不难"},
                {"type": "运营风险", "level": "high", "desc": "社群运营需要持续投入"},
                {"type": "竞争风险", "level": "medium", "desc": "差异化价值很关键"}
            ],
            "milestones": [
                {"week": 1, "milestone": "完成定位和招募文案"},
                {"week": 2, "milestone": "招募30+种子用户"},
                {"week": 4, "milestone": "社群稳定运营"},
                {"week": 8, "milestone": "100+付费会员"}
            ]
        },
        "franchise": {
            "name": "加盟授权",
            "icon": "🏪",
            "description": "建立标准体系，授权他人复制你的模式",
            "steps": [
                {
                    "phase": "标准化期",
                    "title": "体系搭建",
                    "description": "建立可复制的标准体系",
                    "duration": "2-3个月",
                    "deliverables": ["运营手册", "培训体系", "标准化流程"]
                },
                {
                    "phase": "验证期",
                    "title": "小规模验证",
                    "description": "在1-2个店验证模式",
                    "duration": "1-2个月",
                    "deliverables": ["验证报告", "优化方案", "问题清单"]
                },
                {
                    "phase": "招商期",
                    "title": "开放加盟",
                    "description": "开始招募加盟商",
                    "duration": "持续",
                    "deliverables": ["加盟资料", "招商渠道", "支持体系"]
                },
                {
                    "phase": "赋能期",
                    "title": "持续赋能",
                    "description": "为加盟商提供支持和培训",
                    "duration": "持续",
                    "deliverables": ["培训课程", "督导体系", "供应链支持"]
                }
            ],
            "requirements": {
                "capital": {"level": "yes", "desc": "需要一定资金"},
                "technique": {"level": "yes", "desc": "需要成熟模式"},
                "time": {"level": "yes", "desc": "需要时间搭建体系"},
                "network": {"level": "yes", "desc": "需要品牌影响力"}
            },
            "timeline": "6-12个月",
            "investment": "高（体系搭建）",
            "risks": [
                {"type": "市场风险", "level": "medium", "desc": "加盟商质量参差不齐"},
                {"type": "品牌风险", "level": "high", "desc": "加盟商行为影响品牌"},
                {"type": "运营风险", "level": "high", "desc": "需要强运营支持"}
            ],
            "milestones": [
                {"month": 3, "milestone": "完成标准化体系"},
                {"month": 5, "milestone": "模式验证成功"},
                {"month": 8, "milestone": "招募第一批加盟商"},
                {"month": 12, "milestone": "10+加盟商"}
            ]
        },
        "saas": {
            "name": "SaaS工具",
            "icon": "💻",
            "description": "开发行业专用软件，按订阅制收费",
            "steps": [
                {
                    "phase": "调研期",
                    "title": "产品调研",
                    "description": "明确核心需求和使用场景",
                    "duration": "1-2周",
                    "deliverables": ["需求文档", "竞品分析", "产品原型"]
                },
                {
                    "phase": "开发期",
                    "title": "产品开发",
                    "description": "技术开发或外包",
                    "duration": "2-4个月",
                    "deliverables": ["MVP产品", "核心功能", "技术文档"]
                },
                {
                    "phase": "验证期",
                    "title": "Beta测试",
                    "description": "找种子用户测试",
                    "duration": "1-2个月",
                    "deliverables": ["测试报告", "改进清单", "种子用户"]
                },
                {
                    "phase": "商业化",
                    "title": "正式运营",
                    "description": "制定定价，开始商业化",
                    "duration": "持续",
                    "deliverables": ["定价策略", "获客方案", "运营体系"]
                }
            ],
            "requirements": {
                "capital": {"level": "yes", "desc": "开发成本较高"},
                "technique": {"level": "yes", "desc": "需要技术团队"},
                "time": {"level": "yes", "desc": "开发周期长"},
                "network": {"level": "partial", "desc": "有客户基础更好"}
            },
            "timeline": "3-6个月起",
            "investment": "高（技术开发）",
            "risks": [
                {"type": "市场风险", "level": "medium", "desc": "需要找到PMF"},
                {"type": "技术风险", "level": "medium", "desc": "产品体验很关键"},
                {"type": "竞争风险", "level": "high", "desc": "大厂可能进入"}
            ],
            "milestones": [
                {"month": 2, "milestone": "完成产品原型"},
                {"month": 4, "milestone": "MVP上线"},
                {"month": 6, "milestone": "获得第一批付费客户"},
                {"month": 12, "milestone": "100+付费客户"}
            ]
        },
        # ==================== 本地服务型特殊路线 ====================
        "content_marketing": {
            "name": "本地内容营销",
            "icon": "🎬",
            "description": "用抖音/小红书展示你的技艺，吸引外地同乡客户",
            "steps": [
                {
                    "phase": "定位期",
                    "title": "账号定位",
                    "description": "确定账号定位：技艺展示？用户故事？制作过程？",
                    "duration": "1周",
                    "deliverables": ["账号定位文档", "内容方向", "人设设定"]
                },
                {
                    "phase": "启动期",
                    "title": "内容制作",
                    "description": "拍摄第一批内容，展示核心技艺和服务过程",
                    "duration": "2-4周",
                    "deliverables": ["10-20条视频", "内容素材库", "拍摄脚本"]
                },
                {
                    "phase": "增长期",
                    "title": "持续输出",
                    "description": "保持稳定更新，建立粉丝基础",
                    "duration": "1-3个月",
                    "deliverables": ["稳定更新", "粉丝增长", "互动数据"]
                },
                {
                    "phase": "变现期",
                    "title": "商业转化",
                    "description": "通过内容吸引外地客户，提供远程服务或产品",
                    "duration": "持续",
                    "deliverables": ["转化路径", "远程服务方案", "产品链接"]
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "几乎零成本"},
                "technique": {"level": "no", "desc": "手机拍摄即可"},
                "time": {"level": "yes", "desc": "需要持续制作内容"},
                "network": {"level": "no", "desc": "不需要人脉"}
            },
            "timeline": "1-3个月见效",
            "investment": "极低（时间为主）",
            "risks": [
                {"type": "时间成本", "level": "high", "desc": "内容制作需要持续投入"},
                {"type": "效果不确定", "level": "medium", "desc": "需要测试不同内容方向"},
                {"type": "竞争激烈", "level": "medium", "desc": "同类型账号多，需要差异化"}
            ],
            "milestones": [
                {"month": 1, "milestone": "发布第一批内容"},
                {"month": 2, "milestone": "找到内容节奏"},
                {"month": 3, "milestone": "获得第一批外地咨询"},
                {"month": 6, "milestone": "内容变现路径清晰"}
            ]
        },
        "productize": {
            "name": "技艺产品化",
            "icon": "🎁",
            "description": "把你的核心技能/配方变成可销售的产品",
            "steps": [
                {
                    "phase": "提炼期",
                    "title": "技能萃取",
                    "description": "把核心技艺/配方整理成可复制的文档",
                    "duration": "1-2周",
                    "deliverables": ["技术文档", "配方清单", "操作流程"]
                },
                {
                    "phase": "产品化",
                    "title": "内容制作",
                    "description": "制作教程视频或电子书",
                    "duration": "2-4周",
                    "deliverables": ["教程视频/课程", "电子文档", "工具包"]
                },
                {
                    "phase": "上架期",
                    "title": "平台发布",
                    "description": "在各平台发布销售",
                    "duration": "1周",
                    "deliverables": ["销售页面", "定价策略", "推广素材"],
                },
                {
                    "phase": "迭代期",
                    "title": "持续优化",
                    "description": "根据用户反馈改进产品",
                    "duration": "持续",
                    "deliverables": ["产品迭代", "用户反馈", "口碑积累"],
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "几乎零成本"},
                "technique": {"level": "partial", "desc": "需要录制/编写能力"},
                "time": {"level": "yes", "desc": "需要整理和制作"},
                "network": {"level": "no", "desc": "不需要人脉"}
            },
            "timeline": "2-4周",
            "investment": "极低",
            "risks": [
                {"type": "定价难", "level": "medium", "desc": "技能类产品定价需要测试"},
                {"type": "盗版风险", "level": "medium", "desc": "需要考虑防盗版措施"},
                {"type": "竞争", "level": "low", "desc": "独特技艺是壁垒"}
            ],
            "milestones": [
                {"week": 2, "milestone": "完成产品制作"},
                {"week": 4, "milestone": "上架销售"},
                {"month": 2, "milestone": "获得第一批付费用户"},
                {"month": 6, "milestone": "形成稳定收入"}
            ]
        },
        "diaspora_service": {
            "name": "同乡服务",
            "icon": "🌏",
            "description": "服务在外地的本地人，通过内容建立信任，提供远程/邮寄服务",
            "steps": [
                {
                    "phase": "调研期",
                    "title": "用户调研",
                    "description": "了解在外地务工的本地人对家乡产品和服务的需求",
                    "duration": "1周",
                    "deliverables": ["需求调研", "用户画像", "产品清单"]
                },
                {
                    "phase": "准备期",
                    "title": "服务准备",
                    "description": "准备远程服务方案或产品邮寄方案",
                    "duration": "1-2周",
                    "deliverables": ["服务方案", "邮寄包装", "定价策略"],
                },
                {
                    "phase": "获客期",
                    "title": "内容获客",
                    "description": "通过内容吸引目标用户",
                    "duration": "持续",
                    "deliverables": ["内容矩阵", "获客渠道", "转化路径"],
                },
                {
                    "phase": "交付期",
                    "title": "服务交付",
                    "description": "提供远程咨询或产品邮寄",
                    "duration": "持续",
                    "deliverables": ["交付流程", "客户反馈", "复购方案"],
                }
            ],
            "requirements": {
                "capital": {"level": "partial", "desc": "包装和邮寄成本"},
                "technique": {"level": "no", "desc": "现有技能即可"},
                "time": {"level": "yes", "desc": "需要持续服务"},
                "network": {"level": "no", "desc": "通过内容获客"}
            },
            "timeline": "1-2个月启动",
            "investment": "低（包装邮寄）",
            "risks": [
                {"type": "物流", "level": "medium", "desc": "产品邮寄需要解决物流问题"},
                {"type": "信任", "level": "medium", "desc": "远程建立信任需要时间"},
                {"type": "规模", "level": "low", "desc": "初期规模可能有限"}
            ],
            "milestones": [
                {"month": 1, "milestone": "服务方案就绪"},
                {"month": 2, "milestone": "第一批远程客户"},
                {"month": 4, "milestone": "建立稳定客户群"},
                {"month": 6, "milestone": "形成稳定订单"}
            ]
        },
        "deepen_local": {
            "name": "深耕本地",
            "icon": "🏠",
            "description": "不扩张，专注提升本地服务质量和口碑，做精做透",
            "steps": [
                {
                    "phase": "诊断期",
                    "title": "服务诊断",
                    "description": "分析当前服务的优点和不足",
                    "duration": "1周",
                    "deliverables": ["服务诊断报告", "改进清单"]
                },
                {
                    "phase": "提升期",
                    "title": "质量提升",
                    "description": "聚焦提升核心服务质量",
                    "duration": "持续",
                    "deliverables": ["服务标准", "培训体系", "质量监控"],
                },
                {
                    "phase": "口碑期",
                    "title": "口碑建设",
                    "description": "用心服务老客户，促进转介绍",
                    "duration": "持续",
                    "deliverables": ["客户回访", "转介绍机制", "口碑积累"],
                },
                {
                    "phase": "稳定期",
                    "title": "稳定经营",
                    "description": "保持稳定服务质量，享受稳定收益",
                    "duration": "持续",
                    "deliverables": ["稳定收入", "客户忠诚", "良好口碑"]
                }
            ],
            "requirements": {
                "capital": {"level": "no", "desc": "专注服务即可"},
                "technique": {"level": "no", "desc": "发挥现有优势"},
                "time": {"level": "yes", "desc": "用心服务每个客户"},
                "network": {"level": "no", "desc": "靠口碑自然增长"}
            },
            "timeline": "持续",
            "investment": "无需额外投入",
            "risks": [
                {"type": "增长上限", "level": "high", "desc": "本地市场容量有限"},
                {"type": "竞争风险", "level": "medium", "desc": "新进入者可能竞争"},
                {"type": "个人依赖", "level": "medium", "desc": "业务依赖个人服务能力"}
            ],
            "milestones": [
                {"month": 1, "milestone": "服务改进见效"},
                {"month": 3, "milestone": "口碑明显提升"},
                {"month": 6, "milestone": "转介绍率提升50%"},
                {"month": 12, "milestone": "成为本地口碑最好的"}
            ]
        }
    }

    return routes.get(option_id, {})


# ==================== 保留原有的简化接口 ====================

@decision_cost_bp.route('/replicable-products', methods=['POST'])
def replicable_products():
    """简化版：一步完成分析"""
    return step1_analyze()
