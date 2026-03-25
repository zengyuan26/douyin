"""
Skill Loader - On-demand loading of Expert Skills

This module implements on-demand loading advantages:
1. Only read the corresponding skill.md when user calls an expert
2. Reduce memory usage
3. Support dynamic skill content updates
"""
import os
import re
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill 加载器类"""
    
    # 专家命令映射 - 命令 -> Skill 目录名
    COMMAND_MAPPING = {
        # 总控命令
        '/总控': 'chief-operating-officer',
        '/coo': 'chief-operating-officer',
        '/运营官': 'chief-operating-officer',
        '/约瑟夫': 'chief-operating-officer',
        '/新增客户': 'chief-operating-officer',
        '/切换客户': 'chief-operating-officer',
        '/客户资料': 'chief-operating-officer',

        # 专业命令
        '/seo': 'ai-operations-commander',
        '/运营': 'ai-operations-commander',
        '/塔斯': 'ai-operations-commander',
        '/市场': 'market-insights-commander',
        '/舆情': 'market-insights-commander',
        '/艾米莉亚': 'market-insights-commander',
        '/内容': 'content-creator',
        '/创作': 'content-creator',
        '/知识库': 'knowledge-base',
        '/kb': 'knowledge-base',
        '/营销': 'internet-marketing-expert',
        '/起名': 'internet-marketing-expert',
    }

    # Skill 索引信息
    SKILL_INFO = {
        'chief-operating-officer': {
            'name': 'Chief Operating Officer',
            'title': '首席运营官',
            'nickname': '约瑟夫·库珀',
            'description': '营销总策划,整合客户资料收集与营销总控,需求诊断、专家调度、方案整合',
            'welcome_message': '你好,我是首席运营官约瑟夫·库珀,负责统筹客户资料收集、需求诊断、专家调度与方案整合,帮你把零散想法变成一套可落地、可执行的营销作战计划.',
            'type': 'master'
        },
        'ai-operations-commander': {
            'name': 'AI Operations Commander',
            'title': 'AI智能运营专家',
            'nickname': '塔斯',
            'description': '双核驱动的AI智能运营专家,整合账号运营规划与SEO搜索优化,帮客户从0到1搭建账号,获取精准流量',
            'welcome_message': '你好,我是塔斯,AI智能运营专家!我将整合运营规划与SEO优化能力,帮您从0到1搭建账号,获取精准流量,实现从关键词到选题到内容的全链路优化.',
            'type': 'optimization'
        },
        'market-insights-commander': {
            'name': 'Market Insights Commander',
            'title': '市场洞察与社交舆情监控师',
            'nickname': '艾米莉亚·布兰德',
            'description': '双核驱动的市场洞察与舆情监控,整合行业分析、竞品研究、趋势监控与舆情预警',
            'welcome_message': '你好,我是艾米莉亚·布兰德,市场洞察与舆情监控是我的双核专长.我会从市场趋势和舆情动态两个维度,帮你看清市场机会,守护品牌口碑.',
            'type': 'analysis'
        },
        'content-creator': {
            'name': 'Content Creator',
            'title': '内容创作师·墨菲·库珀',
            'nickname': '墨菲·库珀',
            'description': '短视频脚本、图文内容、客户专属内容生成，兼具消费心理学和视觉设计能力',
            'welcome_message': '你好,我是墨菲·库珀,兼具消费心理学和视觉设计能力的内容创作专家。我可以根据你的业务与人群画像,快速产出短视频脚本、图文内容和整套内容规划,让创作不再从零开始.',
            'type': 'creation'
        },
        'knowledge-base': {
            'name': 'Knowledge Base',
            'title': '内容知识库',
            'nickname': '知识库',
            'description': '查询知识库中的行业分析、脚本库、封面设计、关键词布局等参考内容',
            'welcome_message': '你好,我是内容知识库助手,这里集中存放行业分析、脚本库、封面设计和关键词布局等经验沉淀,可以随时调用作为你决策与创作的底层参考.',
            'type': 'reference'
        },
        'internet-marketing-expert': {
            'name': 'Internet Marketing Expert',
            'title': '互联网营销专家',
            'nickname': '营销顾问',
            'description': '账号昵称设计、个人简介撰写、IP定位,围绕问题而非产品的起名思路',
            'welcome_message': '你好,我是互联网营销专家团队,由金枪大叔、薛辉、周鸿祎三位专家组成.我们专注于账号起名和IP定位,帮助你打造好记、有价值的账号.',
            'type': 'planning'
        },
    }

    def __init__(self, skills_dir: str = None):
        """
        初始化 Skill 加载器
        
        Args:
            skills_dir: Skills 目录路径
        """
        if skills_dir is None:
            # 默认使用项目目录下的 skills
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            skills_dir = os.path.join(base_dir, 'skills')
        
        self.skills_dir = skills_dir
        self._skill_cache: Dict[str, str] = {}  # 简单缓存
        logger.info(f"SkillLoader initialized with dir: {skills_dir}")
    
    def parse_command(self, message: str) -> Optional[str]:
        """
        解析消息中的命令
        
        Args:
            message: 用户消息
            
        Returns:
            Skill 目录名,如果无命令则返回 None
        """
        if not message:
            return None
        
        message = message.strip()
        
        # 检查是否包含命令
        for cmd, skill_name in self.COMMAND_MAPPING.items():
            if message.startswith(cmd):
                return skill_name
        
        return None
    
    def get_skill_path(self, skill_name: str) -> Optional[str]:
        """
        获取 Skill 文件路径
        
        Args:
            skill_name: Skill 目录名
            
        Returns:
            skill.md 文件路径
        """
        skill_path = os.path.join(self.skills_dir, skill_name, 'skill.md')
        
        if not os.path.exists(skill_path):
            logger.warning(f"Skill not found: {skill_path}")
            return None
        
        return skill_path
    
    def load_skill(self, skill_name: str) -> Optional[str]:
        """
        加载 Skill 内容(按需加载)
        
        Args:
            skill_name: Skill 目录名
            
        Returns:
            Skill 内容,如果加载失败返回 None
        """
        # 检查缓存
        if skill_name in self._skill_cache:
            logger.debug(f"Loading skill from cache: {skill_name}")
            return self._skill_cache[skill_name]
        
        # 读取文件
        skill_path = self.get_skill_path(skill_name)
        if not skill_path:
            return None
        
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 缓存内容
            self._skill_cache[skill_name] = content
            logger.info(f"Loaded skill: {skill_name} ({len(content)} chars)")
            
            return content
        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}: {e}")
            return None
    
    def get_skill_info(self, skill_name: str) -> Optional[Dict]:
        """
        获取 Skill 基本信息
        
        Args:
            skill_name: Skill 目录名
            
        Returns:
            Skill 信息字典
        """
        return self.SKILL_INFO.get(skill_name)
    
    def get_all_skills(self) -> List[Dict]:
        """
        获取所有可用 Skills 列表
        
        Returns:
            Skills 信息列表
        """
        return [
            {
                'name': info['name'],
                'nickname': info.get('nickname', info['name']),
                'title': info['title'],
                'description': info['description'],
                'type': info['type'],
                'command': self._get_command_for_skill(name),
                'welcome_message': info.get('welcome_message', info['description'])
            }
            for name, info in self.SKILL_INFO.items()
        ]
    
    def _get_command_for_skill(self, skill_name: str) -> Optional[str]:
        """获取 Skill 对应的命令"""
        for cmd, name in self.COMMAND_MAPPING.items():
            if name == skill_name:
                return cmd
        return None
    
    def build_system_prompt(self, skill_name: str, client_info: Dict = None, user_role: str = 'user') -> str:
        """
        构建 System Prompt

        Args:
            skill_name: Skill 目录名
            client_info: 客户信息(可选)
            user_role: 用户角色 (super_admin, admin, public_user, user)

        Returns:
            完整的 System Prompt
        """
        # 安全指令 - 始终注入
        security_instruction = self._get_security_instruction(user_role)

        # 知识库特殊处理 - 需要加载知识库索引
        if skill_name == 'knowledge-base':
            return self._build_knowledge_base_prompt(client_info, security_instruction)

        skill_content = self.load_skill(skill_name)
        if not skill_content:
            return f"{security_instruction}\n\n你是一个 AI 助手."

        # 如果有客户信息,添加到 prompt 开头
        if client_info:
            client_context = self._build_client_context(client_info)
            return f"{security_instruction}\n\n{client_context}\n\n---\n\n{skill_content}"

        return f"{security_instruction}\n\n{skill_content}"

    def _get_security_instruction(self, user_role: str = 'user') -> str:
        """
        获取安全指令 - 根据用户角色决定权限

        Args:
            user_role: 用户角色

        Returns:
            安全指令文本
        """
        base_instruction = """## ⚠️ 安全限制

