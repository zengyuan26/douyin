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
        "assets": ["certificate", "content"]  // 新字段：资产类型
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
    assets = data.get('assets', [])  # 资产类型
    revenue = data.get('revenue', None)  # 收入范围

    if not business:
        return jsonify({"success": False, "message": "请输入业务类型"}), 400

    # 优先尝试LLM分析（所有业务类型统一走LLM）
    analysis_result = _llm_analyze_business(business, scope, assets)

    # 如果LLM分析返回空或失败，使用规则分析作为备用
    if not analysis_result or not analysis_result.get("M1"):
        print(f"LLM分析不可用，使用规则分析: {business}")
        analysis_result = _rule_based_analyze(business, scope, assets, revenue)
        # 备用方案也生成可复制选项
        replicable_options = _generate_replicable_options(business, scope, assets)
    else:
        # 使用LLM返回的可复制选项
        replicable_options = analysis_result.get("replicable_options", []) or _generate_replicable_options(business, scope, assets)

    return jsonify({
        "success": True,
        "data": {
            "step": 1,
            "modules": {
                "M1": analysis_result.get("M1", _get_empty_module("业务本质诊断", "🔍")),
                "M2": analysis_result.get("M2", _get_empty_module("决策成本评估", "⏰")),
                "M3": analysis_result.get("M3", _get_empty_module("资产盘点", "📦")),
                "M4": analysis_result.get("M4", _get_empty_module("AI机遇分析", "🤖"))
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
        for r in resources if r
    ])

    # 范围描述
    scope_desc = {"local": "本地客户", "national": "全国客户", "global": "全球客户"}.get(scope, "本地客户")

    # LLM分析提示词 - 详细版
    prompt = f"""你是一个专业的商业诊断顾问。请对这个业务进行深度分析，输出完整的JSON格式结果。

## 分析框架指导原则（纳瓦尔宝典）

**核心公式：财富 = 价值 × 杠杆 × 时间**

---

### 第一步：识别价值（最关键）

分析"解决问题的核心方式"是什么：

| 方式类型 | 特征 | 剥离难度 |
|---------|------|---------|
| 出卖体力 | 纯手工、不可规模化 | 极高 |
| 出卖时间 | 技能服务、一对一交付 | 高 |
| 出卖知识 | 经验变现、可规模化 | 中 |
| 出卖资源 | 资产变现、杠杆效应 | 低 |
| 出卖系统 | 商业模式、可完全脱离 | 极低 |

**资产依附性判断（关键维度）：**
| 类型 | 资产状态 | 变现方式 | 剥离路径 |
|------|---------|---------|---------|
| 个人技艺型 | 个人拥有 | 必须投入时间换钱 | 内容杠杆+产品化 |
| 知识经验型 | 人脑拥有 | 可产品化后自动售卖 | 课程+社群+出版 |
| 资产占有型 | 直接占有 | 资产直接产生现金流 | 加盟/授权/出售 |
| 资源控制型 | 控制使用权 | 低成本控制资产变现 | 二房东/共享模式/代理 |
| 系统模式型 | 系统自动运转 | 系统直接产生现金流 | SaaS/平台/规模化 |

**关键区分：赚钱 vs 换钱 vs 占钱**
- 赚钱：资产自动产生现金流（租金、系统）
- 换钱：必须投入时间体力（打工、个人服务）
- 占钱：控制他人资产产生现金流（二房东、代理、运营）

**二房东思维：不求所有，但求所用**
- 关键是你能控制多少资源
- 控制权可以脱离所有权
- 轻资产复制 = 控制资产使用权，而非购买资产

分析时必须明确：
1. **资产是什么？** 个人/技术/资源使用权/系统
2. **你拥有它还是控制它？** 所有权 vs 使用权/控制权
3. **现金流如何产生？** 换钱(投入时间) / 占钱(控制资产) / 赚钱(资产自有)
4. **能否低成本复制？** 控制权可以脱离所有权，轻资产复制

关键判断：
- **资产依附谁？** 资产在个人身上，还是可以脱离个人存在？
- **能否脱离个人？** 离开你，这个业务还能运转吗？
- **能否复制？** 别人能做吗？怎么复制？
- **复制代价？** 需要多少时间/金钱/培训？

---

### 第二步：选择杠杆

当价值识别清楚后，选择合适的杠杆放大：

- **代码杠杆**：边际成本趋近于0（AI、产品、工具）
- **媒体杠杆**：一次生产无限分发（自媒体、内容）
- **人力杠杆**：用别人时间（团队、外包）
- **资本杠杆**：用钱买时间（投资、规模化）

**优先级**：代码 > 媒体 > 人力 > 资本

---

### 第三步：时间积累

- 当前业务能否产生复利效应？
- 能否积累可复用的资产（内容、用户、品牌）？

---

业务：{business}
范围：{scope_desc}
资源：{resource_desc}

请输出完整的JSON（不要省略任何字段，不要用...代替）：

**重要：summary字段必须按以下格式输出：**
"价值类型（变现方式）× 杠杆类型 × 时间积累 = X分（定性）"
例如："出卖体力（换钱型）× 难以杠杆化 × 无复利 = 20分（体力陷阱）"
例如："出卖知识（可产品化）× 媒体杠杆 × 内容复利 = 65分（知识IP）"
例如："控制资源（占钱型）× 人力杠杆 × 规模复利 = 75分（资源杠杆）"

格式说明：
- 价值：出卖体力(10分) / 出卖时间(30分) / 出卖知识(50分) / 出卖资源(70分) / 出卖系统(90分)
- 变现方式：换钱型(必须投入时间) / 占钱型(控制资产使用权) / 赚钱型(资产自有现金流)
- 资产类型：个人技艺型 / 知识经验型 / 资产占有型 / 资源控制型 / 系统模式型
- 杠杆：难以杠杆化(10分) / 媒体杠杆(30分) / 人力杠杆(50分) / 代码杠杆(80分) / 资本杠杆(90分)
- 时间：单次出售(10分) / 有限复利(30分) / 内容复利(50分) / 资产复利(70分) / 品牌复利(90分)

---

{{
  "summary": "价值类型 × 杠杆类型 × 时间积累 = X分（简要定性）",
  "M1": {{
    "title": "业务本质诊断",
    "icon": "🔍",
    "items": [
      {{"label": "卖什么", "value": "具体产品/服务", "detail": "详细说明"}},
      {{"label": "卖给谁", "value": "目标客户群体", "detail": "详细说明"}},
      {{"label": "价格区间", "value": "价格范围", "detail": "市场定价"}},
      {{"label": "收入模式", "value": "盈利方式", "detail": "详细说明"}}
    ],
    "summary": "业务本质的详细描述",
    "expandable": true,
    "details": {{
      "核心价值": "核心价值描述",
      "商业模式": "商业模式描述",
      "竞争要素": "竞争要素描述",
      "信任机制": "信任机制描述",
      "资产类型": "个人技艺型/知识经验型/资产占有型/资源控制型/系统模式型",
      "资产控制权": "所有权/使用权/控制权",
      "变现方式": "换钱型/占钱型/赚钱型",
      "剥离路径": "建议的剥离路径"
    }},
    "trust_analysis": {{
      "summary": "信任机制总结",
      "type": "信任类型",
      "description": "信任机制详细描述",
      "key_factors": ["因素1", "因素2"],
      "challenge": "挑战描述",
      "implication": "建议描述"
    }},
    "is_local_service": true/false,
    "is_hard_to_replicate": true/false
  }},
  "M2": {{
    "title": "决策成本评估",
    "icon": "⏰",
    "trap_type": "时间陷阱类型",
    "trap_desc": "陷阱详细描述",
    "can_scale": true/false,
    "items": [
      {{"label": "时间陷阱", "value": "陷阱类型", "detail": "详细说明"}},
      {{"label": "没你能否转", "value": "是/否/部分", "detail": "详细说明"}},
      {{"label": "可复制指数", "value": "X/100", "detail": "复制难度说明"}},
      {{"label": "核心痛点", "value": "主要痛点", "detail": "详细说明"}}
    ],
    "summary": "决策成本评估总结",
    "expandable": true,
    "details": {{
      "自运转能力": "X%（详细说明）",
      "可复制指数": "X/100",
      "核心痛点": "痛点1、痛点2"
    }},
    "special_case": true/false,
    "recommendation_type": "类型",
    "recommendation": {{
      "directive": "建议指令",
      "reason": "原因",
      "strategy": "策略",
      "action_items": ["行动1", "行动2", "行动3"]
    }},
    "财富公式评估": {{
      "价值": {{"score": 85, "desc": "价值评估描述"}},
      "杠杆": {{"score": 60, "desc": "杠杆评估描述", "lever_type": "代码/媒体/人力/资本"}},
      "时间": {{"score": 40, "desc": "时间积累评估描述"}},
      "财富指数": 45
    }},
    "剥离分析": {{
      "能否剥离": "能/否/部分",
      "剥离路径": "直接可剥离/需产品化后剥离/难以剥离",
      "剥离前提": "剥离需要满足的条件",
      "剥离方案": "具体剥离策略"
    }}
  }},
  "M3": {{
    "title": "资产盘点",
    "icon": "📦",
    "items": [
      {{"label": "可产品化资产", "value": "X项", "detail": "详细说明"}},
      {{"label": "复制潜力", "value": "高/中/低", "detail": "详细说明"}},
      {{"label": "资源匹配", "value": "X%", "detail": "详细说明"}}
    ],
    "digital_assets": [
      {{"name": "资产名称", "status": "状态", "value": "价值"}}
    ],
    "replicable_potential": {{
      "score": 75,
      "level": "高/中/低",
      "reason": "原因说明"
    }},
    "resource_match": {{
      "score": 80,
      "strength": "资源强度描述",
      "match_items": ["匹配项1", "匹配项2"]
    }},
    "summary": "资产盘点总结",
    "expandable": true,
    "details": {{
      "可产品化资产": ["资产1", "资产2"],
      "复制潜力评分": "X/100",
      "资源匹配度": "X%"
    }}
  }},
  "M4": {{
    "title": "AI机遇分析",
    "icon": "🤖",
    "special_case": true/false,
    "ai_type": "AI类型",
    "core_insight": {{
      "title": "核心洞察标题",
      "description": "详细描述"
    }},
    "opportunities": [
      {{
        "type": "replace/enhance/automate/create",
        "task": "任务名称",
        "ai_action": "AI行动",
        "impact": "效果影响",
        "priority": "最高/高/中/低"
      }}
    ],
    "ceiling": {{
      "level": 75,
      "desc": "天花板描述"
    }},
    "risk": {{
      "level": "high/medium/low",
      "desc": "风险描述"
    }},
    "time_window": {{
      "value": "short/medium/long",
      "desc": "时间窗口描述"
    }},
    "recommendations": [
      "建议1：详细说明",
      "建议2：详细说明",
      "建议3：详细说明"
    ],
    "summary": "AI机遇总结"
  }},
  "replicable_options": [
    {{
      "id": "选项id（如course、handbook等）",
      "name": "选项名称",
      "icon": "图标emoji",
      "summary": "选项描述",
      "difficulty": "低/中/高",
      "match_score": 85,
      "reason": "为什么适合这个业务",
      "lever_type": "代码/媒体/人力/资本",
      "passive_income_potential": "高/中/低",
      "detach_ability": "完全可剥离/部分可剥离/难以剥离",
      "margin_cost": "边际成本趋近于0/较低/较高"
    }}
  ]
}}

直接输出JSON，不要有任何其他文字。"""

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
                # 验证结果是否有效
                if result and "M1" in result:
                    print(f"LLM解析成功")
                    return result
                else:
                    print(f"LLM返回结果不完整，使用规则分析")
            except:
                # 尝试修复后解析
                try:
                    fixed = fix_json(response)
                    result = json.loads(fixed)
                    if result and "M1" in result:
                        print(f"LLM解析成功（修复后）")
                        return result
                except:
                    # 打印详细错误信息
                    print(f"JSON解析失败，尝试修复...")
                    print(f"修复后内容: {fixed[:500] if 'fixed' in dir() else response[:500]}...")

            # LLM解析失败，使用规则分析
            print(f"LLM分析失败，使用规则分析作为备用")
            return _rule_based_analyze(business, scope, resources)

        except Exception as e:
            print(f"LLM分析失败: {e}")
            import traceback
            traceback.print_exc()
            # LLM失败时使用规则分析
            return _rule_based_analyze(business, scope, resources)
    else:
        # 没有LLM时使用规则分析
        print("LLM不可用，使用规则分析")
        return _rule_based_analyze(business, scope, resources)


def _rule_based_analyze(business: str, scope: str, assets: list, revenue: str = None) -> dict:
    """
    基于规则的深度分析：当LLM不可用时使用完整规则分析
    """
    print(f"使用规则分析: business={business}, scope={scope}, assets={assets}, revenue={revenue}")

    # 调用各个分析模块
    m1 = _analyze_business_essence(business, scope, assets)
    m2 = _analyze_decision_cost(business, scope, assets)
    m3 = _analyze_assets(business, scope, assets, revenue)
    m4 = _analyze_ai_opportunity(business, scope, assets)

    # 生成综合摘要
    summary = m1.get("summary", "")

    return {
        "summary": summary,
        "M1": m1,
        "M2": m2,
        "M3": m3,
        "M4": m4
    }


def _get_empty_module(title: str, icon: str) -> dict:
    """返回一个空模块的默认结构"""
    return {
        "title": title,
        "icon": icon,
        "items": [],
        "summary": "暂无数据"
    }


def _fallback_analysis(business: str, scope: str, resources: list) -> dict:
    """备用分析：当LLM不可用时使用规则分析（已废弃，使用_rule_based_analyze代替）"""
    return _rule_based_analyze(business, scope, resources)


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
        for r in resources if r
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

    # 信任建立分析（核心新增）
    trust_analysis = _analyze_trust_for_decision_cost(business_lower, scope)

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

    # 计算可复制指数（考虑信任建立因素）
    trust_factor = trust_analysis["replication_impact_score"]  # -30 到 +30
    base_replication = 50

    if any(k in business_lower for k in ["心理", "法律", "财税", "医"]):
        replication_score = min(100, max(0, base_replication + trust_factor + 0))  # 资质可传递
        replication_level = "中等"
    elif any(k in business_lower for k in ["培训", "教育", "咨询"]):
        replication_score = min(100, max(0, base_replication + trust_factor + 5))
        replication_level = "中等偏高"
    elif any(k in business_lower for k in ["设计", "装修", "中介"]):
        replication_score = min(100, max(0, base_replication + trust_factor + 0))
        replication_level = "中等"
    elif any(k in business_lower for k in ["美容", "健身", "家政"]):
        replication_score = min(100, max(0, base_replication + trust_factor - 10))
        replication_level = "较低"
    else:
        replication_score = min(100, max(0, base_replication + trust_factor))
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
        },
        # 新增：信任建立分析
        "trust_analysis": trust_analysis
    }


