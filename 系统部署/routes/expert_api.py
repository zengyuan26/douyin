"""
专家对话 API - 基于 Skills 按需加载

这个模块使用 SkillLoader 按需加载专家 Skills，
实现真正的按需加载优势：
1. 只有用户调用某个专家时，才读取对应的 skill.md
2. 减少内存占用
3. 支持动态更新 skill 内容
"""
import json
import logging
import os
from flask import Blueprint, jsonify, request, session, Response, current_app
from flask_login import login_required, current_user
from models.models import db, Client, Expert, ChatSession, ChatMessage, ExpertOutput
from datetime import datetime
from services.llm import get_llm_service
from services.skill_loader import get_skill_loader

logger = logging.getLogger(__name__)

expert_api = Blueprint('expert_api', __name__)


@expert_api.route('/experts', methods=['GET'])
@login_required
def get_experts():
    """获取所有可用专家列表"""
    skill_loader = get_skill_loader()
    skills = skill_loader.get_all_skills()
    
    # 普通用户/渠道用户不展示「知识库」专家，只允许超级管理员在工作台看到并使用
    try:
        if not current_user.is_super_admin():
            skills = [s for s in skills if s.get('name') != 'Knowledge Base']
    except Exception:
        # 防御性处理：如果当前用户对象没有 is_super_admin 方法，则默认按普通用户处理
        skills = [s for s in skills if s.get('name') != 'Knowledge Base']
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': skills
    })


@expert_api.route('/expert/info/<skill_name>', methods=['GET'])
@login_required
def get_expert_info(skill_name):
    """获取指定专家的信息"""
    skill_loader = get_skill_loader()
    info = skill_loader.get_skill_info(skill_name)
    
    if not info:
        return jsonify({
            'code': 404,
            'message': '专家不存在',
            'data': None
        })
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': info
    })


@expert_api.route('/chat/skill', methods=['POST'])
@login_required
def chat_with_skill():
    """与专家对话 - 基于 Skill 按需加载"""
    data = request.get_json()
    message = data.get('message', '')
    skill_name = data.get('skill_name')  # 可选，如果不传则自动解析
    client_id = data.get('client_id') or session.get('current_client_id')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'code': 400, 'message': '消息不能为空'})
    
    skill_loader = get_skill_loader()
    llm_service = get_llm_service()

    # 获取用户角色
    user_role = current_user.role if current_user.is_authenticated else 'user'

    # 安全检查 - 拦截修改 skill 的请求
    is_dangerous, danger_response = skill_loader.is_skill_modification_request(message, user_role)
    if is_dangerous:
        return jsonify({
            'code': 403,
            'message': danger_response,
            'data': None
        })
    
    # 解析命令，确定使用哪个 Skill
    if not skill_name:
        skill_name = skill_loader.parse_command(message)
    
    # 如果没有命令且没有指定技能，默认使用 geo-master
    if not skill_name:
        skill_name = 'geo-master'
    
    # 获取 Skill 信息
    skill_info = skill_loader.get_skill_info(skill_name)
    if not skill_info:
        return jsonify({
            'code': 404,
            'message': f'专家 {skill_name} 不存在',
            'data': None
        })
    
    # 获取客户信息（如果已选择客户）
    client_info = None
    if client_id:
        client = Client.query.get(client_id)
        if client:
            client_info = {
                'client_name': client.name,
                'industry': client.industry.name if client.industry else '',
                'business_description': client.description or '',
                'business_type': client.business_type or '',
                'geographic_scope': client.service_range or '',
                'brand_type': client.brand_type or '',
                'core_advantage': client.core_advantage or ''
            }
    
    # 构建系统提示词（按需加载 Skill 内容），传入用户角色以决定权限
    system_prompt = skill_loader.build_system_prompt(skill_name, client_info, user_role)
    
    # 获取或创建会话
    chat_session = None
    if session_id:
        chat_session = ChatSession.query.get(session_id)
    
    if not chat_session:
        # 创建新会话
        chat_session = ChatSession(
            user_id=current_user.id,
            client_id=client_id,
            title=message[:50] + ('...' if len(message) > 50 else ''),
            is_active=True
        )
        db.session.add(chat_session)
        db.session.commit()
    
    # 保存用户消息
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role='user',
        content=message
    )
    db.session.add(user_msg)
    db.session.commit()
    
    # 获取历史消息（最近10条）
    history_messages = chat_session.messages.order_by(
        ChatMessage.created_at.desc()
    ).limit(10).all()
    history_messages = list(reversed(history_messages))
    
    # 构建消息列表
    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in history_messages:
        if msg.role != 'system':
            messages_for_llm.append({
                "role": msg.role,
                "content": msg.content
            })
    # 添加当前消息
    messages_for_llm.append({"role": "user", "content": message})
    
    # 调用 LLM
    response = llm_service.chat(messages_for_llm, temperature=0.7)
    
    if response:
        # 保存助手回复
        assistant_msg = ChatMessage(
            session_id=chat_session.id,
            role='assistant',
            content=response
        )
        db.session.add(assistant_msg)
        
        # 更新会话时间
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'reply': response,
                'session_id': chat_session.id,
                'skill_name': skill_name,
                'skill_info': skill_info
            }
        })
    else:
        return jsonify({
            'code': 500,
            'message': 'AI 响应失败，请稍后重试'
        })


