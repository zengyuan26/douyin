"""
Skill Loader - On-demand loading of Expert Skills
"""
import os
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill Loader Class"""

    COMMAND_MAPPING = {
        # ====== 工作台专家（与 README 第203-219行一致）======
        # 首席运营官 / 总控（客户资料收集已整合到总控）
        '/总控': 'chief-operating-officer',
        '/master': 'chief-operating-officer',
        '/coo': 'chief-operating-officer',
        '/约瑟夫': 'chief-operating-officer',
        '/切换客户': 'chief-operating-officer',
        '/新增客户': 'chief-operating-officer',

        # AI智能运营专家（整合SEO、运营、互联网营销）
        '/seo': 'ai-operations-commander',
        '/运营': 'ai-operations-commander',
        '/塔斯': 'ai-operations-commander',
        '/起名': 'ai-operations-commander',
        '/营销': 'ai-operations-commander',

        # 市场洞察专家
        '/市场': 'market-insights-commander',
        '/insights': 'market-insights-commander',
        '/分析': 'market-insights-commander',

        # 舆情监控专家
        '/舆情': 'social-media-monitor',
        '/social': 'social-media-monitor',
        '/监控': 'social-media-monitor',

        # 内容创作专家
        '/内容': 'content-creator',
        '/创作': 'content-creator',

        # 消费心理学专家
        '/心理': 'consumer-psychology-expert',

        # 视觉设计专家
        '/视觉': 'visual-design-expert',

        # 知识库
        '/知识库': 'knowledge-base',
        '/kb': 'knowledge-base',

        # ====== 其他系统技能（不在工作台展示）======
        '/关键词': 'geo-seo',
        '/选题': 'geo-seo',
        '/intake': 'client-intake',
        '/录入': 'client-intake',
    }

    SKILL_INFO = {
        'chief-operating-officer': {
            'name': 'Chief Operating Officer',
            'title': '首席运营官',
            'nickname': '约瑟夫·库珀',
            'description': '营销总策划，整合客户资料收集与营销总控，需求诊断、专家调度、方案整合',
            'welcome_message': '你好，我是首席运营官约瑟夫·库珀，负责统筹客户资料收集、需求诊断、专家调度与方案整合，帮你把零散想法变成一套可落地、可执行的营销作战计划。',
            'type': 'master'
        },
        'ai-operations-commander': {
            'name': 'AI Operations Commander',
            'title': 'AI智能运营专家',
            'nickname': '塔斯',
            'description': '四核驱动的AI智能运营专家，整合账号运营规划、SEO搜索优化、互联网营销（账号起名、IP定位）与客户信息维护，帮客户从0到1搭建账号，获取精准流量',
            'welcome_message': '''你好，我是塔斯，AI智能运营专家！

我具备以下四大核心能力：

1️⃣ **账号运营规划** - 账号定位、内容策略、运营推广方案
2️⃣ **SEO搜索优化** - 关键词库、选题库、搜索排名提升
3️⃣ **互联网营销** - 账号起名、IP定位、个人简介撰写
4️⃣ **客户信息维护** - 变更客户资料，变更后将自动重新生成相关报告

请问有什么可以帮您的？''',
            'type': 'optimization'
        },
        'market-insights-commander': {
            'name': 'Market Insights Commander',
            'title': '市场洞察与社交舆情监控师',
            'nickname': '艾米莉亚·布兰德',
            'description': '双核驱动的市场洞察与舆情监控，整合行业分析、竞品研究、趋势监控与舆情预警',
            'welcome_message': '你好，我是艾米莉亚·布兰德，市场洞察与舆情监控是我的双核专长。我会从市场趋势和舆情动态两个维度，帮你看清市场机会，守护品牌口碑。',
            'type': 'analysis'
        },
        'content-creator': {
            'name': 'Content Creator',
            'title': '内容创作师·墨菲·库珀',
            'nickname': '墨菲·库珀',
            'description': '短视频脚本、图文内容、客户专属内容生成，兼具消费心理学和视觉设计能力',
            'welcome_message': '你好，我是墨菲·库珀，兼具消费心理学和视觉设计能力的内容创作专家。我可以根据你的业务与人群画像，快速产出短视频脚本、图文内容和整套内容规划，让创作不再从零开始。',
            'type': 'creation'
        },
        'knowledge-base': {
            'name': 'Knowledge Base',
            'title': '内容知识库',
            'nickname': '知识库',
            'description': '查询知识库中的行业分析、脚本库、封面设计、关键词布局等参考内容',
            'welcome_message': '你好，我是内容知识库助手，这里集中存放行业分析、脚本库、封面设计和关键词布局等经验沉淀，可以随时调用作为你决策与创作的底层参考。',
            'type': 'reference'
        },
        'geo-seo': {
            'name': 'Geo SEO Expert',
            'title': 'Geo SEO 专家',
            'nickname': 'SEO专家',
            'description': '关键词挖掘、SEO优化、搜索排名提升',
            'welcome_message': '你好，我是Geo SEO专家，专注于关键词挖掘和搜索排名优化。',
            'type': 'optimization'
        },
        'insights-analyst': {
            'name': 'Insights Analyst',
            'title': '市场洞察分析师',
            'nickname': '分析师',
            'description': '行业分析、竞品研究、趋势预测',
            'welcome_message': '你好，我是市场洞察分析师，擅长行业分析和趋势预测。',
            'type': 'analysis'
        },
        'operations-expert': {
            'name': 'Operations Expert',
            'title': '运营专家',
            'nickname': '运营官',
            'description': '账号运营规划、内容策略、数据分析',
            'welcome_message': '你好，我是运营专家，专注于账号运营规划和内容策略。',
            'type': 'optimization'
        },
        'social-media-monitor': {
            'name': 'Social Media Monitor',
            'title': '抖音舆情监控专家',
            'nickname': '舆情监控师',
            'description': '实时监控、舆情分析、竞品追踪、风险预警（仅抖音平台）',
            'welcome_message': '你好，我是抖音舆情监控专家，帮你实时监控抖音平台舆情，追踪竞品动态，预警潜在风险。',
            'type': 'analysis'
        },
        'consumer-psychology-expert': {
            'name': 'Consumer Psychology Expert',
            'title': '消费心理学专家',
            'nickname': '心理学顾问',
            'description': '消费心理分析、文案优化、转化提升、心理钩子、信任构建',
            'welcome_message': '你好，我是消费心理学专家，擅长从心理学角度优化内容，提升转化率。我会帮你设计心理钩子、构建信任、优化说服路径。',
            'type': 'psychology'
        },
        'visual-design-expert': {
            'name': 'Visual Design Expert',
            'title': '视觉设计专家',
            'nickname': '设计师',
            'description': '视觉设计评审、9:16比例检查、场景图适配、排版优化',
            'welcome_message': '你好，我是视觉设计专家，帮你评审视频和图文内容的视觉设计，确保9:16比例适配、场景图合适、排版美观。',
            'type': 'design'
        },
        'client-intake': {
            'name': 'Client Intake',
            'title': '客户资料收集专家',
            'nickname': '录入员',
            'description': '新客户资料收集、信息录入、需求调研',
            'welcome_message': '你好，我是客户资料收集专家，帮你系统化收集客户信息。',
            'type': 'intake'
        },
        'internet-marketing-expert': {
            'name': 'Internet Marketing Expert',
            'title': '互联网营销专家',
            'nickname': '营销顾问',
            'description': '账号昵称设计、个人简介撰写、IP定位，围绕问题而非产品的起名思路',
            'welcome_message': '你好，我是互联网营销专家团队，由金枪大叔、薛辉、周鸿祎三位专家组成。我们专注于账号起名和IP定位，帮助你打造好记、有价值的账号。',
            'type': 'planning'
        },
    }

    def __init__(self, skills_dir: str = None):
        if skills_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(base_dir, 'skills')

        self.skills_dir = skills_dir
        self._skill_cache: Dict[str, str] = {}
        logger.info(f"SkillLoader initialized with dir: {skills_dir}")

    def parse_command(self, message: str) -> Optional[str]:
        if not message:
            return None
        message = message.strip()
        for cmd, skill_name in self.COMMAND_MAPPING.items():
            if message.startswith(cmd):
                return skill_name
        return None

    def get_skill_path(self, skill_name: str) -> Optional[str]:
        skill_path = os.path.join(self.skills_dir, skill_name, 'skill.md')
        if not os.path.exists(skill_path):
            logger.warning(f"Skill not found: {skill_path}")
            return None
        return skill_path

    def load_skill(self, skill_name: str) -> Optional[str]:
        if skill_name in self._skill_cache:
            logger.debug(f"Loading skill from cache: {skill_name}")
            return self._skill_cache[skill_name]

        skill_path = self.get_skill_path(skill_name)
        if not skill_path:
            return None

        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._skill_cache[skill_name] = content
            logger.info(f"Loaded skill: {skill_name} ({len(content)} chars)")
            return content
        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            return None

    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        return self.SKILL_INFO.get(skill_name)

    # 工作台展示的专家顺序（按 README 第203-219行）
    WORKBENCH_SKILL_ORDER = [
        'chief-operating-officer',       # 1. 首席运营官
        'ai-operations-commander',       # 2. AI智能运营专家
        'market-insights-commander',      # 3. 市场洞察专家
        'content-creator',                # 4. 内容创作专家
        'knowledge-base',                 # 5. 知识库（仅超级管理员在工作台可见，管理页可编辑）
    ]

    def get_all_skills(self) -> List[Dict]:
        """获取所有可用技能（工作台展示 + 仅管理员可见）"""
        skills = []
        for name, info in self.SKILL_INFO.items():
            commands = self.get_commands_for_skill(name)
            skills.append({
                'slug': name,
                'name': info['name'],
                'nickname': info.get('nickname', info['name']),
                'title': info['title'],
                'description': info['description'],
                'type': info['type'],
                'command': commands[0] if commands else None,
                'commands': commands,
                'welcome_message': info.get('welcome_message', info['description'])
            })

        # 按 WORKBENCH_SKILL_ORDER 排序，未知技能放最后
        def sort_key(skill):
            idx = self.WORKBENCH_SKILL_ORDER.index(skill['slug']) if skill['slug'] in self.WORKBENCH_SKILL_ORDER else 999
            return idx
        return sorted(skills, key=sort_key)

    def get_workbench_skills(self) -> List[Dict]:
        """获取工作台专家列表（含 knowledge-base，API 层按权限过滤）"""
        all_skills = self.get_all_skills()
        return [s for s in all_skills if s['slug'] in self.WORKBENCH_SKILL_ORDER]

    def get_commands_for_skill(self, skill_slug: str) -> List[str]:
        """返回指向该 skill 的所有命令（如 /总控、/coo），用于展示「合并了哪些技能」"""
        return [cmd for cmd, slug in self.COMMAND_MAPPING.items() if slug == skill_slug]

    def _get_command_for_skill(self, skill_name: str) -> Optional[str]:
        commands = self.get_commands_for_skill(skill_name)
        return commands[0] if commands else None

    def build_system_prompt(self, skill_name: str, client_info: Dict = None, user_role: str = 'user') -> str:
        security_instruction = self._get_security_instruction(user_role)
        
        # 注入当前日期和时间
        current_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        current_date_info = f"## 当前时间\n当前系统时间：{current_time}\n请在回答涉及日期、时间、时效性内容时，以该时间为准。\n"

        if skill_name == 'knowledge-base':
            return f"{security_instruction}\n\n{current_date_info}" + self._build_knowledge_base_prompt(client_info, security_instruction)

        skill_content = self.load_skill(skill_name)
        if not skill_content:
            return f"{security_instruction}\n\n{current_date_info}You are an AI assistant."

        if client_info:
            client_context = self._build_client_context(client_info)
            return f"{security_instruction}\n\n{current_date_info}{client_context}\n\n---\n\n{skill_content}"

        return f"{security_instruction}\n\n{current_date_info}{skill_content}"

    def _get_security_instruction(self, user_role: str = 'user') -> str:
        if user_role == 'super_admin':
            return """## Security