def _analyze_trust_for_decision_cost(business_lower: str, scope: str) -> dict:
    """
    分析信任建立机制及其对复制难度的影响
    这是决策成本评估的核心维度之一
    """
    is_local_service = _is_local_service_business(business_lower)

    # 本地服务型（人情型信任）- 复制极难
    if is_local_service and scope == "local":
        return {
            "type": "人情型信任",
            "type_icon": "👥",
            "difficulty": "极高",
            "difficulty_score": 90,
            "description": "信任建立在本地社会关系网络上，靠口碑、关系介绍、回头客",
            "key_factors": [
                {"factor": "主理人威望", "desc": "客户信任你这个人，包括你的为人、做事方式"},
                {"factor": "人情往来", "desc": "通过长期接触积累的人情，互相帮忙、介绍客户"},
                {"factor": "邻里口碑", "desc": "街坊邻居的认可和推荐"},
                {"factor": "回头客", "desc": "客户体验好后持续复购并介绍新客户"}
            ],
            "replication_barrier": "这种信任无法随身携带！外地客户不认识你，没有共同社会网络背书",
            "replication_impact": "复制难度 +40分（非常难）",
            "replication_impact_score": -30,
            "how_to_build": "如果想复制，需要用'内容'建立新的信任背书，而不是复制本地模式",
            "alternative_path": "把技艺产品化（教程、课程）+ 内容获客，服务外地同乡"
        }

    # 本地服务想扩张全国（内容型信任）- 复制较难
    elif is_local_service and scope in ["national", "global"]:
        return {
            "type": "内容型信任",
            "type_icon": "📱",
            "difficulty": "较高",
            "difficulty_score": 60,
            "description": "需要通过内容输出（抖音、小红书）建立专业形象",
            "key_factors": [
                {"factor": "内容影响力", "desc": "视频/图文内容的传播力和专业度"},
                {"factor": "作品展示", "desc": "服务案例、过程记录、对比图"},
                {"factor": "客户评价", "desc": "真实用户反馈和见证"},
                {"factor": "专业资质", "desc": "证书、头衔、行业认可"}
            ],
            "replication_barrier": "没有本地社会网络背书，需要更强的内容营销能力",
            "replication_impact": "复制难度 +20分（较难）",
            "replication_impact_score": -15,
            "how_to_build": "先把本地成功案例做成内容（抖音/小红书），吸引外地客户",
            "alternative_path": "服务在外地的本地人或认同你价值的远方客户"
        }

    # 知识服务型（专业型信任）- 复制中等
    elif any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "培训", "咨询", "教练"]):
        return {
            "type": "专业型信任",
            "type_icon": "🎓",
            "difficulty": "中等",
            "difficulty_score": 50,
            "description": "专业资质本身就是信任背书，可以通过远程服务全国客户",
            "key_factors": [
                {"factor": "专业资质", "desc": "证书、执照、学历等硬性背书"},
                {"factor": "成功案例", "desc": "解决过的问题、帮客户达成的结果"},
                {"factor": "平台认证", "desc": "在专业平台上的认证和排名"},
                {"factor": "行业口碑", "desc": "同行认可和推荐"}
            ],
            "replication_barrier": "资质可以传递，但建立同等口碑需要时间",
            "replication_impact": "复制难度 0分（中等）",
            "replication_impact_score": 0,
            "how_to_build": "培养团队成员获取资质，复制方法论和流程",
            "alternative_path": "适合做线上课程/咨询，边际成本低，可规模化"
        }

    # 技术服务型（作品型信任）- 复制较易
    elif any(k in business_lower for k in ["设计", "装修", "IT", "软件", "开发", "摄影", "摄像"]):
        return {
            "type": "作品型信任",
            "type_icon": "🖼️",
            "difficulty": "较低",
            "difficulty_score": 40,
            "description": "客户通过作品集和案例判断能力，可线上展示触达全国",
            "key_factors": [
                {"factor": "作品质量", "desc": "过往作品的专业度和美观度"},
                {"factor": "案例展示", "desc": "完整案例的前后对比、过程说明"},
                {"factor": "客户评价", "desc": "真实客户的好评和推荐"},
                {"factor": "服务效率", "desc": "响应速度和专业沟通能力"}
            ],
            "replication_barrier": "作品集可以传承，但交付质量依赖团队培训",
            "replication_impact": "复制难度 -10分（较易）",
            "replication_impact_score": 10,
            "how_to_build": "建立标准流程和培训体系，培养团队成员",
            "alternative_path": "标准化流程 + 培养团队，降低对个人的依赖"
        }

    # 品牌型（品牌型信任）- 复制较易
    elif any(k in business_lower for k in ["中介", "代理", "猎头", "房产", "保险", "直销"]):
        return {
            "type": "品牌型信任",
            "type_icon": "🏢",
            "difficulty": "较低",
            "difficulty_score": 35,
            "description": "品牌背书让客户更容易信任新员工或加盟店",
            "key_factors": [
                {"factor": "品牌知名度", "desc": "品牌在市场上的认知度和美誉度"},
                {"factor": "标准流程", "desc": "统一的服务流程和标准"},
                {"factor": "背书体系", "desc": "品牌方提供的支持和背书"},
                {"factor": "系统支持", "desc": "CRM系统、培训体系等支持"}
            ],
            "replication_barrier": "品牌可以授权，但执行质量参差不齐",
            "replication_impact": "复制难度 -15分（较易）",
            "replication_impact_score": 15,
            "how_to_build": "建立品牌标准和加盟体系，统一培训和支持",
            "alternative_path": "加盟/代理模式，快速扩张但需管控品质"
        }

    # 撮合型（资源型信任）- 复制难
    elif any(k in business_lower for k in ["撮合", "平台", "渠道"]):
        return {
            "type": "资源型信任",
            "type_icon": "🔗",
            "difficulty": "高",
            "difficulty_score": 70,
            "description": "信任建立在资源连接能力上",
            "key_factors": [
                {"factor": "资源丰富度", "desc": "掌握的供需双方资源数量"},
                {"factor": "匹配效率", "desc": "快速精准匹配的能力"},
                {"factor": "行业人脉", "desc": "在行业中的关系网络"},
                {"factor": "数据壁垒", "desc": "积累的用户数据和关系网络"}
            ],
            "replication_barrier": "资源和人脉难以快速复制",
            "replication_impact": "复制难度 +25分（难）",
            "replication_impact_score": -20,
            "how_to_build": "建立数据壁垒，向平台化方向演进",
            "alternative_path": "用技术提升匹配效率，建立网络效应"
        }

    else:
        # 通用型
        return {
            "type": "综合型信任",
            "type_icon": "⚖️",
            "difficulty": "中等",
            "difficulty_score": 50,
            "description": "混合多种信任机制",
            "key_factors": [
                {"factor": "产品质量", "desc": "核心产品/服务的质量"},
                {"factor": "服务态度", "desc": "专业、耐心、负责的态度"},
                {"factor": "价格竞争力", "desc": "性价比是否突出"},
                {"factor": "渠道覆盖", "desc": "触达客户的渠道能力"}
            ],
            "replication_barrier": "需要平衡多个维度的竞争要素",
            "replication_impact": "复制难度 0分（中等）",
            "replication_impact_score": 0,
            "how_to_build": "找出你最独特的竞争力，集中资源打造",
            "alternative_path": "差异化定位，找到细分市场"
        }