@expert_api.route('/chat/skill/stream', methods=['POST'])
@login_required
def chat_with_skill_stream():
    """与专家对话 - 流式输出（基于 Skill 按需加载）"""
    data = request.get_json()
    message = data.get('message', '')
    skill_name = data.get('skill_name')
    client_id = data.get('client_id') or session.get('current_client_id')
    session_id = data.get('session_id')
    
    if not message:
        return jsonify({'code': 400, 'message': '消息不能为空'})
    
    skill_loader = get_skill_loader()
    llm_service = get_llm_service()

    # 获取用户角色
    user_role = current_user.role if current_user.is_authenticated else 'user'

    # 安全检查 - 拦截修改 skill 的请求
    is_dangerous, danger_response = skill_loader.is_skill_modification_request(message, user_role)
    if is_dangerous:
        return jsonify({
            'code': 403,
            'message': danger_response,
            'data': None
        })
    
    # 解析命令
    if not skill_name:
        skill_name = skill_loader.parse_command(message)
    
    if not skill_name:
        skill_name = 'geo-master'
    
    # 获取 Skill 信息
    skill_info = skill_loader.get_skill_info(skill_name)
    if not skill_info:
        return jsonify({
            'code': 404,
            'message': f'专家 {skill_name} 不存在',
            'data': None
        })
    
    # 获取客户信息
    client_info = None
    if client_id:
        client = Client.query.get(client_id)
        if client:
            client_info = {
                'client_name': client.name,
                'industry': client.industry.name if client.industry else '',
                'business_description': client.description or '',
                'business_type': client.business_type or '',
                'geographic_scope': client.service_range or '',
                'brand_type': client.brand_type or '',
                'core_advantage': client.core_advantage or ''
            }
    
    # 构建系统提示词，传入用户角色以决定权限
    system_prompt = skill_loader.build_system_prompt(skill_name, client_info, user_role)

    # 获取或创建会话
    chat_session = None
    if session_id:
        chat_session = ChatSession.query.get(session_id)

    if not chat_session:
        chat_session = ChatSession(
            user_id=current_user.id,
            client_id=client_id,
            title=message[:50] + ('...' if len(message) > 50 else ''),
            is_active=True
        )
        db.session.add(chat_session)
        db.session.commit()

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=chat_session.id,
        role='user',
        content=message
    )
    db.session.add(user_msg)

    # 先创建一个空的助手消息，用于流式输出过程中保存中间状态
    assistant_msg = ChatMessage(
        session_id=chat_session.id,
        role='assistant',
        content=''
    )
    db.session.add(assistant_msg)
    db.session.commit()
    assistant_msg_id = assistant_msg.id

    # 获取历史消息
    history_messages = chat_session.messages.filter(
        ChatMessage.id != assistant_msg_id
    ).order_by(ChatMessage.created_at.desc()).limit(10).all()
    history_messages = list(reversed(history_messages))

    # 构建消息列表
    messages_for_llm = [{"role": "system", "content": system_prompt}]
    for msg in history_messages:
        if msg.role != 'system':
            messages_for_llm.append({
                "role": msg.role,
                "content": msg.content
            })
    messages_for_llm.append({"role": "user", "content": message})

    # 流式输出
    def generate():
        full_response = ""

        try:
            for chunk in llm_service.chat_stream(messages_for_llm, temperature=0.7):
                full_response += chunk
                # 发送 SSE 格式的数据
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            # 保存完整回复到数据库
            if full_response:
                # 更新助手消息内容
                assistant_msg.content = full_response
                db.session.add(assistant_msg)

                # 更新会话时间
                chat_session.updated_at = datetime.utcnow()
                db.session.commit()

                # 发送会话结束信息
                end_data = {
                    'done': True,
                    'session_id': chat_session.id,
                    'skill_name': skill_name,
                    'skill_info': skill_info
                }
                yield f"data: {json.dumps(end_data)}\n\n"

        except Exception as e:
            logger.error(f"流式输出错误: {e}")
            # 即使出错，也要保存已生成的部分内容
            if full_response:
                assistant_msg.content = full_response
                db.session.add(assistant_msg)
                chat_session.updated_at = datetime.utcnow()
                db.session.commit()
            error_data = {'error': str(e), 'session_id': chat_session.id, 'partial': True}
            yield f"data: {json.dumps(error_data)}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@expert_api.route('/skill/load/<skill_name>', methods=['GET'])
