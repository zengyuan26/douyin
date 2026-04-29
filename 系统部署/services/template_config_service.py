"""
模板配置服务

功能：
1. 模板 CRUD + 变量管理
2. 模板版本控制
3. 变量替换引擎
4. 模板预览（注入变量后的效果）
"""

import json
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from models.public_models import (
    TemplateVersionHistory,
    TemplateVariable,
    ContentSectionDisplayConfig,
    db
)
from models.models import ReportTemplate
from sqlalchemy import text


class TemplateConfigService:
    """模板配置服务"""

    # 模板类型常量
    TYPE_KEYWORD = 'keyword'          # 关键词库模板
    TYPE_TOPIC = 'topic'             # 选题库模板
    TYPE_MARKET = 'market_analysis'   # 市场分析模板
    TYPE_OPERATION = 'operation'      # 运营规划模板

    # 变量正则：支持 {变量名} 和 {{变量名}}
    VAR_PATTERN = re.compile(r'\{\{?\s*([a-zA-Z0-9_\u4e00-\u9fa5]+)\s*\}?\}')

    @classmethod
    # =========================================================================
    # 一、模板读取
    # =========================================================================

    def get_template(cls, template_type: str, template_category: str = 'universal') -> Optional[Dict]:
        """
        获取指定类型的模板

        Args:
            template_type: 模板类型 keyword/topic/market_analysis/operation
            template_category: 模板分类 universal/industry/custom

        Returns:
            模板字典 或 None
        """
        tpl = ReportTemplate.query.filter_by(
            template_type=template_type,
            template_category=template_category,
            is_active=True
        ).first()

        if not tpl:
            # 尝试通用模板
            tpl = ReportTemplate.query.filter_by(
                template_type=template_type,
                template_category='universal',
                is_active=True
            ).first()

        if not tpl:
            return None

        return cls._template_to_dict(tpl)

    @classmethod
    def get_all_templates(cls, template_type: str = None) -> List[Dict]:
        """获取所有模板列表"""
        query = ReportTemplate.query.filter_by(is_active=True)
        if template_type:
            query = query.filter_by(template_type=template_type)

        templates = query.order_by(ReportTemplate.updated_at.desc()).all()
        return [cls._template_to_dict(t) for t in templates]

    @classmethod
    def get_template_by_id(cls, template_id: int) -> Optional[Dict]:
        """根据ID获取模板"""
        tpl = ReportTemplate.query.get(template_id)
        return cls._template_to_dict(tpl) if tpl else None

    @classmethod
    def _template_to_dict(cls, tpl: ReportTemplate) -> Dict:
        """ORM模型转字典"""
        return {
            'id': tpl.id,
            'template_name': tpl.template_name,
            'template_type': tpl.template_type,
            'template_category': tpl.template_category,
            'template_content': tpl.template_content or '',
            'variables_config': tpl.variables_config or [],
            'version': tpl.version,
            'is_active': tpl.is_active,
            'created_at': tpl.created_at.isoformat() if tpl.created_at else None,
            'updated_at': tpl.updated_at.isoformat() if tpl.updated_at else None,
        }

    # =========================================================================
    # 二、变量管理
    # =========================================================================

    @classmethod
    def get_variables(cls, template_type: str) -> List[Dict]:
        """获取模板变量列表"""
        vars = TemplateVariable.query.filter_by(
            template_type=template_type
        ).order_by(TemplateVariable.display_order).all()

        return [{
            'id': v.id,
            'variable_name': v.variable_name,
            'variable_label': v.variable_label,
            'variable_type': v.variable_type,
            'default_value': v.default_value,
            'description': v.description,
            'is_required': v.is_required,
            'options': json.loads(v.options) if isinstance(v.options, str) else (v.options or []),
            'display_order': v.display_order,
        } for v in vars]

    @classmethod
    def save_variable(cls, template_type: str, var_data: Dict, created_by: int = None) -> Dict:
        """保存模板变量"""
        var_id = var_data.get('id')
        var_name = var_data.get('variable_name', '').strip()

        if not var_name:
            return {'success': False, 'message': '变量名不能为空'}

        if var_id:
            var = TemplateVariable.query.get(var_id)
            if var:
                var.variable_label = var_data.get('variable_label', var.variable_label)
                var.variable_type = var_data.get('variable_type', var.variable_type)
                var.default_value = var_data.get('default_value', var.default_value)
                var.description = var_data.get('description', var.description)
                var.is_required = var_data.get('is_required', var.is_required)
                var.options = json.dumps(var_data.get('options', []), ensure_ascii=False) if var_data.get('options') else None
                var.display_order = var_data.get('display_order', var.display_order)
        else:
            var = TemplateVariable(
                template_type=template_type,
                variable_name=var_name,
                variable_label=var_data.get('variable_label', var_name),
                variable_type=var_data.get('variable_type', 'text'),
                default_value=var_data.get('default_value'),
                description=var_data.get('description'),
                is_required=var_data.get('is_required', False),
                options=json.dumps(var_data.get('options', []), ensure_ascii=False) if var_data.get('options') else None,
                display_order=var_data.get('display_order', 0),
            )
            db.session.add(var)

        db.session.commit()
        return {'success': True, 'variable': {
            'id': var.id,
            'variable_name': var.variable_name,
            'variable_label': var.variable_label,
        }}

    @classmethod
    def delete_variable(cls, variable_id: int) -> bool:
        """删除模板变量"""
        var = TemplateVariable.query.get(variable_id)
        if var:
            db.session.delete(var)
            db.session.commit()
            return True
        return False

    @classmethod
    def save_variables_batch(cls, template_type: str, variables: List[Dict], created_by: int = None) -> Dict:
        """批量保存变量"""
        results = {'saved': 0, 'failed': 0, 'errors': []}
        for var_data in variables:
            result = cls.save_variable(template_type, var_data, created_by)
            if result['success']:
                results['saved'] += 1
            else:
                results['failed'] += 1
                results['errors'].append(result.get('message', '未知错误'))
        return results

    # =========================================================================
    # 三、模板 CRUD
    # =========================================================================

    @classmethod
    def save_template(cls, template_data: Dict, created_by: int = None, save_version: bool = True) -> Dict:
        """
        保存模板（新建或更新）

        Args:
            template_data: 模板数据
            created_by: 创建者ID
            save_version: 是否保存版本快照

        Returns:
            {'success': bool, 'message': str, 'template': dict}
        """
        template_id = template_data.get('id')
        template_type = template_data.get('template_type')
        template_name = template_data.get('template_name', '').strip()

        if not template_name:
            return {'success': False, 'message': '模板名称不能为空'}

        # 自动生成版本号
        if template_id:
            old = ReportTemplate.query.get(template_id)
            if old:
                old_version = old.version or '1.0'
                new_version = cls._bump_version(old_version)
                version = new_version
            else:
                template_id = None
        else:
            version = template_data.get('version', '1.0')

        # 保存版本快照
        if save_version and template_id:
            cls._save_version_snapshot(template_id, template_type, version,
                                       template_data.get('template_content', ''),
                                       template_data.get('variables_config', []),
                                       template_data.get('change_summary', ''),
                                       created_by)

        if template_id:
            tpl = ReportTemplate.query.get(template_id)
            if not tpl:
                return {'success': False, 'message': '模板不存在'}
            tpl.template_name = template_name
            tpl.template_content = template_data.get('template_content', tpl.template_content)
            tpl.variables_config = template_data.get('variables_config', tpl.variables_config)
            tpl.version = version
            tpl.template_category = template_data.get('template_category', tpl.template_category)
        else:
            tpl = ReportTemplate(
                template_name=template_name,
                template_type=template_type,
                template_category=template_data.get('template_category', 'universal'),
                template_content=template_data.get('template_content', ''),
                variables_config=template_data.get('variables_config'),
                version=version,
                is_active=True,
                created_by=created_by,
            )
            db.session.add(tpl)

        db.session.commit()
        return {
            'success': True,
            'message': '模板保存成功',
            'template': cls._template_to_dict(tpl),
            'version': version,
        }

    @classmethod
    def _bump_version(cls, current: str) -> str:
        """递增版本号 v1.0 -> v1.1"""
        try:
            parts = current.lstrip('v').split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return f"v{major}.{minor + 1}"
        except:
            return 'v1.1'

    @classmethod
    def _save_version_snapshot(cls, template_id: int, template_type: str,
                               version: str, content: str, variables: Any,
                               change_summary: str, created_by: int = None):
        """保存版本快照"""
        snapshot = TemplateVersionHistory(
            template_type=template_type,
            template_id=template_id,
            version=version,
            content_snapshot=content,
            variables_snapshot=variables,
            change_summary=change_summary,
            created_by=created_by,
        )
        db.session.add(snapshot)

    # =========================================================================
    # 四、版本历史
    # =========================================================================

    @classmethod
    def get_version_history(cls, template_id: int, limit: int = 20) -> List[Dict]:
        """获取模板版本历史"""
        history = TemplateVersionHistory.query.filter_by(
            template_id=template_id
        ).order_by(
            TemplateVersionHistory.created_at.desc()
        ).limit(limit).all()

        return [{
            'id': h.id,
            'version': h.version,
            'content_snapshot': h.content_snapshot,
            'variables_snapshot': h.variables_snapshot,
            'change_summary': h.change_summary,
            'created_at': h.created_at.isoformat() if h.created_at else None,
        } for h in history]

    @classmethod
    def restore_version(cls, version_id: int, created_by: int = None) -> Dict:
        """恢复历史版本"""
        version = TemplateVersionHistory.query.get(version_id)
        if not version:
            return {'success': False, 'message': '版本不存在'}

        tpl = ReportTemplate.query.get(version.template_id)
        if not tpl:
            return {'success': False, 'message': '模板不存在'}

        # 保存当前版本快照
        cls._save_version_snapshot(
            tpl.id, tpl.template_type, tpl.version,
            tpl.template_content, tpl.variables_config,
            f'恢复自 {version.version}', created_by
        )

        # 恢复到指定版本
        tpl.template_content = version.content_snapshot
        tpl.variables_config = version.variables_snapshot
        new_version = cls._bump_version(tpl.version)
        tpl.version = new_version

        db.session.commit()

        return {
            'success': True,
            'message': f'已恢复到 {version.version}，当前版本 {new_version}',
            'template': cls._template_to_dict(tpl),
        }

    # =========================================================================
    # 五、变量替换引擎
    # =========================================================================

    @classmethod
    def replace_variables(cls, template_content: str, context: Dict[str, Any]) -> str:
        """
        替换模板中的变量

        Args:
            template_content: 模板内容（含 {变量名} 占位符）
            context: 变量上下文字典

        Returns:
            替换后的内容
        """
        if not template_content:
            return ''

        def replacer(match):
            var_name = match.group(1).strip()
            value = context.get(var_name)
            if value is not None:
                return str(value)
            # 如果变量未找到，移除它（不保留占位符）
            return ''

        return cls.VAR_PATTERN.sub(replacer, template_content)

    @classmethod
    def extract_variables(cls, template_content: str) -> List[str]:
        """提取模板中的所有变量名"""
        if not template_content:
            return []
        return list(set(cls.VAR_PATTERN.findall(template_content)))

    @classmethod
    def preview_template(cls, template_content: str, context: Dict[str, Any],
                        highlight_missing: bool = False) -> str:
        """
        预览模板渲染效果

        Args:
            template_content: 模板内容
            context: 变量上下文
            highlight_missing: 是否高亮未填充的变量

        Returns:
            预览后的内容
        """
        if not template_content:
            return ''

        result = cls.replace_variables(template_content, context)

        if highlight_missing:
            # 高亮未替换的变量
            missing = cls.extract_variables(result)
            for var in missing:
                if context.get(var):
                    result = result.replace('{' + var + '}', context[var])
                else:
                    result = result.replace('{' + var + '}', f'<span style="background:#fff3cd">{var}</span>')

        return result

    # =========================================================================
    # 六、模板导入（从 geo-seo skill 文件）
    # =========================================================================

    @classmethod
    def import_from_skill_file(cls, file_path: str, template_type: str,
                               template_name: str = None,
                               created_by: int = None) -> Dict:
        """
        从 skill 文件导入模板

        Args:
            file_path: 文件绝对路径
            template_type: 模板类型 keyword/topic
            template_name: 模板名称（默认用文件名）
            created_by: 创建者ID

        Returns:
            导入结果
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取变量
            variables = cls.extract_variables(content)
            variables_config = [
                {
                    'name': v,
                    'label': v,
                    'type': 'text',
                    'required': False,
                }
                for v in variables
            ]

            # 尝试从文件头部提取元信息
            meta = {}
            meta_pattern = re.compile(r'^#\s*模板名称[：:]\s*(.+)$', re.MULTILINE)
            meta_match = meta_pattern.search(content)
            if meta_match:
                meta['name'] = meta_match.group(1).strip()

            name = template_name or meta.get('name', template_type)
            version_pattern = re.compile(r'^#\s*版本[：:]\s*(.+)$', re.MULTILINE)
            version_match = version_pattern.search(content)
            version = version_match.group(1).strip() if version_match else 'v1.0'

            result = cls.save_template({
                'template_name': name,
                'template_type': template_type,
                'template_category': 'universal',
                'template_content': content,
                'variables_config': variables_config,
                'version': version,
            }, created_by=created_by, save_version=True)

            return result

        except FileNotFoundError:
            return {'success': False, 'message': f'文件不存在: {file_path}'}
        except Exception as e:
            return {'success': False, 'message': f'导入失败: {str(e)}'}

    # =========================================================================
    # 七、常用预设变量（自动注入）
    # =========================================================================

    @classmethod
    def get_realtime_context(cls) -> Dict[str, Any]:
        """
        获取实时上下文（当季热点、节日等）

        这个方法在生成关键词/选题时会被自动调用
        """
        now = datetime.now()
        month = now.month
        day = now.day

        # 节日映射
        festivals = {
            (1, 1): '元旦',
            (2, 14): '情人节',
            (3, 8): '妇女节',
            (4, 5): '清明节',
            (5, 1): '劳动节',
            (5, 4): '青年节',
            (6, 1): '儿童节',
            (6, 18): '618购物节',
            (7, 1): '建党节',
            (7, 7): '七夕节',
            (8, 1): '建军节',
            (9, 10): '教师节',
            (10, 1): '国庆节',
            (11, 11): '双十一',
            (12, 24): '平安夜',
            (12, 25): '圣诞节',
        }

        # 节气映射
        solar_terms = {
            (2, 3): '立春', (2, 18): '雨水', (3, 5): '惊蛰', (3, 20): '春分',
            (4, 4): '清明', (4, 20): '谷雨', (5, 5): '立夏', (5, 21): '小满',
            (6, 5): '芒种', (6, 21): '夏至', (7, 7): '小暑', (7, 22): '大暑',
            (8, 7): '立秋', (8, 22): '处暑', (9, 7): '白露', (9, 22): '秋分',
            (10, 8): '寒露', (10, 23): '霜降', (11, 7): '立冬', (11, 22): '小雪',
            (12, 6): '大雪', (12, 21): '冬至',
        }

        # 季节
        if month in [3, 4, 5]:
            season = '春季'
        elif month in [6, 7, 8]:
            season = '夏季'
        elif month in [9, 10, 11]:
            season = '秋季'
        else:
            season = '冬季'

        # 当前节日/节气
        current_festival = festivals.get((month, day))
        current_solar_term = solar_terms.get((month, day))

        # 月份别称
        month_names = {
            1: '一月/新年', 2: '二月/年关', 3: '三月/开春', 4: '四月/清明',
            5: '五月/劳动', 6: '六月/年中', 7: '七月/暑期', 8: '八月/盛夏',
            9: '九月/金秋', 10: '十月/国庆', 11: '十一月/初冬', 12: '十二月/年末'
        }

        return {
            '当前年份': str(now.year),
            '当前月份': str(month),
            '当前日期': now.strftime('%Y-%m-%d'),
            '当前季节': season,
            '月份名称': month_names.get(month, f'{month}月'),
            '当前节日': current_festival or '无',
            '当前节气': current_solar_term or '无',
            '星期': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()],
            # 消费习惯（按季节）
            '季节消费特点': cls._get_seasonal_consumption(season),
            # 月度热点前缀
            '月度热点前缀': cls._get_monthly_hotspot(month),
        }

    @classmethod
    def _get_seasonal_consumption(cls, season: str) -> str:
        """获取季节性消费特点"""
        mapping = {
            '春季': '踏青、春游、换季采购、春节后返程、春耕备耕',
            '夏季': '消暑、防晒、防蚊、夜经济、毕业季、暑期出行',
            '秋季': '秋收、团圆、中秋礼品、国庆出行、贴秋膘',
            '冬季': '保暖、年货置办、年末冲刺、圣诞元旦、腊八节',
        }
        return mapping.get(season, '')

    @classmethod
    def _get_monthly_hotspot(cls, month: int) -> str:
        """获取月度热点关键词"""
        mapping = {
            1: '新年礼、开门红、年货、返乡、春运',
            2: '情人节、元宵节、开学季、春装上市',
            3: '妇女节、315打假、春游、植树节',
            4: '清明踏青、春季过敏、防晒上市',
            5: '劳动节、青年节、母亲节、517吃货节',
            6: '儿童节、618、毕业季、暑假预热',
            7: '暑期、毕业旅行、防暑降温、夏季清凉',
            8: '七夕、暑期、出伏、秋季养生',
            9: '开学季、教师节、中秋礼、国庆预热',
            10: '国庆黄金周、重阳节、秋收、秋季美食',
            11: '双十一预热、立冬、冬季保暖',
            12: '双十二、圣诞节、元旦预热、年终总结',
        }
        return mapping.get(month, '')

    # =========================================================================
    # 四、内容展示区块配置
    # =========================================================================

    @classmethod
    def get_section_display_config(cls, content_type: str) -> List[Dict]:
        """
        获取指定内容类型的展示区块配置（按 sort_order 排序）

        Args:
            content_type: graphic(图文) / short_video(短视频) / long_text(长文)

        Returns:
            区块配置列表
        """
        configs = ContentSectionDisplayConfig.query.filter_by(
            content_type=content_type
        ).order_by(ContentSectionDisplayConfig.sort_order).all()

        if not configs:
            # 返回默认配置
            return cls._get_default_section_config(content_type)

        result = [cls._section_to_dict(c) for c in configs]

        # 补充策略：DB 配置缺少 slides 时自动从默认值补入
        if content_type == 'graphic':
            existing_keys = {c['section_key'] for c in result}
            defaults = cls._get_default_section_config(content_type)
            for d in defaults:
                if d['section_key'] not in existing_keys:
                    result.append(d)
            # 按 sort_order 重排
            result.sort(key=lambda x: x.get('sort_order', 99))

        return result

    @classmethod
    def _get_default_section_config(cls, content_type: str) -> List[Dict]:
        """获取指定内容类型的默认展示配置"""
        defaults = {
            'graphic': [
                {'section_key': 'title', 'section_label': '标题设计', 'client_label': '一、标题', 'visible_to_client': True, 'copyable': True, 'sort_order': 1, 'is_core_section': True},
                {'section_key': 'slides', 'section_label': '图文详情', 'client_label': '二、图文详情', 'visible_to_client': True, 'copyable': False, 'sort_order': 2, 'is_core_section': True},
                {'section_key': 'content_plan', 'section_label': '内容详情', 'client_label': '三、内容详情', 'visible_to_client': True, 'copyable': True, 'sort_order': 3, 'is_core_section': True},
                {'section_key': 'comment', 'section_label': '评论区运营', 'client_label': '四、评论区运营', 'visible_to_client': True, 'copyable': True, 'sort_order': 4, 'is_core_section': True},
                {'section_key': 'tags', 'section_label': '底部标签', 'client_label': '五、底部标签', 'visible_to_client': True, 'copyable': True, 'sort_order': 5, 'is_core_section': True},
                {'section_key': 'extension', 'section_label': '内容延伸建议', 'client_label': '六、内容延伸建议', 'visible_to_client': True, 'copyable': False, 'sort_order': 6, 'is_core_section': False},
                {'section_key': 'publish', 'section_label': '发布策略', 'client_label': '七、发布策略', 'visible_to_client': True, 'copyable': False, 'sort_order': 7, 'is_core_section': False},
                {'section_key': 'basic_info', 'section_label': '基本信息', 'client_label': '基本信息', 'visible_to_client': False, 'copyable': False, 'sort_order': 8, 'is_core_section': False},
                {'section_key': 'compliance', 'section_label': '合规检查', 'client_label': '合规检查', 'visible_to_client': False, 'copyable': False, 'sort_order': 9, 'is_core_section': False},
            ],
            'short_video': [
                {'section_key': 'title', 'section_label': '标题', 'client_label': '一、标题', 'visible_to_client': True, 'copyable': True, 'sort_order': 1, 'is_core_section': True},
                {'section_key': 'script', 'section_label': '脚本内容', 'client_label': '二、脚本内容', 'visible_to_client': True, 'copyable': True, 'sort_order': 2, 'is_core_section': True},
                {'section_key': 'comment', 'section_label': '评论区运营', 'client_label': '三、评论区运营', 'visible_to_client': True, 'copyable': True, 'sort_order': 3, 'is_core_section': True},
                {'section_key': 'tags', 'section_label': '话题标签', 'client_label': '四、话题标签', 'visible_to_client': True, 'copyable': True, 'sort_order': 4, 'is_core_section': True},
                {'section_key': 'shooting', 'section_label': '拍摄建议', 'client_label': '五、拍摄建议', 'visible_to_client': True, 'copyable': True, 'sort_order': 5, 'is_core_section': False},
                {'section_key': 'publish', 'section_label': '发布策略', 'client_label': '六、发布策略', 'visible_to_client': True, 'copyable': False, 'sort_order': 6, 'is_core_section': False},
            ],
            'long_text': [
                {'section_key': 'title', 'section_label': '标题', 'client_label': '一、标题', 'visible_to_client': True, 'copyable': True, 'sort_order': 1, 'is_core_section': True},
                {'section_key': 'content', 'section_label': '正文内容（可复制发布）', 'client_label': '二、正文内容', 'visible_to_client': True, 'copyable': True, 'sort_order': 2, 'is_core_section': True},
                {'section_key': 'design_reference', 'section_label': '制作参考', 'client_label': '三、制作参考', 'visible_to_client': True, 'copyable': False, 'sort_order': 3, 'is_core_section': False},
                {'section_key': 'comment', 'section_label': '评论区运营', 'client_label': '四、评论区运营', 'visible_to_client': True, 'copyable': True, 'sort_order': 4, 'is_core_section': True},
                {'section_key': 'tags', 'section_label': '标签', 'client_label': '五、标签', 'visible_to_client': True, 'copyable': True, 'sort_order': 5, 'is_core_section': True},
                {'section_key': 'publish', 'section_label': '发布策略', 'client_label': '六、发布策略', 'visible_to_client': True, 'copyable': False, 'sort_order': 6, 'is_core_section': False},
            ],
        }
        return defaults.get(content_type, defaults['graphic'])

    @classmethod
    def _section_to_dict(cls, cfg: 'ContentSectionDisplayConfig') -> Dict:
        """模型转字典"""
        return {
            'id': cfg.id,
            'content_type': cfg.content_type,
            'section_key': cfg.section_key,
            'section_label': cfg.section_label,
            'visible_to_client': cfg.visible_to_client,
            'copyable': cfg.copyable,
            'client_label': cfg.client_label or cfg.section_label,
            'sort_order': cfg.sort_order,
            'is_core_section': cfg.is_core_section,
            'description': cfg.description,
        }

    @classmethod
    def save_section_display_config(
        cls,
        content_type: str,
        sections: List[Dict],
        created_by: int = None
    ) -> Dict:
        """
        保存内容展示区块配置（全量覆盖）

        Args:
            content_type: 内容类型
            sections: 区块配置列表
            created_by: 创建者ID

        Returns:
            保存结果
        """
        try:
            # 删除旧配置
            ContentSectionDisplayConfig.query.filter_by(
                content_type=content_type
            ).delete()

            # 插入新配置
            for idx, sec in enumerate(sections):
                cfg = ContentSectionDisplayConfig(
                    content_type=content_type,
                    section_key=sec.get('section_key', ''),
                    section_label=sec.get('section_label', ''),
                    visible_to_client=sec.get('visible_to_client', True),
                    copyable=sec.get('copyable', True),
                    client_label=sec.get('client_label'),
                    sort_order=sec.get('sort_order', idx),
                    is_core_section=sec.get('is_core_section', False),
                    description=sec.get('description'),
                    created_by=created_by,
                )
                db.session.add(cfg)

            db.session.commit()
            return {'success': True, 'message': '配置保存成功'}

        except Exception as e:
            db.session.rollback()
            return {'success': False, 'message': f'保存失败: {str(e)}'}

    @classmethod
    def get_all_section_display_configs(cls) -> Dict[str, List[Dict]]:
        """
        获取所有内容类型的展示配置

        Returns:
            { 'graphic': [...], 'short_video': [...], 'long_text': [...] }
        """
        all_configs = ContentSectionDisplayConfig.query.order_by(
            ContentSectionDisplayConfig.content_type,
            ContentSectionDisplayConfig.sort_order
        ).all()

        result = {'graphic': [], 'short_video': [], 'long_text': []}
        for cfg in all_configs:
            if cfg.content_type in result:
                result[cfg.content_type].append(cls._section_to_dict(cfg))

        # 填充未配置的默认值
        for ct in ['graphic', 'short_video', 'long_text']:
            if not result[ct]:
                result[ct] = cls._get_default_section_config(ct)

        return result


# 全局实例
template_config_service = TemplateConfigService()