def _analyze_local_service(business: str, scope: str) -> dict:
    """分析本地服务型业务的核心问题"""

    business_lower = business.lower()

    # 获取信任分析
    trust_analysis = _analyze_trust_for_decision_cost(business_lower, scope)

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
            },
            # 新增：信任建立分析
            "trust_analysis": trust_analysis
        }
    else:
        # 选择全国/全球的分析
        result = {
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
            },
            # 新增：信任建立分析
            "trust_analysis": trust_analysis
        }
        return result


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

def _analyze_assets(business: str, scope: str, models_input: list, revenue: str = None) -> dict:
    """
    M3: 杠杆点与资产化路径

    核心问题：
    1. 你现在在出卖什么？（时间？体力？技能？资源？）
    2. 你卖的东西中，哪一部分可以"剥离"出来？
    3. 这个可剥离的东西能否病毒化复制？

    参考《纳瓦尔宝典》+《富爸爸穷爸爸》：
    - 餐盘修复 → 做内容 → 卖教程 → 被动收入
    - 核心是找到那个"可以病毒化复制的点"
    """

    business_lower = business.lower()

    # 分析你的"出卖物"
    what_you_sell = _analyze_what_you_sell(business_lower)

    # 识别可复制的杠杆点
    leverage_points = _identify_replicable_leverage(business_lower, what_you_sell)

    # 资产化路径
    assetization_path = _analyze_assetization_path_v2(business_lower, models_input, leverage_points)

    # 综合评估
    comprehensive = _comprehensive_assessment_v2(leverage_points, assetization_path)

    return {
        "title": "杠杆点与资产化路径",
        "icon": "🎯",
        "items": [
            {"label": "你在出卖", "value": what_you_sell["type"], "detail": what_you_sell["desc"]},
            {"label": "可复制点", "value": leverage_points["has_leverage"] if leverage_points.get("has_leverage") else "待识别", "detail": leverage_points.get("summary", "分析中...")},
            {"label": "资产化路径", "value": assetization_path["level"], "detail": assetization_path["summary"]}
        ],
        "what_you_sell": what_you_sell,
        "leverage_points": leverage_points,
        "assetization_path": assetization_path,
        "comprehensive": comprehensive,
        "summary": comprehensive["summary"],
        "expandable": True,
        "details": {
            "核心洞察": comprehensive.get("core_insight", ""),
            "行动建议": comprehensive.get("action", "")
        }
    }


def _analyze_what_you_sell(business_lower: str) -> dict:
    """
    分析你在出卖什么
    核心：出卖的是什么，决定了能不能复制

    关键洞察（中餐店 vs 麦当劳）：
    - 中餐：依赖主厨技能 → 技能在厨师脑子里 → 难以复制
    - 麦当劳：依赖流程系统 → 系统可以无限复制 → 容易做大

    核心问题：这个业务的"核心资产"是依附在人身上，还是依附在系统/品牌上？
    """
    # 纯时间出租
    if any(k in business_lower for k in ["外卖", "快递", "滴滴", "代驾", "搬运", "临时工"]):
        return {
            "type": "纯时间",
            "desc": "干一小时算一小时，无法积累，无法复制",
            "can_replicate": False,
            "why": "你的时间只能出租一次，无法复制",
            "asset_location": "依附在你身上",
            "example_problem": "骑手跑了就跑了，没有任何积累"
        }

    # 餐饮（中餐问题）
    if any(k in business_lower for k in ["餐饮", "饭店", "餐厅", "小吃", "早餐", "中餐", "川菜", "粤菜", "湘菜"]):
        return {
            "type": "手艺 + 口味（依赖人）",
            "desc": "核心价值在厨师和配方，难以标准化",
            "can_replicate": False,
            "why": "中餐的灵魂在厨师，而厨师需要多年培养，主厨走了店就完了",
            "asset_location": "依附在厨师身上",
            "example_problem": "麦当劳可以复制，因为不依赖厨师；中餐难以复制，因为太依赖主厨",
            "mcdonald_insight": "麦当劳ceo说：'我们不是做汉堡的，我们是做房地产的'",
            "solution_hint": "要么标准化（麦当劳模式），要么卖手艺（培训/教程）"
        }

    # 体力 + 少量技能
    if any(k in business_lower for k in ["美容", "美发", "理发", "家政", "保洁", "按摩"]):
        return {
            "type": "时间 + 体力 + 少量技能",
            "desc": "需要到现场，手艺有一定壁垒",
            "can_replicate": "partial",
            "why": "手艺可以教，但需要人到现场",
            "asset_location": "部分依附在人身上",
            "replicable_part": "技术/手法",
            "non_replicable_part": "服务本身",
            "example_good": "海底捞：标准化服务流程 → 员工可复制",
            "example_bad": "个体美发店：太依赖理发师个人"
        }

    # 技能/专业知识
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "培训", "咨询", "教练"]):
        return {
            "type": "专业知识 + 时间",
            "desc": "出卖专业知识和经验",
            "can_replicate": True,
            "why": "知识可以整理成产品（课程/教程），一次制作持续销售",
            "asset_location": "知识可以独立于你存在",
            "replicable_part": "知识体系、方法论",
            "non_replicable_part": "服务/咨询",
            "example_good": "知识付费：课程录好后，不需要你亲自在场",
            "transformation": "从'亲自服务'到'卖知识产品'"
        }

    # 资源运作（撮合）
    if any(k in business_lower for k in ["中介", "代理", "猎头", "房产", "保险", "二房东", "租赁"]):
        return {
            "type": "资源 + 信息差 + 时间",
            "desc": "撮合供需双方，赚取差价/佣金",
            "can_replicate": "partial",
            "why": "资源/人脉难以复制，但撮合方法可以",
            "asset_location": "核心竞争力在个人关系",
            "replicable_part": "匹配逻辑、系统、流程",
            "non_replicable_part": "现有资源/关系",
            "example_good": "贝壳：把房产中介的逻辑系统化，加盟扩张"
        }

    # 产品制造
    if any(k in business_lower for k in ["制造", "生产", "加工", "灌香肠", "腊肉", "腊肠", "腌菜", "酱料"]):
        return {
            "type": "产品 + 配方/工艺",
            "desc": "生产产品，销售给客户",
            "can_replicate": True,
            "why": "产品可以标准化，配方可以传授",
            "asset_location": "配方/工艺可以独立存在",
            "replicable_part": "产品、配方、流程",
            "non_replicable_part": "核心口味/秘方",
            "example_good": "可口可乐：配方标准化，全世界一个味道",
            "transformation": "从'手工作坊'到'工业化生产'"
        }

    # 餐盘修复等特殊技能
    if any(k in business_lower for k in ["修复", "维修", "修补", "diy", "手工"]):
        return {
            "type": "特殊技能 + 知识",
            "desc": "有一定壁垒的特殊技能",
            "can_replicate": True,
            "why": "技能可以教学，经验可以整理成教程",
            "asset_location": "技能可以独立于你存在",
            "replicable_part": "技术教程、操作流程",
            "non_replicable_part": "实操经验",
            "example_good": "修复教程 → 内容获客 → 卖课/工具"
        }

    # 默认
    return {
        "type": "待分析",
        "desc": "需要更多信息判断",
        "can_replicate": "unknown",
        "why": "请明确你的商业模式",
        "asset_location": "待确定"
    }