@login_required
def load_skill(skill_name):
    """手动加载指定 Skill（用于测试）"""
    skill_loader = get_skill_loader()
    content = skill_loader.load_skill(skill_name)
    
    if not content:
        return jsonify({
            'code': 404,
            'message': f'Skill {skill_name} 不存在',
            'data': None
        })
    
    # 返回前 2000 个字符用于预览
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'skill_name': skill_name,
            'content_preview': content[:2000],
            'content_length': len(content)
        }
    })


@expert_api.route('/skill/cache/clear', methods=['POST'])
@login_required
def clear_skill_cache():
    """清空 Skill 缓存（用于强制重新加载）"""
    skill_loader = get_skill_loader()
    skill_loader.clear_cache()
    
    return jsonify({
        'code': 200,
        'message': 'Skill 缓存已清空'
    })


@expert_api.route('/dispatch_experts', methods=['POST'])
@login_required
def dispatch_experts():
    """调度多个专家生成报告"""
    logger.info(f'[dispatch_experts] 收到请求, user: {current_user.username if current_user else "anonymous"}')
    logger.info(f'[dispatch_experts] 请求头: {dict(request.headers)}')
    logger.info(f'[dispatch_experts] 请求体原始: {request.data}')
    data = request.get_json()
    logger.info(f'[dispatch_experts] 解析后数据: {data}')
    
    client_info = data.get('client_info', {})
    expert_list = data.get('experts', [])  # ['market-insights-commander', 'geo-seo', 'ai-operations-commander']
    
    if not expert_list:
        return jsonify({'code': 400, 'message': '请指定要调度的专家列表'})
    
    skill_loader = get_skill_loader()
    llm_service = get_llm_service()
    
    results = []
    
    completed = 0
    total = len(expert_list)
    for i, expert_name in enumerate(expert_list):
        logger.info(f'[dispatch_experts] 处理专家 {i+1}/{total}: {expert_name}')
        skill_info = skill_loader.get_skill_info(expert_name)
        if not skill_info:
            results.append({
                'expert': expert_name,
                'success': False,
                'message': f'专家 {expert_name} 不存在'
            })
            continue
        
        # 构建客户信息
        client_data = {
            'client_name': client_info.get('name', ''),
            'business_type': client_info.get('business_type', ''),
            'product_type': client_info.get('product_type', ''),
            'service_type': client_info.get('service_type', ''),
            'geographic_scope': client_info.get('service_range', ''),
            'target_area': client_info.get('target_area', ''),
            'brand_type': client_info.get('brand_type', ''),
            'brand_description': client_info.get('brand_description', ''),
            'language_style': client_info.get('language_style', ''),
            'main_product': client_info.get('main_product', ''),
            'business_years': client_info.get('business_years', ''),
            'other_notes': client_info.get('other_info', '')
        }
        
        # 根据专家类型生成不同的提示词
        prompt = _build_expert_prompt(expert_name, client_data)
        
        # 构建系统提示词
        user_role = current_user.role if current_user.is_authenticated else 'user'
        system_prompt = skill_loader.build_system_prompt(expert_name, client_data, user_role)
        
        try:
            logger.info(f'[dispatch_experts] 开始调用 LLM for expert: {expert_name}')
            # 调用 LLM 生成报告（使用配置中指定的模型，不传 model 参数）
            response = llm_service.chat(
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.7
            )
            logger.info(f'[dispatch_experts] LLM 调用完成 for expert: {expert_name}')
            
            report_content = response.get('content', '') if isinstance(response, dict) else str(response)
            
            # 获取客户ID
            client = Client.query.filter_by(name=client_info.get('name')).first()
            
            # 获取或创建专家（先用slug查，再用name查）
            expert = Expert.query.filter_by(slug=expert_name).first()
            if not expert:
                expert = Expert.query.filter_by(name=expert_name).first()
            
            # 保存报告到数据库
            output = ExpertOutput(
                expert_id=expert.id if expert else None,
                client_id=client.id if client else None,
                user_id=current_user.id,
                output_type='analysis',
                title=f"{skill_info.get('title', expert_name)} - {client_info.get('name', '客户')}",
                content=report_content[:5000] if len(report_content) > 5000 else report_content
            )
            db.session.add(output)
            db.session.commit()
            
            results.append({
                'expert': expert_name,
                'success': True,
                'title': output.title,
                'output_id': output.id
            })
            logger.info(f'[dispatch_experts] 专家 {expert_name} 处理完成')
            
        except Exception as e:
            logger.error(f'[dispatch_experts] expert {expert_name} 异常: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())
            results.append({
                'expert': expert_name,
                'success': False,
                'message': str(e)
            })
    
    logger.info(f'[dispatch_experts] 准备返回响应, results: {results}')
    return jsonify({
        'code': 200,
        'message': f'专家调度完成 ({len(results)}/{total})',
        'data': results
    })


@expert_api.route('/dispatch_experts_background', methods=['POST'])
@login_required
def dispatch_experts_background():
    """后台静默调度专家生成报告（不阻塞主请求）"""
    import threading
    
    logger.info(f'[dispatch_experts_background] 收到后台请求')
    data = request.get_json()
    
    client_info = data.get('client_info', {})
    expert_list = data.get('experts', [])  # ['geo-seo', 'ai-operations-commander']
    
    # 获取当前用户 ID，在后台线程中使用
    user_id = current_user.id if current_user.is_authenticated else None
    
    if not expert_list:
        return jsonify({'code': 200, 'message': '无需后台生成'})
    
    def run_background_dispatch():
        """在后台线程中执行"""
        try:
            from flask import current_app
            from flask_login import current_user as bg_current_user
            from models.models import User
            
            with current_app.app_context():
                # 从 user_id 重新加载用户
                if user_id:
                    user = User.query.get(user_id)
                    if user:
                        from flask_login import login_user
                        login_user(user, remember=True)
                
                skill_loader = get_skill_loader()
                llm_service = get_llm_service()
            
            for i, expert_name in enumerate(expert_list):
                logger.info(f'[dispatch_experts_background] 后台处理专家 {i+1}/{len(expert_list)}: {expert_name}')
                skill_info = skill_loader.get_skill_info(expert_name)
                if not skill_info:
                    logger.warning(f'[dispatch_experts_background] 未找到 skill: {expert_name}')
                    continue
                
                # 构建 prompt
                prompt = _build_expert_prompt(expert_name, client_info)
                user_role = current_user.role if current_user.is_authenticated else 'user'
                system_prompt = skill_loader.build_system_prompt(expert_name, client_info, user_role)
                
                try:
                    logger.info(f'[dispatch_experts_background] 开始调用 LLM for expert: {expert_name}')
                    response = llm_service.chat(
                        messages=[
                            {'role': 'system', 'content': system_prompt},
                            {'role': 'user', 'content': prompt}
                        ],
                        temperature=0.7
                    )
                    logger.info(f'[dispatch_experts_background] LLM 调用完成 for expert: {expert_name}')
                    
                    report_content = response.get('content', '') if isinstance(response, dict) else str(response)
                    
                    # 保存报告
                    from models import Client, Expert, ExpertOutput
                    from app import db
                    
                    client = Client.query.filter_by(name=client_info.get('name')).first()
                    expert = Expert.query.filter_by(slug=expert_name).first()
                    if not expert:
                        expert = Expert.query.filter_by(name=expert_name).first()
                    
                    if expert:
                        output = ExpertOutput(
                            expert_id=expert.id,
                            client_id=client.id if client else None,
                            title=f"{skill_info.get('title', expert_name)} - {client_info.get('name', '客户')}",
                            content=report_content[:5000] if len(report_content) > 5000 else report_content
                        )
                        db.session.add(output)
                        db.session.commit()
                        logger.info(f'[dispatch_experts_background] 专家 {expert_name} 报告已保存')
                    
                except Exception as e:
                    logger.error(f'[dispatch_experts_background] expert {expert_name} 异常: {str(e)}')
                    import traceback
                    logger.error(traceback.format_exc())
            
            logger.info(f'[dispatch_experts_background] 所有后台专家处理完成')
            
        except Exception as e:
            logger.error(f'[dispatch_experts_background] 后台线程异常: {str(e)}')
            import traceback
            logger.error(traceback.format_exc())
    
    # 启动后台线程
    thread = threading.Thread(target=run_background_dispatch)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'code': 200,
        'message': f'已启动后台生成 {len(expert_list)} 个报告',
        'data': {'background_experts': expert_list}
    })