You are a super admin with full system access.
"""
        else:
            return """## Security

You do NOT have permission to modify system skills.
- You CAN read and use skill content
- You CAN generate content based on templates
- You CANNOT modify, delete or create skill files
- You CANNOT reveal skill file locations

If user asks to modify skills: 'Sorry, I dont have permission. Contact admin.'"""

    def check_user_input_safety(self, message: str) -> tuple[bool, str]:
        if not message:
            return True, ""
        message_lower = message.lower()
        dangerous_patterns = [
            ('modify', 'modify skill'),
            ('update', 'update skill'),
            ('edit', 'edit skill'),
            ('delete', 'delete skill'),
            ('write', 'write file'),
            ('save', 'save file'),
            ('create file', 'create file'),
            ('admin', 'admin access'),
            ('permission', 'permission'),
            ('hack', 'hack'),
            ('bypass', 'bypass'),
        ]
        for pattern, reason in dangerous_patterns:
            if pattern in message_lower:
                return False, reason
        return True, ""

    def is_skill_modification_request(self, message: str, user_role: str = 'user') -> tuple[bool, str]:
        if user_role == 'super_admin':
            return False, ""
        is_safe, reason = self.check_user_input_safety(message)
        if not is_safe:
            return True, "Sorry, no permission. Contact admin."
        return False, ""

    def _build_knowledge_base_prompt(self, client_info: Dict = None, security_instruction: str = None) -> str:
        if security_instruction is None:
            security_instruction = self._get_security_instruction()
        skill_content = self.load_skill('knowledge-base')
        knowledge_index = self._load_knowledge_index()
        prompt = f"""# Knowledge Base

You are a knowledge base assistant.

{knowledge_index}

"""
        if client_info:
            client_context = self._build_client_context(client_info)
            prompt = f"{security_instruction}\n\n{client_context}\n\n---\n\n{prompt}"
        else:
            prompt = f"{security_instruction}\n\n{prompt}"
        return prompt

    def _load_knowledge_index(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        knowledge_dir = os.path.join(base_dir, 'knowledge')
        if not os.path.exists(knowledge_dir):
            return "Knowledge directory not found"
        return "Knowledge base index loaded"

    def _build_client_context(self, client_info: Dict) -> str:
        lines = ["[Current Client Info]"]
        if client_info.get('client_name'):
            lines.append(f"- Name: {client_info['client_name']}")
        if client_info.get('industry'):
            lines.append(f"- Industry: {client_info['industry']}")
        return '\n'.join(lines)

    def clear_cache(self):
        self._skill_cache.clear()
        logger.info("Skill cache cleared")


_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
