# -*- coding: utf-8 -*-
"""
知识库内容分析 API
用于分析抖音链接并提取可入库的规则
"""

import os
import re
import json
import logging
from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

knowledge_api = Blueprint('knowledge_api', __name__, url_prefix='/api/knowledge')

# 导入电影台词数据
try:
    from data.movie_quotes import get_daily_quote, get_all_quotes
except ImportError:
    # 如果导入失败，定义空函数
    def get_daily_quote():
        return {
            "quote": "Do not go gentle into that good night.",
            "quote_cn": "不要温顺地走进那个良夜。",
            "movie": "星际穿越",
            "poster_url": ""
        }
    def get_all_quotes():
        return []


@knowledge_api.route('/daily-quote', methods=['GET'])
def api_daily_quote():
    """获取每日电影台词"""
    quote = get_daily_quote()
    return jsonify({
        "code": 200,
        "data": quote
    })


@knowledge_api.route('/all-quotes', methods=['GET'])
def api_all_quotes():
    """获取所有电影台词"""
    quotes = get_all_quotes()
    return jsonify({
        "code": 200,
        "data": {"quotes": quotes, "total": len(quotes)}
    })


def parse_llm_json(result_text):
    """解析 LLM 返回的 JSON，支持多种格式并自动修复常见问题"""
    # 1. 尝试从 markdown 代码块中提取
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = result_text

    # 2. 尝试直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 3. 修复常见 JSON 错误后重试
    fixed = json_str

    # 移除行尾的逗号（如 "...", } 或 "...", ]）
    fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)

    # 移除单引号改为双引号（处理不规范的 JSON）
    fixed = re.sub(r"'([^']*)'", r'"\1"', fixed)

    # 移除多余的反引号
    fixed = fixed.strip()
    if fixed.startswith('`'):
        fixed = re.sub(r'^`+', '', fixed)
    if fixed.endswith('`'):
        fixed = re.sub(r'`+$', '', fixed)

    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败，已尝试修复仍失败: {e}, 内容: {result_text[:300]}")
        raise


def get_llm_service():
    """获取 LLM 服务（支持 Ollama 本地大模型）"""
    try:
        from services.llm import get_llm_service as _get_llm
        return _get_llm()
    except Exception as e:
        logger.error(f"获取 LLM 服务失败: {e}")
        return None


