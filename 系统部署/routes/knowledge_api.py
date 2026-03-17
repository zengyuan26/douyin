# -*- coding: utf-8 -*-
"""
知识库内容分析 API
用于分析抖音链接并提取可入库的规则
"""

import os
import re
import json
import logging
import base64
import threading
import time

import requests
from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user
from sqlalchemy.exc import OperationalError

# 导入新添加的模型
try:
    from models.models import KnowledgeAccount, KnowledgeAccountHistory, KnowledgeContent, db
except ImportError:
    db = None

logger = logging.getLogger(__name__)

# 维度与规则匹配辅助工具
from services.analysis_dimension_runner import (
    filter_modules_by_active_dimensions,
    get_account_design_dimensions,
    get_dimension_by_code,
    get_active_dimensions,
    get_all_dimensions,
)
from services.rule_matcher import match_rules_for_text
from services.analysis_task_queue import get_task_queue, TASK_TYPE_PROFILE, TASK_TYPE_DESIGN, TASK_TYPE_SUB_CATEGORY

knowledge_api = Blueprint('knowledge_api', __name__, url_prefix='/api/knowledge')

def _commit_with_retry(max_retries: int = 5, base_delay_s: float = 0.08) -> None:
    """提交事务，遇到 sqlite 'database is locked' 做轻量重试。"""
    last_exc = None
    for i in range(max_retries):
        try:
            db.session.commit()
            return
        except OperationalError as e:
            db.session.rollback()
            last_exc = e
            msg = str(e).lower()
            if "database is locked" not in msg:
                raise
            time.sleep(base_delay_s * (i + 1))
    if last_exc:
        raise last_exc


def resolve_douyin_short_url(url):
    """解析抖音短链接，返回真实的主页链接

    Args:
        url: 抖音链接（可能是短链接或主页链接，也可能是包含链接的文本）

    Returns:
        str: 解析后的真实链接，如果是短链接则返回原始链接
    """
    # 第一步：从文本中提取抖音链接
    # 匹配 v.douyin.com 开头的链接
    url_match = re.search(r'https?://v\.douyin\.com/[a-zA-Z0-9]+', url)
    if url_match:
        extracted_url = url_match.group(0)
        logger.info(f"[resolve_douyin_short_url] 从文本中提取到链接: {extracted_url}")
        url = extracted_url

    # 处理 iesdouyin.com 分享链接 - 需要解析重定向
    if 'iesdouyin.com' in url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=10, stream=True)
            real_url = response.url
            response.close()

            # 转换为 douyin.com 格式
            if 'iesdouyin.com' in real_url:
                real_url = real_url.replace('iesdouyin.com', 'douyin.com')

            logger.info(f"[resolve_douyin_short_url] iesdouyin.com 解析: {url} -> {real_url}")
            return real_url
        except Exception as e:
            logger.warning(f"[resolve_douyin_short_url] 解析 iesdouyin.com 失败: {e}")
            # 尝试直接转换
            return url.replace('iesdouyin.com', 'douyin.com')

    # 检查是否是短链接
    if 'v.douyin.com' not in url:
        return url

    try:
        # 使用 GET 请求获取重定向后的真实链接
        # 使用 allow_redirects=True 自动跟随重定向
        # 设置较短的超时和 User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # 使用 GET 请求而不是 HEAD，因为有些服务器对 HEAD 请求处理不同
        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10, stream=True)
        # 关闭连接
        response.close()

        # 获取最终的真实链接
        real_url = response.url

        logger.info(f"[resolve_douyin_short_url] 短链接 {url} 解析为 {real_url}")

        return real_url
    except Exception as e:
        logger.warning(f"[resolve_douyin_short_url] 解析短链接失败: {e}, 使用原始链接")
        return url

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

# 导入标题关键词分类器
try:
    from utils.title_classifier import TitleKeywordClassifier, classify_title_keywords
except ImportError:
    # 如果导入失败，定义空函数
    def classify_title_keywords(title):
        return {"categories": [], "all_keywords": [], "title_type": "未知"}
    TitleKeywordClassifier = None


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


@knowledge_api.route('/title-classify', methods=['POST'])
@login_required
def api_classify_title():
    """标题关键词分类接口"""
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        
        if not title:
            return jsonify({'code': 400, 'message': '请输入标题'})
        
        # 使用分类器进行分类
        result = classify_title_keywords(title)
        
        return jsonify({
            "code": 200,
            "data": result
        })
    except Exception as e:
        logger.error(f"标题分类失败: {e}")
        return jsonify({'code': 500, 'message': f'分类失败: {str(e)}'})


def parse_llm_json(result_text):
    """解析 LLM 返回的 JSON，支持多种格式并自动修复常见问题"""
    # 1. 尝试从 markdown 代码块中提取
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = result_text

    # 1.5 移除 JSON 中的注释（LLM 可能会输出中文注释）
    lines = json_str.split('\n')
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        # 跳过纯注释行（包括各种形式的注释）
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or stripped.startswith('#'):
            continue
        # 移除行内注释（如 "key": "value", // 注释）
        if '//' in line:
            line = line.split('//')[0]
        # 移除块注释 /* */ 内容
        if '/*' in line:
            line = re.sub(r'/\*.*?\*/', '', line)
        filtered_lines.append(line)
    json_str = '\n'.join(filtered_lines)

    # 1.6 移除注释后移除空行，然后补充缺失的逗号
    # 先移除空行
    json_str = re.sub(r'\n\s*\n', '\n', json_str)
    # 然后添加逗号：匹配 "key": value 后面跟另一个 key 的情况
    json_str = re.sub(
        r'("(?:\w+)":\s*("(?:[^"\\]|\\.)*"|\d+|true|false|null))\s*\n\s*("(?:\w+)":)',
        r'\1,\n\3',
        json_str
    )

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


def get_douyin_real_account_info(url, use_browser=False):
    """使用爬虫获取抖音账号真实信息

    Args:
        url: 抖音链接
        use_browser: 是否使用浏览器模式（需要手动验证验证码）

    Returns:
        dict: 账号信息，如果失败返回 None
    """
    try:
        from services.douyin_scraper import get_douyin_account_info as _scrape
        return _scrape(url, use_browser=use_browser)
    except Exception as e:
        logger.warning(f"[get_douyin_real_account_info] 爬虫获取失败: {e}")
        return None


def get_douyin_video_content_info(url, use_browser=False):
    """使用爬虫获取抖音视频/图文内容信息

    Args:
        url: 抖音视频/图文链接
        use_browser: 是否使用浏览器模式（需要手动验证验证码）

    Returns:
        dict: 视频/图文信息，如果失败返回 None
    """
    try:
        from services.douyin_scraper import get_douyin_video_info as _scrape
        return _scrape(url, use_browser=use_browser)
    except Exception as e:
        logger.warning(f"[get_douyin_video_content_info] 爬虫获取失败: {e}")
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

    // 按顺序展示分析过程
    "analysis_process": {{
        // 1. 标题分析
        "title": {{
            "content": "标题原文",
            "keywords": ["关键词1", "关键词2"],
            "analysis": "标题分析过程：为什么这么写，好在哪"
        }},

        // 2. 封面分析
        "cover": {{
            "content": "封面描述",
            "analysis": "封面分析：为什么这样设计，好在哪"
        }},

        // 3. 内容结构分析
        "content": {{
            "hook": "开头钩子分析：前3秒用了什么钩子",
            "body": "主体内容分析：内容怎么展开",
            "structure": "爆款内容结构分析：整体框架是什么"
        }},

        // 4. 结尾分析
        "ending": {{
            "content": "结尾内容描述",
            "analysis": "结尾分析：如何收尾，好在哪"
        }},

        // 5. 标签分析
        "tags": {{
            "content": ["标签1", "标签2"],
            "analysis": "标签分析：用了哪些标签策略"
        }}
    }},

    // 核心分析结果
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

        # 解析短链接，获取真实的内容链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[knowledge_analyze] 原始链接: {url}, 解析后: {real_url}")

        # 获取 LLM 服务（支持 Ollama 本地大模型）
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        # 构建提示词
        prompt = build_analysis_prompt(real_url, content_type, note)

        # 调用 LLM
        logger.info(f"[knowledge_analyze] 开始分析: {real_url}")
        
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

            # 清理标题中的抖音元数据
            cleaned_title = ''
            if 'title' in result_json and result_json['title']:
                title = result_json['title']
                # 1. 匹配类似 "9.94 BTL:/ o@d.Nw 06/13 " 这样的前缀并移除
                cleaned_title = re.sub(r'^[\d.]+\s*BTL:?\s*[\w@.\/]+\s*\d{2}\/\d{2}\s*', '', title)
                # 2. 匹配 "9.94 复制打开抖音，看看【标题】" 这种格式
                cleaned_title = re.sub(r'^[\d.]+\s*复制打开抖音，看看【[^】]+】', '', cleaned_title)
                # 3. 移除末尾的抖音链接
                cleaned_title = re.sub(r'\s*https?:\/\/v\.douyin\.com\/[^\s]+.*$', '', cleaned_title)
                result_json['title'] = cleaned_title

            # 对标题进行关键词分类和评分
            if cleaned_title:
                try:
                    from utils.title_classifier import TitleKeywordClassifier
                    title_classification = TitleKeywordClassifier.get_keywords_summary(cleaned_title)
                    title_structure_display = TitleKeywordClassifier.get_title_structure_display(cleaned_title)
                    title_scores = TitleKeywordClassifier.calculate_scores(cleaned_title)

                    # 检查标题结构是否在规则库中
                    structure_match = None
                    title_structure = title_classification.get('title_structure', '')
                    if title_structure and title_structure != '普通标题':
                        # 规则库匹配逻辑
                        known_structures = TitleKeywordClassifier.KNOWN_TITLE_STRUCTURES
                        if title_structure in known_structures:
                            structure_match = {'matched': True, 'structure': title_structure, 'message': '标题结构符合优质标题模式'}
                        else:
                            structure_match = {
                                'matched': False,
                                'structure': title_structure_display,
                                'message': '标题结构为新型组合，建议加入规则库观察效果'
                            }

                    # 将分类结果和评分添加到 analysis_process.title 中
                    if 'analysis_process' not in result_json:
                        result_json['analysis_process'] = {}
                    if 'title' not in result_json['analysis_process']:
                        result_json['analysis_process']['title'] = {}
                    result_json['analysis_process']['title']['keyword_classification'] = title_classification
                    result_json['analysis_process']['title']['title_structure_display'] = title_structure_display
                    result_json['analysis_process']['title']['title_scores'] = title_scores
                    result_json['analysis_process']['title']['structure_match'] = structure_match
                except Exception as e:
                    logger.warning(f"标题关键词分类或评分失败: {e}")

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


# ==================== 模块化分析相关函数 ====================

# 模块定义
ANALYSIS_MODULES = {
    'title': {
        'name': '标题分析',
        'order': 1,
        'prompt_builder': None  # 动态生成
    },
    'cover': {
        'name': '封面分析',
        'order': 2,
        'prompt_builder': None
    },
    'topic': {
        'name': '选题分析',
        'order': 3,
        'prompt_builder': None
    },
    'content': {
        'name': '内容结构',
        'order': 4,
        'prompt_builder': None
    },
    'ending': {
        'name': '结尾分析',
        'order': 5,
        'prompt_builder': None
    },
    'tags': {
        'name': '标签分析',
        'order': 6,
        'prompt_builder': None
    },
    'psychology': {
        'name': '心理分析',
        'order': 7,
        'prompt_builder': None
    },
    'commercial': {
        'name': '商业目的',
        'order': 8,
        'prompt_builder': None
    },
    'character': {
        'name': '人物设计',
        'order': 9,
        'prompt_builder': None
    },
    'content_form': {
        'name': '内容形式',
        'order': 10,
        'prompt_builder': None
    },
    'why_popular': {
        'name': '爆款原因',
        'order': 11,
        'prompt_builder': None
    },
    'interaction': {
        'name': '互动数据',
        'order': 12,
        'prompt_builder': None
    }
}


def build_title_prompt(url, note):
    """构建标题分析提示词"""
    prompt = f"""你是一个资深的短视频标题分析专家。请分析以下抖音内容的标题。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 标题分析要点

### 1. 标题关键词组合
分析标题用了哪些关键词组合：
- 流量关键词（吸引眼球的词）
- 核心业务关键词（产品/服务词）
- 科普/行业关键词（专业词）
- 数字（增强可信度）
- 情绪词（引发共鸣）

### 2. 标题为什么有效
- 击中用户什么需求？
- 和竞品比有什么独特性？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "title": "内容标题",
    "author": "作者/账号名",
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
    "analysis_process": {{
        "title": {{
            "content": "标题原文",
            "keywords": ["关键词1", "关键词2"],
            "analysis": "标题分析过程"
        }}
    }}
}}
```"""
    return prompt


def build_cover_prompt(url, note):
    """构建封面分析提示词"""
    prompt = f"""你是一个资深的短视频封面分析专家。请分析以下抖音内容的封面。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 封面分析要点

### 1. 封面内容描述
- 封面画面包含哪些元素？
- 人物/产品/文字的分布？

### 2. 封面设计分析
- 为什么这样设计封面？
- 好在哪里？
- 能吸引用户点击吗？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "cover_analysis": {{
        "content": "封面描述",
        "elements": ["元素1", "元素2"],
        "design_analysis": "设计分析",
        "why_effective": "为什么有效"
    }},
    "analysis_process": {{
        "cover": {{
            "content": "封面描述",
            "analysis": "封面分析"
        }}
    }}
}}
```"""
    return prompt


def build_topic_prompt(url, note):
    """构建选题分析提示词"""
    prompt = f"""你是一个资深的短视频选题分析专家。请分析以下抖音内容的选题。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 选题分析要点

### 1. 选题方向
- 这个选题属于什么方向？
- 是热点话题还是长期选题？

### 2. 目标人群（非常重要）
分析内容针对的目标人群：
- 细分场景人群：[具体人群描述]
- 长尾需求人群：[具体需求]

### 3. 选题切中客户什么
- 痛点（什么痛苦/困扰）
- 情绪（什么情感需求）
- 功能价值（什么实用价值）
- 独特性（和市面上其他方案比有什么不同）

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "topic_analysis": {{
        "direction": "选题方向",
        "topic_type": "热点/长期/节日/其他",
        "target_audience": {{
            "scene_crowd": "细分场景人群",
            "demand_crowd": "长尾需求人群"
        }},
        "hit_what": {{
            "pain_point": "痛点",
            "emotion": "情绪",
            "functional_value": "功能价值",
            "uniqueness": "独特性"
        }}
    }}
}}
```"""
    return prompt


def build_content_structure_prompt(url, note):
    """构建内容结构分析提示词"""
    prompt = f"""你是一个资深的短视频内容结构分析专家。请分析以下抖音内容的结构。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 内容结构分析要点

### 1. 开头钩子（前3秒）
- 用了什么钩子类型？
- 开头画面有什么特点？
- 为什么这样设计钩子？

### 2. 视频内容节奏
- 整体节奏：快/中/慢/张弛有度
- 内容是否一直拽着观众走？

### 3. 情绪变化曲线
分析情绪如何起伏：
- 开头什么情绪？
- 中间情绪如何变化？
- 结尾什么情绪收尾？

### 4. 内容核心价值
- 内容提供了什么价值？
- 对用户有什么帮助？

### 5. 脚本模型
分析用的什么脚本模型：
- 晒过程（展示过程）
- 讲故事（叙述故事）
- 说观点（表达观点）
- 教知识（知识分享）
- 说产品（产品介绍）
- 演段子（娱乐表演）

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "content_structure": {{
        "hook": "开头钩子类型",
        "hook_description": "钩子具体表现",
        "opening_shot": "开头画面特点",
        "rhythm": "内容节奏",
        "rhythm_description": "节奏详细描述",
        "emotion_curve": {{
            "type": "情绪曲线类型",
            "can_drag_audience": "是否能拽着观众走",
            "phases": [
                {{"position": "位置", "emotion": "情绪", "description": "描述"}}
            ]
        }},
        "core_value": "内容核心价值",
        "script_model": "脚本模型类型"
    }},
    "analysis_process": {{
        "content": {{
            "hook": "开头钩子分析",
            "body": "主体内容分析",
            "structure": "内容结构分析"
        }}
    }}
}}
```"""
    return prompt


def build_ending_prompt(url, note):
    """构建结尾分析提示词"""
    prompt = f"""你是一个资深的短视频结尾分析专家。请分析以下抖音内容的结尾。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 结尾分析要点

### 1. 结尾内容描述
- 结尾画面/文字是什么？
- 做了什么动作/说了什么话？

### 2. 结尾设计分析
- 为什么这样收尾？
- 好在哪里？
- 是否引导了互动（评论/点赞/转发）？

### 3. 结尾与整体内容的呼应
- 结尾是否呼应了开头？
- 是否强化了核心信息？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "ending_analysis": {{
        "content": "结尾内容描述",
        "ending_type": "结尾类型（引导互动/总结升华/悬念留扣/自然收尾等）",
        "design_analysis": "设计分析",
        "why_effective": "为什么有效",
        "interaction_guidance": "是否有互动引导"
    }},
    "analysis_process": {{
        "ending": {{
            "content": "结尾内容描述",
            "analysis": "结尾分析"
        }}
    }}
}}
```"""
    return prompt


def build_tags_prompt(url, note):
    """构建标签分析提示词"""
    prompt = f"""你是一个资深的短视频标签分析专家。请分析以下抖音内容的标签策略。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 标签分析要点

### 1. 抖音5个标签组合策略
分析内容用了哪些标签组合：
- 区域+业务关键词：[示例]
- 蓝海长尾词：[示例]
- 区域+品牌词：[示例]
- 核心业务关键词：[示例]
- 产品关键词：[示例]
- 场景词（客户需要解决方案的场景）：[示例]

### 2. 关键词埋入策略
分析关键词如何埋入（便于AI/SEO搜索收录）：
- 标题关键词
- 开头关键词
- 内容关键词
- 标签关键词

### 3. 标签效果分析
- 这些标签能带来哪些流量？
- 是否符合账号定位？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "tag_strategy": {{
        "region_business": "区域+业务关键词",
        "blue_ocean": "蓝海长尾词",
        "region_brand": "区域+品牌词",
        "core_business": "核心业务关键词",
        "product_keywords": "产品关键词",
        "scene_words": "场景词",
        "keyword_placement": "关键词埋入位置"
    }},
    "analysis_process": {{
        "tags": {{
            "content": ["标签1", "标签2"],
            "analysis": "标签分析"
        }}
    }}
}}
```"""
    return prompt


def build_psychology_prompt(url, note):
    """构建心理分析提示词"""
    prompt = f"""你是一个资深的短视频用户心理分析专家。请分析以下内容利用了哪些用户心理。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 心理分析要点

### 1. 利用了什么心理
分析内容利用了观众什么心理：
- 恐惧（害怕失去/担忧）
- 追求（想要获得）
- 规避（想避免问题）
- 损失厌恶（不想亏）
- 从众心理（大家都在看）
- 其他：[具体心理]

### 2. 为什么招人喜欢
- 是因为有用？
- 是因为有趣？
- 是因为能引起共鸣？
- 还是都有？

### 3. 心理诱导效果
- 这些心理手段达到预期效果了吗？
- 用户会产生什么行为？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "psychology_analysis": {{
        "psychology_used": ["利用的心理1", "利用的心理2"],
        "psychology_details": {{
            "fear": "恐惧心理的具体表现",
            "pursuit": "追求心理的具体表现",
            "avoidance": "规避心理的具体表现",
            "loss_aversion": "损失厌恶的具体表现",
            "bandwagon": "从众心理的具体表现"
        }},
        "why_appealing": {{
            "useful": "有用（是/否/部分）",
            "interesting": "有趣（是/否/部分）",
            "resonance": "共鸣（是/否/部分）"
        }}
    }}
}}
```"""
    return prompt


def build_commercial_prompt(url, note):
    """构建商业目的分析提示词"""
    prompt = f"""你是一个资深的短视频商业目的分析专家。请分析以下内容的商业目的。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 商业目的分析要点

### 1. 商业目的
- 这个内容目的是什么？
- 品牌宣传/引流获客/产品销售/IP打造？

### 2. 细分市场
- 内容主题切的是什么细分市场？
- 什么细分场景？

### 3. 爆款元素
- 选题结合了什么爆款元素？
- 为什么能火？

### 4. 变现路径
- 内容如何引导到变现？
- 是否有明确的行动号召？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "commercial_purpose": {{
        "purpose": "商业目的",
        "purpose_type": "品牌宣传/引流获客/产品销售/IP打造",
        "target_market": "目标细分市场",
        "target_scene": "目标细分场景",
        "viral_elements": "结合的爆款元素",
        "monetization_path": "变现路径描述",
        "has_cta": true/false
    }}
}}
```"""
    return prompt


def build_character_prompt(url, note):
    """构建人物设计分析提示词"""
    prompt = f"""你是一个资深的短视频人物设计分析专家。请分析以下内容的人物设计。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 人物设计分析要点

### 1. 出镜情况
- 是否有人物出镜？
- 出镜人物角色？
- 人物出现的时长占比？

### 2. 人物关系
- 人物之间什么关系？
- 婆媳/父子/夫妻/朋友/其他？

### 3. 冲突设计（如果是故事类）
- 有什么冲突/矛盾？
- 冲突如何推进？
- 冲突解决了吗？

### 4. 人物塑造
- 人物性格特点？
- 是否有记忆点？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "character_design": {{
        "has_character": "是否有人物出镜",
        "characters": ["出镜人物角色1", "出镜人物角色2"],
        "character_appearance_ratio": "人物出镜时长占比",
        "relationships": "人物关系描述",
        "conflict": "冲突设计描述",
        "character_traits": "人物性格特点"
    }}
}}
```"""
    return prompt


def build_content_form_prompt(url, note):
    """构建内容形式分析提示词"""
    prompt = f"""你是一个资深的内容形式分析专家。请分析以下抖音内容的形式特点。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 内容形式分析要点

### 1. 内容形式类型
- 图文类内容
- 短视频类内容

### 2. 图文类内容分析（如适用）
- 文字使用原则：
  - 何时尽量少文字？
  - 何时多用数字佐证？
  - 何时讲具体案例？
  - 何时说方言？
- 构图分析：[图文排版特点]

### 3. 短视频类内容分析（如适用）
- 拍摄角度：[拍摄手法]
- 背景音乐选择：[BGM特点]
- 画面与内容关联度
- 剪辑节奏

### 4. 整体风格
- 调性：专业/亲和/幽默/严肃
- 是否有统一的视觉风格？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
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
            "shooting_angle": "拍摄角度",
            "bgm": "背景音乐选择",
            "content_visual_relationship": "画面与内容关联度",
            "editing_rhythm": "剪辑节奏"
        }},
        "overall_style": "整体风格描述"
    }}
}}
```"""
    return prompt


def build_why_popular_prompt(url, note):
    """构建爆款原因分析提示词"""
    prompt = f"""你是一个资深的爆款内容分析专家。请分析以下抖音内容为什么能成为爆款。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 爆款原因分析要点

### 1. 为什么这么多人喜欢
- 内容本身好在哪里？
- 击中什么需求？
- 有什么独特价值？

### 2. 为什么互动会好
- 引发评论的点是什么？
- 让人想留言的原因？
- 是否有争议性话题？

### 3. 为什么愿意分享
- 什么让人想转发？
- 社交货币是什么？
- 是否具有传播属性？

### 4. 爆款元素总结
- 成功的关键因素是什么？
- 可以复用的点是什么？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "why_popular": {{
        "why_liked": "为什么多人喜欢",
        "like_key_factors": ["因素1", "因素2"],
        "why_good_interaction": "为什么互动好",
        "interaction_triggers": ["触发点1", "触发点2"],
        "why_share": "为什么愿意分享",
        "share_factors": ["分享因素1", "分享因素2"],
        "key_success_factors": "成功关键因素总结",
        "replicable_points": "可复用的点"
    }}
}}
```"""
    return prompt


def build_interaction_prompt(url, note):
    """构建互动数据分析提示词"""
    prompt = f"""你是一个资深的数据分析师。请分析以下抖音内容的互动数据。

## 待分析内容
- 链接：{url}
- 补充说明：{note}

---

## 互动数据分析要点

### 1. 互动数据概况
- 点赞数量及质量
- 评论数量及内容分析
- 收藏数量及动机
- 转发数量及场景

### 2. 数据分析
- 点赞多评论少：说明什么？
- 收藏多点赞少：说明什么？
- 转发多说明什么？
- 评论内容反映了什么？

### 3. 互动优化建议
- 如何提升互动率？
- 哪些方面可以改进？

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "interaction_analysis": {{
        "likes": "点赞数",
        "likes_analysis": "点赞分析",
        "comments": "评论数",
        "comments_analysis": "评论分析",
        "favorites": "收藏数",
        "favorites_analysis": "收藏分析",
        "shares": "转发数",
        "shares_analysis": "转发分析",
        "overall_analysis": "整体互动分析结论",
        "improvement_suggestions": "互动优化建议"
    }}
}}
```"""
    return prompt