def _build_expert_prompt(expert_name: str, client_info: dict) -> str:
    """根据专家类型构建提示词"""
    
    base_info = f"""
客户名称：{client_info.get('client_name', '未知')}
客户类型：{client_info.get('business_type', '未知')}
产品类型：{client_info.get('product_type', '未知')}
服务类型：{client_info.get('service_type', '未知')}
地域范围：{client_info.get('geographic_scope', '未知')}
目标区域：{client_info.get('target_area', '未知')}
品牌定位：{client_info.get('brand_type', '未知')}
品牌描述：{client_info.get('brand_description', '未知')}
语言风格：{client_info.get('language_style', '未知')}
主营业务：{client_info.get('main_product', '未知')}
经营年限：{client_info.get('business_years', '未知')}
其他信息：{client_info.get('other_notes', '未知')}
"""
    
    # 获取模板文件路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 市场分析报告模板
    insights_template_path = os.path.join(base_dir, 'skills', 'insights-analyst', '输出', '行业分析', '行业分析报告_模板.md')
    insights_template = ""
    if os.path.exists(insights_template_path):
        with open(insights_template_path, 'r', encoding='utf-8') as f:
            insights_template = f.read()
    
    # 运营规划模板
    operations_template_path = os.path.join(base_dir, 'skills', 'operations-expert', '输出', '运营规划', '运营规划方案_模板.md')
    operations_template = ""
    if os.path.exists(operations_template_path):
        with open(operations_template_path, 'r', encoding='utf-8') as f:
            operations_template = f.read()
    
    # 关键词库模板
    keyword_template_path = os.path.join(base_dir, 'skills', 'geo-seo', '输出', '关键词库', '关键词库_模板.md')
    keyword_template = ""
    if os.path.exists(keyword_template_path):
        with open(keyword_template_path, 'r', encoding='utf-8') as f:
            keyword_template = f.read()
    
    # 选题库模板
    topic_template_path = os.path.join(base_dir, 'skills', 'geo-seo', '输出', '选题推荐', '选题库_模板.md')
    topic_template = ""
    if os.path.exists(topic_template_path):
        with open(topic_template_path, 'r', encoding='utf-8') as f:
            topic_template = f.read()
    
    prompts = {
        'market-insights-commander': f"""
{base_info}

【市场分析报告生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成报告
2. **核心思维流程**：必须按以下7步顺序进行
   - 1️⃣ 行业分析 → 2️⃣ 找蓝海 → 3️⃣ 人群细分 → 4️⃣ 长尾需求 → 5️⃣ 知识技能解决 → 6️⃣ 搜前搜后 → 7️⃣ 行业关联
3. **内容配比规则**：信任佐证+竞争优势内容占比 **15%**，其他内容占比 **85%**
4. **高权重章节**："用户失败经历分析"是必有内容（融入第四步"人群细分"或单独章节）
5. **必须包含信任佐证4大方向**：专业知识技能、环境、过程、案例
6. **必须包含竞争优势4大维度**：vs同行、vs自己动手

## 报告模板
{insights_template}

请生成完整的市场分析报告。
""",
        'ai-operations-commander': f"""
{base_info}

【运营规划方案生成要求 - 必须严格按模板执行】

## 重要提示
1. **必须使用模板**：请严格按照下方提供的模板结构生成运营规划方案
2. **核心思维流程**：必须按以下7步顺序进行
   - 1️⃣ 行业分析 → 2️⃣ 找蓝海 → 3️⃣ 人群细分 → 4️⃣ 长尾需求 → 5️⃣ 知识技能解决 → 6️⃣ 搜前搜后 → 7️⃣ 行业关联
3. **内容配比规则**：信任佐证+竞争优势内容占比 **15%**，其他内容占比 **85%**
4. **高权重内容**：
   - "信任佐证4大方向"必须有（专业知识技能、环境、过程、案例）
   - "竞争优势4大维度"必须有（vs同行、vs自己动手）
5. **搜前搜后分析**：必须覆盖直接需求、关联需求、潜在需求、决策顾虑

## 运营规划模板
{operations_template}

请生成完整的运营规划方案。

同时，请生成：
1. 关键词库（至少100个关键词）
2. 选题库（至少200条选题）

## 关键词库要求
{keyword_template}

## 选题库要求
{topic_template}
""",
        'geo-seo': f"""
{base_info}

【关键词库与选题库生成要求 - 必须严格按模板执行】

## 关键词库要求
{keyword_template}

## 选题库要求
{topic_template}

请生成完整的关键词库和选题库。
"""
    }
    
    return prompts.get(expert_name, base_info + "\n请根据以上信息提供专业分析和建议。")