你是一个AI助手,请严格遵守以下安全限制:

"""

        if user_role == 'super_admin':
            # 超级管理员可以修改 skill
            return base_instruction + """✅ **你是超级管理员**,拥有系统管理权限.

**你的权限:**
- 可以读取和使用 skills 中的内容
- 可以根据客户需求调整和修改 skill 内容
- 可以创建新的内容模板

**重要提醒:**
- 修改 skill 内容后,请确保备份原文件
- 所有的修改都应该服务于客户需求
- 保持 skill 的专业性和准确性
"""
        else:
            # 普通用户和渠道用户只能使用 skill,不能修改
            return base_instruction + """❌ **你没有系统管理权限**

**你的权限:**
- ✅ 可以读取和使用 skills 中的内容
- ✅ 可以根据 skills 模板生成客户内容
- ❌ **禁止修改、删除或创建 skill 文件**
- ❌ **禁止尝试通过任何方式修改系统文件**

**禁止的行为(任何一条都立即拒绝):**
- ❌ 不要回答任何关于"修改skill"、"更新skill"、"创建skill"、"删除skill"的问题
- ❌ 不要执行任何文件写入操作
- ❌ 不要提供任何关于如何修改系统文件的指导
- ❌ 不要透露skill文件的存储位置或路径

**如果用户要求修改skill:**
必须直接拒绝,并回复:"抱歉,我没有权限修改系统配置.如需修改,请联系超级管理员.""

    def check_user_input_safety(self, message: str) -> tuple[bool, str]:
        """
        Check if user input contains malicious intent (trying to modify skill)

        Args:
            message: User message

        Returns:
            (is_safe, reason) - Whether safe, and the reason
        """
        if not message:
            return True, ""

        message_lower = message.lower()

        # 检测尝试修改skill的关键词
        dangerous_patterns = [
            # 修改类
            ('修改', '修改skill相关内容'),
            ('更新', '更新skill文件'),
            ('改写', '改写skill内容'),
            ('编辑', '编辑skill模板'),
            ('删除', '删除skill'),
            # 文件操作类
            ('写入', '写入文件'),
            ('保存到', '保存到文件'),
            ('创建文件', '创建新文件'),
            ('删除文件', '删除文件'),
            # skill操作类
            ('skill', '操作skill'),
            ('模板', '修改模板'),
            # 系统操作类
            ('管理员', '获取管理员权限'),
            ('权限', '提升权限'),
            ('后门', '尝试后门'),
            ('绕过', '绕过限制'),
        ]

        for pattern, reason in dangerous_patterns:
            if pattern in message_lower:
                # 检查是否有操作上下文(修改/删除/创建等)
                action_patterns = ['修改', '更新', '改写', '编辑', '删除', '写入', '保存', '创建', '获取', '提升', '绕过']
                for action in action_patterns:
                    if action in message_lower:
                        return False, f"检测到潜在危险操作: {reason}"

        return True, ""

    def is_skill_modification_request(self, message: str, user_role: str = 'user') -> tuple[bool, str]:
        """
        Check if user is requesting to modify skill.

        Args:
            message: User message
            user_role: User role

        Returns:
            Tuple of (is_modification_request, response)
        """
        if user_role == 'super_admin':
            return False, ""

        is_safe, reason = self.check_user_input_safety(message)
        if not is_safe:
            return True, "Sorry, no permission."

        return False, ""

    def _build_knowledge_base_prompt(self, client_info: Dict = None, security_instruction: str = None) -> str:
        """Build knowledge base system prompt"""
        # 获取安全指令
        if security_instruction is None:
            security_instruction = self._get_security_instruction()

        # 先加载 knowledge-base skill
        skill_content = self.load_skill('knowledge-base')

        # 再加载知识库索引
        knowledge_index = self._load_knowledge_index()

        prompt = f"""# Content Knowledge Base Skill

You are a knowledge base assistant, helping users query reference content in the knowledge base.

## Knowledge Base Index

{knowledge_index}

## Your Tasks

1. When users ask about references or viewing the knowledge base, list relevant categories
2. When users specify a specific category or content, extract relevant information from the knowledge base
3. Help users understand the analysis dimension framework in the knowledge base

## Usage

The knowledge base contains three main types of content:
- Text content: Industry analysis, copy materials, trending title library
- Image/Text content: Topic library, cover design references, keyword layout examples
- Short video content: Script library, shooting technique references, trending structure analysis

"""

        # 如果有客户信息,添加客户上下文
        if client_info:
            client_context = self._build_client_context(client_info)
            prompt = f"{security_instruction}\n\n{client_context}\n\n---\n\n{prompt}"
        else:
            prompt = f"{security_instruction}\n\n{prompt}"

        return prompt

    def _load_knowledge_index(self) -> str:
        """加载知识库完整索引"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        knowledge_dir = os.path.join(base_dir, '知识库')

        if not os.path.exists(knowledge_dir):
            return "知识库目录不存在"

        output = []
        output.append("# 📚 内容分析知识库")
        output.append("")

        # 遍历三大分类
        categories = [
            ('纯文字类', ['行业分析', '文案素材', '爆款标题库']),
            ('图文类', ['行业分析', '选题库', '封面设计参考', '关键词布局案例']),
            ('短视频类', ['行业分析', '脚本库', '拍摄技巧参考', '爆款结构分析'])
        ]

        for category, subdirs in categories:
            output.append(f"## 📁 {category}")
            for subdir in subdirs:
                subdir_path = os.path.join(knowledge_dir, category, subdir)
                if os.path.exists(subdir_path):
                    readme_path = os.path.join(subdir_path, 'README.md')
                    if os.path.exists(readme_path):
                        try:
                            with open(readme_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                # 提取前 500 字符
                                output.append(f"\n### {subdir}")
                                output.append(content[:800])
                        except:
                            pass
            output.append("")

        return "\n".join(output)

    def search_knowledge(self, keyword: str) -> str:
        """搜索知识库内容"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        knowledge_dir = os.path.join(base_dir, '知识库')

        if not os.path.exists(knowledge_dir):
            return "知识库目录不存在"

        results = []
        keyword_lower = keyword.lower()

        # 遍历所有 md 文件
        for root, dirs, files in os.walk(knowledge_dir):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if keyword_lower in content.lower():
                                # 找到相关文件,提取相关段落
                                rel_path = os.path.relpath(file_path, knowledge_dir)
                                results.append(f"\n### 📄 {rel_path}\n")
                                # 找到匹配的段落
                                lines = content.split('\n')
                                for i, line in enumerate(lines):
                                    if keyword_lower in line.lower():
                                        context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                                        results.append(context)
                                        results.append("...")
                    except:
                        pass

        if not results:
            return f"未找到与'{keyword}'相关的内容"

        return f"搜索结果:\n" + "\n".join(results[:5000])  # 限制返回长度
    
    def _build_client_context(self, client_info: Dict) -> str:
        lines = ["[Current Client Info]"]

        if client_info.get('client_name'):
            lines.append(f"- Client Name: {client_info['client_name']}")

        if client_info.get('industry'):
            lines.append(f"- Industry: {client_info['industry']}")

        if client_info.get('business_description'):
            lines.append(f"- Business: {client_info['business_description']}")

        if client_info.get('business_type'):
            lines.append(f"- Business Type: {client_info['business_type']}")

        if client_info.get('geographic_scope'):
            lines.append(f"- Service Area: {client_info['geographic_scope']}")

        if client_info.get('brand_type'):
            lines.append(f"- Brand Type: {client_info['brand_type']}")

        return '\n'.join(lines)
    
    def clear_cache(self):
        """Clear cache"""
        self._skill_cache.clear()
        logger.info("Skill cache cleared")


# Singleton instance
_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    """Get SkillLoader singleton"""
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
