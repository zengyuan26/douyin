"""
公开内容生成平台 - 模板配置加载器

功能：
1. 加载配置文件（_global 目录）
2. 加载内容模板（content_templates 目录）
3. 混合模式：配置优先，数据库覆盖
"""

import json
import os
from typing import Dict, List, Optional, Any
from functools import lru_cache


class TemplateConfigLoader:
    """模板配置加载器"""

    def __init__(self, config_dir: str = None):
        """
        初始化加载器

        Args:
            config_dir: 配置文件目录，默认使用系统部署/config/templates
        """
        if config_dir is None:
            # 默认使用系统部署目录下的配置
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.join(base_dir, 'config', 'templates')

        self.config_dir = config_dir
        self._global_dir = os.path.join(config_dir, '_global')
        self._content_dir = os.path.join(config_dir, 'content_templates')
        self._industry_dir = os.path.join(config_dir, 'industry_analysis')

    def get_config_path(self, filename: str) -> str:
        """获取配置文件路径"""
        return os.path.join(self._global_dir, filename)

    def load_text_file(self, filename: str) -> str:
        """加载文本文件"""
        filepath = self.get_config_path(filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ""
        except Exception as e:
            print(f"[TemplateConfig] 加载文件失败 {filename}: {e}")
            return ""

    def load_json_file(self, filename: str) -> Dict:
        """加载 JSON 文件"""
        filepath = self.get_config_path(filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            print(f"[TemplateConfig] JSON 解析失败 {filename}: {e}")
            return {}
        except Exception as e:
            print(f"[TemplateConfig] 加载文件失败 {filename}: {e}")
            return {}

    @lru_cache(maxsize=1)
    def get_keyword_supplement_config(self) -> Dict:
        """获取关键词补充配置"""
        return self.load_json_file('keyword_supplement_prompt.json')

    @lru_cache(maxsize=1)
    def get_keyword_supplement_system(self) -> str:
        """获取关键词补充系统提示词"""
        return self.load_text_file('keyword_supplement_system.txt')

    @lru_cache(maxsize=1)
    def get_content_generate_config(self) -> Dict:
        """获取内容生成配置"""
        return self.load_json_file('content_generate_prompt.json')

    @lru_cache(maxsize=1)
    def get_content_generate_system(self) -> str:
        """获取内容生成系统提示词"""
        return self.load_text_file('content_generate_system.txt')

    def get_title_templates(self) -> List[Dict]:
        """获取标题模板列表"""
        config = self.get_content_generate_config()
        return config.get('title_templates', [])

    def build_keyword_prompt(self, params: Dict) -> str:
        """
        构建关键词补充提示词

        Args:
            params: {
                'business_type': str,
                'industry': str,
                'brand_type': str,
                'main_products': str,
                'core_advantages': str,
                'target_customers': str,
                'region': str,
                'language': str
            }
        """
        config = self.get_keyword_supplement_config()
        template = config.get('user_template', '')

        # 替换模板变量
        prompt = template.format(**params)
        return prompt

    def build_content_prompt(self, params: Dict) -> str:
        """
        构建内容生成提示词

        Args:
            params: {
                'industry': str,
                'target_customer': str,
                'business_description': str,
                'content_type': str,
                'keywords_info': str,
                'topic_direction': str
            }
        """
        config = self.get_content_generate_config()
        template = config.get('user_template', '')

        # 替换模板变量
        prompt = template.format(**params)
        return prompt

    def get_llm_params(self, template_type: str = 'content_generate') -> Dict:
        """
        获取 LLM 调用参数

        Args:
            template_type: 模板类型

        Returns:
            LLM 参数配置
        """
        if template_type == 'keyword_supplement':
            return self.get_keyword_supplement_config()
        elif template_type == 'content_generate':
            return self.get_content_generate_config()
        else:
            return {
                'temperature': 0.7,
                'max_tokens': 2000
            }

    def get_content_template(self, template_name: str = '图文模板_通用.md') -> str:
        """获取内容模板"""
        filepath = os.path.join(self._content_dir, template_name)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            # 尝试加载通用模板
            return self.get_content_template('图文模板_通用.md')
        except Exception as e:
            print(f"[TemplateConfig] 加载内容模板失败 {template_name}: {e}")
            return ""

    def get_content_template_names(self) -> List[str]:
        """获取所有内容模板名称"""
        templates = []
        try:
            for filename in os.listdir(self._content_dir):
                if filename.endswith('.md'):
                    templates.append(filename)
        except FileNotFoundError:
            pass
        return templates

    def load_industry_analysis_config(self) -> Dict:
        """加载行业分析配置"""
        config = {
            'system_prompt': self.load_text_file('industry_analysis/system_prompt.txt') or
                             self.load_text_file('system_prompt.txt'),
            'output_format': self.load_text_file('industry_analysis/output_format.md')
        }
        return config

    def reload(self):
        """重新加载配置（清除缓存）"""
        self.get_keyword_supplement_config.cache_clear()
        self.get_content_generate_config.cache_clear()
        self.get_keyword_supplement_system.cache_clear()
        self.get_content_generate_system.cache_clear()


# 全局实例
template_config = TemplateConfigLoader()


# =============================================================================
# 便捷函数
# =============================================================================

def get_template_config() -> TemplateConfigLoader:
    """获取模板配置加载器"""
    return template_config


def get_keyword_prompt(params: Dict) -> str:
    """构建关键词补充提示词"""
    return template_config.build_keyword_prompt(params)


def get_content_prompt(params: Dict) -> str:
    """构建内容生成提示词"""
    return template_config.build_content_prompt(params)


def get_llm_config(template_type: str = 'content_generate') -> Dict:
    """获取 LLM 配置"""
    return template_config.get_llm_params(template_type)


def get_system_prompt(template_type: str = 'content_generate') -> str:
    """获取系统提示词"""
    if template_type == 'keyword_supplement':
        return template_config.get_keyword_supplement_system()
    elif template_type == 'content_generate':
        return template_config.get_content_generate_system()
    else:
        return ""