def load_knowledge_base_rules():
    """加载现有的知识库规则"""
    rules_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'skills', 'knowledge-base', '规则'
    )
    
    rules = {}
    
    rule_files = {
        'keywords': '关键词库_规则模板.md',
        'topic': '选题库_规则模板.md',
        'template': '内容模板_规则模板.md',
        'operation': '运营规划_规则模板.md',
        'market': '市场分析_规则模板.md'
    }
    
    for category, filename in rule_files.items():
        filepath = os.path.join(rules_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                rules[category] = f.read()
    
    return rules


def build_analysis_prompt(url, content_type, note):
    """构建分析提示词"""

    existing_rules = load_knowledge_base_rules()

    prompt = f"""你是一个资深的短视频内容拆解专家。请从专业运营角度完整拆解以下抖音内容，提取可复用的爆款逻辑和规则。

## 待分析内容
- 链接：{url}
- 内容类型：{content_type}
- 补充说明：{note}

---

## 一、标题结构分析（为什么这么写）

### 1.1 标题关键词组合
分析标题用了哪些关键词组合：
- 流量关键词（吸引眼球的词）
- 核心业务关键词（产品/服务词）
- 科普/行业关键词（专业词）
- 数字（增强可信度）
- 情绪词（引发共鸣）

**分析格式**：
- 标题关键词组合结构：[具体分析]
- 关键词类型标注：哪些是流量词、业务词、科普词

### 1.2 标题为什么有效
- 击中用户什么需求？
- 和竞品比有什么独特性？

---

## 二、选题分析

### 2.1 选题方向
- 这个选题属于什么方向？

### 2.2 目标人群（非常重要）
分析内容针对的目标人群：
- 细分场景人群：[具体人群描述]
- 长尾需求人群：[具体需求]
- 选题切中客户什么：
  - 痛点（什么痛苦/困扰）
  - 情绪（什么情感需求）
  - 功能价值（什么实用价值）
  - 独特性（和市面上其他方案比有什么不同）

---

## 三、内容结构拆解

### 3.1 开头钩子（前3秒）
- 用了什么钩子类型？
- 开头画面有什么特点？

### 3.2 视频内容节奏
- 整体节奏：快/中/慢/张弛有度
- 内容是否一直拽着观众走？

### 3.3 情绪变化曲线
分析情绪如何起伏：
- 开头什么情绪？
- 中间情绪如何变化？
- 结尾什么情绪收尾？
- 整体是否能拽着观众走？

### 3.4 内容核心价值
- 内容提供了什么价值？
- 对用户有什么帮助？

### 3.5 脚本模型
分析用的什么脚本模型：
- 晒过程（展示过程）
- 讲故事（叙述故事）
- 说观点（表达观点）
- 教知识（知识分享）
- 说产品（产品介绍）
- 演段子（娱乐表演）
- 其他：[具体类型]

---

## 四、用户心理分析

### 4.1 利用了什么心理
分析内容利用了观众什么心理：
- 恐惧（害怕失去/担忧）
- 追求（想要获得）
- 规避（想避免问题）
- 损失厌恶（不想亏）
- 从众心理（大家都在看）
- 其他：[具体心理]

### 4.2 为什么招人喜欢
- 是因为有用？
- 是因为有趣？
- 是因为能引起共鸣？
- 还是都有？

---

## 五、商业目的分析

### 5.1 商业目的
- 这个内容目的是什么？
- 品牌宣传/引流获客/产品销售/IP打造？

### 5.2 细分市场
- 内容主题切的是什么细分市场？
- 什么细分场景？

### 5.3 爆款元素
- 选题结合了什么爆款元素？
- 为什么能火？

---

## 六、人物设计分析

### 6.1 出镜情况
- 是否有人物出镜？
- 出镜人物角色？

### 6.2 人物关系
- 人物之间什么关系？

### 6.3 冲突设计（如果是故事类）
- 有什么冲突/矛盾？
- 冲突如何推进？

---

## 七、内容形式分析

### 7.1 图文类内容
- 文字使用原则：
  - 何时尽量少文字？
  - 何时多用数字佐证？
  - 何时讲具体案例？
  - 何时说方言？
- 构图分析：[图文排版特点]

### 7.2 短视频类内容
- 拍摄角度：[拍摄手法]
- 背景音乐选择：[BGM特点]
- 画面与内容关联度

---

## 八、标签与SEO分析

### 8.1 抖音5个标签组合策略
分析内容用了哪些标签组合：
- 区域+业务关键词：[示例]
- 蓝海长尾词：[示例]
- 区域+品牌词：[示例]
- 核心业务关键词：[示例]
- 产品关键词：[示例]
- 场景词（客户需要解决方案的场景）：[示例]

### 8.2 关键词埋入策略
分析关键词如何埋入（便于AI/SEO搜索收录）：
- 标题关键词
- 开头关键词
- 内容关键词
- 标签关键词

---

## 九、爆款原因深度分析

### 9.1 为什么这么多人喜欢
- 内容本身好在哪里？
- 击中什么需求？

### 9.2 为什么互动会好
- 引发评论的点是什么？
- 让人想留言的原因？

### 9.3 为什么愿意分享
- 什么让人想转发？
- 社交货币是什么？

---

## 十、互动数据分析

### 10.1 互动数据概况
- 点赞、评论、收藏、转发数量
- 数据反映出什么问题？

### 10.2 数据分析
- 点赞多评论少：说明什么？
- 收藏多点赞少：说明什么？
- 转发多说明什么？

---

## 输出格式要求

请严格按照以下JSON格式输出，确保每个字段都有值：

```json
{{
    "title": "内容标题",
    "author": "作者/账号名",
    "platform": "发布平台",
    "content_type": "内容类型(video/image/text)",
    "duration": "时长",

    "title_analysis": {{
        "structure": "标题结构分析（关键词组合）",
        "keyword_types": {{
            "flow_keywords": "流量关键词",
            "business_keywords": "核心业务关键词",
            "knowledge_keywords": "科普/行业关键词",
            "numbers": "数字",
            "emotion_words": "情绪词"
        }},
        "why_effective": "标题为什么有效"
    }},

    "topic_analysis": {{
        "direction": "选题方向",
        "target_audience": {{
            "scene_crowd": "细分场景人群",
            "demand_crowd": "长尾需求人群"
        }},
        "hit_what": {{
            "pain_point": "痛点（用户痛苦/困扰）",
            "emotion": "情绪（情感需求）",
            "functional_value": "功能价值（实用价值）",
            "uniqueness": "独特性（与市面上其他方案的差异）"
        }}
    }},

    "content_structure": {{
        "hook": "开头钩子类型",
        "hook_description": "钩子具体表现",
        "opening_shot": "开头画面特点",
        "rhythm": "内容节奏（快/中/慢/张弛有度）",
        "rhythm_description": "节奏详细描述",
        "emotion_curve": {{
            "type": "情绪曲线类型",
            "can_drag_audience": "是否能拽着观众走",
            "phases": [
                {{"position": "位置", "emotion": "情绪", "description": "描述"}}
            ]
        }},
        "core_value": "内容核心价值",
        "script_model": "脚本模型类型（晒过程/讲故事/说观点/教知识/说产品/演段子）"
    }},

    "psychology_analysis": {{
        "psychology_used": ["利用的心理：恐惧/追求/规避/损失厌恶/从众等"],
        "why_appealing": {{
            "useful": "有用（是/否/部分）",
            "interesting": "有趣（是/否/部分）",
            "resonance": "共鸣（是/否/部分）"
        }}
    }},

    "commercial_purpose": {{
        "purpose": "商业目的（品牌宣传/引流获客/产品销售/IP打造）",
        "target_market": "目标细分市场",
        "target_scene": "目标细分场景",
        "viral_elements": "结合的爆款元素"
    }},

    "character_design": {{
        "has_character": "是否有人物出镜",
        "characters": ["出镜人物角色"],
        "relationships": "人物关系",
        "conflict": "冲突设计（如果有）"
    }},

    "content_form": {{
        "form_type": "内容形式（图文字/短视频）",
        "text_principles": {{
            "less_text_when": "何时尽量少文字",
            "more_numbers_when": "何时多用数字",
            "case_when": "何时讲具体案例",
            "dialect_when": "何时说方言"
        }},
        "visual_analysis": {{
            "composition": "构图分析",
            "shooting_angle": "拍摄角度（短视频）",
            "bgm": "背景音乐选择",
            "content_visual_relationship": "画面与内容关联度"
        }}
    }},

    "tag_strategy": {{
        "region_business": "区域+业务关键词",
        "blue_ocean": "蓝海长尾词",
        "region_brand": "区域+品牌词",
        "core_business": "核心业务关键词",
        "product_keywords": "产品关键词",
        "scene_words": "场景词",
        "keyword_placement": "关键词埋入位置"
    }},

    "why_popular": {{
        "why_liked": "为什么多人喜欢",
        "why_good_interaction": "为什么互动好",
        "why_share": "为什么愿意分享"
    }},

    "interaction_analysis": {{
        "likes": "点赞数",
        "comments": "评论数",
        "favorites": "收藏数",
        "shares": "转发数",
        "analysis": "数据分析结论"
    }},

    "dimensions": [
        {{
            "name": "维度名称",
            "analysis": "分析内容",
            "why": "为什么这样设计",
            "score": 评分(1-10)
        }}
    ],

    "rules": [
        {{
            "category": "规则分类(keywords/topic/template/operation/market)",
            "title": "规则标题",
            "source_dimension": "来自哪个分析维度",
            "content_type": "适用内容类型",
            "description": "规则描述",
            "why_effective": "为什么有效",
            "scenes": "适用场景",
            "is_good": true/false,
            "recommendation": "强烈推荐/推荐/不推荐/待观察",
            "reasoning": "评价理由和依据",
            "score": 评分(1-10)
        }}
    ]
}}
```

请先理解这个内容，然后进行全面深度分析。"""

    return prompt


@knowledge_api.route('/analyze', methods=['POST'])
@login_required
def analyze_content():
    """分析内容接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        content_type = data.get('content_type', 'auto')
        note = data.get('note', '').strip()
        
        if not url:
            return jsonify({'code': 400, 'message': '请输入内容链接'})
        
        # 获取 LLM 服务（支持 Ollama 本地大模型）
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})
        
        # 构建提示词
        prompt = build_analysis_prompt(url, content_type, note)
        
        # 调用 LLM
        logger.info(f"[knowledge_analyze] 开始分析: {url}")
        
        messages = [
            {"role": "system", "content": "你是一个专业的内容分析专家，擅长分析抖音等短视频平台的爆款内容。请严格按照JSON格式输出分析结果。"},
            {"role": "user", "content": prompt}
        ]
        
        result_text = llm_service.chat(messages, temperature=0.7, max_tokens=4000)
        
        if not result_text:
            return jsonify({'code': 500, 'message': 'LLM 调用失败，请检查模型是否正常运行'})
        
        # 提取 JSON
        try:
            result_json = parse_llm_json(result_text)
            
            logger.info(f"[knowledge_analyze] 分析完成，找到 {len(result_json.get('rules', []))} 条规则")
            
            return jsonify({
                'code': 200,
                'message': '分析成功',
                'data': result_json
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 内容: {result_text[:500]}")
            return jsonify({
                'code': 500,
                'message': '分析结果解析失败，请重试'
            })
    
    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        })


@knowledge_api.route('/rules/import', methods=['POST'])
@login_required
def import_rules():
    """规则入库接口"""
    try:
        data = request.get_json()
        rules = data.get('rules', [])
        
        if not rules:
            return jsonify({'code': 400, 'message': '请选择要入库的规则'})
        
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'skills', 'knowledge-base', '规则'
        )
        
        if not os.path.exists(rules_dir):
            os.makedirs(rules_dir)
        
        # 按分类组织规则
        rules_by_category = {}
        for rule in rules:
            category = rule.get('category', 'keywords')
            if category not in rules_by_category:
                rules_by_category[category] = []
            rules_by_category[category].append(rule)
        
        import_results = []
        
        # 更新各分类规则文件
        for category, category_rules in rules_by_category.items():
            rule_files = {
                'keywords': '关键词库_规则模板.md',
                'topic': '选题库_规则模板.md',
                'template': '内容模板_规则模板.md',
                'operation': '运营规划_规则模板.md',
                'market': '市场分析_规则模板.md'
            }
            
            filename = rule_files.get(category)
            if not filename:
                continue
            
            filepath = os.path.join(rules_dir, filename)
            
            # 读取现有内容
            existing_content = ""
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # 添加新规则
            category_names = {
                'keywords': '关键词库',
                'topic': '选题库',
                'template': '内容模板',
                'operation': '运营规划',
                'market': '市场分析'
            }
            
            new_rules_section = f"\n\n## 六、新入库规则（{len(category_rules)}条）\n\n"
            
            for i, rule in enumerate(category_rules, 1):
                new_rules_section += f"### {i}. {rule.get('title', '未命名规则')}\n\n"
                new_rules_section += f"- **来源维度**: {rule.get('source', '未知')}\n"
                new_rules_section += f"- **规则内容**: {rule.get('description', '')}\n"
                new_rules_section += f"- **适用场景**: {rule.get('scenes', '通用')}\n\n"
            
            # 在文件末尾添加更新时间
            import_time = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_rules_section += f"\n---\n*入库时间: {import_time}*"
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(existing_content + new_rules_section)
            
            import_results.append(f"{category_names.get(category, category)}: {len(category_rules)}条")

        return jsonify({
            'code': 200,
            'message': '规则入库成功',
            'data': {
                'count': len(rules),
                'details': import_results
            }
        })

    except Exception as e:
        logger.error(f"规则入库失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'入库失败: {str(e)}'
        })


@knowledge_api.route('/rules', methods=['GET'])
@login_required
def get_rules():
    """获取已入库的规则列表"""
    try:
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'skills', 'knowledge-base', '规则'
        )

        if not os.path.exists(rules_dir):
            return jsonify({
                'code': 200,
                'message': '暂无规则',
                'data': {
                    'rules': [],
                    'categories': []
                }
            })

        rule_files = {
            'keywords': '关键词库_规则模板.md',
            'topic': '选题库_规则模板.md',
            'template': '内容模板_规则模板.md',
            'operation': '运营规划_规则模板.md',
            'market': '市场分析_规则模板.md'
        }

        category_names = {
            'keywords': '关键词库',
            'topic': '选题库',
            'template': '内容模板',
            'operation': '运营规划',
            'market': '市场分析'
        }

        all_rules = []
        categories = []

        for category, filename in rule_files.items():
            filepath = os.path.join(rules_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 解析规则（从 ## 或 ### 标题中提取）
                rules = []
                sections = re.split(r'^#{2,3}\s+', content, flags=re.MULTILINE)
                for i, section in enumerate(sections[1:], 1):  # 跳过第一个空部分
                    lines = section.split('\n')
                    title = lines[0].strip() if lines else ''
                    body = '\n'.join(lines[1:]).strip()
                    if title:
                        rules.append({
                            'id': f"{category}_{i}",
                            'category': category,
                            'category_name': category_names.get(category, category),
                            'title': title,
                            'content': body[:500] + '...' if len(body) > 500 else body,
                            'full_content': body
                        })

                if rules:
                    categories.append({
                        'id': category,
                        'name': category_names.get(category, category),
                        'count': len(rules)
                    })
                    all_rules.extend(rules)

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'rules': all_rules,
                'categories': categories,
                'total': len(all_rules)
            }
        })

    except Exception as e:
        logger.error(f"获取规则失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        })


@knowledge_api.route('/rules/<category>', methods=['GET'])
@login_required
def get_rules_by_category(category):
    """按分类获取规则"""
    try:
        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'skills', 'knowledge-base', '规则'
        )

        rule_files = {
            'keywords': '关键词库_规则模板.md',
            'topic': '选题库_规则模板.md',
            'template': '内容模板_规则模板.md',
            'operation': '运营规划_规则模板.md',
            'market': '市场分析_规则模板.md'
        }

        category_names = {
            'keywords': '关键词库',
            'topic': '选题库',
            'template': '内容模板',
            'operation': '运营规划',
            'market': '市场分析'
        }

        filename = rule_files.get(category)
        if not filename:
            return jsonify({'code': 400, 'message': '无效的分类'})

        filepath = os.path.join(rules_dir, filename)
        if not os.path.exists(filepath):
            return jsonify({
                'code': 200,
                'message': '该分类暂无规则',
                'data': {
                    'category': category,
                    'category_name': category_names.get(category, category),
                    'rules': []
                }
            })

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析规则
        rules = []
        sections = re.split(r'^#{2,3}\s+', content, flags=re.MULTILINE)
        for i, section in enumerate(sections[1:], 1):
            lines = section.split('\n')
            title = lines[0].strip() if lines else ''
            body = '\n'.join(lines[1:]).strip()
            if title:
                rules.append({
                    'id': f"{category}_{i}",
                    'title': title,
                    'content': body
                })

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'category': category,
                'category_name': category_names.get(category, category),
                'rules': rules,
                'total': len(rules)
            }
        })

    except Exception as e:
        logger.error(f"获取规则失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        })


def register_routes(app):
    """注册路由"""
    app.register_blueprint(knowledge_api)


# ========== 账号分析相关接口 ==========

def build_account_analysis_prompt(url, note):
    """构建账号分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请从专业运营角度完整分析以下抖音账号，提取可复用的账号运营策略和规则。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 一、商业定位分析（最重要）

### 1.1 变现方式
分析账号的变现方式是什么：
- 电商卖货（短视频带货/直播带货/橱窗）
- 本地服务引流（引流到店/引流到微信）
- 培训（线上卖课/线下培训/咨询）
- 其他变现方式

### 1.2 卖货策略（如果是电商）
- 单品策略：只卖一个产品
- 赛道策略：聚焦某个细分领域
- 全品策略：什么都卖（分析为什么做或不做全品）

### 1.3 变现链路
- 变现链路是否清晰？
- 内容到成交的路径是什么？

---

## 二、账号基础信息设计分析

### 2.1 昵称设计
分析账号昵称是怎么设计的：
- 怎么好记？
- 怎么和核心业务关联？
- 体现了什么巧思？
- 是否占领了用户心智？

### 2.2 简介设计
分析账号简介是怎么写的：
- 吸引目标用户的点是什么？
- 传递了什么价值？
- 引导关注的话术？

### 2.3 头像设计
分析头像为什么这样设计：
- 是否符合账号定位？
- 是否便于识别？

---

## 三、内容结构分析

### 3.1 人物出镜分析
- 人物出镜的视频占比多少？
- 不出镜的视频占比多少？
- **为什么需要人物出镜**（如果出镜多）？
- **为什么没有人物出镜**（如果不出镜多）？

### 3.2 主题占比分析
分析各种主题的内容占比：
- 与商业变现直接关联的内容占比
- 日常运营内容占比
- 各类主题的分布比例

### 3.3 内容与变现关联
- 内容是否围绕变现目的设计？
- 引流内容 vs 转化内容的比例？

---

## 四、目标客户画像

### 4.1 客户特征
详细描述目标客户：
- 年龄阶段
- 性别比例
- 职业/身份
- 消费能力
- 地域分布

### 4.2 客户需求
- 客户有什么痛点？
- 客户需要什么解决方案？

---

## 五、关键词布局分析

### 5.1 前50关键词
分析账号的关键词布局：
- 核心业务关键词
- 产品关键词
- 场景关键词
- 人群关键词
- 地域关键词
- 其他重要关键词

### 5.2 关键词分布位置
- 昵称中的关键词
- 简介中的关键词
- 话题标签中的关键词
- 视频标题中的关键词

---

## 六、视频内容分析

### 6.1 视频类型分布
分析账号发布了哪些类型的视频：
- 知识分享类
- 干货教程类
- 产品展示类
- 客户见证类
- 剧情类
- 情感治愈类
- 种草安利类
- 其他

### 6.2 内容风格
- 整体内容调性（专业/亲和/幽默/严肃）
- 拍摄风格
- 剪辑风格
- 配音/配乐风格

---

## 七、账号定位分析

### 7.1 账号类型
- 单业务账号还是多业务账号
- 主要业务和次要业务

### 7.2 人设打造
- 是否有IP人设
- 人设与业务的关联

---

## 输出格式要求

请严格按照以下JSON格式输出，确保每个字段都有值：

```json
{{
    "account_name": "账号名称",
    "account_position": "账号定位描述（20字以内）",

    "commercial_positioning": {{
        "monetization_method": "变现方式（电商卖货/本地服务引流/培训/线上卖课/其他）",
        "sales_strategy": "卖货策略（单品策略/赛道策略/全品策略/不适用）",
        "monetization_chain": "变现链路描述",
        "chain_clarity": "变现链路是否清晰（清晰/一般/不清晰）"
    }},

    "nickname_design": {{
        "design": "昵称设计分析",
        "memory_point": "好记的点",
        "business_association": "与核心业务的关联",
        "user_mind_capture": "如何占领用户心智"
    }},

    "bio_design": {{
        "design": "简介设计分析",
        "attraction_point": "吸引目标用户的点",
        "value_message": "传递的价值信息",
        "guidance": "引导关注的话术"
    }},

    "avatar_design": {{
        "design": "头像设计分析",
        "position_match": "是否符合账号定位",
        "recognition": "是否便于识别"
    }},

    "content_analysis": {{
        "character_appearance": {{
            "percentage": "人物出镜视频占比",
            "no_character_percentage": "不出镜视频占比",
            "why_has_character": "为什么需要人物出镜（如果出镜多）",
            "why_no_character": "为什么没有人物出镜（如果不出镜多）"
        }},
        "topic_distribution": {{
            "commercial_related": "与商业变现直接关联的内容占比",
            "daily_operation": "日常运营内容占比",
            "topic_details": "各类主题分布详情"
        }},
        "content_monetization_relation": "内容与变现的关联度"
    }},

    "target_customer": {{
        "age_range": "年龄阶段",
        "gender_ratio": "性别比例",
        "occupation": "职业/身份",
        "consumption_level": "消费能力",
        "region": "地域分布",
        "pain_points": "客户痛点",
        "needs": "客户需要的解决方案"
    }},

    "keyword_layout": {{
        "top_50_keywords": ["关键词1", "关键词2", "关键词3"...] ,
        "keyword_distribution": {{
            "in_nickname": "昵称中的关键词",
            "in_bio": "简介中的关键词",
            "in_tags": "话题标签中的关键词",
            "in_titles": "视频标题中的关键词"
        }}
    }},

    "video_types": {{
        "types": ["视频类型1", "视频类型2"...],
        "distribution": "视频类型分布"
    }},

    "content_style": {{
        "tone": "整体内容调性",
        "shooting_style": "拍摄风格",
        "editing_style": "剪辑风格",
        "audio_style": "配音/配乐风格"
    }},

    "account_type": {{
        "type": "单业务/多业务",
        "main_business": "主要业务",
        "secondary_business": "次要业务（如果有）"
    }},

    "persona": {{
        "has_ip": "是否有IP人设",
        "ip_description": "人设描述",
        "ip_business_relation": "人设与业务的关联"
    }},

    "rules": [
        {{
            "category": "operation/market 之一",
            "title": "规则标题",
            "source_dimension": "来自哪个分析维度",
            "description": "规则详细内容",
            "why_effective": "为什么有效",
            "scenes": "适用场景",
            "is_good": true/false,
            "recommendation": "强烈推荐/推荐/不推荐/待观察",
            "reasoning": "评价理由和依据",
            "score": 评分(1-10)
        }}
    ]
}}
```

请先完整了解这个账号的整体情况，然后进行全面深度分析。"""

    return prompt


@knowledge_api.route('/account/analyze', methods=['POST'])
@login_required
def analyze_account():
    """账号分析接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        note = data.get('note', '').strip()

        if not url:
            return jsonify({'code': 400, 'message': '请输入账号主页链接'})

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        # 构建提示词
        prompt = build_account_analysis_prompt(url, note)

        logger.info(f"[account_analyze] 开始分析: {url}")

        messages = [
            {"role": "system", "content": "你是一个专业的账号分析专家，擅长分析抖音账号的整体定位和运营策略。请严格按照JSON格式输出分析结果。"},
            {"role": "user", "content": prompt}
        ]

        result_text = llm_service.chat(messages, temperature=0.7, max_tokens=4000)

        if not result_text:
            return jsonify({'code': 500, 'message': 'LLM 调用失败，请检查模型是否正常运行'})

        # 提取 JSON
        try:
            result_json = parse_llm_json(result_text)

            logger.info(f"[account_analyze] 分析完成，找到 {len(result_json.get('rules', []))} 条规则")

            return jsonify({
                'code': 200,
                'message': '分析成功',
                'data': result_json
            })

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 内容: {result_text[:500]}")
            return jsonify({
                'code': 500,
                'message': '分析结果解析失败，请重试'
            })

    except Exception as e:
        logger.error(f"账号分析失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        })


# ========== 电子书分析相关接口 ==========

import uuid
from datetime import datetime

# 存储上传的电子书信息（生产环境应存入数据库）
ebook_storage = {}


def extract_pdf_text(file_path):
    """从 PDF 提取文本"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        logger.error(f"PDF 文本提取失败: {e}")
        return None


def extract_epub_text(file_path):
    """从 EPUB 提取文本"""
    try:
        import ebooklib.epub as epub
        book = epub.read_epub(file_path)
        text = ""
        for item in book.get_items():
            if item.get_type() == 9:  # DOC_TYPE.HTML
                content = item.get_content().decode('utf-8')
                import re
                clean = re.sub(r'<[^>]+>', '', content)
                text += clean + "\n"
        return text
    except Exception as e:
        logger.error(f"EPUB 文本提取失败: {e}")
        return None


@knowledge_api.route('/ebook/upload', methods=['POST'])
@login_required
def upload_ebook():
    """电子书上传统一接口"""
    try:
        if 'files' not in request.files:
            return jsonify({'code': 400, 'message': '请上传文件'})

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'code': 400, 'message': '请上传文件'})

        # 创建上传目录
        upload_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'uploads', 'ebooks'
        )
        os.makedirs(upload_dir, exist_ok=True)

        uploaded_files = []

        for file in files:
            if file.filename == '':
                continue

            ext = file.filename.split('.')[-1].lower()
            if ext not in ['pdf', 'epub']:
                continue

            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            filename = f"{file_id}_{file.filename}"
            filepath = os.path.join(upload_dir, filename)

            # 保存文件
            file.save(filepath)

            # 提取文本
            if ext == 'pdf':
                text = extract_pdf_text(filepath)
            else:
                text = extract_epub_text(filepath)

            if not text:
                logger.warning(f"文本提取失败: {file.filename}")
                text = ""

            # 存储信息
            ebook_storage[file_id] = {
                'id': file_id,
                'filename': file.filename,
                'filepath': filepath,
                'text': text,
                'size': os.path.getsize(filepath),
                'type': ext,
                'upload_time': datetime.now().isoformat()
            }

            uploaded_files.append({
                'id': file_id,
                'filename': file.filename,
                'size': os.path.getsize(filepath),
                'type': ext
            })

        if not uploaded_files:
            return jsonify({'code': 400, 'message': '未找到有效的 PDF 或 EPUB 文件'})

        return jsonify({
            'code': 200,
            'message': f'成功上传 {len(uploaded_files)} 个文件',
            'data': {
                'files': uploaded_files
            }
        })

    except Exception as e:
        logger.error(f"上传失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'上传失败: {str(e)}'})


@knowledge_api.route('/ebooks', methods=['GET'])
@login_required
def get_ebooks():
    """获取已上传的电子书列表"""
    try:
        ebooks = []
        for ebook in ebook_storage.values():
            ebooks.append({
                'id': ebook['id'],
                'filename': ebook['filename'],
                'size': ebook['size'],
                'type': ebook['type'],
                'upload_time': ebook['upload_time']
            })

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {'ebooks': ebooks}
        })

    except Exception as e:
        logger.error(f"获取列表失败: {e}")
        return jsonify({'code': 500, 'message': str(e)})


@knowledge_api.route('/ebook/<file_id>', methods=['DELETE'])
@login_required
def delete_ebook(file_id):
    """删除电子书"""
    try:
        ebook = ebook_storage.get(file_id)
        if not ebook:
            return jsonify({'code': 404, 'message': '文件不存在'})

        # 删除文件
        if os.path.exists(ebook['filepath']):
            os.remove(ebook['filepath'])

        # 移除存储
        del ebook_storage[file_id]

        return jsonify({
            'code': 200,
            'message': '删除成功'
        })

    except Exception as e:
        logger.error(f"删除失败: {e}")
        return jsonify({'code': 500, 'message': str(e)})


def build_ebook_analysis_prompt(ebook_text, filename):
    """构建电子书分析提示词"""
    prompt = f"""你是一个知识管理专家。请分析以下电子书内容，提取可以应用到抖音内容创作的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则（每个分类都要尽量提取）：

### 一、关键词库
- 标题关键词选择逻辑
- 简介关键词布局
- 评论区关键词引导
- 标签关键词优化

### 二、选题库
- 爆款选题方向
- 选题角度和切入点
- 选题时效性把握
- 选题与热点结合

### 三、内容模板
- 开头钩子设计
- 内容结构模式
- 结尾引导设计
- 情绪调动技巧

### 四、运营规划（重点提取）
- **账号起名** - 如何起一个好记、有辨识度的名字
- **账号简介** - 简介怎么写吸引人
- **头像设计** - 头像选择建议
- **主页装修** - 背景图、置顶视频等
- **发布时机** - 什么时候发布效果最好
- **互动策略** - 评论区互动、回复技巧
- **粉丝运营** - 粉丝群运营、粉丝粘性提升
- **数据复盘** - 如何分析数据优化内容

### 五、市场分析（重点提取）
- **市场分析报告** - 行业现状和趋势
- **目标用户画像** - 目标受众特征分析
- **竞品分析** - 竞争对手研究
- **市场趋势** - 未来发展方向预测
- **用户痛点** - 目标用户的核心需求
- **变现模式** - 商业模式和变现路径

## 输出格式
请严格按照以下JSON格式输出，rules数组中每条规则都要有category字段，并且每条规则都要给出评价：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点（100字以内）",
    "rules": [
        {{
            "category": "keywords/topic/template/operation/market 之一",
            "title": "规则标题",
            "summary": "规则摘要（50字以内）",
            "description": "规则详细内容",
            "scenes": "适用场景",
            "is_good": true/false,
            "recommendation": "强烈推荐/推荐/不推荐/待观察",
            "reasoning": "评价理由和依据",
            "score": 评分(1-10)
        }}
    ]
}}
```

请只输出JSON，不要有其他内容。"""
    return prompt


@knowledge_api.route('/ebook/analyze', methods=['POST'])
@login_required
def analyze_ebook():
    """分析电子书接口"""
    try:
        data = request.get_json()
        file_ids = data.get('file_ids', [])

        if not file_ids:
            return jsonify({'code': 400, 'message': '请选择要分析的文件'})

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        all_rules = []

        for file_id in file_ids:
            ebook = ebook_storage.get(file_id)
            if not ebook:
                continue

            text = ebook.get('text', '').strip()
            if not text:
                continue

            # 构建提示词
            prompt = build_ebook_analysis_prompt(text, ebook['filename'])

            logger.info(f"[ebook_analyze] 开始分析: {ebook['filename']}")

            messages = [
                {"role": "system", "content": "你是一个专业的知识管理专家，擅长从书籍中提取可落地的规则。请严格按照JSON格式输出。"},
                {"role": "user", "content": prompt}
            ]

            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=4000)

            if not result_text:
                continue

            # 提取 JSON
            try:
                result_json = parse_llm_json(result_text)

                rules = result_json.get('rules', [])
                for rule in rules:
                    rule['source_file'] = ebook['filename']
                all_rules.extend(rules)

            except (json.JSONDecodeError, Exception) as e:
                logger.error(f"解析失败: {e}")
                continue

        if not all_rules:
            return jsonify({'code': 400, 'message': '未能从电子书中提取到有效规则'})

        return jsonify({
            'code': 200,
            'message': f'成功提取 {len(all_rules)} 条规则',
            'data': {
                'rules': all_rules
            }
        })

    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})


@knowledge_api.route('/ebook/rules/import', methods=['POST'])
@login_required
def import_ebook_rules():
    """电子书规则入库接口"""
    try:
        data = request.get_json()
        rules = data.get('rules', [])

        if not rules:
            return jsonify({'code': 400, 'message': '请选择要入库的规则'})

        rules_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'skills', 'knowledge-base', '规则'
        )

        if not os.path.exists(rules_dir):
            os.makedirs(rules_dir)

        # 按分类组织规则
        rules_by_category = {}
        for rule in rules:
            category = rule.get('category', 'keywords')
            if category not in rules_by_category:
                rules_by_category[category] = []
            rules_by_category[category].append(rule)

        import_results = []
        rule_files = {
            'keywords': '关键词库_规则模板.md',
            'topic': '选题库_规则模板.md',
            'template': '内容模板_规则模板.md',
            'operation': '运营规划_规则模板.md',
            'market': '市场分析_规则模板.md'
        }
        category_names = {
            'keywords': '关键词库',
            'topic': '选题库',
            'template': '内容模板',
            'operation': '运营规划',
            'market': '市场分析'
        }

        for category, category_rules in rules_by_category.items():
            filename = rule_files.get(category)
            if not filename:
                continue

            filepath = os.path.join(rules_dir, filename)

            # 读取现有内容
            existing_content = ""
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_content = f.read()

            # 构建新规则内容
            new_rules_section = f"\n\n## 电子书入库规则（{len(category_rules)}条）\n\n"

            for i, rule in enumerate(category_rules, 1):
                new_rules_section += f"### {i}. {rule.get('title', '未命名规则')}\n\n"
                new_rules_section += f"- **来源**: {rule.get('source_file', '未知来源')}\n"
                new_rules_section += f"- **规则内容**: {rule.get('description', '')}\n"
                new_rules_section += f"- **适用场景**: {rule.get('scenes', '通用')}\n\n"

            # 添加更新时间
            import_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_rules_section += f"\n---\n*入库时间: {import_time}*"

            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(existing_content + new_rules_section)

            import_results.append(f"{category_names.get(category, category)}: {len(category_rules)}条")

        return jsonify({
            'code': 200,
            'message': '规则入库成功',
            'data': {
                'imported_count': len(rules),
                'details': import_results
            }
        })

    except Exception as e:
        logger.error(f"规则入库失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'入库失败: {str(e)}'})
