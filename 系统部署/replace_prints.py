#!/usr/bin/env python3
"""批量将 print() 替换为 logging"""

import re
import sys
from pathlib import Path

LOGGER_IMPORT_TEMPLATE = """
import logging
logger = logging.getLogger(__name__)
"""

# 匹配规则：替换模式 → 替换后的 logging 调用
# 按文件分类处理
REPLACEMENTS = {}

def add_pattern(pattern: str, replacement: str):
    REPLACEMENTS[pattern] = replacement


# ==================== public_content_generator.py ====================
# 这些是最严重的，直接打印 LLM 原始响应

# 调试信息块（打印原始响应）
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] === 调试信息 ==="\)'] = 'logger.debug("[identify_customer_identities] 开始识别客户身份")'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] 业务描述: \{business_desc\}"\)'] = 'logger.debug("[identify_customer_identities] 业务描述: %s", business_desc)'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] 经营范围: \{business_range\}, 经营类型: \{business_type\}"\)'] = 'logger.debug("[identify_customer_identities] 经营范围: %s, 经营类型: %s", business_range, business_type)'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] LLM原始响应:\\n\{response\[:2000\] if response else \'None\'\}"\)'] = 'logger.debug("[identify_customer_identities] LLM原始响应: %s", response[:500] if response else None)'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] ToB身份: \{\[x\.get\(\'buyer\', \{\}\)\.get\(\'name\', \'\'\) for x in to_b\]\}"\)'] = 'logger.debug("[identify_customer_identities] ToB身份: %s", [x.get("buyer", {}).get("name", "") for x in to_b])'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] ToC身份: \{\[x\.get\(\'buyer\', \{\}\)\.get\(\'name\', \'\'\) for x in to_c\]\}"\)'] = 'logger.debug("[identify_customer_identities] ToC身份: %s", [x.get("buyer", {}).get("name", "") for x in to_c])'
REPLACEMENTS[r'print\(f"\[identify_customer_identities\] === 调试结束 ===\\n"\)'] = 'logger.debug("[identify_customer_identities] 识别完成")'
REPLACEMENTS[r'print\(f"\[ContentGenerator\] identify_customer_identities 异常: \{e\}"\)'] = 'logger.error("[identify_customer_identities] 异常: %s", e)'
REPLACEMENTS[r'print\(f"\[ContentGenerator\] 堆栈: \{traceback\.format_exc\(\)\}"\)'] = 'logger.exception("[identify_customer_identities] 堆栈")'

REPLACEMENTS[r'print\(f"\[ContentGenerator\] LLM 画像直出失败，回退规则: \{e\}"\)'] = 'logger.warning("[ContentGenerator] LLM画像直出失败，回退规则: %s", e)'
REPLACEMENTS[r'print\(f"\[ContentGenerator\] AI增强失败，使用规则结果: \{e\}"\)'] = 'logger.warning("[ContentGenerator] AI增强失败，使用规则结果: %s", e)'
REPLACEMENTS[r'print\(f"\[ContentGenerator\] identify_problems_and_initial_personas 异常: \{e\}"\)'] = 'logger.error("[identify_problems_and_initial_personas] 异常: %s", e)'
REPLACEMENTS[r'print\(f"\[ContentGenerator\] generate_persona_batch_by_problem 异常: \{e\}"\)'] = 'logger.error("[generate_persona_batch_by_problem] 异常: %s", e)'

REPLACEMENTS[r'print\(f"\[_挖掘_使用方_付费方问题\] 业务描述: \{business_desc\}"\)'] = 'logger.debug("[_挖掘_使用方_付费方问题] 业务描述: %s", business_desc)'
REPLACEMENTS[r'print\(f"\[_挖掘_使用方_付费方问题\] LLM响应前500字:\\n\{response\[:500\] if response else \'None\'\}"\)'] = 'logger.debug("[_挖掘_使用方_付费方问题] LLM响应前500字: %s", response[:500] if response else None)'
REPLACEMENTS[r'print\(f"\[_挖掘_使用方_付费方问题\] 异常: \{e\}"\)'] = 'logger.error("[_挖掘_使用方_付费方问题] 异常: %s", e)'
REPLACEMENTS[r'print\(f"\[_挖掘_使用方_付费方问题\] 堆栈:\\n\{traceback\.format_exc\(\)\}"\)'] = 'logger.exception("[_挖掘_使用方_付费方问题] 堆栈")'

REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] 问题: \{problem\.get\(\'name\', \'\'\)\}"\)'] = 'logger.debug("[_generate_persona_batch] 问题: %s", problem.get("name", ""))'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] LLM响应前500字:\\n\{response\[:500\] if response else \'None\'\}"\)'] = 'logger.debug("[_generate_persona_batch] LLM响应前500字: %s", response[:500] if response else None)'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析成功 \(方法1\)"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析成功(方法1)")'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析失败 \(方法1\): \{je\}"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析失败(方法1): %s", je)'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析成功 \(方法2 - 数组\)"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析成功(方法2-数组)")'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析失败 \(方法2\): \{je\}"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析失败(方法2): %s", je)'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析成功 \(方法3 - 直接\)"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析成功(方法3-直接)")'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] JSON解析失败 \(方法3\): \{je\}"\)'] = 'logger.debug("[_generate_persona_batch] JSON解析失败(方法3): %s", je)'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] 解析到 targets 数量: \{len\(targets\)\}"\)'] = 'logger.debug("[_generate_persona_batch] 解析到targets数量: %s", len(targets))'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] 清理后 targets 数量: \{len\(cleaned_targets\)\}"\)'] = 'logger.debug("[_generate_persona_batch] 清理后targets数量: %s", len(cleaned_targets))'
REPLACEMENTS[r'print\(f"\[_generate_persona_batch\] 异常: \{e\}"\)'] = 'logger.error("[_generate_persona_batch] 异常: %s", e)'