# 模块提示词构建器映射
MODULE_PROMPT_BUILDERS = {
    'title': build_title_prompt,
    'cover': build_cover_prompt,
    'topic': build_topic_prompt,
    'content': build_content_structure_prompt,
    'ending': build_ending_prompt,
    'tags': build_tags_prompt,
    'psychology': build_psychology_prompt,
    'commercial': build_commercial_prompt,
    'character': build_character_prompt,
    'content_form': build_content_form_prompt,
    'why_popular': build_why_popular_prompt,
    'interaction': build_interaction_prompt
}


@knowledge_api.route('/analyze-modules', methods=['POST'])
@login_required
def analyze_modules():
    """模块化分析内容接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        note = data.get('note', '').strip()
        modules = data.get('modules', [])

        if not url:
            return jsonify({'code': 400, 'message': '请输入内容链接'})

        if not modules:
            return jsonify({'code': 400, 'message': '请选择至少一个分析模块'})

        # 解析短链接，获取真实的内容链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[analyze_modules] 原始链接: {url}, 解析后: {real_url}")

        # 验证模块有效性
        valid_modules = set(ANALYSIS_MODULES.keys())
        selected_modules = set(modules)
        invalid_modules = selected_modules - valid_modules
        if invalid_modules:
            return jsonify({'code': 400, 'message': f'无效的模块: {", ".join(invalid_modules)}'})

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        logger.info(f"[analyze_modules] 开始分析: {real_url}, 模块: {modules}")

        # 按顺序分析选中的模块
        results = {}
        analysis_process = {}

        for module in modules:
            prompt_builder = MODULE_PROMPT_BUILDERS.get(module)
            if not prompt_builder:
                continue

            prompt = prompt_builder(real_url, note)

            messages = [
                {"role": "system", "content": "你是一个专业的内容分析专家，擅长分析抖音等短视频平台的内容。请严格按照JSON格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ]

            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)

            if result_text:
                try:
                    result_json = parse_llm_json(result_text)

                    # 如果是标题模块，清理标题中的抖音元数据
                    if module == 'title' and 'title' in result_json:
                        cleaned_title = result_json['title']
                        cleaned_title = re.sub(r'^[\d.]+\s*BTL:?\s*[\w@.\/]+\s*\d{2}\/\d{2}\s*', '', cleaned_title)
                        cleaned_title = re.sub(r'^[\d.]+\s*复制打开抖音，看看【[^】]+】', '', cleaned_title)
                        cleaned_title = re.sub(r'\s*https?:\/\/v\.douyin\.com\/[^\s]+.*$', '', cleaned_title)
                        result_json['title'] = cleaned_title

                        # 对标题进行关键词分类和评分
                        try:
                            from utils.title_classifier import TitleKeywordClassifier
                            title_classification = TitleKeywordClassifier.get_keywords_summary(cleaned_title)
                            title_structure_display = TitleKeywordClassifier.get_title_structure_display(cleaned_title)
                            title_scores = TitleKeywordClassifier.calculate_scores(cleaned_title)

                            if 'analysis_process' not in result_json:
                                result_json['analysis_process'] = {}
                            if 'title' not in result_json['analysis_process']:
                                result_json['analysis_process']['title'] = {}
                            result_json['analysis_process']['title']['keyword_classification'] = title_classification
                            result_json['analysis_process']['title']['title_structure_display'] = title_structure_display
                            result_json['analysis_process']['title']['title_scores'] = title_scores
                        except Exception as e:
                            logger.warning(f"标题关键词分类或评分失败: {e}")

                    results[module] = result_json

                    # 收集 analysis_process
                    if 'analysis_process' in result_json:
                        analysis_process.update(result_json['analysis_process'])

                except json.JSONDecodeError as e:
                    logger.warning(f"模块 {module} JSON解析失败: {e}")
                    results[module] = {'error': '解析失败', 'raw': result_text[:200]}
            else:
                results[module] = {'error': 'LLM 调用失败'}

        # 合并结果
        merged_result = {
            'title': results.get('title', {}).get('title', ''),
            'author': results.get('title', {}).get('author', ''),
            'content_type': 'video',
            'analysis_process': analysis_process,
            'modules_results': results
        }

        # 添加各个模块的结果
        for module, result in results.items():
            if module == 'title':
                if 'title_analysis' in result:
                    merged_result['title_analysis'] = result['title_analysis']
            elif module == 'topic':
                if 'topic_analysis' in result:
                    merged_result['topic_analysis'] = result['topic_analysis']
            elif module == 'content':
                if 'content_structure' in result:
                    merged_result['content_structure'] = result['content_structure']
            elif module == 'psychology':
                if 'psychology_analysis' in result:
                    merged_result['psychology_analysis'] = result['psychology_analysis']
            elif module == 'commercial':
                if 'commercial_purpose' in result:
                    merged_result['commercial_purpose'] = result['commercial_purpose']
            elif module == 'character':
                if 'character_design' in result:
                    merged_result['character_design'] = result['character_design']
            elif module == 'content_form':
                if 'content_form' in result:
                    merged_result['content_form'] = result['content_form']
            elif module == 'tags':
                if 'tag_strategy' in result:
                    merged_result['tag_strategy'] = result['tag_strategy']
            elif module == 'why_popular':
                if 'why_popular' in result:
                    merged_result['why_popular'] = result['why_popular']
            elif module == 'interaction':
                if 'interaction_analysis' in result:
                    merged_result['interaction_analysis'] = result['interaction_analysis']
            elif module == 'ending':
                if 'ending_analysis' in result:
                    merged_result['ending_analysis'] = result['ending_analysis']
            elif module == 'cover':
                if 'cover_analysis' in result:
                    merged_result['cover_analysis'] = result['cover_analysis']

        logger.info(f"[analyze_modules] 模块分析完成: {url}, 完成模块: {list(results.keys())}")

        return jsonify({
            'code': 200,
            'message': '分析成功',
            'data': merged_result
        })

    except Exception as e:
        logger.error(f"模块分析失败: {e}", exc_info=True)
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

# 账号分析模块定义
ACCOUNT_MODULES = {
    'commercial': {
        'name': '商业定位',
        'order': 1,
        'description': '变现方式、卖货策略、变现链路'
    },
    'basic_info': {
        'name': '账号基础信息',
        'order': 2,
        'description': '昵称设计、简介设计、头像设计'
    },
    'content_structure': {
        'name': '内容结构',
        'order': 3,
        'description': '人物出镜、主题占比、内容与变现关联'
    },
    'target_customer': {
        'name': '目标客户',
        'order': 4,
        'description': '客户特征、客户需求'
    },
    'keywords': {
        'name': '关键词布局',
        'order': 5,
        'description': '关键词、关键词分布位置'
    },
    'video_types': {
        'name': '视频类型',
        'order': 6,
        'description': '视频类型分布、内容风格'
    },
    'account_position': {
        'name': '账号定位',
        'order': 7,
        'description': '账号类型、人设打造'
    }
}


def build_account_analysis_prompt(url, account_info_text=""):
    """构建账号分析提示词
    
    Args:
        url: 账号主页链接
        account_info_text: 爬虫获取的真实账号信息（可选）
    """
    # 如果有真实账号信息，加入到提示词中
    account_section = ""
    if account_info_text:
        account_section = f"\n{account_info_text}\n"
    
    prompt = f"""你是一个资深的账号运营分析专家。请从专业运营角度完整分析以下抖音账号，提取可复用的账号运营策略和规则。

## 待分析账号
- 账号主页链接：{url}{account_section}

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

### 5.1 核心关键词（1-3个最主要的流量/转化关键词）
核心关键词应该直接与业务相关，是用户搜索最多、流量最大的词
- 如卖奶粉则核心关键词应包含"奶粉"相关
- 如灌香肠则核心关键词应包含"灌香肠"、"香肠"相关

### 5.2 产品关键词
- 行业关键词
- 品名词
- 品牌词

### 5.3 流量关键词
- 地域关键词
- 用途关键词
- 属性关键词
- 场景关键词

### 5.4 转化关键词
- 价格关键词
- 促销关键词
- 口碑关键词

### 5.5 关键词分布位置
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
        "core_keywords": ["核心关键词1", "核心关键词2", "核心关键词3"],
        "product_keywords": {{
            "industry_keywords": ["行业词1", "行业词2"],
            "product_name_keywords": ["品名词1", "品名词2"],
            "brand_keywords": ["品牌词1", "品牌词2"]
        }},
        "traffic_keywords": {{
            "region_keywords": ["地域词1", "地域词2"],
            "usage_keywords": ["用途词1", "用途词2"],
            "attribute_keywords": ["属性词1", "属性词2"],
            "scene_keywords": ["场景词1", "场景词2"]
        }},
        "conversion_keywords": {{
            "price_keywords": ["价格词1", "价格词2"],
            "promotion_keywords": ["促销词1", "促销词2"],
            "reputation_keywords": ["口碑词1", "口碑词2"]
        }},
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


# ========== 账号分析各模块独立提示词构建函数 ==========


def build_account_profile_from_manual_prompt(account_data):
    """根据手动录入的账号信息构建目标客户画像和关键词布局

    Args:
        account_data: 手动录入的账号信息字典
            - name: 账号名称
            - platform: 平台
            - url: 主页链接
            - business_type: 业务类型（卖货类/服务类/两者都有）
            - product_type: 产品类型（实物商品/批发供应链/其他）
            - service_type: 服务类型（本地生活/线上专业/知识付费/其他）
            - service_range: 地域范围（本地/跨区域/全球）
            - target_area: 具体城市/区域
            - brand_type: 品牌定位（个人IP/企业品牌/两者兼顾）
            - language_style: 语言风格（普通话/方言）
            - main_product: 主营业务（含占比）
            - target_user: 目标用户（付费者/使用者）
    """
    name = account_data.get('name', '')
    platform = account_data.get('platform', '')
    nickname = account_data.get('nickname', '')  # 昵称
    bio = account_data.get('bio', '')  # 简介
    business_type = account_data.get('business_type', '')
    product_type = account_data.get('product_type', '')
    service_type = account_data.get('service_type', '')
    service_range = account_data.get('service_range', '')
    target_area = account_data.get('target_area', '') or '全国'
    brand_type = account_data.get('brand_type', '')
    language_style = account_data.get('language_style', '')
    main_product = account_data.get('main_product', '')
    target_user = account_data.get('target_user', '')

    # 构建业务描述
    business_desc = []
    if business_type:
        business_desc.append(f"业务类型: {business_type}")
    if product_type:
        business_desc.append(f"产品类型: {product_type}")
    if service_type:
        business_desc.append(f"服务类型: {service_type}")
    if service_range:
        business_desc.append(f"地域范围: {service_range}")
    if target_area:
        business_desc.append(f"目标区域: {target_area}")
    if main_product:
        business_desc.append(f"主营业务: {main_product}")

    business_info = '\n'.join([f"- {item}" for item in business_desc if item]) if business_desc else "未填写"

    # 账号设计信息（昵称+简介）
    account_design_info = ""
    if nickname or bio:
        parts = []
        if nickname:
            parts.append(f"- 账号昵称: {nickname}")
        if bio:
            parts.append(f"- 账号简介: {bio}")
        account_design_info = "\n".join(parts)

    prompt = f"""你是一个资深的账号运营专家。请根据以下手动录入的账号信息，分析目标客户画像、关键词布局和人设定位。

## 账号基本信息
- 账号名称: {name}
- 平台: {platform}
- 主页链接: {account_data.get('url', '未填写')}

## 账号设计信息（昵称+简介）
{account_design_info if account_design_info else "- 暂无昵称和简介信息"}

## 业务信息
{business_info}

## 目标用户类型: {target_user or '未填写'}
## 品牌定位: {brand_type or '未填写'}
## 语言风格: {language_style or '未填写'}

---

## 分析任务

### 1. 目标客户画像分析
基于上述业务信息，分析该账号的目标客户画像：
- 年龄阶段：目标客户大概什么年龄段
- 性别比例：主要客户性别
- 职业/身份：客户主要是做什么的
- 消费能力：客户的消费水平
- 地域分布：客户主要分布在哪些地区
- 客户痛点：目标客户有什么痛点或需求
- 使用场景：客户在什么场景下会需要这个产品/服务

### 2. 关键词布局分析
基于业务信息，推测应该布局的关键词：

#### 2.1 核心关键词（1-3个最主要的流量/转化关键词）
根据核心业务确定，如：桶装水、定制水、矿泉水

#### 2.2 产品关键词
与销售产品直接相关的关键词：
- 行业词：行业通用关键词
- 品名词：具体产品名称
- 品牌词：品牌相关关键词

#### 2.3 流量关键词
用于获取流量的关键词：
- 地域词：地域相关关键词（如：{target_area or '根据地域范围'}）
- 用途词：产品功能/用途相关关键词
- 属性词：产品属性描述词（颜色、材质、规格等）
- 场景词：使用场景相关关键词

#### 2.4 转化关键词
促进成交的关键词：
- 价格词：价格相关
- 促销词：优惠活动相关
- 口碑词：口碑评价相关

### 3. 人设定位分析
结合账号昵称和简介，分析该账号适合的人设类型：

**人设定位类型（5选1）**：
- 陪伴者-我懂你：像朋友一样陪伴，分享日常生活，建立情感连接。特点：亲切、日常、温暖
- 教导者-我教你：专业老师形象，教知识、讲道理、给建议。特点：专业、权威、有深度
- 崇拜者-秀自己：展示自己牛X的地方，让粉丝崇拜。特点：成功、优秀、高端
- 陪衬者-不如你：故意表现不如粉丝，让粉丝有优越感。特点：谦虚、亲和、接地气
- 搞笑者-逗笑你：主要目的是让粉丝开心快乐。特点：幽默、搞笑、轻松

请根据昵称和简介的风格，判断最合适的人设类型。

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "persona_role": "人设定位类型（从以下5种选择：陪伴者-我懂你、教导者-我教你、崇拜者-秀自己、陪衬者-不如你、搞笑者-逗笑你）",
    "target_audience": {{
        "age_range": "目标客户年龄阶段",
        "gender_ratio": "性别比例",
        "occupation": "职业/身份",
        "consumption_level": "消费能力",
        "region": "地域分布",
        "pain_points": ["客户痛点1", "客户痛点2"],
        "needs": ["客户需求1", "客户需求2"],
        "usage_scenes": ["使用场景1", "使用场景2"]
    }},

    "keyword_layout": {{
        "core_keywords": ["核心关键词1", "核心关键词2", "核心关键词3"],
        "product_keywords": {{
            "industry_keywords": ["行业词1", "行业词2"],
            "product_name_keywords": ["品名词1", "品名词2"],
            "brand_keywords": ["品牌词1", "品牌词2"]
        }},
        "traffic_keywords": {{
            "region_keywords": ["地域词1", "地域词2"],
            "usage_keywords": ["用途词1", "用途词2"],
            "attribute_keywords": ["属性词1", "属性词2"],
            "scene_keywords": ["场景词1", "场景词2"]
        }},
        "conversion_keywords": {{
            "price_keywords": ["价格词1", "价格词2"],
            "promotion_keywords": ["促销词1", "促销词2"],
            "reputation_keywords": ["口碑词1", "口碑词2"]
        }}
    }},

    "reasoning": "根据业务信息推导关键词的逻辑说明"
}}
```

注意：
1. 核心关键词应该直接与业务相关，如卖奶粉则核心关键词应包含"奶粉"相关
2. 地域范围如果是"跨区域"，则地域词可以留空或填"全国"
3. 关键词要具有实际搜索价值和转化价值
4. 如果某些关键词类型不适用，可以为空数组但字段必须存在

**人设定位类型说明（5选1）**：
- 陪伴者-我懂你：像朋友一样陪伴，分享日常生活，建立情感连接
- 教导者-我教你：专业老师形象，教知识、讲道理、给建议
- 崇拜者-秀自己：展示自己牛X的地方，让粉丝崇拜
- 陪衬者-不如你：故意表现不如粉丝，让粉丝有优越感
- 搞笑者-逗笑你：主要目的是让粉丝开心快乐"""
    return prompt


