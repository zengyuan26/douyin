# -*- coding: utf-8 -*-
"""
知识库内容分析 API
用于分析抖音链接并提取可入库的规则
"""

import os
import re
import json
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

knowledge_api = Blueprint('knowledge_api', __name__, url_prefix='/api/knowledge')


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
    
    prompt = f"""你是一个内容分析专家。请分析以下抖音内容链接，提取可复用的规则。

## 待分析内容
- 链接：{url}
- 内容类型：{content_type}
- 补充说明：{note}

## 分析要求
请按照以下维度进行分析，每个维度都要回答"为什么"（即为什么这样设计，这样设计的好处是什么）：

### 一、账号分析维度
- 账号定位
- 昵称设计
- 简介设计
- 人设打造

### 二、内容分析维度
- 选题方向（为什么选这个选题）
- 标题设计（为什么用这种标题）
- 封面设计（这个封面好在哪）
- 内容结构（内容如何组织）
- 关键词布局（为什么放这些关键词）
- 情绪调动（如何调动情绪）
- 行动引导（引导话术为何有效）

### 三、爆款结构维度
- 开头钩子（前3秒吸引力）
- 情绪曲线
- 结尾设计

### 四、用户心理维度
- 痛点挖掘
- 痒点触发
- 认知颠覆
- 信任建立

## 输出格式要求
请按以下JSON格式输出分析结果：

```json
{{
    "title": "内容标题",
    "author": "作者/账号名",
    "platform": "发布平台",
    "content_type": "内容类型(video/account/image/text)",
    "duration": "时长（如适用）",
    "likes": "点赞数（如适用）",
    "comments": "评论数（如适用）",
    "favorites": "收藏数（如适用）",
    "shares": "转发数（如适用）",
    "interaction_analysis": {{
        "summary": "互动数据整体概况（如：点赞高评论中等，属于热门内容）",
        "likes_comments_ratio": "点赞与评论的比例分析（如：点赞多评论少，说明内容引发情感共鸣但缺乏讨论点）",
        "likes_favorites_ratio": "点赞与收藏的比例分析（如：收藏多点赞少，说明内容有价值但不够引发共鸣）",
        "shares_analysis": "转发行为分析（如：转发多说明内容有社交属性/实用价值）",
        "strengths": ["优点1", "优点2"],
        "weaknesses": ["缺点1", "缺点2"],
        "improvement_suggestions": ["改进建议1", "改进建议2"]
    }},
    "emotion_curve": {{
        "type": "情绪曲线类型（平静-起伏型/持续高潮型/悬念型/反转型/平铺直叙型）",
        "description": "情绪曲线详细描述",
        "phases": [
            {{
                "time_point": "时间点或位置（如：0-3秒/开头/中间/结尾）",
                "emotion": "情绪状态（如：紧张、期待、惊讶、疑问、恍然大悟、温暖、搞笑等）",
                "technique": "运用的技巧（如：设置悬念、打破期待、留悬念、揭晓答案等）",
                "purpose": "这个设计的目的"
            }}
        ],
        "score": 评分(1-10)
    }},
    "content_rhythm": {{
        "type": "节奏类型（快节奏/中节奏/慢节奏/张弛有度型）",
        "description": "节奏整体描述",
        "segments": [
            {{
                "time_range": "时间段（如：0-15秒）",
                "rhythm": "节奏特点（如：快速切换、高潮、铺垫、平缓）",
                "content": "主要内容概括",
                "technique": "使用的技巧（如：镜头快速切换、特写、慢动作、配乐变化等）"
            }}
        ],
        "score": 评分(1-10)
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
            "source": "来源维度",
            "description": "规则描述",
            "scenes": "适用场景"
        }}
    ]
}}
```

## 情绪曲线分析要点
请分析内容中的情绪变化轨迹：
- **开头钩子**：如何吸引注意力（悬念、冲突、提问、反常识等）
- **情绪铺垫**：如何建立情绪基调
- **情绪高潮**：如何调动情绪峰值
- **情绪转折**：如何制造反转或惊喜
- **结尾情绪**：如何收尾（升华、悬念、温暖、呼应等）

## 内容节奏分析要点
请分析内容的节奏安排：
- **快节奏**：适合娱乐、挑战、剧情类内容，镜头切换频繁，信息密度高
- **慢节奏**：适合情感、故事、知识类内容，给观众时间消化和感受
- **张弛有度**：有铺垫有高潮，让观众情绪有起伏，不单调

## 情绪类型参考
紧张、期待、惊讶、疑问、恍然大悟、温暖、搞笑、心疼、愤怒、感动、治愈、励志、焦虑、怀念、怀旧、浪漫、甜蜜、治愈、解压、爽感、燃、泪目、破防、共鸣、羡慕、佩服、好奇、不可思议

## 节奏技巧参考
镜头快速切换、特写强调、慢动作渲染、留白、反复强调、配乐变化、声音特效、空镜过渡、倒叙、闪回、平行剪辑

请根据实际内容进行分析：
- 点赞多评论少：说明内容引发情感共鸣但缺乏讨论点，评论区不活跃
- 评论多点赞少：说明内容引发争议或讨论，但观众不愿意点赞
- 收藏多点赞少：说明内容有实用价值，但情感共鸣不够
- 转发多点赞少：说明内容有社交属性或实用价值，用户愿意分享给他人
- 点赞收藏都多：说明内容既有价值又有共鸣，是优质内容
- 互动数据都低：说明内容没有引起用户兴趣，需要优化选题和内容

请先尝试理解这个链接的内容（可以是视频描述、图文内容等），然后进行深度分析。"""
    
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
            # 尝试从 markdown 代码块中提取
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
            if json_match:
                result_json = json.loads(json_match.group(1))
            else:
                result_json = json.loads(result_text)
            
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
    prompt = f"""你是一个账号分析专家。请分析以下抖音账号主页，从整体上把握这个账号的定位和运营策略。

## 待分析账号
- 账号主页链接：{url}
- 补充说明：{note}

## 分析要求
请从以下维度进行深度分析：

### 一、账号基本信息分析
- 账号名称和简介
- 账号定位（做什么内容、服务谁）
- 头像和主页设计风格

### 二、业务类型分析
- 是单业务账号还是多业务账号
- 主要业务和次要业务分别是什么
- 业务之间的关联性

### 三、业务模式分析
- 带货模式（带货直播/短视频带货/橱窗）
- 引流模式（引流到微信/引流到私域）
- 品牌模式（品牌宣传/IP打造）
- 知识付费模式（课程/咨询/培训）
- 混合模式

### 四、视频类型分析
分析账号发布了哪些类型的视频：
- 知识分享类
- 剧情类
- 种草安利类
- 干货教程类
- 情感治愈类
- 剧情反转类
- 产品展示类
- 客户见证类
- 其他

### 五、视频布局分析

#### 5.1 关键词布局
- 标题关键词选择
- 评论区关键词引导
- 话题标签使用
- 关键词分布策略

#### 5.2 选题布局
- 选题方向和角度
- 选题时效性（节日/热点/常规）
- 选题系列化程度
- 爆款选题复用

### 六、内容风格分析
- 整体内容调性（专业/亲和/幽默/严肃）
- 拍摄风格
- 剪辑风格
- 配音/配乐风格

### 七、变现路径分析
- 目前通过什么方式变现
- 变现链路是否清晰
- 未来可能的变现方向

### 八、目标用户画像
- 目标用户年龄阶段
- 目标用户性别比例
- 目标用户兴趣特征
- 目标用户消费能力

## 输出格式
请严格按照以下JSON格式输出分析结果：

```json
{{
    "account_name": "账号名称",
    "account_position": "账号定位描述（20字以内）",
    "business_type": "单业务/多业务",
    "business_model": "带货/引流/品牌/IP/知识付费/混合模式",
    "video_types": ["视频类型1", "视频类型2", "视频类型3"],
    "video_layout": {{
        "keyword_strategy": "关键词布局策略分析",
        "topic_strategy": "选题布局策略分析"
    }},
    "content_style": "内容风格描述",
    "monetization": "变现路径描述",
    "target_audience": {{
        "age_range": "年龄阶段",
        "gender": "性别比例",
        "interest": ["兴趣1", "兴趣2"],
        "characteristics": ["特征1", "特征2"]
    }},
    "rules": [
        {{
            "category": "operation/market 之一",
            "title": "规则标题",
            "description": "规则详细内容",
            "scenes": "适用场景"
        }}
    ]
}}
```

请先尝试理解这个账号的整体情况，然后进行深度分析。每个维度都要给出具体的分析结论。"""
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
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
            if json_match:
                result_json = json.loads(json_match.group(1))
            else:
                result_json = json.loads(result_text)

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
请严格按照以下JSON格式输出，rules数组中每条规则都要有category字段：

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
            "scenes": "适用场景"
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
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', result_text)
                if json_match:
                    result_json = json.loads(json_match.group(1))
                else:
                    result_json = json.loads(result_text)

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