def ensure_logger_import(content: str) -> str:
    """确保文件有 logger 导入"""
    if 'import logging' in content and 'logger = logging.getLogger' in content:
        return content

    # 在文件顶部的 import 区域之后添加
    lines = content.split('\n')
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            insert_idx = i + 1

    # 插入 logger 设置
    logger_lines = ['', 'import logging', 'logger = logging.getLogger(__name__)', '']
    lines[insert_idx:insert_idx] = logger_lines

    return '\n'.join(lines)


def replace_prints_in_file(filepath: Path) -> int:
    """替换文件中的 print 语句，返回替换数量"""
    content = filepath.read_text(encoding='utf-8')
    original = content
    count = 0

    for pattern, replacement in REPLACEMENTS.items():
        new_content, n = re.subn(pattern, replacement, content)
        if n > 0:
            count += n
            content = new_content

    # 通用替换：处理未被精确匹配覆盖的 print
    # 移除直接打印 LLM 响应的大段 print
    patterns_to_remove = [
        r'print\(f"\[.*?\] LLM响应.*?\{.*?\}\)"\n',
        r'print\(f"\[.*?\] 堆栈.*?\{.*?\}\)"\n',
        r'print\(f"\[.*?\] raw.*?\{.*?\}\)"\n',
        r'print\(f"\[.*?\] 原始.*?\{.*?\}\)"\n',
    ]
    for p in patterns_to_remove:
        new_content, n = re.subn(p, '', content)
        if n > 0:
            count += n
            content = new_content

    # 通用异常处理 print → logger.exception
    exc_patterns = [
        (r'print\(f"\[([^\]]+)\] 异常: \{e\}"\)', r'logger.error("[\1] 异常: %s", e)'),
        (r'print\(f"\[([^\]]+)\] 异常: \{(.*?)\}"\)', r'logger.error("[\1] 异常: %s", \2)'),
        (r'print\(f"异常: \{e\}"\)', r'logger.exception("异常: %s", e)'),
        (r'print\(f"异常: \{(.*?)\}"\)', r'logger.error("异常: %s", \1)'),
        (r'print\(f"\[([^\]]+)\] 失败: \{e\}"\)', r'logger.error("[\1] 失败: %s", e)'),
        (r'print\(f"\[([^\]]+)\] 失败: \{(.*?)\}"\)', r'logger.error("[\1] 失败: %s", \2)'),
        (r'print\(f"\[([^\]]+)\] 错误: \{e\}"\)', r'logger.error("[\1] 错误: %s", e)'),
        (r'print\(f"\[([^\]]+)\] 错误: \{(.*?)\}"\)', r'logger.error("[\1] 错误: %s", \2)'),
    ]
    for p, r in exc_patterns:
        new_content, n = re.subn(p, r, content)
        if n > 0:
            count += n
            content = new_content

    # 通用 info/debug print → logger.debug
    info_patterns = [
        (r'print\(f"\[([^\]]+)\] 开始"\)', r'logger.info("[\1] 开始")'),
        (r'print\(f"\[([^\]]+)\] 完成"\)', r'logger.info("[\1] 完成")'),
        (r'print\(f"\[([^\]]+)\] 成功"\)', r'logger.info("[\1] 成功")'),
        (r'print\(f"\[([^\]]+)\] 跳过: \{(.*?)\}"\)', r'logger.info("[\1] 跳过: %s", \2)'),
        (r'print\(f"\[([^\]]+)\] .*?数量: \{(.*?)\}"\)', r'logger.debug("[\1] 数量: %s", \2)'),
        (r'print\(f"\[([^\]]+)\] .*?结果: \{(.*?)\}"\)', r'logger.debug("[\1] 结果: %s", \2)'),
        (r'print\(f"\[([^\]]+)\] .*?长度: \{(.*?)\}"\)', r'logger.debug("[\1] 长度: %s", \2)'),
    ]
    for p, r in info_patterns:
        new_content, n = re.subn(p, r, content)
        if n > 0:
            count += n
            content = new_content

    # 剩余未被覆盖的 print: 简单 print() → logger.debug()
    remaining_pattern = r'print\(f?"([^"]*)"\)'
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith('print(') and not stripped.startswith('logger.'):
            # 尝试提取内容
            m = re.match(r'^(\s*)print\(f?"([^"]*)"\)$', stripped)
            if m:
                indent = m.group(1)
                msg = m.group(2)
                # 如果是纯文本 print，替换
                if '{' not in msg and '}' not in msg:
                    new_lines.append(f'{indent}logger.debug("{msg}")')
                    count += 1
                    continue
        new_lines.append(line)

    content = '\n'.join(new_lines)

    if content != original:
        content = ensure_logger_import(content)
        filepath.write_text(content, encoding='utf-8')

    return count


def main():
    base = Path('/Volumes/增元/项目/douyin/系统部署')
    files = [
        'services/public_content_generator.py',
        'services/unified_library_generator.py',
        'services/init_public_data.py',
        'services/public_auth.py',
        'services/douyin_scraper.py',
        'services/background_task_service.py',
        'services/topic_library_generator.py',
        'routes/public_api.py',
        'routes/portrait_api.py',
        'services/template_config_loader.py',
        'routes/knowledge_api.py',
        'services/topic_generator.py',
        'services/template_generator.py',
        'services/public_cache.py',
        'services/keyword_library_generator.py',
        'services/content_generator.py',
        'services/public_template_matcher.py',
        'services/public_quota_manager.py',
        'routes/admin.py',
    ]

    total = 0
    for f in files:
        path = base / f
        if path.exists():
            n = replace_prints_in_file(path)
            if n > 0:
                print(f'  {f}: {n} 条')
            total += n
        else:
            print(f'  [跳过] {f} (不存在)')

    print(f'\n总计替换: {total} 条 print → logging')


if __name__ == '__main__':
    main()