def _identify_replicable_leverage(business_lower: str, what_you_sell: dict) -> dict:
    """
    识别可复制的杠杆点
    核心：找到那个可以病毒化复制的"点"

    态度：不给中庸答案，不行就是不行
    """
    can_replicate = what_you_sell.get("can_replicate", False)
    replicable_part = what_you_sell.get("replicable_part", "")
    business_type = what_you_sell.get("type", "")

    if can_replicate == False:
        # 纯时间出租 - 直接否定
        return {
            "has_leverage": "❌ 无杠杆点",
            "summary": "你的业务本质上无法积累资产，100%在出租时间",
            "verdict": "❌ 不行",
            "verdict_reason": "时间出租=干一天算一天，没有积累，没有未来",
            "problem": "没有任何东西可以'剥离'出来做产品，因为你的价值=时间本身",
            "leverage_type": None,
            "leverage_points": [],
            "core_insight": "你必须转型，没有任何优化空间",
            "difficulty": "极高（需要完全转型）",
            "action": "放弃这条路，选择一个有杠杆点的业务"
        }

    if can_replicate == "partial":
        # 部分可复制 - 明确难度
        if "手艺" in business_type or "体力" in business_type:
            # 美发/美容等 - 难度高
            return {
                "has_leverage": "⚡ 有杠杆点，但难度高",
                "summary": "手艺可以标准化，但需要系统化改造",
                "verdict": "⚡ 可以，但很难",
                "verdict_reason": "成功案例少（海底捞算一个），失败率高",
                "problem": "你现在的竞争力在'人'身上，要变成在'系统'身上，需要彻底重构",
                "leverage_type": "系统杠杆 + 品牌杠杆",
                "leverage_points": [
                    {
                        "name": "标准化流程",
                        "desc": "把服务流程标准化，雇人执行",
                        "difficulty": "极高",
                        "difficulty_reason": "中餐美发标准化成功率<5%，需要极强的管理能力",
                        "example": "失败案例远多于成功案例",
                        "viral_score": 30,
                        "action": "适合极少数有管理天赋的人，普通人慎重"
                    },
                    {
                        "name": "转型卖手艺",
                        "desc": "把技术做成教程/培训",
                        "difficulty": "中等",
                        "difficulty_reason": "需要你从'做事'变成'教人做事'",
                        "example": "成功的理发师转型培训的比单纯开店的少",
                        "viral_score": 70,
                        "action": "如果你热爱教人，这是个好方向"
                    }
                ],
                "core_insight": "⚠️ 这条路很难走，成功率低。问问自己：你是那5%有管理天赋的人吗？",
                "difficulty": "极高",
                "action": "要么成为海底捞（极难），要么转型卖手艺（更现实）"
            }

        elif "资源" in business_type or "撮合" in business_type:
            # 中介/猎头等 - 难度中等
            return {
                "has_leverage": "⚡ 有杠杆点",
                "summary": "方法可以系统化，但资源/人脉难复制",
                "verdict": "⚡ 可以做",
                "verdict_reason": "贝壳/链家已经验证这条路是可行的",
                "problem": "你的核心竞争力在关系，关系无法转移",
                "leverage_type": "系统杠杆 + 品牌杠杆",
                "leverage_points": [
                    {
                        "name": "标准化 + 品牌化",
                        "desc": "让客户认品牌不认个人",
                        "difficulty": "高",
                        "difficulty_reason": "需要大量资金和时间建立品牌",
                        "example": "贝壳：砸钱建立品牌 → 系统化流程 → 加盟扩张",
                        "viral_score": 60,
                        "action": "普通人：深耕本地，做出口碑"
                    },
                    {
                        "name": "工具化",
                        "desc": "开发系统提升匹配效率",
                        "difficulty": "高（需要技术合伙人）",
                        "difficulty_reason": "技术开发成本高，周期长",
                        "example": "猎头SaaS、房产小程序",
                        "viral_score": 70,
                        "action": "找技术合伙人，或者用现成工具"
                    }
                ],
                "core_insight": "你的方法可以复制，但需要时间和资金",
                "difficulty": "高",
                "action": "从小做起，先验证模型，再扩张"
            }

        # 默认部分可复制
        return {
            "has_leverage": "⚡ 有杠杆点",
            "summary": "有路径，但需要努力",
            "verdict": "⚡ 可以做",
            "difficulty": "中等",
            "leverage_points": []
        }

    if can_replicate == True:
        # 技能/知识型 - 明确可行
        return {
            "has_leverage": "✅ 有杠杆点",
            "summary": f"你的'{replicable_part}'可以'剥离'出来做成产品",
            "verdict": "✅ 可以做",
            "verdict_reason": "知识产品化是普通人最容易成功的资产化路径",
            "problem": "你现在在亲自出卖这部分，需要转变思维",
            "leverage_type": "内容杠杆 + 产品杠杆",
            "leverage_points": [
                {
                    "name": "教程/课程",
                    "desc": "把技能整理成教程，卖给想学的人",
                    "difficulty": "低",
                    "difficulty_reason": "录课门槛低，成功案例多（知识付费已验证）",
                    "example": "餐盘修复教程 → 卖99元/份，录一次卖1000份",
                    "viral_score": 80,
                    "action": "整理核心技能 → 录制教程 → 内容获客 → 销售"
                },
                {
                    "name": "内容影响力",
                    "desc": "做内容展示技能，吸引潜在客户",
                    "difficulty": "低",
                    "difficulty_reason": "抖音/小红书已验证，普通人可以做到",
                    "example": "抖音发修复视频 → 引流 → 接单/卖教程",
                    "viral_score": 90,
                    "action": "持续输出内容 → 建立影响力 → 被动获客"
                },
                {
                    "name": "培训/授权",
                    "desc": "培训学员，收取学费或授权费",
                    "difficulty": "中等",
                    "difficulty_reason": "需要教学能力和口碑积累",
                    "example": "开培训班 → 学员学会后接单 → 你赚学费",
                    "viral_score": 60,
                    "action": "先做内容建立口碑，再招生培训"
                }
            ],
            "core_insight": f"✅ 关键洞察：你的'{replicable_part}'是你最大的资产，开始整理它",
            "difficulty": "低（知识产品化已验证）",
            "action": "🎯 立即行动：从录制第一个教程开始"
        }

    return {
        "has_leverage": "❓ 待分析",
        "summary": "需要更多信息",
        "difficulty": "待评估",
        "leverage_points": []
    }