def build_account_commercial_prompt(url):
    """构建商业定位分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的商业定位。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 商业定位分析要点

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

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "commercial_positioning": {{
        "monetization_method": "变现方式",
        "sales_strategy": "卖货策略",
        "monetization_chain": "变现链路描述",
        "chain_clarity": "变现链路是否清晰"
    }},
    "analysis_process": {{
        "commercial": {{
            "content": "分析内容",
            "analysis": "详细分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_basic_info_prompt(url):
    """构建账号基础信息分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的基础信息设计。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 账号基础信息设计分析要点

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

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
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
    "analysis_process": {{
        "basic_info": {{
            "nickname": "昵称分析",
            "bio": "简介分析",
            "avatar": "头像分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_content_structure_prompt(url):
    """构建内容结构分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的内容结构。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 内容结构分析要点

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

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "content_analysis": {{
        "character_appearance": {{
            "percentage": "人物出镜视频占比",
            "no_character_percentage": "不出镜视频占比",
            "why_has_character": "为什么需要人物出镜",
            "why_no_character": "为什么没有人物出镜"
        }},
        "topic_distribution": {{
            "commercial_related": "与商业变现直接关联的内容占比",
            "daily_operation": "日常运营内容占比",
            "topic_details": "各类主题分布详情"
        }},
        "content_monetization_relation": "内容与变现的关联度"
    }},
    "analysis_process": {{
        "content_structure": {{
            "character": "人物出镜分析",
            "topics": "主题占比分析",
            "monetization": "变现关联分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_target_customer_prompt(url):
    """构建目标客户分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的目标客户画像。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 目标客户画像分析要点

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

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "target_customer": {{
        "age_range": "年龄阶段",
        "gender_ratio": "性别比例",
        "occupation": "职业/身份",
        "consumption_level": "消费能力",
        "region": "地域分布",
        "pain_points": "客户痛点",
        "needs": "客户需要的解决方案"
    }},
    "analysis_process": {{
        "target_customer": {{
            "features": "客户特征分析",
            "needs": "客户需求分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_keywords_prompt(url):
    """构建关键词布局分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的关键词布局。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 关键词布局分析要点

### 核心关键词（1-3个最主要的流量/转化关键词）
核心关键词应该直接与业务相关，是用户搜索最多、流量最大的词
- 如卖奶粉则核心关键词应包含"奶粉"相关
- 如灌香肠则核心关键词应包含"灌香肠"、"香肠"相关

### 产品关键词
- 行业关键词
- 品名词
- 品牌词

### 流量关键词
- 地域关键词
- 用途关键词
- 属性关键词
- 场景关键词

### 转化关键词
- 价格关键词
- 促销关键词
- 口碑关键词

### 关键词分布位置
- 昵称中的关键词
- 简介中的关键词
- 话题标签中的关键词
- 视频标题中的关键词

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "keyword_layout": {{
        "core_keywords": ["核心关键词1", "核心关键词2", "核心关键词3"],
        "product_keywords": {{
            "industry_keywords": ["行业词1", "行业词2"],
            "product_name_keywords": ["品名词1", "品名词2"],
            "brand_keywords": ["品牌词1", "品牌词2"]
        }},
        "traffic_keywords": {{
            "region_keywords": ["地域词1", "地域词2"],
            "usage_keywords": ["用途词1", "用途词2"],
            "attribute_keywords": ["属性词1", "属性词2"],
            "scene_keywords": ["场景词1", "场景词2"]
        }},
        "conversion_keywords": {{
            "price_keywords": ["价格词1", "价格词2"],
            "promotion_keywords": ["促销词1", "促销词2"],
            "reputation_keywords": ["口碑词1", "口碑词2"]
        }},
        "keyword_distribution": {{
            "in_nickname": "昵称中的关键词",
            "in_bio": "简介中的关键词",
            "in_tags": "话题标签中的关键词",
            "in_titles": "视频标题中的关键词"
        }}
    }},
    "analysis_process": {{
        "keywords": {{
            "content": "关键词列表",
            "analysis": "关键词布局分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_video_types_prompt(url):
    """构建视频类型分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的视频类型和内容风格。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 视频内容分析要点

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

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "video_types": {{
        "types": ["视频类型1", "视频类型2"],
        "distribution": "视频类型分布"
    }},
    "content_style": {{
        "tone": "整体内容调性",
        "shooting_style": "拍摄风格",
        "editing_style": "剪辑风格",
        "audio_style": "配音/配乐风格"
    }},
    "analysis_process": {{
        "video_types": {{
            "content": "视频类型分析",
            "analysis": "详细分析"
        }}
    }}
}}
```"""
    return prompt


def build_account_position_prompt(url, note):
    """构建账号定位分析提示词"""
    prompt = f"""你是一个资深的账号运营分析专家。请分析以下抖音账号的定位和人设打造。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

---

## 账号定位分析要点

### 7.1 账号类型
- 单业务账号还是多业务账号
- 主要业务和次要业务

### 7.2 人设打造
- 是否有IP人设
- 人设与业务的关联

---

## 输出格式要求

请严格按照以下JSON格式输出：

```json
{{
    "account_type": {{
        "type": "单业务/多业务",
        "main_business": "主要业务",
        "secondary_business": "次要业务"
    }},
    "persona": {{
        "has_ip": "是否有IP人设",
        "ip_description": "人设描述",
        "ip_business_relation": "人设与业务的关联"
    }},
    "analysis_process": {{
        "account_position": {{
            "type": "账号类型分析",
            "persona": "人设打造分析"
        }}
    }}
}}
```"""
    return prompt


# 模块提示词构建器映射
ACCOUNT_MODULE_PROMPT_BUILDERS = {
    'commercial': build_account_commercial_prompt,
    'basic_info': build_account_basic_info_prompt,
    'content_structure': build_account_content_structure_prompt,
    'target_customer': build_account_target_customer_prompt,
    'keywords': build_account_keywords_prompt,
    'video_types': build_account_video_types_prompt,
    'account_position': build_account_position_prompt
}


@knowledge_api.route('/account/analyze', methods=['POST'])
@login_required
def analyze_account():
    """账号分析接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        note = data.get('note', '').strip()
        use_browser = data.get('use_browser', False)  # 是否使用浏览器模式

        if not url:
            return jsonify({'code': 400, 'message': '请输入账号主页链接'})

        # 解析短链接，获取真实的主页链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[account_analyze] 原始链接: {url}, 解析后: {real_url}")

        # ========== 优先使用爬虫获取真实账号信息 ==========
        scraped_info = get_douyin_real_account_info(real_url, use_browser=use_browser)
        
        account_info_text = ""
        if scraped_info and scraped_info.get('nickname'):
            logger.info(f"[account_analyze] 爬虫获取到账号信息: {scraped_info.get('nickname')}")
            account_info_text = f"""
## 账号真实信息（从抖音页面抓取）
- 账号昵称：{scraped_info.get('nickname', '未知')}
- 账号简介：{scraped_info.get('bio', '无')}
- 粉丝数：{scraped_info.get('fans_count', '未知')}
- 关注数：{scraped_info.get('following_count', '未知')}
- 获赞数：{scraped_info.get('likes_count', '未知')}
- IP属地：{scraped_info.get('ip_location', '未知')}
- 头像URL：{scraped_info.get('avatar_url', '无')}
"""
        else:
            logger.warning(f"[account_analyze] 爬虫获取失败，将使用 LLM 推测")

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        # 构建提示词（加入真实账号信息）
        prompt = build_account_analysis_prompt(real_url, account_info_text)

        logger.info(f"[account_analyze] 开始分析: {real_url}")

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
            
            # 如果爬虫获取到了信息，也返回给前端
            if scraped_info:
                result_json['_scraped_info'] = scraped_info

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


@knowledge_api.route('/account/analyze-modules', methods=['POST'])
@login_required
def analyze_account_modules():
    """账号模块化分析接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        modules = data.get('modules', [])

        if not url:
            return jsonify({'code': 400, 'message': '请输入账号主页链接'})

        if not modules:
            return jsonify({'code': 400, 'message': '请选择至少一个分析模块'})

        # 解析短链接，获取真实的主页链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[account_analyze_modules] 原始链接: {url}, 解析后: {real_url}")

        # 验证模块有效性
        valid_modules = set(ACCOUNT_MODULES.keys())
        selected_modules = set(modules)
        invalid_modules = selected_modules - valid_modules
        if invalid_modules:
            return jsonify({'code': 400, 'message': f'无效的模块: {", ".join(invalid_modules)}'})

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        logger.info(f"[account_analyze_modules] 开始分析: {real_url}, 模块: {modules}")

        # 按顺序分析选中的模块
        results = {}
        analysis_process = {}

        for module in modules:
            prompt_builder = ACCOUNT_MODULE_PROMPT_BUILDERS.get(module)
            if not prompt_builder:
                continue

            prompt = prompt_builder(real_url, note)

            messages = [
                {"role": "system", "content": "你是一个专业的账号分析专家，擅长分析抖音账号的整体定位和运营策略。请严格按照JSON格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ]

            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)

            if result_text:
                try:
                    result_json = parse_llm_json(result_text)
                    results[module] = result_json

                    # 收集 analysis_process
                    if 'analysis_process' in result_json:
                        analysis_process.update(result_json['analysis_process'])

                except json.JSONDecodeError as e:
                    logger.warning(f"模块 {module} JSON解析失败: {e}")
                    results[module] = {'error': '解析失败', 'raw': result_text[:200]}
            else:
                results[module] = {'error': 'LLM 调用失败'}

        # 合并结果
        merged_result = {
            'account_name': results.get('commercial', {}).get('account_name', '') or results.get('basic_info', {}).get('account_name', ''),
            'analysis_process': analysis_process,
            'modules_results': results
        }

        # 添加各个模块的结果
        for module, result in results.items():
            if module == 'commercial':
                if 'commercial_positioning' in result:
                    merged_result['commercial_positioning'] = result['commercial_positioning']
            elif module == 'basic_info':
                if 'nickname_design' in result:
                    merged_result['nickname_design'] = result['nickname_design']
                if 'bio_design' in result:
                    merged_result['bio_design'] = result['bio_design']
                if 'avatar_design' in result:
                    merged_result['avatar_design'] = result['avatar_design']
            elif module == 'content_structure':
                if 'content_analysis' in result:
                    merged_result['content_analysis'] = result['content_analysis']
            elif module == 'target_customer':
                if 'target_customer' in result:
                    merged_result['target_customer'] = result['target_customer']
            elif module == 'keywords':
                if 'keyword_layout' in result:
                    merged_result['keyword_layout'] = result['keyword_layout']
            elif module == 'video_types':
                if 'video_types' in result:
                    merged_result['video_types'] = result['video_types']
                if 'content_style' in result:
                    merged_result['content_style'] = result['content_style']
            elif module == 'account_position':
                if 'account_type' in result:
                    merged_result['account_type'] = result['account_type']
                if 'persona' in result:
                    merged_result['persona'] = result['persona']

        # 从商业定位模块提取账号名称
        if 'commercial_positioning' in merged_result:
            # 尝试从其他模块获取账号名称
            for module, result in results.items():
                if 'account_name' in result and result['account_name']:
                    merged_result['account_name'] = result['account_name']
                    break

        logger.info(f"[account_analyze_modules] 模块分析完成: {url}, 完成模块: {list(results.keys())}")

        return jsonify({
            'code': 200,
            'message': '分析成功',
            'data': merged_result
        })

    except Exception as e:
        logger.error(f"账号模块分析失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        })


# ========== 电子书分析相关接口 ==========

import uuid
from datetime import datetime

# 电子书分析模块定义
EBOOK_MODULES = {
    'keywords': {
        'name': '关键词库',
        'order': 1,
        'description': '标题关键词、简介关键词、标签关键词'
    },
    'topic': {
        'name': '选题库',
        'order': 2,
        'description': '爆款选题、选题角度、时效性'
    },
    'template': {
        'name': '内容模板',
        'order': 3,
        'description': '开头钩子、内容结构、结尾引导'
    },
    'operation': {
        'name': '运营规划',
        'order': 4,
        'description': '账号起名、简介、头像、发布时机、互动策略'
    },
    'market': {
        'name': '市场分析',
        'order': 5,
        'description': '用户画像、竞品分析、痛点需求、变现模式'
    }
}

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


# ========== 电子书分析各模块独立提示词构建函数 ==========

def build_ebook_keywords_prompt(ebook_text, filename):
    """构建电子书关键词库分析提示词"""
    prompt = f"""你是一个知识管理专家。请从以下电子书中提取关键词库相关的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则：

### 关键词库
- 标题关键词选择逻辑
- 简介关键词布局
- 评论区关键词引导
- 标签关键词优化

## 输出格式
请严格按照以下JSON格式输出：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点",
    "rules": [
        {{
            "category": "keywords",
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


def build_ebook_topic_prompt(ebook_text, filename):
    """构建电子书选题库分析提示词"""
    prompt = f"""你是一个知识管理专家。请从以下电子书中提取选题库相关的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则：

### 选题库
- 爆款选题方向
- 选题角度和切入点
- 选题时效性把握
- 选题与热点结合

## 输出格式
请严格按照以下JSON格式输出：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点",
    "rules": [
        {{
            "category": "topic",
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


def build_ebook_template_prompt(ebook_text, filename):
    """构建电子书内容模板分析提示词"""
    prompt = f"""你是一个知识管理专家。请从以下电子书中提取内容模板相关的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则：

### 内容模板
- 开头钩子设计
- 内容结构模式
- 结尾引导设计
- 情绪调动技巧

## 输出格式
请严格按照以下JSON格式输出：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点",
    "rules": [
        {{
            "category": "template",
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


def build_ebook_operation_prompt(ebook_text, filename):
    """构建电子书运营规划分析提示词"""
    prompt = f"""你是一个知识管理专家。请从以下电子书中提取运营规划相关的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则（重点提取）：

### 运营规划
- **账号起名** - 如何起一个好记、有辨识度的名字
- **账号简介** - 简介怎么写吸引人
- **头像设计** - 头像选择建议
- **主页装修** - 背景图、置顶视频等
- **发布时机** - 什么时候发布效果最好
- **互动策略** - 评论区互动、回复技巧
- **粉丝运营** - 粉丝群运营、粉丝粘性提升
- **数据复盘** - 如何分析数据优化内容

## 输出格式
请严格按照以下JSON格式输出：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点",
    "rules": [
        {{
            "category": "operation",
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


def build_ebook_market_prompt(ebook_text, filename):
    """构建电子书市场分析提示词"""
    prompt = f"""你是一个知识管理专家。请从以下电子书中提取市场分析相关的规则和知识。

## 待分析电子书
- 文件名：{filename}
- 内容长度：约 {len(ebook_text)} 字符

## 电子书内容
```
{ebook_text[:15000]}
```
{"...（内容过长，已截断）" if len(ebook_text) > 15000 else ""}

## 分析要求
请从以下分类中提取规则（重点提取）：

### 市场分析
- **市场分析报告** - 行业现状和趋势
- **目标用户画像** - 目标受众特征分析
- **竞品分析** - 竞争对手研究
- **市场趋势** - 未来发展方向预测
- **用户痛点** - 目标用户的核心需求
- **变现模式** - 商业模式和变现路径

## 输出格式
请严格按照以下JSON格式输出：

```json
{{
    "book_title": "书名",
    "core_knowledge": "本书核心知识要点",
    "rules": [
        {{
            "category": "market",
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


# 电子书模块提示词构建器映射
EBOOK_MODULE_PROMPT_BUILDERS = {
    'keywords': build_ebook_keywords_prompt,
    'topic': build_ebook_topic_prompt,
    'template': build_ebook_template_prompt,
    'operation': build_ebook_operation_prompt,
    'market': build_ebook_market_prompt
}


@knowledge_api.route('/ebook/analyze', methods=['POST'])
@login_required
def analyze_ebook():
    """分析电子书接口"""
    try:
        data = request.get_json()
        file_ids = data.get('file_ids', [])
        modules = data.get('modules', [])  # 支持模块化分析

        if not file_ids:
            return jsonify({'code': 400, 'message': '请选择要分析的文件'})

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        all_rules = []
        modules_results = {}

        # 判断是完整分析还是模块分析
        use_module_analysis = len(modules) > 0

        # 如果使用模块分析，验证模块有效性
        if use_module_analysis:
            valid_modules = set(EBOOK_MODULES.keys())
            selected_modules = set(modules)
            invalid_modules = selected_modules - valid_modules
            if invalid_modules:
                return jsonify({'code': 400, 'message': f'无效的模块: {", ".join(invalid_modules)}'})

        for file_id in file_ids:
            ebook = ebook_storage.get(file_id)
            if not ebook:
                continue

            text = ebook.get('text', '').strip()
            if not text:
                continue

            if use_module_analysis:
                # 模块化分析
                for module in modules:
                    prompt_builder = EBOOK_MODULE_PROMPT_BUILDERS.get(module)
                    if not prompt_builder:
                        continue

                    prompt = prompt_builder(text, ebook['filename'])

                    logger.info(f"[ebook_analyze] 开始分析: {ebook['filename']}, 模块: {module}")

                    messages = [
                        {"role": "system", "content": "你是一个专业的知识管理专家，擅长从书籍中提取可落地的规则。请严格按照JSON格式输出。"},
                        {"role": "user", "content": prompt}
                    ]

                    result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)

                    if result_text:
                        try:
                            result_json = parse_llm_json(result_text)
                            rules = result_json.get('rules', [])
                            for rule in rules:
                                rule['source_file'] = ebook['filename']
                            all_rules.extend(rules)

                            # 保存模块结果
                            if module not in modules_results:
                                modules_results[module] = []
                            modules_results[module].extend(rules)

                        except (json.JSONDecodeError, Exception) as e:
                            logger.error(f"解析失败: {e}")
                            continue
            else:
                # 完整分析
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
                'rules': all_rules,
                'modules': modules if use_module_analysis else list(EBOOK_MODULES.keys()),
                'modules_results': modules_results
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


# ========== 爆款拆解相关接口 ==========

@knowledge_api.route('/account/basic-info', methods=['POST'])
@login_required
def get_account_basic_info():
    """获取账号基础信息（仅昵称等基本信息）"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        use_browser = data.get('use_browser', False)

        if not url:
            return jsonify({'code': 400, 'message': '请输入账号主页链接'})

        # 解析短链接，获取真实的主页链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[get_account_basic_info] 原始链接: {url}, 解析后: {real_url}")

        # ========== 优先使用爬虫获取真实账号信息 ==========
        scraped_info = get_douyin_real_account_info(real_url, use_browser=use_browser)
        
        if scraped_info and scraped_info.get('nickname'):
            logger.info(f"[get_account_basic_info] 爬虫获取到账号: {scraped_info.get('nickname')}")
            return jsonify({
                'code': 200,
                'message': '获取成功',
                'data': {
                    'account_name': scraped_info.get('nickname', ''),
                    'bio': scraped_info.get('bio', ''),
                    'avatar_url': scraped_info.get('avatar_url', ''),
                    'fans_count': scraped_info.get('fans_count', ''),
                    'following_count': scraped_info.get('following_count', ''),
                    'likes_count': scraped_info.get('likes_count', ''),
                    'ip_location': scraped_info.get('ip_location', ''),
                    'source': 'scraper'  # 标记数据来源
                }
            })
        
        # 如果爬虫失败，回退到 LLM 推测
        logger.warning(f"[get_account_basic_info] 爬虫获取失败，使用 LLM 推测")

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        logger.info(f"[get_account_basic_info] LLM推测: {real_url}")

        # 构建简单的账号信息获取提示词
        prompt = f"""你是一个账号信息提取助手。请从以下抖音账号主页链接中提取基础信息。

## 待分析账号
- 账号主页链接：{real_url}

## 任务
请返回以下JSON格式的信息（只需要最基础的信息）：
1. 账号昵称（account_name）
2. 简介（bio）
3. 头像描述（avatar_description）

如果无法直接获取，请根据链接特点推断或返回空值。

## 输出格式
请严格按照以下JSON格式输出：
```json
{{
    "account_name": "账号昵称",
    "bio": "账号简介",
    "avatar_description": "头像描述"
}}
```

请只输出JSON，不要有其他内容。"""

        messages = [
            {"role": "system", "content": "你是一个账号信息提取助手，擅长从链接中提取账号信息。请严格按照JSON格式输出。"},
            {"role": "user", "content": prompt}
        ]

        result_text = llm_service.chat(messages, temperature=0.3, max_tokens=500)

        if not result_text:
            return jsonify({'code': 500, 'message': '获取账号信息失败'})

        # 调试日志：查看 LLM 返回的原始结果
        logger.info(f"[get_account_basic_info] LLM原始返回: {result_text[:500]}")

        # 提取 JSON
        try:
            result_json = parse_llm_json(result_text)

            account_name = result_json.get('account_name', '')
            # 如果账号名称为空，尝试从 URL 中提取账号 ID 作为名称
            if not account_name:
                # 从解析后的真实链接中提取账号 ID
                match = re.search(r'/user/([A-Za-z0-9_-]+)', real_url)
                if match:
                    account_name = f"账号_{match.group(1)[:8]}"
                else:
                    account_name = "未知账号"

            logger.info(f"[get_account_basic_info] 获取成功: {account_name}")

            return jsonify({
                'code': 200,
                'message': '获取成功',
                'data': {
                    'account_name': account_name,
                    'bio': result_json.get('bio', ''),
                    'avatar_description': result_json.get('avatar_description', ''),
                    'url': real_url
                }
            })

        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 内容: {result_text[:500]}")
            return jsonify({
                'code': 500,
                'message': '解析失败，请重试'
            })

    except Exception as e:
        logger.error(f"获取账号信息失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        })


@knowledge_api.route('/content/basic-info', methods=['POST'])
@login_required
def get_content_basic_info():
    """获取内容（视频/图文）基础信息"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        use_browser = data.get('use_browser', True)  # 默认使用浏览器模式

        if not url:
            return jsonify({'code': 400, 'message': '请输入内容链接'})

        # 解析短链接，获取真实的内容链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[get_content_basic_info] 原始链接: {url}, 解析后: {real_url}")

        # ========== 使用爬虫获取内容信息 ==========
        scraped_info = get_douyin_video_content_info(real_url, use_browser=use_browser)

        if scraped_info and scraped_info.get('title'):
            logger.info(f"[get_content_basic_info] 爬虫获取到内容: {scraped_info.get('title')}")
            return jsonify({
                'code': 200,
                'message': '获取成功',
                'data': {
                    'title': scraped_info.get('title', ''),
                    'description': scraped_info.get('description', ''),
                    'author': scraped_info.get('author', ''),
                    'hashtags': scraped_info.get('hashtags', []),
                    'url': scraped_info.get('url', real_url),
                    'source': 'scraper'
                }
            })

        # 如果爬虫失败，返回提示
        logger.warning(f"[get_content_basic_info] 爬虫获取失败，将使用 LLM 分析")
        return jsonify({
            'code': 200,
            'message': '获取成功（使用LLM分析）',
            'data': {
                'title': '',
                'description': '',
                'author': '',
                'hashtags': [],
                'url': real_url,
                'source': 'llm'
            }
        })

    except Exception as e:
        logger.error(f"获取内容信息失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'获取失败: {str(e)}'
        })
@login_required
@knowledge_api.route('/analyze-with-account', methods=['POST'])
def analyze_content_with_account():
    """带账号上下文的内容分析接口"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        content_type = data.get('content_type', 'auto')
        note = data.get('note', '').strip()
        modules = data.get('modules', [])
        account_info = data.get('account_info')
        content_info = data.get('content_info')  # 爬虫获取的内容信息

        if not url:
            return jsonify({'code': 400, 'message': '请输入内容链接'})

        # 解析短链接，获取真实的内容链接
        real_url = resolve_douyin_short_url(url)
        logger.info(f"[analyze_with_account] 原始链接: {url}, 解析后: {real_url}")

        # 获取 LLM 服务
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        logger.info(f"[analyze_with_account] 开始分析: {real_url}")

        # 如果选择了模块，使用模块化分析（受分析维度管理控制）
        if modules and len(modules) > 0:
            # 只保留在「内容分析」分类下启用的维度对应的 code
            filtered_modules = filter_modules_by_active_dimensions(
                modules, category="content"
            )
            return analyze_modules_with_account(
                real_url, content_type, note, filtered_modules, account_info, content_info
            )

        # 完整分析
        prompt = build_analysis_prompt_with_account(real_url, content_type, note, account_info)

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

            # 清理标题中的抖音元数据
            cleaned_title = ''
            if 'title' in result_json and result_json['title']:
                title = result_json['title']
                cleaned_title = re.sub(r'^[\d.]+\s*BTL:?\s*[\w@.\/]+\s*\d{2}\/\d{2}\s*', '', title)
                cleaned_title = re.sub(r'^[\d.]+\s*复制打开抖音，看看【[^】]+】', '', cleaned_title)
                cleaned_title = re.sub(r'\s*https?:\/\/v\.douyin\.com\/[^\s]+.*$', '', cleaned_title)
                result_json['title'] = cleaned_title

            # 对标题进行关键词分类和评分
            if cleaned_title:
                try:
                    from utils.title_classifier import TitleKeywordClassifier
                    title_classification = TitleKeywordClassifier.get_keywords_summary(cleaned_title)
                    title_structure_display = TitleKeywordClassifier.get_title_structure_display(cleaned_title)
                    title_scores = TitleKeywordClassifier.calculate_scores(cleaned_title)

                    if 'analysis_process' not in result_json:
                        result_json['analysis_process'] = {}
                    if 'title' not in result_json['analysis_process']:
                        result_json['analysis_process']['title'] = {}
                    result_json['analysis_process']['title']['keyword_classification'] = title_classification
                    result_json['analysis_process']['title']['title_structure_display'] = title_structure_display
                    result_json['analysis_process']['title']['title_scores'] = title_scores
                except Exception as e:
                    logger.warning(f"标题关键词分类或评分失败: {e}")

            logger.info(f"[analyze_with_account] 分析完成，找到 {len(result_json.get('rules', []))} 条规则")

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


def build_analysis_prompt_with_account(url, content_type, note, account_info):
    """构建带账号上下文的分析提示词"""

    # 构建账号上下文信息
    account_context = ""
    if account_info:
        account_context = f"""
## 账号上下文信息
- 账号名称：{account_info.get('name', '未知')}
- 账号主页：{account_info.get('url', '')}
"""
        if account_info.get('basic_info'):
            basic = account_info['basic_info']
            if basic.get('bio'):
                account_context += f"- 账号简介：{basic.get('bio')}\n"
            if basic.get('commercial_positioning'):
                cp = basic['commercial_positioning']
                account_context += f"- 变现方式：{cp.get('monetization_method', '')}\n"
            if basic.get('target_customer'):
                tc = basic['target_customer']
                account_context += f"- 目标客户：{tc.get('occupation', '')}，{tc.get('age_range', '')}\n"
            if basic.get('keyword_layout'):
                kw = basic['keyword_layout']
                # 优先使用 core_keywords，如果没有则使用 top_50_keywords 兼容旧数据
                core_kw = kw.get('core_keywords') or kw.get('top_50_keywords', [])
                if core_kw:
                    account_context += f"- 核心关键词：{', '.join(core_kw[:10])}\n"

    prompt = f"""你是一个资深的短视频内容拆解专家。请从专业运营角度完整拆解以下抖音内容，提取可复用的爆款逻辑和规则。

## 待分析内容
- 链接：{url}
- 内容类型：{content_type}
- 补充说明：{note}
{account_context}

---

## 一、标题结构分析

### 1.1 标题关键词组合
- 流量关键词/核心业务关键词/科普关键词/数字/情绪词

### 1.2 标题为什么有效
- 击中用户什么需求？
- 和竞品比有什么独特性？

---

## 二、选题分析

### 2.1 选题方向

### 2.2 目标人群（结合账号信息分析）
- 细分场景人群
- 长尾需求人群
- 痛点/情绪/功能价值/独特性

---

## 三、内容结构拆解
- 开头钩子（前3秒）
- 视频内容节奏
- 脚本模型

---

## 四、用户心理分析
- 利用的心理：恐惧/追求/规避/损失厌恶/从众
- 为什么招人喜欢

---

## 五、商业目的分析
- 商业目的：品牌宣传/引流获客/产品销售/IP打造
- 细分市场

---

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
    "title": "内容标题",
    "author": "作者/账号名",
    "title_analysis": {{
        "structure": "标题结构分析",
        "keyword_types": {{
            "flow_keywords": "流量关键词",
            "business_keywords": "核心业务关键词",
            "knowledge_keywords": "科普关键词",
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
            "pain_point": "痛点",
            "emotion": "情绪",
            "functional_value": "功能价值",
            "uniqueness": "独特性"
        }}
    }},
    "content_structure": {{
        "hook": "开头钩子类型",
        "rhythm": "内容节奏",
        "script_model": "脚本模型类型"
    }},
    "psychology_analysis": {{
        "psychology_used": ["利用的心理"],
        "why_appealing": {{
            "useful": "有用",
            "interesting": "有趣",
            "resonance": "共鸣"
        }}
    }},
    "commercial_purpose": {{
        "purpose": "商业目的",
        "target_market": "目标细分市场"
    }},
    "rules": [
        {{
            "category": "规则分类",
            "title": "规则标题",
            "description": "规则描述",
            "is_good": true,
            "recommendation": "推荐",
            "score": 8
        }}
    ]
}}
```

请先理解这个内容，然后进行全面深度分析。"""

    return prompt


def analyze_modules_with_account(url, content_type, note, modules, account_info, content_info=None):
    """带账号上下文的模块化分析"""
    try:
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        # 需要账号信息的模块
        account_dependent_modules = {'psychology', 'commercial', 'character', 'content_form', 'why_popular'}

        # 按顺序分析选中的模块
        results = {}
        analysis_process = {}

        # 如果有爬虫获取的内容信息，将其融入note中
        enhanced_note = note
        if content_info:
            # 将爬虫获取的信息添加到备注中
            scraped_parts = []
            if content_info.get('title'):
                scraped_parts.append(f"视频标题: {content_info.get('title')}")
            if content_info.get('description'):
                scraped_parts.append(f"视频描述: {content_info.get('description')}")
            if content_info.get('hashtags'):
                hashtags_str = ' '.join(content_info.get('hashtags', []))
                scraped_parts.append(f"话题标签: {hashtags_str}")
            if content_info.get('author'):
                scraped_parts.append(f"作者: {content_info.get('author')}")

            if scraped_parts:
                enhanced_note = f"{note}\n\n【爬取信息】\n" + "\n".join(scraped_parts) if note else "【爬取信息】\n" + "\n".join(scraped_parts)
                logger.info(f"[analyze_modules_with_account] 使用爬取信息: {scraped_parts[:2]}")

        for module in modules:
            prompt_builder = MODULE_PROMPT_BUILDERS.get(module)
            if not prompt_builder:
                continue

            # 检查需要账号上下文
            if module in account_dependent_modules and account_info:
                prompt = build_module_prompt_with_account(module, url, enhanced_note, account_info)
            else:
                prompt = prompt_builder(url, enhanced_note)

            messages = [
                {"role": "system", "content": "你是一个专业的内容分析专家。请严格按照JSON格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ]

            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)

            if result_text:
                try:
                    result_json = parse_llm_json(result_text)

                    # 如果是标题模块，清理标题中的抖音元数据
                    if module == 'title' and 'title' in result_json:
                        cleaned_title = result_json['title']
                        cleaned_title = re.sub(r'^[\d.]+\s*BTL:?\s*[\w@.\/]+\s*\d{2}\/\d{2}\s*', '', cleaned_title)
                        cleaned_title = re.sub(r'^[\d.]+\s*复制打开抖音，看看【[^】]+】', '', cleaned_title)
                        cleaned_title = re.sub(r'\s*https?:\/\/v\.douyin\.com\/[^\s]+.*$', '', cleaned_title)
                        result_json['title'] = cleaned_title

                        try:
                            from utils.title_classifier import TitleKeywordClassifier
                            title_classification = TitleKeywordClassifier.get_keywords_summary(cleaned_title)
                            title_structure_display = TitleKeywordClassifier.get_title_structure_display(cleaned_title)
                            title_scores = TitleKeywordClassifier.calculate_scores(cleaned_title)

                            if 'analysis_process' not in result_json:
                                result_json['analysis_process'] = {}
                            if 'title' not in result_json['analysis_process']:
                                result_json['analysis_process']['title'] = {}
                            result_json['analysis_process']['title']['keyword_classification'] = title_classification
                            result_json['analysis_process']['title']['title_structure_display'] = title_structure_display
                            result_json['analysis_process']['title']['title_scores'] = title_scores
                        except Exception as e:
                            logger.warning(f"标题关键词分类或评分失败: {e}")

                    results[module] = result_json

                    if 'analysis_process' in result_json:
                        analysis_process.update(result_json['analysis_process'])

                except json.JSONDecodeError as e:
                    logger.warning(f"模块 {module} JSON解析失败: {e}")
                    results[module] = {'error': '解析失败', 'raw': result_text[:200]}
            else:
                results[module] = {'error': 'LLM 调用失败'}

        # 合并结果
        merged_result = {
            'title': results.get('title', {}).get('title', ''),
            'author': account_info.get('name', '') if account_info else '',
            'content_type': 'video',
            'analysis_process': analysis_process,
            'modules_results': results
        }

        # 添加各个模块的结果
        for module, result in results.items():
            if module == 'title':
                if 'title_analysis' in result:
                    merged_result['title_analysis'] = result['title_analysis']
            elif module == 'topic':
                if 'topic_analysis' in result:
                    merged_result['topic_analysis'] = result['topic_analysis']
            elif module == 'content':
                if 'content_structure' in result:
                    merged_result['content_structure'] = result['content_structure']
            elif module == 'psychology':
                if 'psychology_analysis' in result:
                    merged_result['psychology_analysis'] = result['psychology_analysis']
            elif module == 'commercial':
                if 'commercial_purpose' in result:
                    merged_result['commercial_purpose'] = result['commercial_purpose']
            elif module == 'character':
                if 'character_design' in result:
                    merged_result['character_design'] = result['character_design']
            elif module == 'content_form':
                if 'content_form' in result:
                    merged_result['content_form'] = result['content_form']
            elif module == 'tags':
                if 'tag_strategy' in result:
                    merged_result['tag_strategy'] = result['tag_strategy']
            elif module == 'why_popular':
                if 'why_popular' in result:
                    merged_result['why_popular'] = result['why_popular']
            elif module == 'interaction':
                if 'interaction_analysis' in result:
                    merged_result['interaction_analysis'] = result['interaction_analysis']
            elif module == 'ending':
                if 'ending_analysis' in result:
                    merged_result['ending_analysis'] = result['ending_analysis']
            elif module == 'cover':
                if 'cover_analysis' in result:
                    merged_result['cover_analysis'] = result['cover_analysis']

        logger.info(f"[analyze_modules_with_account] 模块分析完成: {url}, 完成模块: {list(results.keys())}")

        # ========== AI 额外给出分析维度的建议 ==========
        try:
            dimensions_hint = get_ai_dimension_suggestions(url, results, content_info)
            if dimensions_hint:
                merged_result['ai_dimension_suggestions'] = dimensions_hint
                logger.info(f"[analyze_modules_with_account] 获取到 {len(dimensions_hint)} 条AI分析维度建议")
        except Exception as e:
            logger.warning(f"[analyze_modules_with_account] 获取AI维度建议失败: {e}")

        # 如果有爬虫获取的内容信息，将其添加到结果中
        if content_info:
            if content_info.get('title') and not merged_result.get('title'):
                merged_result['title'] = content_info.get('title')
            if content_info.get('author') and not merged_result.get('author'):
                merged_result['author'] = content_info.get('author')
            merged_result['scraped_info'] = content_info

        return jsonify({
            'code': 200,
            'message': '分析成功',
            'data': merged_result
        })

    except Exception as e:
        logger.error(f"模块分析失败: {e}", exc_info=True)
        return jsonify({
            'code': 500,
            'message': f'分析失败: {str(e)}'
        })


def get_ai_dimension_suggestions(url, module_results, content_info=None):
    """让 AI 额外给出更多分析维度的建议"""
    try:
        llm_service = get_llm_service()
        if not llm_service:
            return None

        # 提取已分析的模块信息
        analyzed_modules = list(module_results.keys())

        # 构建已分析的内容摘要
        content_summary_parts = []
        for module, result in module_results.items():
            if isinstance(result, dict):
                # 提取关键信息
                module_key = f"{module}_analysis"
                if module_key in result:
                    content_summary_parts.append(f"【{module}】{str(result[module_key])[:200]}")

        content_summary = "\n\n".join(content_summary_parts[:5])  # 限制长度

        # 爬取的内容信息
        extra_info = ""
        if content_info:
            if content_info.get('title'):
                extra_info += f"- 视频标题：{content_info.get('title')}\n"
            if content_info.get('description'):
                desc = content_info.get('description')[:300]
                extra_info += f"- 视频描述：{desc}...\n"
            if content_info.get('hashtags'):
                extra_info += f"- 话题标签：{', '.join(content_info.get('hashtags', [])[:10])}\n"

        prompt = f"""基于以下已完成的分析，请给出更多可用的分析维度建议。

## 已分析的维度
{', '.join(analyzed_modules)}

## 已分析的内容摘要
{content_summary}

## 额外信息
{extra_info if extra_info else '无'}

请给出2-4个可以进一步分析的角度，每个角度用一句话说明。
要求：
1. 必须是已分析维度之外的新角度
2. 要具体、可执行
3. 优先考虑内容本身的特点

请以JSON数组格式返回，每项包含：
- dimension: 维度英文标识
- name: 中文名称
- reason: 为什么建议分析这个维度
"""
        messages = [
            {"role": "system", "content": "你是一个专业的内容分析专家，擅长发现内容的分析角度。请严格按照JSON格式输出。"},
            {"role": "user", "content": prompt}
        ]

        result_text = llm_service.chat(messages, temperature=0.7, max_tokens=1000)

        if not result_text:
            return None

        # 解析 JSON
        suggestions = parse_llm_json(result_text)
        if isinstance(suggestions, list):
            return suggestions
        return None

    except Exception as e:
        logger.warning(f"[get_ai_dimension_suggestions] 获取AI维度建议失败: {e}")
        return None


def build_module_prompt_with_account(module, url, note, account_info):
    """为需要账号信息的模块构建带上下文的提示词"""
    # 基础账号信息
    account_context = f"""
## 账号上下文信息
- 账号名称：{account_info.get('name', '未知')}
- 账号主页：{account_info.get('url', '')}
"""
    if account_info.get('basic_info'):
        basic = account_info['basic_info']
        if basic.get('bio'):
            account_context += f"- 账号简介：{basic.get('bio')}\n"
        if basic.get('commercial_positioning'):
            cp = basic['commercial_positioning']
            account_context += f"- 变现方式：{cp.get('monetization_method', '')}\n"
            account_context += f"- 卖货策略：{cp.get('sales_strategy', '')}\n"
        if basic.get('target_customer'):
            tc = basic['target_customer']
            account_context += f"- 目标客户年龄：{tc.get('age_range', '')}\n"
            account_context += f"- 目标客户职业：{tc.get('occupation', '')}\n"
            account_context += f"- 客户痛点：{tc.get('pain_points', '')}\n"
        if basic.get('keyword_layout'):
            kw = basic['keyword_layout']
            # 优先使用 core_keywords，如果没有则使用 top_50_keywords 兼容旧数据
            core_kw = kw.get('core_keywords') or kw.get('top_50_keywords', [])
            if core_kw:
                account_context += f"- 核心关键词：{', '.join(core_kw[:10])}\n"

    # 心理分析模块
    if module == 'psychology':
        prompt = f"""你是一个资深的短视频用户心理分析专家。请结合账号信息分析以下内容利用了哪些用户心理。

## 待分析内容
- 链接：{url}
- 补充说明：{note}
{account_context}

---

## 心理分析要点

### 1. 利用了什么心理
- 恐惧/追求/规避/损失厌恶/从众心理

### 2. 为什么招人喜欢
- 有用/有趣/共鸣

---

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
    "psychology_analysis": {{
        "psychology_used": ["利用的心理1", "利用的心理2"],
        "why_appealing": {{
            "useful": "有用",
            "interesting": "有趣",
            "resonance": "共鸣"
        }}
    }}
}}
```"""
        return prompt

    # 商业目的模块
    if module == 'commercial':
        prompt = f"""你是一个资深的短视频商业目的分析专家。请结合账号信息分析以下内容的商业目的。

## 待分析内容
- 链接：{url}
- 补充说明：{note}
{account_context}

---

## 商业目的分析要点

### 1. 商业目的
- 品牌宣传/引流获客/产品销售/IP打造

### 2. 细分市场
- 内容主题切的是什么细分市场？

### 3. 爆款元素
- 选题结合了什么爆款元素？

---

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
    "commercial_purpose": {{
        "purpose": "商业目的",
        "target_market": "目标细分市场",
        "viral_elements": "爆款元素"
    }}
}}
```"""
        return prompt

    # 爆款原因模块
    if module == 'why_popular':
        prompt = f"""你是一个资深的爆款内容分析专家。请结合账号信息分析以下抖音内容为什么能成为爆款。

## 待分析内容
- 链接：{url}
- 补充说明：{note}
{account_context}

---

## 爆款原因分析要点

### 1. 为什么这么多人喜欢
- 内容本身好在哪里？
- 击中什么需求？

### 2. 为什么互动会好
- 引发评论的点是什么？

### 3. 为什么愿意分享
- 什么让人想转发？

---

## 输出格式

请严格按照以下JSON格式输出：

```json
{{
    "why_popular": {{
        "why_liked": "为什么多人喜欢",
        "why_good_interaction": "为什么互动好",
        "why_share": "为什么愿意分享"
    }}
}}
```"""
        return prompt

    # 其他模块使用默认提示词
    prompt_builder = MODULE_PROMPT_BUILDERS.get(module)
    if prompt_builder:
        return prompt_builder(url, note)

    return ""


# ========== 手动录入相关接口 ==========

@knowledge_api.route('/accounts', methods=['GET'])
@login_required
def get_accounts():
    """获取账号列表"""
    try:
        # 获取查询参数
        platform = request.args.get('platform')
        status = request.args.get('status')
        search = request.args.get('search')
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)

        # 构建查询
        query = KnowledgeAccount.query
        if platform:
            query = query.filter(KnowledgeAccount.platform == platform)
        if status:
            query = query.filter(KnowledgeAccount.status == status)
        if search:
            query = query.filter(KnowledgeAccount.name.ilike(f'%{search}%'))

        # 获取总数
        total = query.count()

        # 分页
        accounts = query.order_by(KnowledgeAccount.updated_at.desc()).paginate(
            page=page, per_page=page_size, error_out=False
        )

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'items': [{
                    'id': acc.id,
                    'name': acc.name,
                    'platform': acc.platform,
                    'url': acc.url,
                    'current_data': acc.current_data,
                    'status': acc.status,
                    'created_at': acc.created_at.isoformat() if acc.created_at else None,
                    'updated_at': acc.updated_at.isoformat() if acc.updated_at else None,
                    # 详细信息
                    'business_type': acc.business_type,
                    'product_type': acc.product_type,
                    'service_type': acc.service_type,
                    'service_range': acc.service_range,
                    'target_area': acc.target_area,
                    'brand_type': acc.brand_type,
                    'language_style': acc.language_style,
                    'target_user': acc.target_user,
                    'main_product': acc.main_product,
                    # 内容布局字段
                    'content_persona': acc.content_persona,
                    'content_topic': acc.content_topic,
                    'content_daily': acc.content_daily,
                    # 内容布局（文本描述）
                    'persona_type': acc.persona_type,
                    'topic_content': acc.topic_content,
                    'daily_operation': acc.daily_operation
                } for acc in accounts.items],
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': accounts.pages
            }
        })
    except Exception as e:
        logger.error(f"获取账号列表失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>', methods=['GET'])
@login_required
def get_account(account_id):
    """获取单个账号详情"""
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})
        
        # 刷新session确保获取最新数据（任务队列在独立线程中更新了数据）
        db.session.expire_all()
        
        # 强制刷新并检查原始数据库数据
        db.session.flush()
        
        # 检查 analysis_result
        analysis_result = account.analysis_result
        has_sub_cat = 'sub_category_analysis' in (analysis_result or {})
        
        # 将调试信息加入响应（生产环境可移除）
        debug_info = {
            'has_sub_category_analysis': has_sub_cat,
            'sub_category_keys': list(analysis_result.get('sub_category_analysis', {}).keys()) if isinstance(analysis_result, dict) and has_sub_cat else []
        }
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'debug': debug_info,
            'data': {
                'id': account.id,
                'name': account.name,
                'platform': account.platform,
                'url': account.url,
                'current_data': account.current_data,
                'status': account.status,
                'created_at': account.created_at.isoformat() if account.created_at else None,
                'updated_at': account.updated_at.isoformat() if account.updated_at else None,
                # 详细信息
                'business_type': account.business_type,
                'product_type': account.product_type,
                'service_type': account.service_type,
                'service_range': account.service_range,
                'target_area': account.target_area,
                'brand_type': account.brand_type,
                'language_style': account.language_style,
                'target_user': account.target_user,
                'main_product': account.main_product,
                # 账号分析增强字段
                'core_business': account.core_business,
                'core_keywords': account.core_keywords,
                'keyword_types': account.keyword_types,
                'account_positioning': account.account_positioning,
                'content_strategy': account.content_strategy,
                'target_audience': account.target_audience,
                'analysis_result': account.analysis_result,
                # 人设定位和商业定位
                'persona_role': account.persona_role,
                'commercial_positioning': account.commercial_positioning,
                'monetization_type': account.monetization_type,
                # 内容布局字段
                'content_persona': account.content_persona,
                'content_topic': account.content_topic,
                'content_daily': account.content_daily,
                # 内容布局（文本描述）
                'persona_type': account.persona_type,
                'topic_content': account.topic_content,
                'daily_operation': account.daily_operation,
                # 自动分析配置
                'auto_analysis_config': account.auto_analysis_config,
                # 增量分析控制字段
                'analysis_status': {
                    'nickname_analyzed_at': account.nickname_analyzed_at.isoformat() if account.nickname_analyzed_at else None,
                    'bio_analyzed_at': account.bio_analyzed_at.isoformat() if account.bio_analyzed_at else None,
                    'other_analyzed_at': account.other_analyzed_at.isoformat() if account.other_analyzed_at else None,
                    'last_nickname': account.last_nickname,
                    'last_bio': account.last_bio,
                    'current_nickname': account.name,
                    'current_bio': account.current_data.get('bio', '') if account.current_data else ''
                }
            }
        })
    except Exception as e:
        logger.error(f"获取账号详情失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/accounts', methods=['POST'])
@login_required
def create_account():
    """创建账号"""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        platform = data.get('platform', '').strip()
        url = data.get('url', '').strip()
        current_data = data.get('current_data', {})

        if not name:
            return jsonify({'code': 400, 'message': '请输入账号名称'})

        # 创建账号
        account = KnowledgeAccount(
            name=name,
            platform=platform,
            url=url,
            current_data=current_data,
            status='active',
            # 详细信息
            business_type=data.get('business_type'),
            product_type=data.get('product_type'),
            service_type=data.get('service_type'),
            service_range=data.get('service_range'),
            target_area=data.get('target_area') or '全国',
            brand_type=data.get('brand_type'),
            language_style=data.get('language_style'),
            target_user=data.get('target_user'),
            main_product=data.get('main_product'),
            # 账号定位新增字段
            persona_role=data.get('persona_role'),
            commercial_positioning=data.get('commercial_positioning'),
            monetization_type=data.get('monetization_type'),
            target_audience=data.get('target_audience'),
            # 内容布局（数量）
            content_persona=data.get('content_persona', 0),
            content_topic=data.get('content_topic', 0),
            content_daily=data.get('content_daily', 0),
            # 内容布局（文本描述）
            persona_type=data.get('persona_type'),
            topic_content=data.get('topic_content'),
            daily_operation=data.get('daily_operation')
        )
        db.session.add(account)
        _commit_with_retry()

        # 获取自动分析配置
        auto_config = data.get('auto_analysis_config', account.auto_analysis_config)
        account.auto_analysis_config = auto_config

        # 根据配置决定触发哪些分析任务
        # 默认只触发: nickname, bio, account_positioning（用户手动触发的单独分析 keyword_library/market_analysis/operation_planning）
        create_config = auto_config.get('on_create', {})

        # 需要分析的任务类型
        task_types_to_run = []

        # 始终执行 profile（基础画像分析）
        task_types_to_run.append(TASK_TYPE_PROFILE)

        # 如果有业务信息，执行 design
        if account.business_type or account.product_type or account.service_type:
            task_types_to_run.append(TASK_TYPE_DESIGN)

        # 根据配置决定 sub_category 分析哪些
        sub_cats_enabled = [k for k, v in create_config.items() if v]
        if sub_cats_enabled:
            task_types_to_run.append(TASK_TYPE_SUB_CATEGORY)

        # 触发后台分析任务（使用任务队列控制并发）
        if task_types_to_run:
            app = current_app._get_current_object()
            task_queue = get_task_queue()
            task_queue.add_task(
                account.id,
                task_types_to_run,
                app=app,
                extra_data={'target_sub_cats': sub_cats_enabled} if sub_cats_enabled else None
            )

        # 同时创建历史记录（单独事务，减少持锁时间）
        history = KnowledgeAccountHistory(
            account_id=account.id,
            data=current_data,
            change_note='初始创建'
        )
        db.session.add(history)
        _commit_with_retry()

        return jsonify({
            'code': 200,
            'message': '创建成功',
            'data': {
                'id': account.id,
                'name': account.name,
                'platform': account.platform,
                'url': account.url,
                'current_data': account.current_data,
                'status': account.status,
                'target_audience': account.target_audience,
                'core_keywords': account.core_keywords
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建账号失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>', methods=['PUT'])
@login_required
def update_account(account_id):
    """更新账号信息"""
    try:
        data = request.get_json()

        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        # 记录变更前的数据用于历史
        old_data = {
            'name': account.name,
            'platform': account.platform,
            'url': account.url,
            'current_data': account.current_data,
            'status': account.status,
            'business_type': account.business_type,
            'product_type': account.product_type,
            'service_type': account.service_type,
            'service_range': account.service_range,
            'target_area': account.target_area,
            'brand_type': account.brand_type,
            'language_style': account.language_style,
            'target_user': account.target_user,
            'main_product': account.main_product,
            'content_persona': account.content_persona,
            'content_topic': account.content_topic,
            'content_daily': account.content_daily,
            'persona_type': account.persona_type,
            'topic_content': account.topic_content,
            'daily_operation': account.daily_operation
        }

        # 变更记录
        changes = []

        # 更新字段
        # 增量分析控制：记录需要重新分析的标志
        need_nickname_analysis = False
        need_bio_analysis = False
        need_other_analysis = False

        if 'name' in data:
            new_val = data['name'].strip()
            if new_val != (account.name or ''):
                changes.append(f'账号名称: {account.name} -> {new_val}')
                # 昵称变更：标记需要重新分析昵称
                account.last_nickname = new_val
                account.nickname_analyzed_at = None
                need_nickname_analysis = True
            account.name = new_val
        if 'platform' in data:
            new_val = data['platform'].strip()
            if new_val != (account.platform or ''):
                changes.append(f'平台: {account.platform} -> {new_val}')
            account.platform = new_val
        if 'url' in data:
            new_val = data['url'].strip()
            if new_val != (account.url or ''):
                changes.append(f'主页链接变更')
            account.url = new_val
        if 'current_data' in data:
            # 将 current_data 转换为字符串比较
            old_current = json.dumps(account.current_data or {}, sort_keys=True, ensure_ascii=False)
            new_current = json.dumps(data['current_data'] or {}, sort_keys=True, ensure_ascii=False)
            if old_current != new_current:
                changes.append(f'账号数据更新')
                # 检查简介是否变更
                old_bio = account.current_data.get('bio', '') if account.current_data else ''
                new_bio = data['current_data'].get('bio', '')
                if new_bio != old_bio:
                    # 简介变更：标记需要重新分析简介
                    account.last_bio = new_bio
                    account.bio_analyzed_at = None
                    need_bio_analysis = True
                # 检查业务信息是否变更（影响其他分析）
                old_business = account.current_data.get('business_info', {}) if account.current_data else {}
                new_business = data['current_data'].get('business_info', {})
                if old_business != new_business:
                    need_other_analysis = True
            account.current_data = data['current_data']
        if 'status' in data:
            if data['status'] != account.status:
                changes.append(f'状态: {account.status} -> {data["status"]}')
            account.status = data['status']

        # 详细信息字段
        if 'business_type' in data:
            if str(data['business_type'] or '') != str(account.business_type or ''):
                changes.append(f'业务类型变更')
                need_other_analysis = True
            account.business_type = data['business_type']
        if 'product_type' in data:
            if str(data['product_type'] or '') != str(account.product_type or ''):
                changes.append(f'产品类型变更')
                need_other_analysis = True
            account.product_type = data['product_type']
        if 'service_type' in data:
            if str(data['service_type'] or '') != str(account.service_type or ''):
                changes.append(f'服务类型变更')
                need_other_analysis = True
            account.service_type = data['service_type']
        if 'service_range' in data:
            if str(data['service_range'] or '') != str(account.service_range or ''):
                changes.append(f'地域范围变更')
            account.service_range = data['service_range']
        if 'target_area' in data:
            new_val = data['target_area'] if data['target_area'] else '全国'
            if str(new_val) != str(account.target_area or ''):
                changes.append(f'目标地区变更')
            account.target_area = new_val
        if 'brand_type' in data:
            if str(data['brand_type'] or '') != str(account.brand_type or ''):
                changes.append(f'品牌定位变更')
            account.brand_type = data['brand_type']
        if 'language_style' in data:
            if str(data['language_style'] or '') != str(account.language_style or ''):
                changes.append(f'语言风格变更')
            account.language_style = data['language_style']
        if 'target_user' in data:
            if str(data['target_user'] or '') != str(account.target_user or ''):
                changes.append(f'目标用户变更')
                need_other_analysis = True
            account.target_user = data['target_user']
        if 'main_product' in data:
            if str(data['main_product'] or '') != str(account.main_product or ''):
                changes.append(f'主营业务变更')
                need_other_analysis = True
            account.main_product = data['main_product']

        # 账号定位新增字段
        if 'persona_role' in data:
            if str(data['persona_role'] or '') != str(account.persona_role or ''):
                changes.append(f'人设定位变更')
            account.persona_role = data['persona_role']
        if 'commercial_positioning' in data:
            if str(data['commercial_positioning'] or '') != str(account.commercial_positioning or ''):
                changes.append(f'商业定位变更')
            account.commercial_positioning = data['commercial_positioning']
        if 'monetization_type' in data:
            if str(data['monetization_type'] or '') != str(account.monetization_type or ''):
                changes.append(f'变现类型变更')
            account.monetization_type = data['monetization_type']
        if 'target_audience' in data:
            if str(data['target_audience'] or '') != str(account.target_audience or ''):
                changes.append(f'目标客户变更')
            account.target_audience = data['target_audience']

        # 内容布局字段
        if 'content_persona' in data:
            if int(data['content_persona'] or 0) != int(account.content_persona or 0):
                changes.append(f'人设IP类内容比例变更')
            account.content_persona = data['content_persona']
        if 'content_topic' in data:
            if int(data['content_topic'] or 0) != int(account.content_topic or 0):
                changes.append(f'主题内容比例变更')
            account.content_topic = data['content_topic']
        if 'content_daily' in data:
            if int(data['content_daily'] or 0) != int(account.content_daily or 0):
                changes.append(f'日常运营比例变更')
            account.content_daily = data['content_daily']
        # 内容布局（文本描述）
        if 'persona_type' in data:
            if int(data['persona_type'] or 0) != int(account.persona_type or 0):
                changes.append(f'人设类型变更')
            account.persona_type = data['persona_type']
        if 'topic_content' in data:
            if int(data['topic_content'] or 0) != int(account.topic_content or 0):
                changes.append(f'主题内容变更')
            account.topic_content = data['topic_content']
        if 'daily_operation' in data:
            if int(data['daily_operation'] or 0) != int(account.daily_operation or 0):
                changes.append(f'日常运营变更')
            account.daily_operation = data['daily_operation']

        # 如果有变更，记录历史
        if changes:
            change_note = data.get('change_note', '手动更新')
            if changes:
                change_note = '; '.join(changes)

            history = KnowledgeAccountHistory(
                account_id=account.id,
                data=account.current_data or {},
                change_note=change_note
            )
            db.session.add(history)

        # 更新自动分析配置
        if 'auto_analysis_config' in data:
            account.auto_analysis_config = data['auto_analysis_config']

        _commit_with_retry()

        # 根据配置决定是否自动触发分析
        # 只有开启了自动分析的配置，才会触发
        auto_config = account.auto_analysis_config or {}
        update_config = auto_config.get('on_update', {})

        # 需要分析的分类
        sub_cats_to_analyze = []

        # 根据变更内容和配置决定触发哪些分析
        if need_nickname_analysis and update_config.get('nickname', False):
            sub_cats_to_analyze.append('nickname_analysis')
        if need_bio_analysis and update_config.get('bio', False):
            sub_cats_to_analyze.append('bio_analysis')
        if need_other_analysis and update_config.get('account_positioning', False):
            sub_cats_to_analyze.append('account_positioning')
        # keyword_library, market_analysis, operation_planning 默认关闭，不自动触发

        # 如果有需要分析的分类，触发任务
        if sub_cats_to_analyze:
            app = current_app._get_current_object()
            task_queue = get_task_queue()
            task_queue.add_task(
                account.id,
                [TASK_TYPE_SUB_CATEGORY],
                app=app,
                extra_data={'target_sub_cats': sub_cats_to_analyze}
            )

        # 返回增量分析标志，供前端判断是否需要提示用户
        analysis_status = {
            'need_nickname_analysis': need_nickname_analysis,
            'need_bio_analysis': need_bio_analysis,
            'need_other_analysis': need_other_analysis
        }

        return jsonify({
            'code': 200,
            'message': '更新成功',
            'data': {
                'id': account.id,
                'name': account.name,
                'platform': account.platform,
                'url': account.url,
                'current_data': account.current_data,
                'status': account.status,
                'analysis_status': analysis_status
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新账号失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>/analyze-async', methods=['POST'])
@login_required
def analyze_account_async(account_id):
    """后台异步触发账号画像/关键词 + 账号设计分析（不阻塞前端保存/跳转）"""
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        app = current_app._get_current_object()

        has_business_info = any([
            account.business_type,
            account.product_type,
            account.service_type,
            account.main_product
        ])

        # 触发后台分析任务（使用任务队列控制并发）
        app = current_app._get_current_object()
        task_queue = get_task_queue()
        if has_business_info:
            # 有业务信息才需要 profile 分析
            task_queue.add_task(
                account.id,
                [TASK_TYPE_PROFILE, TASK_TYPE_DESIGN, TASK_TYPE_SUB_CATEGORY],
                app=app
            )
        else:
            # 没有业务信息，只做 design 和 sub_category 分析
            task_queue.add_task(
                account.id,
                [TASK_TYPE_DESIGN, TASK_TYPE_SUB_CATEGORY],
                app=app
            )

        return jsonify({'code': 200, 'message': '已触发后台分析'})
    except Exception as e:
        logger.error(f"触发后台账号分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'触发失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>/analyze-specific', methods=['POST'])
@login_required
def analyze_specific_types(account_id):
    """手动触发指定的分析类型（用于用户主动触发 keyword_library/market_analysis/operation_planning）
    
    请求体:
    {
        "types": ["keyword_library", "market_analysis", "operation_planning"],  // 要分析的类型
        "force": false  // 是否强制重新分析
    }
    """
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        data = request.get_json() or {}
        target_types = data.get('types', [])
        force = data.get('force', False)

        # 有效的分析类型
        valid_types = ['nickname_analysis', 'bio_analysis', 'account_positioning', 
                       'keyword_library', 'market_analysis', 'operation_planning']
        
        # 过滤有效的类型
        target_sub_cats = [t for t in target_types if t in valid_types]
        
        if not target_sub_cats:
            return jsonify({'code': 400, 'message': '请指定有效的分析类型'})

        # 如果不是强制分析，检查是否已有分析结果，避免重复分析
        if not force:
            existing_sub_data = (account.analysis_result or {}).get('sub_category_analysis', {})
            # 如果已经有分析结果，跳过
            if any(existing_sub_data.get(t) for t in target_sub_cats):
                return jsonify({
                    'code': 200, 
                    'message': '该分析已有结果，如需重新分析请勾选"强制重新分析"',
                    'data': {'skipped': True, 'existing_types': target_sub_cats}
                })

        # 触发后台分析任务
        app = current_app._get_current_object()
        task_queue = get_task_queue()
        task_queue.add_task(
            account.id,
            [TASK_TYPE_SUB_CATEGORY],
            app=app,
            extra_data={'target_sub_cats': target_sub_cats, 'force': force}
        )

        type_names = {
            'nickname_analysis': '昵称分析',
            'bio_analysis': '简介分析',
            'account_positioning': '账号定位',
            'keyword_library': '关键词库',
            'market_analysis': '市场分析',
            'operation_planning': '运营规划'
        }
        names = [type_names.get(t, t) for t in target_sub_cats]

        return jsonify({
            'code': 200, 
            'message': f'已触发分析：{", ".join(names)}'
        })
    except Exception as e:
        logger.error(f"手动触发分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'触发失败: {str(e)}'})


@knowledge_api.route('/rules/account-design', methods=['POST'])
@login_required
def save_account_design_rule():
    """将账号设计分析（昵称/简介）的单个维度沉淀到规则库。

    前端传入:
    - account_id: 账号ID
    - dimension_code: 维度code（如 nickname_keyword, bio_structure）
    """
    try:
        from models.models import KnowledgeRule

        data = request.get_json() or {}
        account_id = data.get('account_id')
        dimension_code = (data.get('dimension_code') or '').strip()

        if not account_id or not dimension_code:
            return jsonify({'code': 400, 'message': '缺少必要参数'})

        # 根据 dimension_code 获取维度信息
        dimension = get_dimension_by_code(dimension_code)
        if not dimension:
            return jsonify({'code': 404, 'message': '维度不存在'})

        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        analysis = account.analysis_result or {}
        design = analysis.get('account_design') or {}

        # 解析 dimension_code 获取是 nickname 还是 bio
        if dimension_code.startswith('nickname_'):
            nickname = account.name or ''
            nickname_analysis = design.get('nickname_analysis') or {}
            # 提取对应维度的分析结果
            dim_result = nickname_analysis.get(dimension_code) or {}
            kind = 'nickname'
        elif dimension_code.startswith('bio_'):
            bio = (account.current_data or {}).get('bio', '')
            bio_analysis = design.get('bio_analysis') or {}
            dim_result = bio_analysis.get(dimension_code) or {}
            kind = 'bio'
        else:
            return jsonify({'code': 400, 'message': '无效的维度code'})

        # 构建规则内容
        dimension_name = dimension.name or dimension_code
        title = data.get('title') or f'{dimension_name}：{account.name or "未知账号"}'
        custom_content = data.get('content')

        if custom_content:
            content = custom_content
        else:
            # 根据维度自动生成内容
            content = _build_dimension_content(
                kind=kind,
                dimension_code=dimension_code,
                dimension_name=dimension_name,
                account=account,
                dim_result=dim_result
            )

        # 入库，使用维度的规则分类和类型配置
        # 如果维度配置了 rule_category 和 rule_type，则使用配置的值
        rule_category = dimension.rule_category if dimension.rule_category else 'operation'
        rule_type = dimension.rule_type if dimension.rule_type else f'account_design_{dimension_code}'

        # 确定一级分类
        sub_cat = dimension.sub_category
        if sub_cat in ['nickname_analysis', 'bio_analysis', 'account_positioning', 'market_analysis', 'keyword_library', 'operation_planning']:
            source_category = 'account'
        elif sub_cat in ['title', 'hook', 'ending', 'visual_design', 'content_body', 'topic', 'structure', 'commercial', 'psychology', 'emotion']:
            source_category = 'content'
        else:
            source_category = 'methodology'

        rule = KnowledgeRule(
            category=rule_category,
            rule_title=title,
            rule_content=content,
            rule_type=rule_type,
            source_category=source_category,
            source_dimension=dimension_code,
            source_sub_category=dimension.sub_category,  # 分析对象
            dimension_name=dimension.name,  # 维度名称
            dimension_id=dimension.id,  # 关联维度
            status='active'
        )
        db.session.add(rule)
        _commit_with_retry()
        return jsonify({'code': 200, 'message': '已入库', 'data': {'id': rule.id}})

    except Exception as e:
        db.session.rollback()
        return jsonify({'code': 500, 'message': f'保存规则失败: {str(e)}'})


@knowledge_api.route('/rules/sub-category', methods=['POST'])
@login_required
def save_sub_category_rule():
    """将二级分类分析（昵称分析/简介分析）的整体结果沉淀到规则库。

    前端传入:
    - account_id: 账号ID
    - sub_category: 二级分类（如 nickname_analysis）
    - data: 包含 formula, score 等字段的对象
    """
    try:
        from models.models import KnowledgeRule

        data = request.get_json() or {}
        account_id = data.get('account_id')
        sub_category = (data.get('sub_category') or '').strip()
        rule_data = data.get('data', {})

        if not account_id or not sub_category:
            return jsonify({'code': 400, 'message': '缺少必要参数'})

        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        # 获取该二级分类的维度信息
        dims = get_active_dimensions(category='account', sub_category=sub_category)
        if not dims:
            return jsonify({'code': 400, 'message': '该二级分类没有配置维度'})

        # 获取分析结果
        analysis = account.analysis_result or {}
        sub_analysis = analysis.get('sub_category_analysis', {}).get(sub_category, {})
        score = rule_data.get('score', sub_analysis.get('score', 0))
        formula = rule_data.get('formula', sub_analysis.get('formula', ''))
        score_reason = rule_data.get('score_reason', sub_analysis.get('score_reason', ''))

        if not formula:
            return jsonify({'code': 400, 'message': '没有可入库的公式'})

        # 构建规则标题和内容
        sub_cat_name = ACCOUNT_SUB_CATEGORY_NAMES.get(sub_category, sub_category)
        rule_title = f'{sub_cat_name}：{formula[:30]}...' if len(formula) > 30 else f'{sub_cat_name}：{formula}'

        # 规则内容
        content = f"""## {sub_cat_name}公式

### 评分
{score}分

### 评分理由
{score_reason}

### 设计公式
{formula}

### 账号信息
- 昵称: {account.name or '未填写'}
- 简介: {account.current_data.get('bio', '') if account.current_data else '未填写'}
"""

        # 获取第一个维度作为主维度
        main_dimension = dims[0] if dims else None
        rule_category = main_dimension.rule_category if main_dimension and main_dimension.rule_category else 'operation'
        rule_type = main_dimension.rule_type if main_dimension and main_dimension.rule_type else f'{sub_category}_formula'

        # 确定一级分类
        if sub_category in ['nickname_analysis', 'bio_analysis', 'account_positioning', 'market_analysis', 'keyword_library', 'operation_planning']:
            source_category = 'account'
        elif sub_category in ['title', 'hook', 'ending', 'visual_design', 'content_body', 'topic', 'structure', 'commercial', 'psychology', 'emotion']:
            source_category = 'content'
        else:
            source_category = 'methodology'

        rule = KnowledgeRule(
            category=rule_category,
            rule_title=rule_title,
            rule_content=content,
            rule_type=rule_type,
            source_category=source_category,
            source_dimension=sub_category,
            source_sub_category=sub_category,
            dimension_name=sub_cat_name,
            dimension_id=main_dimension.id if main_dimension else None,
            status='active'
        )
        db.session.add(rule)
        _commit_with_retry()
        return jsonify({'code': 200, 'message': '已入库', 'data': {'id': rule.id}})

    except Exception as e:
        db.session.rollback()
        logger.error(f"保存二级分类规则失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'保存规则失败: {str(e)}'})


@knowledge_api.route('/rules/account-design/content', methods=['GET'])
@login_required
def get_account_design_rule_content():
    """获取账号设计规则的详细内容（用于入库前比对）

    前端传入:
    - account_id: 账号ID
    - dimension_code: 维度code（如 nickname_keyword, bio_structure）
    """
    try:
        account_id = request.args.get('account_id', type=int)
        dimension_code = request.args.get('dimension_code', '').strip()

        if not account_id or not dimension_code:
            return jsonify({'code': 400, 'message': '缺少必要参数'})

        # 根据 dimension_code 获取维度信息
        dimension = get_dimension_by_code(dimension_code)
        if not dimension:
            return jsonify({'code': 404, 'message': '维度不存在'})

        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        analysis = account.analysis_result or {}
        design = analysis.get('account_design') or {}

        # 解析 dimension_code 获取是 nickname 还是 bio
        if dimension_code.startswith('nickname_'):
            nickname = account.name or ''
            nickname_analysis = design.get('nickname_analysis') or {}
            dim_result = nickname_analysis.get(dimension_code) or {}
            kind = 'nickname'
        elif dimension_code.startswith('bio_'):
            bio = (account.current_data or {}).get('bio', '')
            bio_analysis = design.get('bio_analysis') or {}
            dim_result = bio_analysis.get(dimension_code) or {}
            kind = 'bio'
        else:
            return jsonify({'code': 400, 'message': '无效的维度code'})

        # 构建规则内容
        dimension_name = dimension.name or dimension_code
        title = f'{dimension_name}：{account.name or "未知账号"}'

        content = _build_dimension_content(
            kind=kind,
            dimension_code=dimension_code,
            dimension_name=dimension_name,
            account=account,
            dim_result=dim_result
        )

        rule_category = dimension.rule_category if dimension.rule_category else 'operation'
        rule_type = dimension.rule_type if dimension.rule_type else f'account_design_{dimension_code}'

        return jsonify({
            'code': 200,
            'data': {
                'rule_title': title,
                'rule_content': content,
                'category': rule_category,
                'rule_type': rule_type,
                'source_dimension': dimension_code
            }
        })

    except Exception as e:
        logger.error(f"获取账号设计规则内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"账号设计规则入库失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'入库失败: {str(e)}'})


def _build_dimension_content(kind, dimension_code, dimension_name, account, dim_result):
    """根据维度和分析结果构建规则内容"""
    if kind == 'nickname':
        nickname = account.name or ''
        lines = [f"## 昵称", f"{nickname or '-'}\n"]

        if dimension_code == 'nickname_keyword':
            lines.append("## 维度：核心关键词检测")
            lines.append(f"- 是否包含关键词：{dim_result.get('has_keyword', '未知')}")
            lines.append(f"- 关键词类型：{dim_result.get('keyword_type', '无')}")
            lines.append(f"- 关键词内容：{dim_result.get('keyword_content', '无')}")

        elif dimension_code == 'nickname_memorability':
            lines.append("## 维度：易记性分析")
            lines.append(f"- 字符长度：{dim_result.get('length', '未知')}")
            lines.append(f"- 易记程度：{dim_result.get('memorability', '未知')}")
            lines.append(f"- 易记原因：{dim_result.get('memorability_reason', '未知')}")
            lines.append(f"- 有重复字符：{'是' if dim_result.get('has_repeat_chars') else '否'}")
            lines.append(f"- 规律类型：{dim_result.get('has_pattern', '无')}")

        elif dimension_code == 'nickname_feature':
            lines.append("## 维度：特征分析")
            feat = dim_result
            if feat.get('body_feature'):
                lines.append(f"- 身体特征：{feat.get('body_feature')}")
            if feat.get('emotion_feature'):
                lines.append(f"- 情绪特征：{feat.get('emotion_feature')}")
            if feat.get('professional_feature'):
                lines.append(f"- 专业特征：{feat.get('professional_feature')}")
            if feat.get('persona_feature'):
                lines.append(f"- 人设特征：{feat.get('persona_feature')}")
            if not any([feat.get('body_feature'), feat.get('emotion_feature'),
                        feat.get('professional_feature'), feat.get('persona_feature')]):
                lines.append("- 特征：无明显特征")

        elif dimension_code == 'nickname_advantage':
            lines.append("## 维度：优点总结")
            advantages = dim_result.get('advantages') or []
            if advantages:
                lines.append("### 优点")
                for adv in advantages:
                    lines.append(f"- {adv}")
            suitable = dim_result.get('suitable_for')
            if suitable:
                lines.append(f"\n### 适合对象\n{suitable}")

        else:
            # 其他维度，输出全部信息
            lines.append(f"## 维度：{dimension_name}")
            for k, v in dim_result.items():
                if k not in ('dimension_code', 'dimension_name'):
                    lines.append(f"- {k}: {v}")

        return "\n".join(lines)

    else:  # bio
        bio = (account.current_data or {}).get('bio', '')
        lines = [f"## 简介", f"{bio or '-'}\n"]

        if dimension_code == 'bio_structure':
            lines.append("## 维度：结构分析")
            lines.append(f"- 有结构：{'是' if dim_result.get('has_structure') else '否'}")
            lines.append(f"- 有联系方式：{'是' if dim_result.get('has_contact') else '否'}")
            lines.append(f"- 有价值主张：{'是' if dim_result.get('has_value_proposition') else '否'}")
            lines.append(f"- 有行动号召：{'是' if dim_result.get('has_cta') else '否'}")

        elif dimension_code == 'bio_content':
            lines.append("## 维度：内容要素")
            elements = dim_result.get('content_elements') or []
            if elements:
                lines.append("### 内容要素")
                for elem in elements:
                    lines.append(f"- {elem}")
            lines.append(f"- 有差异化卖点：{'是' if dim_result.get('has_differentiation') else '否'}")
            lines.append(f"- 有清晰报价：{'是' if dim_result.get('has_clear_offer') else '否'}")

        elif dimension_code == 'bio_advantage':
            lines.append("## 维度：优点总结")
            advantages = dim_result.get('advantages') or []
            if advantages:
                lines.append("### 优点")
                for adv in advantages:
                    lines.append(f"- {adv}")
            improvements = dim_result.get('improvements') or []
            if improvements:
                lines.append("\n### 可改进")
                for imp in improvements:
                    lines.append(f"- {imp}")

        else:
            lines.append(f"## 维度：{dimension_name}")
            for k, v in dim_result.items():
                if k not in ('dimension_code', 'dimension_name'):
                    lines.append(f"- {k}: {v}")

        return "\n".join(lines)


def _run_account_profile_analysis(app, account_id):
    """后台执行账号画像与关键词分析（不占请求，供线程调用）"""
    with app.app_context():
        try:
            account = KnowledgeAccount.query.get(account_id)
            if not account:
                return
            has_business_info = any([
                account.business_type,
                account.product_type,
                account.service_type,
                account.main_product
            ])
            if not has_business_info:
                return
            account_data = {
                'name': account.name,
                'platform': account.platform,
                'url': account.url,
                'nickname': account.name or '',  # 昵称
                'bio': (account.current_data.get('bio', '') if account.current_data else ''),  # 简介
                'business_type': account.business_type,
                'product_type': account.product_type,
                'service_type': account.service_type,
                'service_range': account.service_range,
                'target_area': account.target_area,
                'brand_type': account.brand_type,
                'language_style': account.language_style,
                'main_product': account.main_product,
                'target_user': account.target_user
            }
            prompt = build_account_profile_from_manual_prompt(account_data)
            llm_service = get_llm_service()
            if not llm_service:
                return
            messages = [
                {"role": "system", "content": "你是一个专业的账号运营专家，擅长分析目标客户画像和关键词布局。请严格按照JSON格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ]
            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)
            if not result_text:
                return
            llm_result = parse_llm_json(result_text)
            if 'target_audience' in llm_result:
                account.target_audience = llm_result['target_audience']

            # 根据业务类型自动计算商业定位
            # 卖货类业务 = 电商(卖货)，其他 = 引流
            business_type = account.business_type or ''
            if '卖货' in business_type or '电商' in business_type:
                account.commercial_positioning = '卖货'
            else:
                account.commercial_positioning = '引流'

            # 变现类型：根据主营业务判断
            # 只有主营业务1有数据=单品，否则=赛道级
            # 支持格式："红糖(60%), 配饰(30%)" 或 "红糖批发, 配饰批发" 或 "红糖"
            main_product = account.main_product or ''
            logger.info(f"[_run_account_profile_analysis] 主营业务: {main_product}")
            if main_product:
                # 解析主营业务
                parts = main_product.split(',')
                has_main = False  # 主营业务1有数据
                has_secondary = False  # 主营业务2或3有数据
                
                for i, part in enumerate(parts):
                    part = part.strip()
                    if not part:
                        continue
                    
                    # 检查是否有有效数据
                    has_valid_data = False
                    
                    # 格式1: "名称(百分比%)"
                    if '(' in part and ')' in part:
                        name = part.split('(')[0].strip()
                        ratio_str = part.split('(')[1].replace(')', '').strip()
                        try:
                            ratio_val = float(ratio_str.replace('%', ''))
                            if ratio_val > 0:
                                has_valid_data = True
                        except:
                            pass
                    # 格式2: 纯名称（没有百分比）
                    elif part:
                        has_valid_data = True
                    
                    if has_valid_data:
                        if i == 0:
                            has_main = True
                        else:
                            has_secondary = True
                
                if has_main and not has_secondary:
                    account.monetization_type = '单品'
                else:
                    account.monetization_type = '赛道级'
            else:
                account.monetization_type = '赛道级'

            # 记录调试日志
            logger.info(f"[_run_account_profile_analysis] 保存前: persona_role={account.persona_role}, commercial_positioning={account.commercial_positioning}, monetization_type={account.monetization_type}, target_audience={account.target_audience}")

            # 根据分析结果获取人设定位
            # 如果LLM返回了persona_role则使用，否则默认尝试从账号定位推断
            if 'persona_role' in llm_result:
                account.persona_role = llm_result['persona_role']

            if 'keyword_layout' in llm_result:
                core_keywords = llm_result['keyword_layout'].get('core_keywords', [])
                if core_keywords:
                    account.core_keywords = core_keywords
                current_analysis = account.analysis_result or {}
                current_analysis['keyword_layout'] = llm_result['keyword_layout']
                account.analysis_result = current_analysis
            
            # 记录保存后的值
            logger.info(f"[_run_account_profile_analysis] 保存后: persona_role={account.persona_role}, commercial_positioning={account.commercial_positioning}, monetization_type={account.monetization_type}")
            
            db.session.commit()
            logger.info(f"[_run_account_profile_analysis] 分析成功，账号: {account.name}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"后台账号分析失败: {e}", exc_info=True)


def build_account_design_prompt(nickname, bio, business_info=None):
    """根据昵称和简介构建账号设计分析提示词

    Args:
        nickname: 账号昵称
        bio: 账号简介
        business_info: 业务信息（可选），用于辅助分析
    """
    business_desc = ""
    if business_info:
        business_desc = f"""
## 业务信息（供参考）
- 主营业务: {business_info.get('main_product', '未填写')}
- 业务类型: {business_info.get('business_type', '未填写')}
- 产品类型: {business_info.get('product_type', '未填写')}
- 目标用户: {business_info.get('target_user', '未填写')}
"""

    # 从「分析维度管理」中读取账号设计相关维度（昵称/简介）
    # 按维度分组，用于构建 prompt
    dimension_desc = ""
    dimension_codes = {}  # 用于 prompt 中告知 LLM 要分析的维度 code
    try:
        design_dims = get_account_design_dimensions()
        nickname_dims = design_dims.get("nickname") or []
        bio_dims = design_dims.get("bio") or []

        # 收集维度 code 列表
        dimension_codes["nickname"] = [d["code"] for d in nickname_dims if d.get("code")]
        dimension_codes["bio"] = [d["code"] for d in bio_dims if d.get("code")]

        if nickname_dims or bio_dims:
            parts = []
            if nickname_dims:
                items = [
                    f"- **{d['code']}** ({d['name']})" + (f"：{d['description']}" if d["description"] else "")
                    for d in nickname_dims
                ]
                parts.append(
                    "### 账号昵称需要重点关注的分析维度（来自分析维度管理）\n"
                    + "\n".join(items)
                )
            if bio_dims:
                items = [
                    f"- **{d['code']}** ({d['name']})" + (f"：{d['description']}" if d["description"] else "")
                    for d in bio_dims
                ]
                parts.append(
                    "### 账号简介需要重点关注的分析维度（来自分析维度管理）\n"
                    + "\n".join(items)
                )
            dimension_desc = "\n".join(parts)
    except Exception as e:
        # 维度读取失败时不影响原有分析逻辑
        logger.warning("加载账号设计分析维度失败: %s", e)

    prompt = f"""你是一个资深的账号运营专家，擅长分析账号昵称和简介的设计优劣。

## 待分析内容

### 昵称: {nickname or '未填写'}
### 简介: {bio or '未填写'}
{business_desc}

---

## 分析任务

请从以下维度分析该账号的昵称和简介设计：

### 一、昵称分析（必须包含以下维度）

1. **核心关键词检测**
   - 是否包含行业关键词/产品关键词/地域关键词/品牌关键词
   - 关键词类型：行业词/产品词/地域词/品牌词/功能词/其他

2. **易记性分析**
   - 字符长度
   - 是否有重复字符
   - 是否有规律（数字/拼音/叠字）
   - 是否易读易记

3. **特征分析**
   - 身体特征：是否有描述身体部位的词（如：哥/叔/姐/妹/爷/婆等）
   - 情绪特征：是否有表达情绪的词（如：甜/辣/酷/萌/搞笑等）
   - 专业特征：是否有体现专业度的词（如：师傅/老师/医生/专家等）
   - 人设特征：是否有明确人设标签

4. **优点总结**
   - 为什么容易记（节奏/押韵/重复/结构/画面感）
   - 为什么这个昵称好
   - 适合什么类型账号
   - 适合什么目标受众

{dimension_desc}

### 二、简介分析

1. **结构分析**
   - 是否分段落/分点
   - 是否包含联系方式
   - 是否包含核心价值主张

2. **内容要素**
   - 是否说明是做什么的
   - 是否有差异化卖点
   - 是否有行动号召

3. **优点总结**
   - 为什么这个简介好
   - 可以改进的地方

---

## 输出格式要求

请严格按照以下JSON格式输出。注意：每个分析维度都需要标注对应的维度 code（来自分析维度管理的编码）。

```json
{{
    "nickname_analysis": {{
        // 维度: nickname_keyword (核心关键词检测)
        "nickname_keyword": {{
            "dimension_code": "nickname_keyword",
            "dimension_name": "核心关键词检测",
            "has_keyword": true或false,
            "keyword_type": "行业词/产品词/地域词/品牌词/功能词/无",
            "keyword_content": "如果有关键词，具体是什么"
        }},
        // 维度: nickname_memorability (易记性分析)
        "nickname_memorability": {{
            "dimension_code": "nickname_memorability",
            "dimension_name": "易记性分析",
            "length": 字符数,
            "memorability": "易记/一般/难记",
            "memorability_reason": "一句话说明为什么容易记/不容易记",
            "has_repeat_chars": true或false,
            "has_pattern": "数字/拼音/叠字/无"
        }},
        // 维度: nickname_feature (特征分析)
        "nickname_feature": {{
            "dimension_code": "nickname_feature",
            "dimension_name": "特征分析",
            "body_feature": "如果有，描述身体特征的词",
            "emotion_feature": "如果有，描述情绪的词",
            "professional_feature": "如果有，体现专业度的词",
            "persona_feature": "如果有，人设标签"
        }},
        // 维度: nickname_advantage (优点总结)
        "nickname_advantage": {{
            "dimension_code": "nickname_advantage",
            "dimension_name": "优点总结",
            "advantages": ["优点1", "优点2"],
            "suitable_for": "适合的账号类型/目标受众"
        }}
        // 你可以添加更多维度，只要包含 dimension_code 和 dimension_name 即可
    }},
    "bio_analysis": {{
        // 维度: bio_structure (结构分析)
        "bio_structure": {{
            "dimension_code": "bio_structure",
            "dimension_name": "结构分析",
            "has_structure": true或false,
            "has_contact": true或false,
            "has_value_proposition": true或false,
            "has_cta": true或false
        }},
        // 维度: bio_content (内容要素)
        "bio_content": {{
            "dimension_code": "bio_content",
            "dimension_name": "内容要素",
            "content_elements": ["包含的内容要素"],
            "has_differentiation": true或false,
            "has_clear_offer": true或false
        }},
        // 维度: bio_advantage (优点总结)
        "bio_advantage": {{
            "dimension_code": "bio_advantage",
            "dimension_name": "优点总结",
            "advantages": ["优点1", "优点2"],
            "improvements": ["可改进点1", "可改进点2"]
        }}
    }},
    "overall_score": "1-10分",
    "recommendation": "总体评价和建议"
}}
```
"""
    return prompt


def _match_rules_for_account_design(text, rule_types=None):
    """对比规则库，查找与账号设计文本（昵称/简介）相似的规则。

    使用通用的 rule_matcher 进行匹配，统一规则匹配行为。
    """
    return match_rules_for_text(
        text=text,
        category="operation",
        rule_types=rule_types,
        status="active",
        limit=5,
    )


def _run_account_design_analysis(app, account_id):
    """后台执行账号设计分析（昵称+简介），并对比规则库"""
    with app.app_context():
        try:
            account = KnowledgeAccount.query.get(account_id)
            if not account:
                return

            # 获取昵称和简介
            nickname = account.name or ''
            bio = account.current_data.get('bio', '') if account.current_data else ''

            if not nickname and not bio:
                return

            # 准备业务信息
            business_info = None
            if any([account.business_type, account.product_type, account.main_product]):
                business_info = {
                    'main_product': account.main_product,
                    'business_type': account.business_type,
                    'product_type': account.product_type,
                    'target_user': account.target_user
                }

            # 构建提示词
            prompt = build_account_design_prompt(nickname, bio, business_info)

            # 调用 LLM
            llm_service = get_llm_service()
            if not llm_service:
                return

            messages = [
                {"role": "system", "content": "你是一个资深的账号运营专家，擅长分析账号昵称和简介的设计优劣。请严格按照JSON格式输出分析结果。"},
                {"role": "user", "content": prompt}
            ]

            result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)
            if not result_text:
                return

            llm_result = parse_llm_json(result_text)

            # 对比规则库（运营规划 -> 账号设计）
            nickname_matched = _match_rules_for_account_design(nickname, rule_types=['account_design_nickname'])
            bio_matched = _match_rules_for_account_design(bio, rule_types=['account_design_bio'])

            # 保存分析结果
            current_analysis = account.analysis_result or {}
            current_analysis['account_design'] = llm_result
            current_analysis['rule_library_check'] = {
                'nickname': {
                    'matched_rules': nickname_matched,
                    'should_suggest_add': len(nickname_matched) == 0
                },
                'bio': {
                    'matched_rules': bio_matched,
                    'should_suggest_add': len(bio_matched) == 0
                }
            }
            account.analysis_result = current_analysis

            db.session.commit()
            logger.info(f"[_run_account_design_analysis] 账号设计分析成功，账号: {account.name}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"后台账号设计分析失败: {e}", exc_info=True)


# 账号分析二级分类列表（不含关键词库）
ACCOUNT_SUB_CATEGORIES = [
    'nickname_analysis',   # 昵称分析
    'bio_analysis',        # 简介分析
    'account_positioning', # 账号定位
    'market_analysis',     # 市场分析
    'operation_planning',  # 运营规划
]

ACCOUNT_SUB_CATEGORY_NAMES = {
    'nickname_analysis': '昵称分析',
    'bio_analysis': '简介分析',
    'account_positioning': '账号定位',
    'market_analysis': '市场分析',
    'operation_planning': '运营规划',
}


# 系统默认的昵称分析维度（作为用户维度的补充）
SYSTEM_NICKNAME_DIMENSION_CODES = [
    'nickname_keyword', 'nickname_memorability', 'nickname_feature', 'nickname_advantage'
]


# ========== 公式要素缓存 ==========
# 内存缓存：{sub_category: {'elements': [...], 'updated_at': timestamp}}
_formula_elements_cache = {}
_formula_elements_cache_ttl = 300  # 缓存有效期5分钟


def _get_cached_formula_elements(sub_category):
    """从缓存获取公式要素"""
    import time
    now = time.time()

    if sub_category in _formula_elements_cache:
        cached = _formula_elements_cache[sub_category]
        if now - cached.get('updated_at', 0) < _formula_elements_cache_ttl:
            return cached.get('elements')

    # 缓存过期或不存在，从数据库读取
    return _load_formula_elements_from_db(sub_category)


def _load_formula_elements_from_db(sub_category):
    """从数据库加载公式要素"""
    import time
    try:
        from models.models import FormulaElementType

        elements = FormulaElementType.query.filter_by(
            sub_category=sub_category,
            is_active=True
        ).order_by(FormulaElementType.priority.asc()).all()

        # 更新缓存
        _formula_elements_cache[sub_category] = {
            'elements': elements,
            'updated_at': time.time()
        }

        return elements
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"从数据库加载公式要素失败: {e}")
        return None


def _invalidate_formula_elements_cache(sub_category=None):
    """清除公式要素缓存"""
    if sub_category:
        _formula_elements_cache.pop(sub_category, None)
    else:
        _formula_elements_cache.clear()


def _get_formula_elements(sub_category):
    """获取公式要素（带缓存）"""
    return _get_cached_formula_elements(sub_category)


def _build_formula_elements_text(sub_category):
    """构建公式要素说明文本（用于 prompt）"""
    elements = _get_formula_elements(sub_category)

    if not elements:
        return None

    if sub_category == 'nickname_analysis':
        # 构建要素列表
        element_lines = []
        for e in elements:
            examples_str = e.examples.replace('|', '、') if e.examples else ''
            element_lines.append(f"   - **{e.name}**：{e.description}" + (f"（如：{examples_str}）" if examples_str else ""))

        elements_text = "\n".join(element_lines)

        # 构建优先级说明
        priority_text = " > ".join([e.name for e in elements])

        # 构建示例
        example_texts = []
        for e in elements:
            if e.examples:
                # 取第一个示例
                first_example = e.examples.split('|')[0]
                example_texts.append(f"   - **{e.name}({first_example})**")

        example_str = "\n".join(example_texts) if example_texts else None

        return {
            'elements_text': elements_text,
            'priority_text': priority_text,
            'example_str': example_str,
            'count': len(elements)
        }

    elif sub_category == 'bio_analysis':
        element_lines = []
        for e in elements:
            examples_str = e.examples.replace('|', '、') if e.examples else ''
            element_lines.append(f"   - **{e.name}**：{e.description}" + (f"（如：{examples_str}）" if examples_str else ""))

        elements_text = "\n".join(element_lines)

        return {
            'elements_text': elements_text,
            'count': len(elements)
        }

    return None


def _save_discovered_formula_elements(account_id, sub_category_results, account_info):
    """从分析结果中提取发现的新要素并保存为待审核建议"""
    try:
        from models.models import FormulaElementSuggestion, FormulaElementType
        import logging
        logger = logging.getLogger(__name__)

        # 获取已存在的要素 code
        existing_codes = set()
        for sub_cat in ['nickname_analysis', 'bio_analysis']:
            existing = FormulaElementType.query.filter_by(
                sub_category=sub_cat, is_active=True
            ).all()
            existing_codes.update((sub_cat, e.code) for e in existing)

        # 检查每个分析结果中的 discovered_elements
        for sub_cat, result in sub_category_results.items():
            llm_data = result.get('llm_data', {})
            discovered = llm_data.get('discovered_elements', [])

            if not discovered:
                continue

            # 获取来源信息
            source_nickname = account_info.get('nickname', '')
            source_bio = account_info.get('bio', '')

            for elem in discovered:
                if not elem:
                    continue

                code = elem.get('code', '')
                name = elem.get('name', '')
                if not code or not name:
                    continue

                # 检查是否已存在
                if (sub_cat, code) in existing_codes:
                    continue

                # 检查是否已有待审核的建议
                existing_suggestion = FormulaElementSuggestion.query.filter_by(
                    sub_category=sub_cat,
                    code=code,
                    status='pending'
                ).first()

                if existing_suggestion:
                    continue

                # 创建新建议
                suggestion = FormulaElementSuggestion(
                    account_id=account_id,
                    sub_category=sub_cat,
                    name=name,
                    code=code,
                    description=elem.get('description', ''),
                    example=elem.get('example', ''),
                    source_nickname=source_nickname,
                    source_formula=result.get('formula', ''),
                    status='pending'
                )
                db.session.add(suggestion)
                logger.info(f"[FormulaElement] 发现新要素建议: {sub_cat}/{code} - {name}")

        db.session.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"保存发现的新要素失败: {e}", exc_info=True)
        db.session.rollback()


# ========== 公式要素 CRUD API ==========

def register_formula_elements_routes(bp):
    """注册公式要素 API 路由"""

    @bp.route('/api/formula-elements/', methods=['GET'])
    def get_formula_elements():
        """获取所有公式要素（可按 sub_category 过滤）"""
        from flask import jsonify, request
        from models.models import FormulaElementType

        sub_category = request.args.get('sub_category')

        query = FormulaElementType.query
        if sub_category:
            query = query.filter_by(sub_category=sub_category)

        elements = query.order_by(
            FormulaElementType.sub_category,
            FormulaElementType.priority
        ).all()

        return jsonify({
            'code': 0,
            'data': [{
                'id': e.id,
                'sub_category': e.sub_category,
                'name': e.name,
                'code': e.code,
                'description': e.description,
                'examples': e.examples,
                'priority': e.priority,
                'is_active': e.is_active,
                'usage_tips': e.usage_tips,
                'created_at': e.created_at.isoformat() if e.created_at else None,
                'updated_at': e.updated_at.isoformat() if e.updated_at else None,
            } for e in elements]
        })

    @bp.route('/api/formula-elements/', methods=['POST'])
    def create_formula_element():
        """创建公式要素"""
        from flask import jsonify, request
        from models.models import FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        data = request.get_json()

        # 验证必填字段
        required = ['sub_category', 'name', 'code']
        for field in required:
            if not data.get(field):
                return jsonify({'code': 400, 'message': f'缺少必填字段: {field}'}), 400

        # 检查 code 唯一性
        existing = FormulaElementType.query.filter_by(
            sub_category=data['sub_category'],
            code=data['code']
        ).first()
        if existing:
            return jsonify({'code': 400, 'message': '该要素编码已存在'}), 400

        element = FormulaElementType(
            sub_category=data['sub_category'],
            name=data['name'],
            code=data['code'],
            description=data.get('description', ''),
            examples=data.get('examples', ''),
            priority=data.get('priority', 0),
            is_active=data.get('is_active', True),
            usage_tips=data.get('usage_tips', '')
        )

        from app import db
        db.session.add(element)
        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache(data['sub_category'])

        return jsonify({
            'code': 0,
            'message': '创建成功',
            'data': {'id': element.id}
        })

    @bp.route('/api/formula-elements/<int:element_id>', methods=['PUT'])
    def update_formula_element(element_id):
        """更新公式要素"""
        from flask import jsonify, request
        from models.models import FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        element = FormulaElementType.query.get(element_id)
        if not element:
            return jsonify({'code': 404, 'message': '要素不存在'}), 404

        data = request.get_json()

        # 更新字段
        if 'name' in data:
            element.name = data['name']
        if 'description' in data:
            element.description = data['description']
        if 'examples' in data:
            element.examples = data['examples']
        if 'priority' in data:
            element.priority = data['priority']
        if 'is_active' in data:
            element.is_active = data['is_active']
        if 'usage_tips' in data:
            element.usage_tips = data['usage_tips']

        from app import db
        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache(element.sub_category)

        return jsonify({
            'code': 0,
            'message': '更新成功'
        })

    @bp.route('/api/formula-elements/<int:element_id>', methods=['DELETE'])
    def delete_formula_element(element_id):
        """删除公式要素"""
        from flask import jsonify
        from models.models import FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        element = FormulaElementType.query.get(element_id)
        if not element:
            return jsonify({'code': 404, 'message': '要素不存在'}), 404

        sub_category = element.sub_category

        from app import db
        db.session.delete(element)
        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache(sub_category)

        return jsonify({
            'code': 0,
            'message': '删除成功'
        })

    @bp.route('/api/formula-elements/init', methods=['POST'])
    def init_formula_elements():
        """初始化默认公式要素"""
        from flask import jsonify
        from models.models import FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        from app import db

        # 昵称分析默认要素
        nickname_elements = [
            {'code': 'product_word', 'name': '产品词', 'description': '具体产品/服务、业务关键词（最高优先级）', 'examples': '香肠|茶叶|手机|AI', 'priority': 1},
            {'code': 'identity_tag', 'name': '身份标签', 'description': '身份/职业', 'examples': '哥|姐|老师|医生|创始人', 'priority': 2},
            {'code': 'persona_word', 'name': '人设词', 'description': '人格化角色/形象', 'examples': '魔女|西施|侠客|公主', 'priority': 3},
            {'code': 'style_word', 'name': '风格词', 'description': '外观/气质/体型描述', 'examples': '红发|高冷|胖|瘦', 'priority': 4},
            {'code': 'industry_word', 'name': '行业词', 'description': '行业/技术前缀（仅当无法确定具体产品时使用）', 'examples': '数码|美食|旅游', 'priority': 5},
            {'code': 'region_word', 'name': '地域词', 'description': '地区名称', 'examples': '南漳|北京|上海', 'priority': 6},
            {'code': 'attribute_word', 'name': '属性词', 'description': '品质/特点', 'examples': '手工|野生|正宗', 'priority': 7},
            {'code': 'number_word', 'name': '数字词', 'description': '年份/数量', 'examples': '20年|10年|90年', 'priority': 8},
            {'code': 'action_word', 'name': '行动词', 'description': '动作/行为', 'examples': '吃|玩|学', 'priority': 9},
        ]

        # 简介分析默认要素
        bio_elements = [
            {'code': 'identity_tag', 'name': '身份标签', 'description': '职业背景、学历、职称、专业身份', 'examples': '10年大厂PM|XX创始人|XX专家', 'priority': 1},
            {'code': 'value_proposition', 'name': '价值主张', 'description': '卖什么产品/服务、提供什么具体价值', 'examples': '专注茶叶20年|只卖正宗XX|专业手工XX', 'priority': 2},
            {'code': 'differentiation', 'name': '差异化标签', 'description': '为什么关注你，你和别人不一样在哪', 'examples': '只讲真话|不割韭菜|0基础也能学', 'priority': 3},
            {'code': 'cta', 'name': '行动号召', 'description': '让粉丝做什么、关注后做什么', 'examples': '关注送XX|扫码领取|私信咨询|到店试吃', 'priority': 4},
            {'code': 'price_info', 'name': '价格信息', 'description': '具体的价格/报价', 'examples': '2.5元/斤|99元/盒', 'priority': 5},
            {'code': 'contact', 'name': '联系方式', 'description': '联系方式', 'examples': '微信号|电话|地址', 'priority': 6},
            {'code': 'content_element', 'name': '内容要素', 'description': '其他内容要素', 'examples': 'slogan|品牌故事', 'priority': 7},
        ]

        created_count = 0

        # 创建昵称要素
        for item in nickname_elements:
            exists = FormulaElementType.query.filter_by(
                sub_category='nickname_analysis',
                code=item['code']
            ).first()
            if not exists:
                element = FormulaElementType(
                    sub_category='nickname_analysis',
                    **item,
                    is_active=True
                )
                db.session.add(element)
                created_count += 1

        # 创建简介要素
        for item in bio_elements:
            exists = FormulaElementType.query.filter_by(
                sub_category='bio_analysis',
                code=item['code']
            ).first()
            if not exists:
                element = FormulaElementType(
                    sub_category='bio_analysis',
                    **item,
                    is_active=True
                )
                db.session.add(element)
                created_count += 1

        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache()

        return jsonify({
            'code': 0,
            'message': f'初始化成功，共创建 {created_count} 个要素'
        })

    @bp.route('/api/formula-elements/export', methods=['GET'])
    def export_formula_elements():
        """导出公式要素（JSON格式）"""
        from flask import jsonify, request
        from models.models import FormulaElementType

        sub_category = request.args.get('sub_category')

        query = FormulaElementType.query
        if sub_category:
            query = query.filter_by(sub_category=sub_category)

        elements = query.order_by(
            FormulaElementType.sub_category,
            FormulaElementType.priority
        ).all()

        export_data = {
            'version': '1.0',
            'exported_at': datetime.utcnow().isoformat(),
            'elements': [{
                'sub_category': e.sub_category,
                'name': e.name,
                'code': e.code,
                'description': e.description,
                'examples': e.examples,
                'priority': e.priority,
                'is_active': e.is_active,
                'usage_tips': e.usage_tips,
            } for e in elements]
        }

        return jsonify({
            'code': 0,
            'data': export_data
        })

    @bp.route('/api/formula-elements/import', methods=['POST'])
    def import_formula_elements():
        """导入公式要素（JSON格式）"""
        from flask import jsonify, request
        from models.models import FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        data = request.get_json()

        if not data or 'elements' not in data:
            return jsonify({'code': 400, 'message': '无效的导入数据'}), 400

        from app import db

        imported_count = 0
        skipped_count = 0

        for item in data['elements']:
            # 检查是否已存在（按 sub_category + code）
            exists = FormulaElementType.query.filter_by(
                sub_category=item.get('sub_category'),
                code=item.get('code')
            ).first()

            if exists:
                # 更新已存在的
                exists.name = item.get('name', exists.name)
                exists.description = item.get('description', exists.description)
                exists.examples = item.get('examples', exists.examples)
                exists.priority = item.get('priority', exists.priority)
                exists.is_active = item.get('is_active', exists.is_active)
                exists.usage_tips = item.get('usage_tips', exists.usage_tips)
                skipped_count += 1
            else:
                # 创建新的
                element = FormulaElementType(
                    sub_category=item.get('sub_category'),
                    name=item.get('name'),
                    code=item.get('code'),
                    description=item.get('description', ''),
                    examples=item.get('examples', ''),
                    priority=item.get('priority', 0),
                    is_active=item.get('is_active', True),
                    usage_tips=item.get('usage_tips', '')
                )
                db.session.add(element)
                imported_count += 1

        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache()

        return jsonify({
            'code': 0,
            'message': f'导入成功：新增 {imported_count} 个，更新 {skipped_count} 个'
        })

    @bp.route('/api/formula-elements/suggestions', methods=['GET'])
    def get_formula_element_suggestions():
        """获取待审核的要素建议"""
        from flask import jsonify, request
        from models.models import FormulaElementSuggestion

        status = request.args.get('status', 'pending')

        query = FormulaElementSuggestion.query
        if status:
            query = query.filter_by(status=status)

        suggestions = query.order_by(
            FormulaElementSuggestion.created_at.desc()
        ).all()

        return jsonify({
            'code': 0,
            'data': [{
                'id': s.id,
                'sub_category': s.sub_category,
                'name': s.name,
                'code': s.code,
                'description': s.description,
                'example': s.example,
                'source_nickname': s.source_nickname,
                'source_formula': s.source_formula,
                'status': s.status,
                'created_at': s.created_at.isoformat() if s.created_at else None,
            } for s in suggestions]
        })

    @bp.route('/api/formula-elements/suggestions/<int:suggestion_id>/approve', methods=['POST'])
    def approve_formula_element_suggestion(suggestion_id):
        """审核通过要素建议，添加到要素库"""
        from flask import jsonify, request
        from models.models import FormulaElementSuggestion, FormulaElementType
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        suggestion = FormulaElementSuggestion.query.get(suggestion_id)
        if not suggestion:
            return jsonify({'code': 404, 'message': '建议不存在'}), 404

        if suggestion.status != 'pending':
            return jsonify({'code': 400, 'message': '该建议已处理'}), 400

        # 检查是否已存在相同 code 的要素
        existing = FormulaElementType.query.filter_by(
            sub_category=suggestion.sub_category,
            code=suggestion.code
        ).first()

        if existing:
            # 更新现有要素
            existing.name = suggestion.name
            existing.description = suggestion.description
            existing.examples = suggestion.example
            message = '要素已更新'
        else:
            # 创建新要素
            element = FormulaElementType(
                sub_category=suggestion.sub_category,
                name=suggestion.name,
                code=suggestion.code,
                description=suggestion.description,
                examples=suggestion.example,
                priority=99,  # 默认放到最后
                is_active=True
            )
            db.session.add(element)
            message = '要素已添加'

        # 更新建议状态
        suggestion.status = 'approved'
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.reviewer_id = current_user.id

        note = request.json.get('note', '') if request.json else ''
        suggestion.review_note = note

        db.session.commit()

        # 清除缓存
        _invalidate_formula_elements_cache(suggestion.sub_category)

        return jsonify({
            'code': 0,
            'message': message
        })

    @bp.route('/api/formula-elements/suggestions/<int:suggestion_id>/reject', methods=['POST'])
    def reject_formula_element_suggestion(suggestion_id):
        """拒绝要素建议"""
        from flask import jsonify, request
        from models.models import FormulaElementSuggestion
        from flask_login import current_user

        if not current_user or not current_user.is_authenticated:
            return jsonify({'code': 401, 'message': '未登录'}), 401

        suggestion = FormulaElementSuggestion.query.get(suggestion_id)
        if not suggestion:
            return jsonify({'code': 404, 'message': '建议不存在'}), 404

        if suggestion.status != 'pending':
            return jsonify({'code': 400, 'message': '该建议已处理'}), 400

        suggestion.status = 'rejected'
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.reviewer_id = current_user.id

        note = request.json.get('note', '') if request.json else ''
        suggestion.review_note = note

        db.session.commit()

        return jsonify({
            'code': 0,
            'message': '已拒绝'
        })


def _get_merged_nickname_dimensions():
    """获取昵称分析维度：用户设置的维度（必选） + 系统默认维度（补充）"""
    from models.models import AnalysisDimension
    # 用户维度：分析维度管理中启用的
    user_dims = get_active_dimensions(category='account', sub_category='nickname_analysis')
    # 按 is_default 排序：用户维度(is_default=False)在前，系统维度(is_default=True)在后
    user_dims_sorted = sorted(user_dims, key=lambda d: (1 if getattr(d, 'is_default', False) else 0, d.sort_order or 0))
    existing_codes = {d.code for d in user_dims_sorted}
    # 系统维度作为补充：若用户未配置，则追加
    for code in SYSTEM_NICKNAME_DIMENSION_CODES:
        if code not in existing_codes:
            dim = AnalysisDimension.query.filter_by(
                sub_category='nickname_analysis', code=code, is_active=True
            ).first()
            if dim:
                user_dims_sorted.append(dim)
                existing_codes.add(code)
    return user_dims_sorted


def _run_account_sub_category_analysis(app, account_id, target_sub_cats=None):
    """后台执行账号二级分类分析（评分+公式），不占请求
    
    Args:
        app: Flask app
        account_id: 账号ID
        target_sub_cats: 要分析的分类列表，为空时分析全部
    """
    from datetime import datetime
    
    logger.info(f"[_run_account_sub_category_analysis] 开始分析 account_id={account_id}, target={target_sub_cats}")
    with app.app_context():
        try:
            account = KnowledgeAccount.query.get(account_id)
            if not account:
                return

            # 确定要分析的分类
            sub_cats_to_analyze = target_sub_cats if target_sub_cats else ACCOUNT_SUB_CATEGORIES

            # 收集账号信息
            account_info = {
                'nickname': account.name or '',
                'bio': account.current_data.get('bio', '') if account.current_data else '',
                'platform': account.platform or '',
                'url': account.url or '',
                'business_type': account.business_type or '',
                'product_type': account.product_type or '',
                'service_type': account.service_type or '',
                'main_product': account.main_product or '',
                'service_range': account.service_range or '',
                'target_area': account.target_area or '',
                'brand_type': account.brand_type or '',
                'language_style': account.language_style or '',
                'target_user': account.target_user or '',
                'core_business': account.core_business or '',
            }

            # 业务信息描述
            business_parts = []
            if account_info['business_type']:
                business_parts.append(f"业务类型: {account_info['business_type']}")
            if account_info['product_type']:
                business_parts.append(f"产品类型: {account_info['product_type']}")
            if account_info['main_product']:
                business_parts.append(f"主营业务: {account_info['main_product']}")
            if account_info['core_business']:
                business_parts.append(f"核心业务: {account_info['core_business']}")
            if account_info['target_user']:
                business_parts.append(f"目标用户: {account_info['target_user']}")
            business_desc = '\n'.join(business_parts) if business_parts else '未填写'

            # 获取各二级分类的维度
            sub_category_results = {}

            llm_service = get_llm_service()
            if not llm_service:
                return

            # 对每个二级分类进行分析（根据 target_sub_cats 决定分析范围）
            for sub_cat in sub_cats_to_analyze:
                # 昵称分析：用户维度必选 + 系统维度补充；其他分类：仅用启用中的维度
                if sub_cat == 'nickname_analysis':
                    dims = _get_merged_nickname_dimensions()
                    # #region agent log
                    try:
                        with open('/Volumes/增元/项目/douyin/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({
                                'location': 'knowledge_api:_run_account_sub_category_analysis',
                                'message': 'nickname_analysis merged dims',
                                'data': {'dim_codes': [d.code for d in dims], 'dim_names': [d.name for d in dims]},
                                'timestamp': __import__('time').time() * 1000
                            }, ensure_ascii=False) + '\n')
                    except Exception:
                        pass
                    # #endregion
                elif sub_cat == 'bio_analysis':
                    # 简介分析：使用固定的7个维度
                    from models.models import AnalysisDimension
                    bio_dim_codes = ['bio_identity', 'bio_value', 'bio_differentiate', 'bio_action', 'bio_structure', 'bio_content', 'bio_advantage']
                    dims = []
                    for code in bio_dim_codes:
                        dim = AnalysisDimension.query.filter_by(
                            sub_category='bio_analysis', code=code, is_active=True
                        ).first()
                        if dim:
                            dims.append(dim)
                        else:
                            # 如果数据库没有，则创建临时对象
                            class TempDim:
                                def __init__(self, code, name, description=''):
                                    self.code = code
                                    self.name = name
                                    self.description = description
                            dim_map = {
                                'bio_identity': ('身份标签', '是否有身份标签（如：XX创始人、XX专家）'),
                                'bio_value': ('价值主张', '是否有价值主张（如：专注XX年、只做XX）'),
                                'bio_differentiate': ('差异化标签', '是否有差异化标签（如：XX第一人、XX冠军）'),
                                'bio_action': ('行动号召', '是否有行动号召（如：+V、扫码等）'),
                                'bio_structure': ('结构分析', '是否有清晰结构：身份+价值+差异化+CTA'),
                                'bio_content': ('内容要素', '包含哪些内容要素'),
                                'bio_advantage': ('优点总结', '简介有哪些优点和可改进点')
                            }
                            dim_info = dim_map.get(code, (code, ''))
                            dims.append(TempDim(code, dim_info[0], dim_info[1]))
                    # 调试日志
                    logger.info(f"[DEBUG] bio_analysis dims: {[(d.code, d.name) for d in dims]}")
                else:
                    dims = get_active_dimensions(category='account', sub_category=sub_cat) or []

                # 构建该二级分类的分析提示词
                prompt = _build_sub_category_analysis_prompt(sub_cat, account_info, dims, business_desc)

                # 调用 LLM
                logger.info(f"[_run_account_sub_category_analysis] 开始调用 LLM for {sub_cat}")
                messages = [
                    {"role": "system", "content": f"你是一个资深的账号运营专家，擅长分析{ACCOUNT_SUB_CATEGORY_NAMES.get(sub_cat, '账号')}。请严格按照JSON格式输出分析结果和评分。"},
                    {"role": "user", "content": prompt}
                ]

                result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)
                logger.info(f"[_run_account_sub_category_analysis] LLM 返回 result_text={'有内容' if result_text else '空'}")
                if not result_text:
                    logger.warning(f"[_run_account_sub_category_analysis] {sub_cat} LLM 返回为空，跳过")
                    continue

                llm_result = parse_llm_json(result_text)

                # 提取评分和公式
                sub_category_results[sub_cat] = {
                    'sub_category_name': ACCOUNT_SUB_CATEGORY_NAMES.get(sub_cat, sub_cat),
                    'dimensions': [],
                    'score': llm_result.get('score', 0),
                    'score_reason': llm_result.get('score_reason', ''),
                    'formula': llm_result.get('formula', ''),
                    'suggestions': llm_result.get('suggestions', []),
                    'llm_data': llm_result
                }

                # 保存各维度的详细分析结果
                logger.info(f"[DEBUG] dims for {sub_cat}: {[(d.code, d.name) for d in dims] if dims else 'empty'}")
                logger.info(f"[DEBUG] llm_result keys: {list(llm_result.keys())}")
                for dim in dims:
                    dim_code = dim.code
                    logger.info(f"[DEBUG] checking dim_code={dim_code}, in llm_result: {dim_code in llm_result}")
                    if dim_code in llm_result:
                        sub_category_results[sub_cat]['dimensions'].append({
                            'code': dim_code,
                            'name': dim.name,
                            'data': llm_result[dim_code]
                        })
                logger.info(f"[DEBUG] extracted dimensions count: {len(sub_category_results[sub_cat]['dimensions'])}")

            # 保存分析结果 - 必须创建深拷贝，否则SQLAlchemy检测不到变化
            import copy
            current_analysis = copy.deepcopy(account.analysis_result) if account.analysis_result else {}
            
            # 合并已有的 sub_category_analysis，而不是直接覆盖
            existing_sub_analysis = current_analysis.get('sub_category_analysis', {})
            merged_sub_analysis = {**existing_sub_analysis, **sub_category_results}
            current_analysis['sub_category_analysis'] = merged_sub_analysis
            
            # 调试日志
            logger.info(f"[DEBUG] Before setting - id(current_analysis): {id(current_analysis)}")
            logger.info(f"[DEBUG] Before setting - id(account.analysis_result): {id(account.analysis_result) if account.analysis_result else 'None'}")
            
            account.analysis_result = current_analysis
            
            logger.info(f"[DEBUG] After setting - id(account.analysis_result): {id(account.analysis_result)}")
            logger.info(f"[DEBUG] sub_category_analysis saved: {sub_category_results}")
            logger.info(f"[DEBUG] nickname_analysis dimensions count: {len(sub_category_results.get('nickname_analysis', {}).get('dimensions', []))}")
            logger.info(f"[DEBUG] full analysis_result to save: {current_analysis}")
            for sub_cat, sub_data in sub_category_results.items():
                logger.info(f"[DEBUG] {sub_cat}: dimensions={len(sub_data.get('dimensions', []))}, llm_data keys={list(sub_data.get('llm_data', {}).keys())[:5]}")

            db.session.commit()
            logger.info(f"[_run_account_sub_category_analysis] 账号二级分类分析成功，账号: {account.name}")

            # 提取并保存发现的新要素
            _save_discovered_formula_elements(
                account_id=account.id,
                sub_category_results=sub_category_results,
                account_info=account_info
            )

            # 更新分析时间戳（用于增量分析控制）
            now = datetime.utcnow()
            if 'nickname_analysis' in sub_cats_to_analyze:
                account.nickname_analyzed_at = now
                account.last_nickname = account.name
            if 'bio_analysis' in sub_cats_to_analyze:
                account.bio_analyzed_at = now
                account.last_bio = account.current_data.get('bio', '') if account.current_data else ''
            if any(cat in sub_cats_to_analyze for cat in ['account_positioning', 'market_analysis', 'operation_planning']):
                account.other_analyzed_at = now
            db.session.commit()
            
            # 验证保存是否成功 - 使用filter_by而不是get
            account_check = KnowledgeAccount.query.filter_by(id=account_id).first()
            saved_result = account_check.analysis_result if account_check else None
            logger.info(f"[DEBUG] Verification after commit - has sub_category_analysis: {'sub_category_analysis' in (saved_result or {})}")
            logger.info(f"[DEBUG] Verification keys: {list(saved_result.keys()) if isinstance(saved_result, dict) else 'not dict'}")
            
            # 验证 nickname_analysis 内容
            if saved_result and 'sub_category_analysis' in saved_result:
                nickname_analysis = saved_result['sub_category_analysis'].get('nickname_analysis', {})
                logger.info(f"[DEBUG] Verification nickname_analysis keys: {list(nickname_analysis.keys())}")
                logger.info(f"[DEBUG] Verification nickname score: {nickname_analysis.get('score', 'N/A')}")
                logger.info(f"[DEBUG] Verification nickname formula: {nickname_analysis.get('formula', 'N/A')}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"后台账号二级分类分析失败: {e}", exc_info=True)
            logger.error(f"[_run_account_sub_category_analysis] 完整错误: {repr(e)}")


def _build_sub_category_analysis_prompt(sub_cat, account_info, dims, business_desc):
    """构建二级分类分析的提示词"""
    nickname = account_info['nickname']
    bio = account_info['bio']

    # 基础信息
    base_info = f"""
## 账号基础信息
- 昵称: {nickname or '未填写'}
- 简介: {bio or '未填写'}
- 平台: {account_info['platform'] or '未填写'}
- 主页链接: {account_info['url'] or '未填写'}

## 业务信息
{business_desc}
"""

    # 维度信息
    dim_desc = ""
    if dims:
        dim_items = []
        for d in dims:
            dim_code = getattr(d, 'code', '')
            dim_name = getattr(d, 'name', '')
            dim_desc_val = getattr(d, 'description', '')
            if dim_desc_val:
                dim_items.append(f"- **{dim_code}** ({dim_name})：{dim_desc_val}")
            else:
                dim_items.append(f"- **{dim_code}** ({dim_name})")
        dim_desc = "\n## 分析维度\n" + "\n".join(dim_items)

    # 根据不同二级分类构建不同提示词
    if sub_cat == 'nickname_analysis':
        # 动态构建各维度的分析说明与 JSON 示例
        dim_sections = []
        json_dim_examples = []
        for i, d in enumerate(dims, 1):
            code, name = d.code, d.name
            desc = (d.description or '').strip()
            if code in SYSTEM_NICKNAME_DIMENSION_CODES:
                if code == 'nickname_keyword':
                    # 核心关键词检测：需要参考业务信息中的主营业务
                    dim_sections.append(f"""### 维度{i}: {code} ({name})
- **重要**：请根据账号的"业务信息"中的"主营业务"来判断
- 判断方法：先看主营业务是什么（如：卖红糖、灌香肠、卖茶叶），再判断昵称是否包含该业务的核心关键词
- 是否包含关键词 (has_keyword): true/false（如果昵称包含业务相关的核心关键词则为true）
- 关键词类型 (keyword_type): 行业词/产品词/地域词/品牌词/功能词/无
- 关键词内容 (keyword_content): 具体关键词内容（应从主营业务中提取，如主营业务是"卖福建红糖"，则关键词应为"红糖"或"福建红糖"）
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                    json_dim_examples.append(f'''    "{code}": {{
        "has_keyword": true,
        "keyword_type": "产品词",
        "keyword_content": "红糖",
        "score": 90,
        "reason": "昵称包含主营业务核心产品词",
        "conclusion": "昵称中包含产品词，能让用户快速了解业务"
    }}''')
                elif code == 'nickname_memorability':
                    dim_sections.append(f"""### 维度{i}: {code} ({name})
- 字符长度 (length): 数字
- 易记程度 (memorability): 易记/一般/难记
- 易记原因 (memorability_reason): 简单说明
- 有无重复字符 (has_repeat_chars): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                    json_dim_examples.append(f'''    "{code}": {{
        "length": 5,
        "memorability": "易记",
        "memorability_reason": "5个字朗朗上口",
        "has_repeat_chars": false,
        "score": 85,
        "reason": "长度适中无重复",
        "conclusion": "5个字易读易记"
    }}''')
                elif code == 'nickname_feature':
                    dim_sections.append(f"""### 维度{i}: {code} ({name})
- 身体特征 (body_feature): 是否有描述身体部位的词
- 情绪特征 (emotion_feature): 是否有表达情绪的词
- 专业特征 (professional_feature): 是否有体现专业度的词
- 人设特征 (persona_feature): 是否有人设标签
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                    json_dim_examples.append(f'''    "{code}": {{
        "body_feature": "无",
        "emotion_feature": "无",
        "professional_feature": "无",
        "persona_feature": "有",
        "score": 80,
        "reason": "有人设标签",
        "conclusion": "明确人设定位"
    }}''')
                elif code == 'nickname_advantage':
                    dim_sections.append(f"""### 维度{i}: {code} ({name})
- 节奏感 (rhythm): 是否有节奏感
- 押韵 (rhyme): 是否押韵
- 结构特点 (structure): 结构特点描述
- 画面感 (imagery): 是否有画面感
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                    json_dim_examples.append(f'''    "{code}": {{
        "rhythm": "有",
        "rhyme": "无",
        "structure": "3+2结构",
        "imagery": "无",
        "score": 85,
        "reason": "结构清晰",
        "conclusion": "结构简洁明了"
    }}''')
            else:
                # 用户自定义维度：通用格式
                extra = f"（{desc}）" if desc else ""
                dim_sections.append(f"""### 维度{i}: {code} ({name}) {extra}
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "score": 80,
        "reason": "符合{name}的期望",
        "conclusion": "简要结论"
    }}''')

        dim_sections_text = "\n\n".join(dim_sections)
        json_dims_block = ",\n".join(json_dim_examples)

        # 尝试从数据库获取公式要素配置
        formula_config = _build_formula_elements_text('nickname_analysis')

        if formula_config:
            # 使用数据库中的要素配置
            elements_text = formula_config['elements_text']
            priority_text = formula_config['priority_text']
            example_str = formula_config.get('example_str')

            formula_section = f"""3. **可用公式 (formula)**: **必须分析这个昵称的实际构成元素**，格式如"要素类型(具体内容)"。要素类型必须是以下{formula_config['count']}种之一：
{elements_text}

   **分析优先级**：{priority_text}

   例如："""

            # 添加示例
            if example_str:
                formula_section += f"""
{example_str}"""
            else:
                formula_section += f"""
   - 对于昵称"灌肠西施"，公式应该是"产品词(灌肠) + 身份标签(西施)"
   - 对于昵称"纽约王老师"，公式应该是"地域词(纽约) + 身份标签(王老师)"
   - 对于昵称"南漳黄姐灌香肠手工20年"，公式应该是"地域词(南漳) + 身份标签(黄姐) + 产品词(灌香肠) + 属性词(手工) + 数字词(20年)"
   - **对于昵称"罗胖香肠90年"**，公式应该是"产品词(香肠) + 数字词(90年) + 风格词(胖)"
   - **对于昵称"AI红发魔女"**，公式应该是"产品词(AI) + 风格词(红发) + 人设词(魔女)"
   - **对于昵称"红发魔女"**，公式应该是"风格词(红发) + 人设词(魔女)"
   - **对于昵称"数码哥"**，公式应该是"行业词(数码) + 身份标签(哥)" """
        else:
            # 使用默认硬编码
            formula_section = """3. **可用公式 (formula)**: **必须分析这个昵称的实际构成元素**，格式如"要素类型(具体内容)"。要素类型必须是以下10种之一：
   - **产品词**：具体产品/服务、业务关键词（**最高优先级**，如：AI代表AI相关业务、香肠、茶叶、手机）
   - **身份标签**：身份/职业（如：哥、姐、老师、医生、创始人）
   - **人设词**：人格化角色/形象（如：魔女、西施、侠客、公主）
   - **风格词**：外观/气质/体型描述（如：红发、金丝雀、高冷、胖、瘦、矮）
   - **行业词**：行业/技术前缀（**仅当无法确定具体产品时使用**，如：数码、美食、旅游）
   - **地域词**：地区名称（如：南漳、北京、上海）
   - **属性词**：品质/特点（如：手工、野生、正宗）
   - **数字词**：年份/数量（如：20年、10年）
   - **行动词**：动作/行为（如：吃、玩、学）

   **分析优先级**：产品词 > 身份标签 > 人设词 > 风格词 > 行业词 > 地域词 > 属性词 > 数字词 > 行动词

   例如：
   - 对于昵称"灌肠西施"，公式应该是"产品词(灌肠) + 身份标签(西施)"
   - 对于昵称"纽约王老师"，公式应该是"地域词(纽约) + 身份标签(王老师)"
   - 对于昵称"南漳黄姐灌香肠手工20年"，公式应该是"地域词(南漳) + 身份标签(黄姐) + 产品词(灌香肠) + 属性词(手工) + 数字词(20年)"
   - **对于昵称"罗胖香肠90年"**，公式应该是"产品词(香肠) + 数字词(90年) + 风格词(胖)"
   - **对于昵称"AI红发魔女"**，公式应该是"产品词(AI) + 风格词(红发) + 人设词(魔女)"
   - **对于昵称"红发魔女"**，公式应该是"风格词(红发) + 人设词(魔女)"
   - **对于昵称"数码哥"**，公式应该是"行业词(数码) + 身份标签(哥)" """

        return f"""{base_info}
{dim_desc}

## 分析任务

请分析账号昵称 **"{nickname}"**，按照以下要求输出JSON：

1. **整体评分 (score)**: 0-100分，根据昵称的实际质量。**评分必须有严格区分度**：
   - 90-100分：非常优秀，有明显的记忆点、人设明确、业务清晰
   - 75-89分：较好，有一定特点但可以优化
   - 60-74分：一般，缺少明显记忆点或人设模糊
   - 60分以下：较差，需要重新设计
   **注意**：大多数昵称应该在60-85分之间，极少有完美昵称，不要轻易给90分以上！
2. **评分理由 (score_reason)**: 一句话说明评分理由，必须说明具体原因
{formula_section}
4. **优化建议 (suggestions)**: 根据昵称实际情况列出2-3条有针对性的优化建议。注意：若昵称已含地域词（如南漳、北京等），则不要建议增加地域词；若已含数字（如20、10等），则不要建议加入数字。建议必须基于实际缺失的要素提出。

5. **各维度详细分析**（必须包含以下所有维度，不可遗漏）：

{dim_sections_text}

## 输出格式

```json
{{
    "score": 75,
    "score_reason": "缺少记忆点，建议加入差异化元素",
    "formula": "产品词(灌肠) + 身份标签(西施)",
    "suggestions": ["可加入地域词突出地域特色", "可加入数字或年份强调专业度"],
    "discovered_elements": [
        {{"name": "新要素名称", "code": "new_element_code", "description": "要素定义", "example": "示例"}}
    ],
{json_dims_block}
}}
```

**重要**：
- 请直接分析提供的昵称 **{nickname}** 的实际构成
- formula 字段必须填写这个昵称的实际组成部分，不能是通用模板
- 评分要根据实际质量打分，大多数在60-85分之间
- **特别注意**：分析"产品词+风格词+人设词"组合的昵称（如"AI红发魔女"）时，产品词(如AI)是业务关键词，优先级最高！
- **发现新要素**：如果分析过程中发现当前要素库中没有涵盖的新要素类型，请在 discovered_elements 字段中列出，包括：name(要素名称)、code(要素编码)、description(要素定义)、example(示例)；如果没有新要素则返回空数组 []""";

    elif sub_cat == 'bio_analysis':
        # 构建各维度的分析说明与 JSON 示例
        dim_sections = []
        json_dim_examples = []
        
        # 简介分析的7个维度
        bio_dims = [
            ('bio_identity', '身份标签', '是否有身份标签（如：XX创始人、XX专家）'),
            ('bio_value', '价值主张', '是否有价值主张（如：专注XX年、只做XX）'),
            ('bio_differentiate', '差异化标签', '是否有差异化标签（如：XX第一人、XX冠军）'),
            ('bio_action', '行动号召', '是否有行动号召（如：+V、扫码等）'),
            ('bio_structure', '结构分析', '是否有清晰结构：身份+价值+差异化+行动号召'),
            ('bio_content', '内容要素', '包含哪些内容要素'),
            ('bio_advantage', '优点总结', '简介有哪些优点和可改进点')
        ]
        
        for code, name, desc in bio_dims:
            if code == 'bio_identity':
                dim_sections.append(f"""### 维度: {code} ({name})
- 是否有身份标签 (has_identity): true/false
- 身份内容 (identity): 具体身份描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "has_identity": true,
        "identity": "XX品牌创始人",
        "score": 85,
        "reason": "包含明确身份标签",
        "conclusion": "身份明确，有专业背书"
    }}''')
            elif code == 'bio_value':
                dim_sections.append(f"""### 维度: {code} ({name})
- 是否有价值主张 (has_value): true/false
- 价值主张内容 (value_proposition): 具体价值描述
- 清晰度 (clarity): 高/中/低
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "has_value": true,
        "value_proposition": "专注茶叶20年",
        "clarity": "高",
        "score": 80,
        "reason": "价值主张清晰",
        "conclusion": "明确传达核心价值"
    }}''')
            elif code == 'bio_differentiate':
                dim_sections.append(f"""### 维度: {code} ({name})
- 是否有差异化 (has_differentiation): true/false
- 差异化内容 (differentiation): 具体差异化描述
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "has_differentiation": true,
        "differentiation": "XX第一人",
        "score": 75,
        "reason": "有差异化但不够突出",
        "conclusion": "具备一定差异化"
    }}''')
            elif code == 'bio_action':
                dim_sections.append(f"""### 维度: {code} ({name})
- 是否有行动号召 (has_cta): true/false
- 行动号召内容 (cta_content): 具体的行动号召内容
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "has_cta": true,
        "cta_content": "关注后私信领取",
        "score": 70,
        "reason": "有行动号召但不够明确",
        "conclusion": "有引导意识"
    }}''')
            elif code == 'bio_structure':
                dim_sections.append(f"""### 维度: {code} ({name})
- 是否有结构 (has_structure): true/false
- 有联系方式 (has_contact): true/false
- 有价值主张 (has_value_proposition): true/false
- 有行动号召 (has_cta): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "has_structure": true,
        "has_contact": false,
        "has_value_proposition": true,
        "has_cta": true,
        "score": 80,
        "reason": "结构清晰有价值主张",
        "conclusion": "结构完整，缺少联系方式"
    }}''')
            elif code == 'bio_content':
                dim_sections.append(f"""### 维度: {code} ({name})
- 内容要素 (content_elements): 包含的内容要素列表
- 有差异化 (has_differentiation): true/false
- 有明确报价 (has_clear_offer): true/false
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "content_elements": ["身份", "专业", "成就"],
        "has_differentiation": true,
        "has_clear_offer": false,
        "score": 75,
        "reason": "内容要素完整但缺少报价",
        "conclusion": "要素齐全待完善"
    }}''')
            elif code == 'bio_advantage':
                dim_sections.append(f"""### 维度: {code} ({name})
- 优点 (advantages): 优点列表
- 可改进点 (improvements): 可改进的地方列表
- 评分 (score): 0-100分
- 评分理由 (reason): 为什么给这个评分
- 分析结论 (conclusion): 一句话总结""")
                json_dim_examples.append(f'''    "{code}": {{
        "advantages": ["结构清晰", "价值主张明确"],
        "improvements": ["缺少联系方式"],
        "score": 70,
        "reason": "整体不错但缺少联系方式",
        "conclusion": "有提升空间，建议添加联系方式"
    }}''')

        dim_sections_text = "\n\n".join(dim_sections)
        json_dims_block = ",\n".join(json_dim_examples)

        # 尝试从数据库获取公式要素配置
        formula_config = _build_formula_elements_text('bio_analysis')

        if formula_config:
            # 使用数据库中的要素配置
            elements_text = formula_config['elements_text']

            formula_section = f"""3. **可用公式 (formula)**: **必须分析这个简介的实际构成元素**，格式如"要素类型(具体内容)"。**重要：要素类型必须是以下{formula_config['count']}种之一：**
{elements_text}

   **特别注意**：
     - 身份标签指：职业背景、学历、职称、专业身份等（如：10年大厂PM、苏黎世大学博士、XX创始人、XX专家）
     - 价值主张指：你卖什么产品/服务、提供什么具体价值。例：专注茶叶20年｜只卖正宗XX｜专业手工XX
     - 差异化标签指：为什么关注你，你和别人不一样在哪。例：只讲真话｜不割韭菜｜0基础也能学
     - 行动号召(CTA)指：让粉丝做什么、关注后做什么。例：关注送XX｜扫码领取｜私信咨询｜到店试吃
     - 价格信息指：具体的价格/报价（如：2.5元/斤、99元/盒）"""
        else:
            # 使用默认硬编码
            formula_section = """3. **可用公式 (formula)**: **必须分析这个简介的实际构成元素**，格式如"要素类型(具体内容)"。**重要：要素类型必须是以下7种之一：身份标签、价值主张、差异化标签、行动号召、价格信息、联系方式、内容要素**。例如：
   - 对于简介"XX品牌创始人，专注XX20年，全国XX冠军，+V领取资料"，公式应该是"身份标签(XX品牌创始人) + 价值主张(专注XX20年) + 差异化标签(全国XX冠军) + 行动号召(+V领取资料)"
   - 对于简介"20年老店拎肉来灌，2.5元/斤，关注到店有好礼"，公式应该是"价值主张(20年老店体现资历) + 行动号召(拎肉来灌) + 行动号召(关注到店有好礼) + 价格信息(2.5元/斤)"
   - **特别注意**：
     - 身份标签指：职业背景、学历、职称、专业身份等（如：10年大厂PM、苏黎世大学博士、XX创始人、XX专家）
     - 价值主张指：你卖什么产品/服务、提供什么具体价值。例：专注茶叶20年｜只卖正宗XX｜专业手工XX
     - 差异化标签指：为什么关注你，你和别人不一样在哪。例：只讲真话｜不割韭菜｜0基础也能学
     - 行动号召(CTA)指：让粉丝做什么、关注后做什么。例：关注送XX｜扫码领取｜私信咨询｜到店试吃
     - 价格信息指：具体的价格/报价（如：2.5元/斤、99元/盒）"""

        return f"""{base_info}
{dim_desc}

## 分析任务

请分析账号简介 **"{bio}"**，按照以下要求输出JSON：

1. **整体评分 (score)**: 0-100分，根据简介的实际质量。**评分必须有严格区分度**：
   - 90-100分：非常优秀，结构完整、要素齐全、有差异化、有行动号召
   - 75-89分：较好，结构完整但某些要素缺失
   - 60-74分：一般，缺少明显结构或核心要素
   - 60分以下：较差，需要重新设计
2. **评分理由 (score_reason)**: 一句话说明评分理由，**必须基于简介的实际内容来评价**
{formula_section}
4. **优化建议 (suggestions)**: 根据简介实际情况列出2-3条有针对性的优化建议。**重要规则**：
   - **必须先分析简介实际包含的要素**：如果简介已经有"价值主张"就不要再建议添加价值主张；如果简介已经有"行动号召"就不要再建议添加行动号召；如果简介已经有"联系方式"就不要再建议添加联系方式
   - 只能建议添加简介中**真正缺失**的要素

5. **各维度详细分析**（必须包含以下所有维度，不可遗漏）：

{dim_sections_text}

## 输出格式

```json
{{
    "score": 75,
    "score_reason": "结构清晰但缺少联系方式",
    "formula": "身份标签(10年大厂PM) + 价值主张(带你学ai) + 差异化标签(0基础也能学) + 差异化标签(普通人也能学会)",
    "suggestions": ["建议添加联系方式方便粉丝私信", "可以突出人设标签增强记忆点"],
    "discovered_elements": [
        {{"name": "新要素名称", "code": "new_element_code", "description": "要素定义", "example": "示例"}}
    ],
{json_dims_block}
}}
```

**重要**：
- 请直接分析提供的简介 **{bio}** 的实际构成
- formula 字段必须填写这个简介的实际组成部分，不能是通用模板
- 评分要根据实际质量打分
- **发现新要素**：如果分析过程中发现当前要素库中没有涵盖的新要素类型，请在 discovered_elements 字段中列出，包括：name(要素名称)、code(要素编码)、description(要素定义)、example(示例)；如果没有新要素则返回空数组 []"""

    elif sub_cat == 'account_positioning':
        return f"""{base_info}
{dim_desc}

## 分析任务

请分析账号定位，按照以下要求输出JSON：

1. **评分 (score)**: 0-100分，根据账号定位的清晰度
2. **评分理由 (score_reason)**: 一句话说明评分理由
3. **可用公式 (formula)**: 总结出一个可复用的账号定位公式/规律
4. **优化建议 (suggestions)**: 列出2-3条优化建议

## 输出格式

```json
{{
    "score": 75,
    "score_reason": "定位较清晰但目标人群不够明确",
    "formula": "根据该账号定位的实际构成元素，总结出一个可复用的账号定位公式，例如：【实际人设】+【实际业务】+【实际目标人群】+【实际差异化】",
    "suggestions": ["建议明确目标人群画像", "可以突出差异化竞争优势"]
}}
```
"""

    elif sub_cat == 'market_analysis':
        return f"""{base_info}
{dim_desc}

## 分析任务

请分析目标市场和竞争情况，按照以下要求输出JSON：

1. **评分 (score)**: 0-100分，根据市场定位的准确度
2. **评分理由 (score_reason)**: 一句话说明评分理由
3. **可用公式 (formula)**: 总结出一个可复用的市场分析思路
4. **优化建议 (suggestions)**: 列出2-3条优化建议

## 输出格式

```json
{{
    "score": 70,
    "score_reason": "目标市场较清晰但竞争分析不足",
    "formula": "根据该市场分析的实际内容，总结出一个可复用的市场分析思路，例如：{{目标人群画像}}+{{痛点需求}}+{{解决方案}}+{{竞争优势}}",
    "suggestions": ["建议深入分析竞争对手", "可以增加差异化定位"]
}}
```
"""

    elif sub_cat == 'operation_planning':
        return f"""{base_info}
{dim_desc}

## 分析任务

请分析内容运营策略，按照以下要求输出JSON：

1. **评分 (score)**: 0-100分，根据运营策略的完整性
2. **评分理由 (score_reason)**: 一句话说明评分理由
3. **可用公式 (formula)**: 总结出一个可复用的运营规划公式
4. **优化建议 (suggestions)**: 列出2-3条优化建议

## 输出格式

```json
{{
    "score": 75,
    "score_reason": "运营方向明确但内容规划不够具体",
    "formula": "根据该运营策略的实际内容，总结出一个可复用的运营规划公式，例如：{{人设内容占比}}+{{主题内容占比}}+{{日常运营占比}}",
    "suggestions": ["建议明确内容发布频率", "可以增加互动活动规划"]
}}
```
"""

    return base_info


@knowledge_api.route('/accounts/<int:account_id>/analyze-sub-categories', methods=['POST'])
@login_required
def analyze_account_sub_categories(account_id):
    """手动触发账号二级分类分析（评分+公式）
    
    请求参数（可选）:
    - force: 强制全量分析（true/false）
    - target: 指定分析某个分类（nickname/bio/other/all）
    """
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        # 解析请求参数
        data = request.get_json() or {}
        force = data.get('force', False)
        target = data.get('target', 'auto')  # auto/nickname/bio/other/all
        
        # 确定要分析的分类
        if force or target == 'all':
            # 强制全量分析
            target_sub_cats = None  # None 表示全部
            message = '已触发全量分析'
        elif target == 'nickname':
            target_sub_cats = ['nickname_analysis']
            message = '已触发昵称分析'
        elif target == 'bio':
            target_sub_cats = ['bio_analysis']
            message = '已触发简介分析'
        elif target == 'other':
            target_sub_cats = ['account_positioning', 'market_analysis', 'operation_planning']
            message = '已触发其他分析'
        else:
            # 智能增量分析：根据分析状态决定
            target_sub_cats = []
            
            # 检查昵称是否需要分析
            need_nickname = account.nickname_analyzed_at is None or \
                           (account.last_nickname != account.name)
            if need_nickname:
                target_sub_cats.append('nickname_analysis')
            
            # 检查简介是否需要分析
            current_bio = account.current_data.get('bio', '') if account.current_data else ''
            need_bio = account.bio_analyzed_at is None or \
                      (account.last_bio != current_bio)
            if need_bio:
                target_sub_cats.append('bio_analysis')
            
            # 检查其他分析是否需要（业务信息变更）
            need_other = account.other_analyzed_at is None
            if need_other:
                target_sub_cats.extend(['account_positioning', 'market_analysis', 'operation_planning'])
            
            if not target_sub_cats:
                return jsonify({'code': 200, 'message': '数据无变化，无需重新分析', 'data': {'skipped': True}})
            
            message = f'已触发增量分析：{", ".join(target_sub_cats)}'

        # 触发后台分析（使用任务队列控制并发）
        app = current_app._get_current_object()
        task_queue = get_task_queue()
        
        # 将目标分类传递给任务
        task_queue.add_task(
            account.id, 
            [TASK_TYPE_SUB_CATEGORY], 
            app=app,
            extra_data={'target_sub_cats': target_sub_cats}
        )

        # 调试：检查任务是否添加成功
        queue_status = task_queue.get_queue_status()
        logger.info(f"[DEBUG] 任务已添加，target_sub_cats={target_sub_cats}，队列状态: {queue_status}")

        return jsonify({'code': 200, 'message': message, 'data': {'target_sub_cats': target_sub_cats}})
    except Exception as e:
        logger.error(f"触发账号二级分类分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'触发失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>/analyze-profile', methods=['POST'])
@login_required
def analyze_account_profile(account_id):
    """手动触发账号画像和关键词分析"""
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})

        # 检查是否有足够的业务信息
        has_business_info = any([
            account.business_type,
            account.product_type,
            account.service_type,
            account.main_product
        ])

        if not has_business_info:
            return jsonify({
                'code': 400,
                'message': '请先填写业务信息（业务类型、产品类型、服务类型或主营业务）后再进行分析'
            })

        # 构建账号数据
        account_data = {
            'name': account.name,
            'platform': account.platform,
            'url': account.url,
            'nickname': account.name or '',  # 昵称
            'bio': (account.current_data.get('bio', '') if account.current_data else ''),  # 简介
            'business_type': account.business_type,
            'product_type': account.product_type,
            'service_type': account.service_type,
            'service_range': account.service_range,
            'target_area': account.target_area,
            'brand_type': account.brand_type,
            'language_style': account.language_style,
            'main_product': account.main_product,
            'target_user': account.target_user
        }

        # 构建提示词
        prompt = build_account_profile_from_manual_prompt(account_data)

        # 调用 LLM
        llm_service = get_llm_service()
        if not llm_service:
            return jsonify({'code': 500, 'message': 'LLM 服务未配置'})

        messages = [
            {"role": "system", "content": "你是一个专业的账号运营专家，擅长分析目标客户画像和关键词布局。请严格按照JSON格式输出分析结果。"},
            {"role": "user", "content": prompt}
        ]

        result_text = llm_service.chat(messages, temperature=0.7, max_tokens=2000)

        if not result_text:
            return jsonify({'code': 500, 'message': 'LLM 调用失败'})

        # 解析结果
        try:
            llm_result = parse_llm_json(result_text)
        except Exception as e:
            logger.error(f"解析LLM结果失败: {e}")
            return jsonify({'code': 500, 'message': '分析结果解析失败'})

        # 保存结果到数据库
        if 'target_audience' in llm_result:
            account.target_audience = llm_result['target_audience']

        # 根据业务类型自动计算商业定位
        # 卖货类业务 = 电商(卖货)，其他 = 引流
        business_type = account.business_type or ''
        if '卖货' in business_type or '电商' in business_type:
            account.commercial_positioning = '卖货'
        else:
            account.commercial_positioning = '引流'

        # 变现类型：根据主营业务判断
        # 只有主营业务1有数据=单品，否则=赛道级
        # 支持格式："红糖(60%), 配饰(30%)" 或 "红糖批发, 配饰批发" 或 "红糖"
        main_product = account.main_product or ''
        if main_product:
            # 解析主营业务
            parts = main_product.split(',')
            has_main = False  # 主营业务1有数据
            has_secondary = False  # 主营业务2或3有数据
            
            for i, part in enumerate(parts):
                part = part.strip()
                if not part:
                    continue
                
                # 检查是否有有效数据
                has_valid_data = False
                
                # 格式1: "名称(百分比%)"
                if '(' in part and ')' in part:
                    name = part.split('(')[0].strip()
                    ratio_str = part.split('(')[1].replace(')', '').strip()
                    try:
                        ratio_val = float(ratio_str.replace('%', ''))
                        if ratio_val > 0:
                            has_valid_data = True
                    except:
                        pass
                # 格式2: 纯名称（没有百分比）
                elif part:
                    has_valid_data = True
                
                if has_valid_data:
                    if i == 0:
                        has_main = True
                    else:
                        has_secondary = True
            
            if has_main and not has_secondary:
                account.monetization_type = '单品'
            else:
                account.monetization_type = '赛道级'
        else:
            account.monetization_type = '赛道级'

        # 根据分析结果获取人设定位
        # 如果LLM返回了persona_role则使用
        if 'persona_role' in llm_result:
            account.persona_role = llm_result['persona_role']

        if 'keyword_layout' in llm_result:
            # 保存核心关键词
            core_keywords = llm_result['keyword_layout'].get('core_keywords', [])
            if core_keywords:
                account.core_keywords = core_keywords

            # 保存完整关键词布局
            current_analysis = account.analysis_result or {}
            current_analysis['keyword_layout'] = llm_result['keyword_layout']
            account.analysis_result = current_analysis

        db.session.commit()

        logger.info(f"[analyze_account_profile] 分析成功，账号: {account.name}")

        return jsonify({
            'code': 200,
            'message': '分析成功',
            'data': llm_result
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"账号分析失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>', methods=['DELETE'])
@login_required
def delete_account(account_id):
    """删除账号"""
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})
        
        db.session.delete(account)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除账号失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>/history', methods=['GET'])
@login_required
def get_account_history(account_id):
    """获取账号历史记录"""
    try:
        account = KnowledgeAccount.query.get(account_id)
        if not account:
            return jsonify({'code': 404, 'message': '账号不存在'})
        
        history = KnowledgeAccountHistory.query.filter_by(
            account_id=account_id
        ).order_by(KnowledgeAccountHistory.created_at.desc()).all()
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'id': h.id,
                'account_id': h.account_id,
                'data': h.data,
                'change_note': h.change_note,
                'created_at': h.created_at.isoformat() if h.created_at else None
            } for h in history]
        })
    except Exception as e:
        logger.error(f"获取账号历史失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/analysis-queue/status', methods=['GET'])
@login_required
def get_analysis_queue_status():
    """获取分析任务队列状态"""
    try:
        task_queue = get_task_queue()
        status = task_queue.get_queue_status()

        # 获取账号名称
        if db is not None:
            try:
                account_ids = []
                for task in status.get('queue_preview', []):
                    account_ids.append(task['account_id'])
                for task in status.get('running_preview', []):
                    account_ids.append(task['account_id'])

                if account_ids:
                    accounts = KnowledgeAccount.query.filter(KnowledgeAccount.id.in_(account_ids)).all()
                    account_names = {acc.id: acc.name for acc in accounts}

                    # 更新任务预览中的账号名称
                    for task in status.get('queue_preview', []):
                        task['account_name'] = account_names.get(task['account_id'], f'账号{task["account_id"]}')
                    for task in status.get('running_preview', []):
                        task['account_name'] = account_names.get(task['account_id'], f'账号{task["account_id"]}')
            except Exception as e:
                logger.warning(f"获取账号名称失败: {e}")

        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': status
        })
    except Exception as e:
        logger.error(f"获取队列状态失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/accounts/<int:account_id>/analysis-status', methods=['GET'])
@login_required
def get_account_analysis_status(account_id):
    """获取账号分析任务状态"""
    try:
        task_queue = get_task_queue()
        status = task_queue.get_task_status(account_id)
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': status
        })
    except Exception as e:
        logger.error(f"获取分析状态失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


# ========== 内容相关接口 ==========

@knowledge_api.route('/contents', methods=['GET'])
@login_required
def get_contents():
    """获取内容列表"""
    try:
        # 获取查询参数
        account_id = request.args.get('account_id', type=int)
        content_type = request.args.get('content_type')
        source_type = request.args.get('source_type')
        
        # 构建查询
        query = KnowledgeContent.query
        if account_id:
            query = query.filter(KnowledgeContent.account_id == account_id)
        if content_type:
            query = query.filter(KnowledgeContent.content_type == content_type)
        if source_type:
            query = query.filter(KnowledgeContent.source_type == source_type)
        
        contents = query.order_by(KnowledgeContent.updated_at.desc()).all()
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': [{
                'id': c.id,
                'account_id': c.account_id,
                'title': c.title,
                'content_url': c.content_url,
                'content_type': c.content_type,
                'source_type': c.source_type,
                'content_data': c.content_data,
                'analysis_result': c.analysis_result,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'updated_at': c.updated_at.isoformat() if c.updated_at else None
            } for c in contents]
        })
    except Exception as e:
        logger.error(f"获取内容列表失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/contents/<int:content_id>', methods=['GET'])
@login_required
def get_content(content_id):
    """获取单个内容详情"""
    try:
        content = KnowledgeContent.query.get(content_id)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})
        
        return jsonify({
            'code': 200,
            'message': '获取成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type,
                'content_data': content.content_data,
                'analysis_result': content.analysis_result,
                'created_at': content.created_at.isoformat() if content.created_at else None,
                'updated_at': content.updated_at.isoformat() if content.updated_at else None
            }
        })
    except Exception as e:
        logger.error(f"获取内容详情失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'获取失败: {str(e)}'})


@knowledge_api.route('/contents', methods=['POST'])
@login_required
def create_content():
    """创建内容"""
    try:
        data = request.get_json()
        
        account_id = data.get('account_id')
        title = data.get('title', '').strip()
        content_url = data.get('content_url', '').strip()
        content_type = data.get('content_type', 'manual')
        source_type = data.get('source_type', 'manual')
        content_data = data.get('content_data', {})
        
        if not title:
            return jsonify({'code': 400, 'message': '请输入内容标题'})
        
        # 创建内容
        content = KnowledgeContent(
            account_id=account_id,
            title=title,
            content_url=content_url,
            content_type=content_type,
            source_type=source_type,
            content_data=content_data
        )
        db.session.add(content)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '创建成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'创建失败: {str(e)}'})


@knowledge_api.route('/contents/<int:content_id>', methods=['PUT'])
@login_required
def update_content(content_id):
    """更新内容"""
    try:
        data = request.get_json()
        
        content = KnowledgeContent.query.get(content_id)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})
        
        # 更新字段
        if 'account_id' in data:
            content.account_id = data['account_id']
        if 'title' in data:
            content.title = data['title'].strip()
        if 'content_url' in data:
            content.content_url = data['content_url'].strip()
        if 'content_type' in data:
            content.content_type = data['content_type']
        if 'source_type' in data:
            content.source_type = data['source_type']
        if 'content_data' in data:
            content.content_data = data['content_data']
        if 'analysis_result' in data:
            content.analysis_result = data['analysis_result']
        
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '更新成功',
            'data': {
                'id': content.id,
                'account_id': content.account_id,
                'title': content.title,
                'content_url': content.content_url,
                'content_type': content.content_type,
                'source_type': content.source_type
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'更新失败: {str(e)}'})


@knowledge_api.route('/contents/<int:content_id>', methods=['DELETE'])
@login_required
def delete_content(content_id):
    """删除内容"""
    try:
        content = KnowledgeContent.query.get(content_id)
        if not content:
            return jsonify({'code': 404, 'message': '内容不存在'})
        
        db.session.delete(content)
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': '删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除内容失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'})


# ========== 图片识别相关接口 ==========

@knowledge_api.route('/analyze/account-image', methods=['POST'])
@login_required
def analyze_account_image():
    """分析账号主页截图"""
    try:
        data = request.get_json()
        image_data = data.get('image_data', '')  # base64 编码的图片或 URL
        
        if not image_data:
            return jsonify({'code': 400, 'message': '请上传图片'})
        
        # 导入图片分析服务
        try:
            from services.image_analyzer import analyze_account_image as do_analyze
            result = do_analyze(image_data)
            
            if 'error' in result:
                return jsonify({'code': 500, 'message': result['error']})
            
            return jsonify({
                'code': 200,
                'message': '分析成功',
                'data': result
            })
        except ImportError:
            return jsonify({'code': 500, 'message': '图片分析服务未配置'})
            
    except Exception as e:
        logger.error(f"分析账号图片失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})


@knowledge_api.route('/analyze/content-image', methods=['POST'])
@login_required
def analyze_content_image():
    """分析内容截图"""
    try:
        data = request.get_json()
        image_data = data.get('image_data', '')  # base64 编码的图片或 URL
        
        if not image_data:
            return jsonify({'code': 400, 'message': '请上传图片'})
        
        # 导入图片分析服务
        try:
            from services.image_analyzer import analyze_content_image as do_analyze
            result = do_analyze(image_data)
            
            if 'error' in result:
                return jsonify({'code': 500, 'message': result['error']})
            
            return jsonify({
                'code': 200,
                'message': '分析成功',
                'data': result
            })
        except ImportError:
            return jsonify({'code': 500, 'message': '图片分析服务未配置'})
            
    except Exception as e:
        logger.error(f"分析内容图片失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'分析失败: {str(e)}'})


# ========== 场景库/热点库入库（从爆款拆解提取） ==========

@knowledge_api.route('/scenes/extract', methods=['POST'])
@login_required
def extract_scenes_from_analysis():
    """从爆款拆解分析结果中提取场景/人群/热点，一键入库"""
    try:
        from models.models import UsageScenario, DemandScenario, PainPoint, HotTopic, SeasonalTopic, KnowledgeAccount, KnowledgeContent

        data = request.get_json()
        source_type = data.get('source_type')  # 'account' 或 'content'
        source_id = data.get('source_id')
        analysis_result = data.get('analysis_result', {})
        items = data.get('items', [])  # 要入库的项

        if not items:
            return jsonify({'code': 400, 'message': '请选择要入库的内容'})

        saved_count = 0
        for item in items:
            item_type = item.get('type')  # 'usage_scene' / 'demand_scene' / 'pain_point' / 'hot_topic'
            name = item.get('name', '').strip()
            if not name:
                continue

            # 提取适用场景、适用人群、标签等
            scenes = item.get('scenes', [])
            audience = item.get('audience', [])
            keywords = item.get('keywords', [])
            industry = item.get('industry', '')
            description = item.get('description', '')
            reason = item.get('reason', '')  # 入库理由/为什么有效

            if item_type == 'usage_scene':
                # 使用场景
                existing = UsageScenario.query.filter_by(scenario_name=name).first()
                if not existing:
                    scene = UsageScenario(
                        scenario_name=name,
                        industry=industry,
                        scenario_description=description or reason,
                        target_users=audience,
                        pain_points=[],
                        needs=[],
                        keywords=keywords + scenes,
                        related_products=[]
                    )
                    db.session.add(scene)
                    saved_count += 1
            elif item_type == 'demand_scene':
                # 需求场景
                existing = DemandScenario.query.filter_by(scenario_name=name).first()
                if not existing:
                    scene = DemandScenario(
                        scenario_name=name,
                        demand_type=industry or 'general',
                        scenario_description=description or reason,
                        trigger_condition='',
                        user_goals=audience,
                        emotional_needs=[],
                        keywords=keywords + scenes,
                    )
                    db.session.add(scene)
                    saved_count += 1
            elif item_type == 'pain_point':
                # 痛点
                existing = PainPoint.query.filter_by(pain_point_name=name).first()
                if not existing:
                    pain = PainPoint(
                        pain_point_name=name,
                        industry=industry,
                        pain_type=item.get('pain_type', 'general'),
                        description=description or reason,
                        severity=item.get('severity', 'medium'),
                        affected_users=audience,
                        current_solutions=[],
                        opportunities='',
                        keywords=keywords + scenes
                    )
                    db.session.add(pain)
                    saved_count += 1
            elif item_type == 'hot_topic':
                # 热点话题
                existing = HotTopic.query.filter_by(topic_name=name).first()
                if not existing:
                    hot = HotTopic(
                        topic_name=name,
                        topic_source='爆款拆解提取',
                        topic_url='',
                        hot_level=item.get('hot_level', '中'),
                        category=item.get('category', 'content'),
                        description=description or reason,
                        related_keywords=keywords,
                        related_industry=industry,
                        applicable_content_types=item.get('content_types', []),
                        start_date=None,
                        end_date=None,
                        status='active'
                    )
                    db.session.add(hot)
                    saved_count += 1
            elif item_type == 'seasonal_topic':
                # 季节性话题
                existing = SeasonalTopic.query.filter_by(topic_name=name).first()
                if not existing:
                    seasonal = SeasonalTopic(
                        topic_name=name,
                        topic_type=item.get('topic_type', 'festival'),
                        topic_date=item.get('topic_date'),
                        recurrence='yearly',
                        description=description or reason,
                        marketing_angles=audience,
                        content_suggestions=scenes,
                        related_industry=industry,
                        keywords=keywords
                    )
                    db.session.add(seasonal)
                    saved_count += 1

        db.session.commit()
        return jsonify({'code': 200, 'message': f'成功入库 {saved_count} 项', 'saved_count': saved_count})

    except Exception as e:
        db.session.rollback()
        logger.error(f"场景入库失败: {e}", exc_info=True)
        return jsonify({'code': 500, 'message': f'入库失败: {str(e)}'})