def _analyze_assetization_path_v2(business_lower: str, models_input: list, leverage_points: dict) -> dict:
    """
    分析资产化路径 v2
    核心：从出卖时间 → 拥有可复制的产品 → 拥有资产
    """
    has_leverage = leverage_points.get("has_leverage", "")

    if "❌ 无杠杆点" in has_leverage:
        return {
            "level": "❌ 无法资产化",
            "summary": "纯时间出租，必须转型",
            "path": "转型 → 选择一个有杠杆点的业务",
            "stages": [
                {"stage": "1. 认清现实", "desc": "纯时间出租无法积累资产"},
                {"stage": "2. 转型方向", "desc": "选择技能型或资源型业务"},
                {"stage": "3. 建立杠杆", "desc": "找到可复制的产品/内容"}
            ]
        }

    if "✅ 有杠杆点" in has_leverage:
        return {
            "level": "优秀",
            "summary": "有明确的资产化路径",
            "path": "内容/教程 → 影响力 → 被动收入",
            "stages": [
                {"stage": "1. 提取", "desc": "从业务中提取可复制的部分（技术/知识）"},
                {"stage": "2. 产品化", "desc": "做成教程/课程/工具"},
                {"stage": "3. 内容获客", "desc": "用内容建立影响力"},
                {"stage": "4. 被动收入", "desc": "产品销售不需要你亲自在场"},
                {"stage": "5. 积累资产", "desc": "用收入购买硬资产（房产/设备）"}
            ],
            "example": "餐盘修复 → 修复教程（99元） → 抖音发视频 → 教程被动销售 → 攒钱买设备扩大产能"
        }

    if "⚡ 有部分杠杆点" in has_leverage:
        return {
            "level": "中等",
            "summary": "有路径但需要更多积累",
            "path": "标准化 → 系统化 → 规模化",
            "stages": [
                {"stage": "1. 标准化", "desc": "把核心流程梳理清楚"},
                {"stage": "2. 团队化", "desc": "雇人执行，你做管理"},
                {"stage": "3. 系统化", "desc": "开发工具/系统提升效率"},
                {"stage": "4. 品牌化", "desc": "让客户认品牌不认个人"},
                {"stage": "5. 规模化", "desc": "加盟/合伙/融资"}
            ],
            "example": "中介 → 标准化流程 → 雇人执行 → 品牌化 → 加盟扩张"
        }

    return {
        "level": "待分析",
        "summary": "需要更多信息",
        "path": "待规划"
    }


def _comprehensive_assessment_v2(leverage_points: dict, assetization_path: dict) -> dict:
    """
    综合评估 v2
    """
    has_leverage = leverage_points.get("has_leverage", "")

    if "✅ 有杠杆点" in has_leverage:
        # 找出最高viral_score的杠杆点
        best_point = max(leverage_points.get("leverage_points", []), key=lambda x: x.get("viral_score", 0), default={})

        return {
            "score": 80,
            "level": "优秀",
            "summary": "✅ 你找到了可病毒化复制的杠杆点",
            "core_insight": leverage_points.get("core_insight", ""),
            "action": f"🎯 立即行动：从'{best_point.get('name', '核心技能')}'开始，录制第一个教程/内容",
            "viral_point": best_point.get("name", ""),
            "viral_score": best_point.get("viral_score", 0),
            "example": best_point.get("example", "")
        }

    if "⚡ 有部分杠杆点" in has_leverage:
        return {
            "score": 50,
            "level": "中等",
            "summary": "⚡ 你有杠杆点，但需要系统化",
            "core_insight": leverage_points.get("core_insight", ""),
            "action": "📋 优先事项：标准化核心流程，建立可复制的系统",
            "viral_point": "系统/品牌",
            "viral_score": 60
        }

    return {
        "score": 20,
        "level": "较弱",
        "summary": "❌ 你目前没有找到可复制的杠杆点",
        "core_insight": "核心问题：你的业务本质是出租时间，无法提取可复制的部分",
        "action": "🔄 转型建议：选择技能型或资源型业务，找到那个'可以剥离出来做产品的点'",
        "viral_point": "无",
        "viral_score": 0
    }


def _analyze_asset_detachability(business_lower: str, scope: str) -> dict:
    """
    分析各类资产的"可剥离性"
    核心问题：这个资产能不能从你身上剥离？
    - 可剥离：剥离后你能脱身，业务还能运转
    - 依附型：剥离后你还得在，无法脱身
    """
    assets = []
    summary_parts = []

    # 知识/经验类 - 可剥离
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育", "培训", "咨询", "教练"]):
        assets.append({
            "name": "专业知识体系",
            "type": "knowledge",
            "detachability": "high",
            "detach_label": "可剥离",
            "detach_desc": "整理成课程/教程/电子书，边际成本趋近于零",
            "replication_form": "在线课程、付费专栏、训练营",
            "barrier": "需要整理和包装，但整理后可持续销售",
            "can_escape": True,  # 能否让你脱身
            "escape_desc": "用户购买后你可不再参与"
        })
        summary_parts.append("知识可产品化")

    # 方法论/流程类 - 可剥离
    if any(k in business_lower for k in ["设计", "装修", "IT", "软件", "管理", "运营"]):
        assets.append({
            "name": "方法论/流程",
            "type": "methodology",
            "detachability": "high",
            "detach_label": "可剥离",
            "detach_desc": "标准化流程、模板、工具包",
            "replication_form": "模板工具、SaaS产品、培训手册",
            "barrier": "需要提炼和文档化",
            "can_escape": True,
            "escape_desc": "用户按流程自行执行，你可脱身"
        })
        summary_parts.append("方法论可标准化")

    # 案例/作品类 - 可剥离
    if any(k in business_lower for k in ["设计", "装修", "摄影", "文案", "营销"]):
        assets.append({
            "name": "案例/作品集",
            "type": "portfolio",
            "detachability": "medium",
            "detach_label": "可部分剥离",
            "detach_desc": "作品可以展示，但交付仍需参与",
            "replication_form": "案例库、作品集电子书、教程",
            "barrier": "展示型产品可脱身，交付型仍需参与",
            "can_escape": True,
            "escape_desc": "如果只卖教程/案例，可以脱身"
        })
        summary_parts.append("案例可展示化")

    # 客户关系类 - 难以剥离
    if any(k in business_lower for k in ["销售", "中介", "代理", "猎头", "房产", "保险"]):
        assets.append({
            "name": "客户关系",
            "type": "relationships",
            "detachability": "low",
            "detach_label": "难以剥离",
            "detach_desc": "客户信任你这个人，不是信任品牌",
            "replication_form": "建立品牌，让客户信任品牌而非个人",
            "barrier": "客户跟你走，不是跟品牌走",
            "can_escape": False,
            "escape_desc": "你需要持续维护，否则客户流失"
        })
        summary_parts.append("⚠️ 客户关系难剥离")

    # 人力服务类 - 依附型
    if any(k in business_lower for k in ["美容", "健身", "按摩", "理发", "餐饮", "家政"]):
        assets.append({
            "name": "手艺/服务",
            "type": "skill",
            "detachability": "low",
            "detach_label": "依附型",
            "detach_desc": "核心价值在你的手艺，无法转移",
            "replication_form": "培训徒弟/员工，但品质难保证",
            "barrier": "品质完全依赖个人，无法规模化",
            "can_escape": False,
            "escape_desc": "你不上班就没收入"
        })
        summary_parts.append("⚠️ 手艺无法剥离")

    # 资质/认证类 - 可剥离
    if any(k in business_lower for k in ["心理", "法律", "财税", "医", "教育"]):
        assets.append({
            "name": "专业资质",
            "type": "certification",
            "detachability": "medium",
            "detach_label": "可转移但有条件",
            "detach_desc": "资质可给团队成员，但建立同等信任需时间",
            "replication_form": "培养持证员工，授权使用资质",
            "barrier": "资质背后是信任，需要时间积累",
            "can_escape": "partial",
            "escape_desc": "有资质的人可以在，但客户可能只认你"
        })
        summary_parts.append("资质可转移")

    # 数据/信息类 - 可剥离
    if any(k in business_lower for k in ["咨询", "分析", "数据", "报告"]):
        assets.append({
            "name": "数据/洞察",
            "type": "data",
            "detachability": "high",
            "detach_label": "可剥离",
            "detach_desc": "行业数据、洞察、报告可以产品化",
            "replication_form": "付费报告、订阅服务、API接口",
            "barrier": "需要持续更新，但边际成本低",
            "can_escape": True,
            "escape_desc": "用户付费后自行使用，你可脱身"
        })
        summary_parts.append("数据可产品化")

    # 如果没有匹配到，添加通用分析
    if not assets:
        assets.append({
            "name": "行业经验",
            "type": "experience",
            "detachability": "medium",
            "detach_label": "视情况而定",
            "detach_desc": "经验可以提炼，但需要主动整理",
            "replication_form": "整理成教程/咨询/课程",
            "barrier": "取决于你愿不愿意花时间整理",
            "can_escape": "partial",
            "escape_desc": "整理后可以脱身，但需要前期投入"
        })
        summary_parts.append("经验待整理")

    # 计算统计
    detachable_count = sum(1 for a in assets if a["detachability"] == "high")
    attached_count = sum(1 for a in assets if a["detachability"] == "low")
    partial_count = sum(1 for a in assets if a["detachability"] == "medium")

    # 生成剥离结论
    if detachable_count > attached_count:
        detach_conclusion = "✅ 你的资产以可剥离型为主，可以尝试产品化和规模化"
        detach_score = 70 + detachable_count * 10
    elif attached_count > detachable_count:
        detach_conclusion = "⚠️ 你的资产以依附型为主，核心价值在你本人，复制难度大"
        detach_score = 30 - attached_count * 10
    else:
        detach_conclusion = "⚡ 你的资产混合存在，需要选择性产品化"
        detach_score = 50

    detach_score = max(10, min(90, detach_score))

    return {
        "assets": assets,
        "summary": "、".join(summary_parts) + f"。剥离可行性评分：{detach_score}分",
        "detach_conclusion": detach_conclusion,
        "detach_score": detach_score,
        "detachable_count": detachable_count,
        "attached_count": attached_count,
        "partial_count": partial_count
    }


def _calculate_replication_potential(asset_analysis: dict, resource_match: dict) -> dict:
    """计算复制可行性"""

    detach_score = asset_analysis['detach_score']
    resource_score = resource_match.get('score', 50)

    # 综合评分
    composite_score = (detach_score * 0.7) + (resource_score * 0.3)

    if composite_score >= 70:
        return {
            "score": int(composite_score),
            "level": "高",
            "reason": "资产可剥离，资源匹配好，适合规模化",
            "replication_path": "知识产品化 + 内容获客 + 自动化交付",
            "main_barrier": "需要系统整理和持续运营"
        }
    elif composite_score >= 50:
        return {
            "score": int(composite_score),
            "level": "中等",
            "reason": "部分资产可剥离，但存在瓶颈",
            "replication_path": "选择性产品化 + 培养团队分担",
            "main_barrier": "核心环节仍需你参与"
        }
    else:
        return {
            "score": int(composite_score),
            "level": "低",
            "reason": "资产依附型强，复制意味着重建",
            "replication_path": "建立标准 + 培训团队 + 品牌化",
            "main_barrier": "你需要从执行者转变为管理者"
        }


def _analyze_local_service_assets(business: str, scope: str) -> dict:
    """分析本地服务型业务的资产"""

    business_lower = business.lower()

    # 分析可剥离性
    asset_analysis = _analyze_local_service_detachability(business_lower, scope)

    return {
        "title": "资产盘点",
        "icon": "📦",
        "items": [
            {"label": "可剥离资产", "value": f"{asset_analysis['detachable_count']}项", "detail": "可以产品化，从你身上剥离"},
            {"label": "依附资产", "value": f"{asset_analysis['attached_count']}项", "detail": "依赖你本人，无法带走"},
            {"label": "脱身可能", "value": asset_analysis['escape_possible'], "detail": asset_analysis['escape_reason']}
        ],
        "asset_analysis": asset_analysis,
        "summary": asset_analysis['summary'],
        "expandable": True,
        "details": {
            "剥离结论": asset_analysis['detach_conclusion'],
            "复制形式": asset_analysis['replication_form'],
            "最大风险": asset_analysis['main_risk']
        }
    }


def _analyze_local_service_detachability(business_lower: str, scope: str) -> dict:
    """分析本地服务型资产的剥离可能性"""

    assets = []
    summary_parts = []

    # 食品加工类
    if any(k in business_lower for k in ["灌香肠", "腊肉", "腊肠", "腌菜", "酱料", "豆腐", "豆芽", "面条", "馒头", "糕点"]):
        # 配方 - 可剥离
        assets.append({
            "name": "配方/工艺",
            "detachability": "high",
            "detach_label": "✅ 可剥离",
            "detach_desc": "配方可以整理成文档，传授给他人",
            "replication_form": "教程、课程、授权使用",
            "can_escape": True,
            "escape_note": "配方传授后可脱身"
        })
        # 口碑 - 不可剥离
        assets.append({
            "name": "本地口碑",
            "detachability": "low",
            "detach_label": "❌ 无法剥离",
            "detach_desc": "口碑是本地的，离开就消失",
            "replication_form": "只能重建，无法转移",
            "can_escape": False,
            "escape_note": "外地客户不认识你"
        })
        # 产品本身 - 可邮寄/可产品化
        assets.append({
            "name": "产品（成品）",
            "detachability": "high",
            "detach_label": "✅ 可剥离",
            "detach_desc": "可以做成预制菜/真空包装，邮寄外地",
            "replication_form": "产品化销售、代理分销",
            "can_escape": True,
            "escape_note": "产品可以离开你销售"
        })
        # 制作经验 - 部分可剥离
        assets.append({
            "name": "制作经验",
            "detachability": "medium",
            "detach_label": "⚡ 部分可剥离",
            "detach_desc": "可以录制教程，但'感觉'难以传递",
            "replication_form": "教程视频、直播教学",
            "can_escape": "partial",
            "escape_note": "教程可脱身，但精髓需要亲自传授"
        })
        summary_parts.append("配方可产品化，但口碑无法复制")

    # 餐饮类
    elif any(k in business_lower for k in ["餐饮", "饭店", "餐厅", "小吃", "早餐"]):
        assets.append({
            "name": "招牌菜/特色",
            "detachability": "medium",
            "detach_label": "⚡ 部分可剥离",
            "detach_desc": "可以做预制菜，但堂食体验无法复制",
            "replication_form": "预制菜、调料包",
            "can_escape": "partial",
            "escape_note": "产品可卖，但堂食体验带不走"
        })
        assets.append({
            "name": "服务流程",
            "detachability": "medium",
            "detach_label": "⚡ 部分可剥离",
            "detach_desc": "可以标准化流程，但人情味难以传递",
            "replication_form": "运营手册、培训课程",
            "can_escape": "partial",
            "escape_note": "流程可复制，但服务温度难复制"
        })
        assets.append({
            "name": "地理位置",
            "detachability": "low",
            "detach_label": "❌ 无法剥离",
            "detach_desc": "位置是固定的，离开这个位置价值归零",
            "replication_form": "无",
            "can_escape": False,
            "escape_note": "换地址等于重新开始"
        })
        summary_parts.append("堂食体验难以复制，产品化是出路")

    # 美发美容类
    elif any(k in business_lower for k in ["美容", "美发", "理发", "化妆"]):
        assets.append({
            "name": "技术/手艺",
            "detachability": "low",
            "detach_label": "❌ 无法剥离",
            "detach_desc": "手艺在你手上，无法转移",
            "replication_form": "培训徒弟",
            "can_escape": False,
            "escape_note": "你不上班就没收入"
        })
        assets.append({
            "name": "客户关系",
            "detachability": "low",
            "detach_label": "❌ 无法剥离",
            "detach_desc": "客户信任你这个人，不是店",
            "replication_form": "建立品牌，但需要时间",
            "can_escape": False,
            "escape_note": "客户只认你，换人就走"
        })
        assets.append({
            "name": "技术教程",
            "detachability": "high",
            "detach_label": "✅ 可剥离",
            "detach_desc": "可以录制教程，教别人技术",
            "replication_form": "线上课程、付费教程",
            "can_escape": True,
            "escape_note": "教程录好后可持续销售"
        })
        summary_parts.append("手艺无法转移，但可以教别人")

    # 维修类
    elif any(k in business_lower for k in ["维修", "电器", "手机", "电脑", "汽车"]):
        assets.append({
            "name": "维修技术",
            "detachability": "medium",
            "detach_label": "⚡ 部分可剥离",
            "detach_desc": "可以整理成教程，培训员工",
            "replication_form": "教程、技术咨询、培训",
            "can_escape": "partial",
            "escape_note": "教给员工后可以脱身一部分"
        })
        assets.append({
            "name": "故障排除经验",
            "detachability": "high",
            "detach_label": "✅ 可剥离",
            "detach_desc": "典型故障可以整理成案例库",
            "replication_form": "教程、维修手册、咨询",
            "can_escape": True,
            "escape_note": "案例库可以脱离你存在"
        })
        assets.append({
            "name": "工具/设备",
            "detachability": "high",
            "detach_label": "✅ 可剥离",
            "detach_desc": "工具设备可以购置，流程可以复制",
            "replication_form": "加盟连锁、技术授权",
            "can_escape": True,
            "escape_note": "设备和流程可以转移"
        })
        summary_parts.append("技术可传授，案例可产品化")

    # 通用本地服务
    else:
        assets.append({
            "name": "服务经验",
            "detachability": "medium",
            "detach_label": "⚡ 部分可剥离",
            "detach_desc": "可以整理成流程和标准",
            "replication_form": "手册、培训、咨询",
            "can_escape": "partial",
            "escape_note": "标准化后可以部分脱身"
        })
        assets.append({
            "name": "本地口碑",
            "detachability": "low",
            "detach_label": "❌ 无法剥离",
            "detach_desc": "口碑是本地积累，离开就消失",
            "replication_form": "只能在新地方重建",
            "can_escape": False,
            "escape_note": "外地没人认识你"
        })
        summary_parts.append("经验可整理，口碑难复制")

    # 计算统计
    detachable_count = sum(1 for a in assets if a["detachability"] == "high")
    attached_count = sum(1 for a in assets if a["detachability"] == "low")
    partial_count = sum(1 for a in assets if a["detachability"] == "medium")

    # 剥离结论
    if detachable_count >= attached_count:
        detach_conclusion = "⚡ 你的资产有可产品化部分，建议聚焦可剥离资产"
        escape_possible = "部分可能"
        escape_reason = "可产品化的部分可以脱身，但核心服务仍需参与"
    else:
        detach_conclusion = "⚠️ 你的核心资产依附于你本人，复制意味着重建"
        escape_possible = "较难"
        escape_reason = "想脱身需要彻底转型为产品/内容提供者"

    # 复制形式
    replicable_assets = [a for a in assets if a["detachability"] != "low"]
    if replicable_assets:
        replication_form = "、".join([a["replication_form"] for a in replicable_assets[:2]])
    else:
        replication_form = "只能重新建立"

    # 最大风险
    attached_assets = [a for a in assets if a["detachability"] == "low"]
    if attached_assets:
        main_risk = f"'{attached_assets[0]['name']}'无法转移，限制了规模化"
    else:
        main_risk = "需要投入时间整理和标准化"

    return {
        "assets": assets,
        "summary": "、".join(summary_parts),
        "detach_conclusion": detach_conclusion,
        "escape_possible": escape_possible,
        "escape_reason": escape_reason,
        "detachable_count": detachable_count,
        "attached_count": attached_count,
        "partial_count": partial_count,
        "replication_form": replication_form,
        "main_risk": main_risk
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


# ==================== 快速诊断接口 ====================

@decision_cost_bp.route('/quick-analyze', methods=['POST'])
def quick_analyze():
    """
    快速诊断分析：基于10道题的答案生成个性化报告

    请求体：
    {
        "answers": {"q1": "skill", "q2": "need_train", ...},
        "score": 450
    }

    返回：
    {
        "success": true,
        "data": {
            "score": 450,
            "percentage": 68,
            "stage": "第二阶段",
            "stage_label": "发展期",
            "stage_emoji": "🚀",
            "value_type": "skill",
            "value_type_label": "卖手艺",
            "asset_type": "skill_only",
            "asset_type_label": "技艺型",
            "leverages": ["content", "passive"],
            "strengths": ["✨ 有专业技能", "💪 亲自服务客户", "🌟 口碑积累中"],
            "weaknesses": ["⚠️ 过度依赖自己", "🚧 缺乏杠杆放大", "📈 收入有天花板"],
            "insights": ["洞察1", "洞察2", "洞察3", "洞察4"],
            "recommendations": [
                {"title": "行动标题", "action": "具体做法", "result": "预期结果"}
            ]
        }
    }
    """
    data = request.get_json() or {}
    answers = data.get('answers', {})
    score = data.get('score', 0)

    # 阶段判断
    if score < 120:
        stage, stage_label, stage_emoji = "第一阶段", "起步期", "🌱"
    elif score < 200:
        stage, stage_label, stage_emoji = "第二阶段", "发展期", "🚀"
    elif score < 280:
        stage, stage_label, stage_emoji = "第三阶段", "成熟期", "⭐"
    else:
        stage, stage_label, stage_emoji = "第四阶段", "突破期", "👑"

    # 推断价值类型
    value_type = answers.get('q1', 'skill')
    value_type_labels = {
        'product': '卖产品',
        'skill': '卖手艺',
        'knowledge': '卖知识',
        'labor': '卖体力'
    }
    value_type_label = value_type_labels.get(value_type, '卖手艺')

    # 推断资产类型
    if answers.get('q3') == 'no_impact':
        asset_type, asset_type_label = 'system', '系统型'
    elif answers.get('q2') == 'only_me':
        asset_type, asset_type_label = 'skill_only', '技艺型'
    else:
        asset_type, asset_type_label = 'knowledge', '知识型'

    # 推断杠杆类型
    leverages = []
    if answers.get('q5') in ['yes_active', 'yes_sometimes']:
        leverages.append('content')
    if answers.get('q4') in ['small_team', 'big_team']:
        leverages.append('team')
    if answers.get('q7') in ['yes', 'some']:
        leverages.append('passive')

    # 尝试调用LLM生成个性化内容
    strengths = []
    weaknesses = []
    insights = []
    recommendations = []

    if LLM_AVAILABLE:
        try:
            llm_result = _llm_quick_analyze(answers, score, stage, value_type_label, asset_type_label, leverages)
            if llm_result:
                strengths = llm_result.get('strengths', [])
                weaknesses = llm_result.get('weaknesses', [])
                insights = llm_result.get('insights', [])
                recommendations = llm_result.get('recommendations', [])
        except Exception as e:
            print(f"LLM快速分析失败: {e}")

    # 如果LLM失败，使用默认内容
    if not strengths:
        strengths = _default_strengths(answers, value_type_label)
    if not weaknesses:
        weaknesses = _default_weaknesses(answers)
    if not insights:
        insights = _default_insights(answers, score)
    if not recommendations:
        recommendations = _default_recommendations(answers, stage)

    return jsonify({
        "success": True,
        "data": {
            "score": score,
            "percentage": min(int(score / 400 * 100), 100),
            "stage": stage,
            "stage_label": stage_label,
            "stage_emoji": stage_emoji,
            "value_type": value_type,
            "value_type_label": value_type_label,
            "asset_type": asset_type,
            "asset_type_label": asset_type_label,
            "leverages": leverages,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "insights": insights,
            "recommendations": recommendations
        }
    })


def _llm_quick_analyze(answers, score, stage, value_type, asset_type, leverages):
    """调用LLM生成快速诊断的个性化内容"""

    answers_text = "\n".join([f"- {k}: {v}" for k, v in answers.items()])
    leverage_text = "、".join(leverages) if leverages else "无"

    # 判断信息差/认知差（统一逻辑）
    q1 = answers.get('q1', '')
    q2 = answers.get('q2', '')
    q5 = answers.get('q5', '')
    has_info_gap = q1 == 'labor' or q5 in ['yes_active', 'yes_sometimes']
    has_cognition_gap = q1 == 'knowledge' or q2 == 'only_me'
    if has_info_gap and has_cognition_gap:
        profit_model = "信息差+认知差双轮驱动"
    elif has_cognition_gap:
        profit_model = "认知差变现"
    else:
        profit_model = "信息差变现"

    prompt = f"""用户完成了快速商业诊断测试，请根据回答生成个性化报告。

用户回答：
{answers_text}

基本信息：
- 总分：{score}分
- 阶段：{stage}
- 价值类型：{value_type}
- 资产类型：{asset_type}
- 已有杠杆：{leverage_text}
- 盈利模式：{profit_model}

请生成JSON格式的报告，包含：

1. strengths: 3条优势，简短有力（格式："✨ 优势描述"）
2. weaknesses: 3条不足（格式："⚠️ 不足描述"）
3. insights: 4条核心洞察，第1条必须分析"{profit_model}"对天花板的影响，其他3条要让用户觉得"说中了"（不超过25字）
4. recommendations: 3条行动建议，每条包含title、action、result

直接返回JSON，不要其他内容。"""

    try:
        result = chat_with_llm(
            prompt=prompt,
            system="你是一个专业的商业模式分析师。你的回答只包含JSON格式。",
            temperature=0.7,
            max_tokens=1500
        )

        # 解析JSON
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', result)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"LLM调用失败: {e}")

    return None


def _default_strengths(answers, value_type):
    """生成默认优势列表"""
    strengths = []

    if answers.get('q2') == 'need_train':
        strengths.append("✨ 有一定的专业能力")
    elif answers.get('q2') == 'only_me':
        strengths.append("✨ 有独特的专业技能")

    if answers.get('q6') == 'referral':
        strengths.append("💪 口碑积累不错")
    elif answers.get('q6') == 'passive':
        strengths.append("💪 有自然流量")

    if answers.get('q10') == 'very_much':
        strengths.append("🌟 有做大事业的意愿")

    if not strengths:
        strengths = ["✨ 有稳定的客户基础", "💪 专业能力在积累", "🌟 发展潜力不错"]

    return strengths[:3]


def _default_weaknesses(answers):
    """生成默认不足列表"""
    weaknesses = []

    if answers.get('q3') == 'stop':
        weaknesses.append("⚠️ 过度依赖自己")
    if answers.get('q4') == 'alone':
        weaknesses.append("🚧 缺乏团队杠杆")
    if answers.get('q5') == 'no':
        weaknesses.append("📈 内容获客未开发")
    if answers.get('q7') == 'no':
        weaknesses.append("💰 缺乏被动收入")
    if answers.get('q8') == 'very_limited':
        weaknesses.append("🏔️ 收入天花板明显")

    if not weaknesses:
        weaknesses = ["⚠️ 收入模式有提升空间", "🚧 杠杆利用不足", "📈 可进一步产品化"]

    return weaknesses[:3]


def _default_insights(answers, score):
    """生成默认洞察"""
    insights = []

    # 信息差 vs 认知差分析（统一逻辑）
    q1 = answers.get('q1', '')
    q2 = answers.get('q2', '')
    q5 = answers.get('q5', '')

    has_info_gap = q1 == 'labor' or q5 in ['yes_active', 'yes_sometimes']
    has_cognition_gap = q1 == 'knowledge' or q2 == 'only_me'

    if has_info_gap and has_cognition_gap:
        insights.append("🔮 你的模式：信息差+认知差双轮驱动，天花板较高")
    elif has_cognition_gap:
        insights.append("🧠 你的模式：认知差变现，天花板取决于你的独特性")
    else:
        insights.append("📡 你的模式：信息差变现，容易被模仿，需快速建立壁垒")

    if answers.get('q3') in ['stop', 'some_impact'] or answers.get('q4') == 'alone':
        insights.append("⏰ 你的技能很值钱，但被困在时间牢笼里")

    if answers.get('q7') == 'no':
        insights.append("💤 收入完全依赖主动工作，缺乏睡后收入")

    if answers.get('q5') == 'no':
        insights.append("📢 还没有利用内容杠杆，获客效率低")

    return insights[:4]


def _default_recommendations(answers, stage):
    """生成默认建议"""
    recommendations = []

    recommendations.append({
        "title": "整理你的方法论",
        "action": "花3天时间，把你的工作流程写成文档",
        "result": "形成可复制的方法"
    })

    if answers.get('q5') == 'no':
        recommendations.append({
            "title": "开始发布内容",
            "action": "每周在小红书发2条作品展示",
            "result": "建立个人品牌，吸引客户"
        })

    if answers.get('q7') == 'no':
        recommendations.append({
            "title": "开发一个低价产品",
            "action": "把你的经验做成教程或模板",
            "result": "边际成本为零的收入"
        })

    if len(recommendations) < 3:
        recommendations.append({
            "title": "建立客户社群",
            "action": "把客户聚集到微信群，定期分享价值",
            "result": "提高复购率和转介绍"
        })

    return recommendations[:3]


# ==================== 深度分析接口 ====================

@decision_cost_bp.route('/deep-analyze/business', methods=['POST'])
def deep_analyze_business():
    """
    深度分析Step1：业务信息分析

    请求体：
    {
        "business_desc": "心理咨询师...",
        "scope": "local",
        "customer_tags": ["职场人士", "宝妈"],
        "quick_answers": {...},
        "quick_score": 250
    }

    返回：
    {
        "success": true,
        "data": {
            "trust_type": "技艺展示型",
            "trust_desc": "...",
            "剥离建议": [...]
        }
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    data = request.get_json() or {}
    business_desc = data.get('business_desc', '').strip()
    scope = data.get('scope', 'local')
    customer_tags = data.get('customer_tags', [])

    if not business_desc:
        return jsonify({"success": False, "message": "请描述你的业务"}), 400

    # 基于业务类型推断信任获取方式
    quick_answers = data.get('quick_answers', {})
    business_type = quick_answers.get('q1', 'skill')

    trust_types = {
        'product': {
            'type': '产品品质型',
            'icon': '📦',
            'desc': '通过产品质量、功能体验、价格优势建立信任。客户信任的是产品本身，而非你这个人。',
            'factors': ['产品评价', '销量数据', '品牌背书', '售后保障'],
            '剥离建议': [
                {'title': '建立可沉淀的信任资产', 'desc': '把产品评价、用户反馈整理成案例库，新客户能看到真实口碑。'},
                {'title': '设计信任传递机制', 'desc': '让购买过的客户成为你的背书者，形成「购买 → 好评 → 转介绍」的自动循环。'}
            ]
        },
        'skill': {
            'type': '技艺展示型',
            'icon': '🛠️',
            'desc': '通过作品集、案例展示、专业资质建立信任。客户信任的是你的专业能力和过往作品。',
            'factors': ['作品集', '成功案例', '客户评价', '专业资质'],
            '剥离建议': [
                {'title': '建立作品资产库', 'desc': '系统整理过往作品，按行业/类型分类，方便新客户快速了解你的能力。'},
                {'title': '案例故事化', 'desc': '把成功案例写成「问题-方案-结果」的故事格式，增强说服力。'}
            ]
        },
        'knowledge': {
            'type': '知识权威型',
            'icon': '📚',
            'desc': '通过专业背景、内容输出、权威背书建立信任。客户信任的是你的知识储备和解读能力。',
            'factors': ['专业背景', '内容输出', '权威推荐', '行业认可'],
            '剥离建议': [
                {'title': '内容资产化', 'desc': '把你输出的内容（文章、视频、直播）整理成体系，建立知识IP。'},
                {'title': '背书矩阵', 'desc': '争取行业KOL推荐、媒体采访、协会认证等多维度背书。'}
            ]
        },
        'labor': {
            'type': '服务口碑型',
            'icon': '💪',
            'desc': '通过服务质量、准时交付、态度细节建立信任。客户信任的是你的可靠性和服务态度。',
            'factors': ['服务质量', '准时交付', '态度细节', '转介绍率'],
            '剥离建议': [
                {'title': '服务SOP化', 'desc': '把服务流程标准化，确保每个客户体验一致，降低对个人的依赖。'},
                {'title': '口碑可视化', 'desc': '收集客户好评、截图、评价，整理成「客户证言库」。'}
            ]
        }
    }

    trust_data = trust_types.get(business_type, trust_types['skill'])

    return jsonify({
        "success": True,
        "data": {
            "trust_type": trust_data['type'],
            "trust_icon": trust_data['icon'],
            "trust_desc": trust_data['desc'],
            "factors": trust_data['factors'],
            "剥离建议": trust_data['剥离建议']
        }
    })


@decision_cost_bp.route('/deep-analyze/bluocean', methods=['POST'])
def deep_analyze_bluocean():
    """
    深度分析Step4：蓝海市场分析

    请求体：
    {
        "business_desc": "...",
        "scope": "local",
        "customer_tags": ["职场人士"],
        "personality_type": "IN",
        "quick_answers": {...}
    }

    返回：
    {
        "success": true,
        "data": {
            "niche_markets": [...],
            "small_markets": [...],
            "differentiators": [...]
        }
    }
    """
    user = get_current_public_user()
    if not user:
        return jsonify({"success": False, "message": "请先登录"}), 401

    data = request.get_json() or {}
    business_desc = data.get('business_desc', '')
    scope = data.get('scope', 'local')
    customer_tags = data.get('customer_tags', [])
    personality_type = data.get('personality_type', 'IN')
    quick_answers = data.get('quick_answers', {})

    business_type = quick_answers.get('q1', 'skill')

    # 基于业务类型生成蓝海数据
    niche_markets = _generate_niche_markets(business_type, customer_tags)
    small_markets = _generate_small_markets(business_type, scope)
    differentiators = _generate_differentiators(business_type, personality_type)

    return jsonify({
        "success": True,
        "data": {
            "niche_markets": niche_markets,
            "small_markets": small_markets,
            "differentiators": differentiators
        }
    })


def _generate_niche_markets(business_type, customer_tags):
    """生成细分人群"""
    base_markets = {
        'skill': [
            {'icon': '🎨', 'name': '设计师群体', 'desc': '平面设计、UI设计、插画师，需要接单指导和能力展示'},
            {'icon': '💻', 'name': '程序员转型', 'desc': '技术人转管理或自由职业的规划需求'},
            {'icon': '📸', 'name': '摄影爱好者', 'desc': '想把爱好变成副业或主业的人群'}
        ],
        'knowledge': [
            {'icon': '📖', 'name': '考证人群', 'desc': '需要通过考试的上班族，时间紧迫，需要高效学习法'},
            {'icon': '💪', 'name': '自律困难户', 'desc': '想学习但缺乏自制力，需要监督和陪伴'},
            {'icon': '🏢', 'name': '企业内训', 'desc': '中小企业员工的技能提升需求'}
        ],
        'product': [
            {'icon': '🛒', 'name': '电商创业者', 'desc': '想开网店但缺乏选品和运营经验的小白'},
            {'icon': '🏪', 'name': '实体店主', 'desc': '线下店铺想拓展线上渠道的经营者'},
            {'icon': '📱', 'name': '微商转型', 'desc': '想从朋友圈微商转型到正规电商的群体'}
        ],
        'labor': [
            {'icon': '🏠', 'name': '家政创业者', 'desc': '想从家政阿姨转型为管理者的群体'},
            {'icon': '🚗', 'name': '司机转型', 'desc': '滴滴/货运司机想拓展副业或转型的需求'},
            {'icon': '🍜', 'name': '小吃摊主', 'desc': '想把手艺变成正规餐饮店的小创业者'}
        ]
    }

    return base_markets.get(business_type, base_markets['skill'])


def _generate_small_markets(business_type, scope):
    """生成小众需求市场"""
    markets = [
        {
            'icon': '📱',
            'name': '线上轻咨询',
            'desc': f'30分钟语音/视频咨询{"全国" if scope != "local" else "本地"}可做，价格适中，适合初次体验'
        },
        {
            'icon': '📦',
            'name': '标准化产品包',
            'desc': '把专业知识打包成模板/清单/课程，边际成本为零，可批量售卖'
        },
        {
            'icon': '👥',
            'name': '小班训练营',
            'desc': '8-15人小班制，深度陪伴式学习，客单价可提高3-5倍'
        }
    ]

    # 根据scope调整
    if scope == 'global':
        markets.append({
            'icon': '🌐',
            'name': '海外华人市场',
            'desc': '服务海外华人群体，时差和语言障碍反而成为壁垒'
        })

    return markets


def _generate_differentiators(business_type, personality_type):
    """生成差异化策略"""
    base_diffs = [
        {
            'icon': '🎨',
            'name': '差异化定位',
            'desc': '聚焦细分人群，打造专属标签，如「程序员创业顾问」「宝妈理财师」'
        },
        {
            'icon': '📚',
            'name': '内容IP化',
            'desc': '持续输出专业知识，建立行业影响力，实现自动获客'
        },
        {
            'icon': '🔄',
            'name': '产品矩阵',
            'desc': '低价引流产品 + 中价服务 + 高价私教，阶梯变现，最大化客户价值'
        }
    ]

    # 根据性格类型调整建议
    if personality_type == 'IN':
        base_diffs.append({
            'icon': '✍️',
            'name': '深度内容型',
            'desc': '适合做长图文、深度文章、系列课程，用内容深度建立壁垒'
        })
    elif personality_type == 'EN':
        base_diffs.append({
            'icon': '🎬',
            'name': '视频直播型',
            'desc': '适合做短视频、直播，用个人魅力和感染力吸引粉丝'
        })
    elif personality_type == 'IS':
        base_diffs.append({
            'icon': '📋',
            'name': '案例作品型',
            'desc': '适合积累大量成功案例，用作品说话，证明专业能力'
        })
    else:
        base_diffs.append({
            'icon': '💡',
            'name': '创意差异化',
            'desc': '适合开发独特的产品形式或服务方式，用创新吸引眼球'
        })

    return base_diffs
