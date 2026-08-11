"""Extract metadata from 备电 markdown content files and output JSON."""
import os, re, json, sys

DIR = "/Volumes/增元/项目/douyin/.cursor/skill/content-creator/输出/脚本/备电"

def extract_frontmatter(text):
    """Extract key-value metadata from first lines before ---"""
    result = {}
    lines = text.split("\n")
    for line in lines[:15]:
        line = line.strip()
        if line.startswith(">"):
            line = line.lstrip(">").strip()
            # Match "key：value" or "key: value" patterns
            m = re.match(r'[-*\s]*(.+?)[：:]\s*(.+)', line)
            if m:
                key, val = m.group(1).strip(), m.group(2).strip()
                result[key] = val
        elif line.startswith("# ") and not result.get("title"):
            result["title"] = line.lstrip("# ").strip()
    return result

def extract_table_row(text, row_label):
    """Extract a value from a markdown table row like | 选题 | value |"""
    pattern = rf'\|\s*{row_label}\s*\|\s*(.+?)\s*\|'
    m = re.search(pattern, text)
    return m.group(1).strip() if m else None

def is_valid_keyword(kw):
    """Filter out noise like hex colors, CSS values, single chars."""
    kw = kw.strip()
    if len(kw) < 2 or len(kw) > 15:
        return False
    if kw.isdigit():
        return False
    # Hex color: 3/6 hex digits
    if re.match(r'^[0-9a-fA-F]{3,8}$', kw):
        return False
    # Common CSS noise
    if kw.lower() in ('aaa', 'bbb', 'ccc', 'ddd', 'eee', 'fff', 'rgb', 'rgba',
                       'px', 'em', 'rem', 'jpg', 'png', 'gpt', 'ai',
                       '关键词', '关键词类型', '长尾词', '核心词', '场景词', '问题词'):
        return False
    return True

def extract_seo_keywords(text):
    """Extract SEO keywords. Returns list of unique keywords."""
    keywords = set()
    # Pattern 1: SEO section table rows
    for m in re.finditer(r'\|\s*(?:核心词|长尾词|场景词|问题词|关键词类型)\s*\|\s*(.+?)\s*\|', text):
        for kw in re.split(r'[、，,;；]', m.group(1)):
            if is_valid_keyword(kw):
                keywords.add(kw.strip())
    # Pattern 2: hashtag lines at end of file (only after content, not in prompts)
    # Find the last block of hashtags before end of file or before ---
    last_section = text.rsplit('---', 1)[-1] if '---' in text else text
    for m in re.finditer(r'#([\w一-鿿]+)', last_section):
        tag = m.group(1).strip()
        if is_valid_keyword(tag) and len(tag) < 20:
            keywords.add(tag)
    # Pattern 3: 标签 section
    tag_section = re.search(r'标签.*?\n((?:\|.*?\n)+)', text, re.DOTALL)
    if tag_section:
        for line in tag_section.group(1).split("\n"):
            for m in re.finditer(r'#([\w一-鿿]+)', line):
                t = m.group(1).strip()
                if is_valid_keyword(t) and len(t) < 20:
                    keywords.add(t)
    return sorted(keywords)

def extract_tags_structured(text):
    """Extract structured tags (L1/L2/L3)"""
    tags = {"L1": [], "L2": [], "L3": []}
    tag_section = re.search(r'###\s+\d+\.\d+\s+标签.*?\n((?:\|.*?\n)+)', text, re.DOTALL)
    if not tag_section:
        return tags
    for line in tag_section.group(1).split("\n"):
        # L1 row
        m = re.search(r'\|\s*L1.*?\|\s*(.+?)\s*\|', line)
        if m:
            tags["L1"] = [t.strip() for t in re.split(r'[、，,]', m.group(1)) if t.strip()]
        m = re.search(r'\|\s*L2.*?\|\s*(.+?)\s*\|', line)
        if m:
            tags["L2"] = [t.strip() for t in re.split(r'[、，,]', m.group(1)) if t.strip()]
        m = re.search(r'\|\s*L3.*?\|\s*(.+?)\s*\|', line)
        if m:
            tags["L3"] = [t.strip() for t in re.split(r'[、，,]', m.group(1)) if t.strip()]
    return tags

def classify_type(filename):
    """Classify content type from filename"""
    f = filename.lower()
    if 'gamma' in f or '摩尔生图' in f or '金字塔图' in f or 'canva' in f:
        return None  # exclude build artifacts
    if '图文a型' in f or 'a型' in f or '图文a_' in f:
        return 'A型图文'
    elif '图文b型' in f or 'b型' in f or 'b_' in f:
        return 'B型图文'
    elif '清单体' in f:
        return '清单体口播'
    elif '口播' in f:
        return '口播脚本'
    elif '短视频' in f:
        return '短视频'
    elif '概念图谱' in f:
        return '概念图谱'
    elif '图文_' in f or '图文 ' in f:
        return '图文'
    else:
        return '其他'

def extract_title(text, filename, fm):
    """Extract the best title available"""
    # Method 1: from 主标题 or 主标
    m = re.search(r'\*\*主标[题意]?\*\*[：:]\s*(.+?)(?:\n|\*\*)', text)
    if m:
        t = m.group(1).strip().rstrip('*').strip()
        if t:
            return t
    # Method 2: from 推荐 title
    m = re.search(r'\*\*推荐[：:]\s*[①②③④⑤]\s*\*\s*(.+?)\s*\n', text)
    if m:
        return m.group(1).strip()
    # Method 3: from heading # (first one)
    m = re.search(r'^#\s+(.+?)$', text, re.MULTILINE)
    if m:
        t = m.group(1).strip()
        # Remove prefix patterns
        t = re.sub(r'^(图文[A-Z]型_|短视频_|短视频脚本 _ |短视频脚本 — |口播脚本_|口播_|清单体_|概念图谱_|图文_)', '', t)
        t = re.sub(r'_(备电|v\d+)$', '', t)
        return t
    # Fallback: clean filename
    name = os.path.splitext(filename)[0]
    name = re.sub(r'^(图文[A-Z]型_|图文_|短视频_|短视频脚本 — |口播_|清单体_|概念图谱_|Gamma输入_)', '', name)
    name = re.sub(r'_(备电|v\d+|_备电)$', '', name)
    name = name.replace('_', ' ')
    return name

def extract_topic(text, content_type):
    """Extract 选题/topic"""
    # Pattern 1: Table row
    topic = extract_table_row(text, '选题')
    if topic:
        return topic
    # Pattern 2: 核心问题 in frontmatter
    m = re.search(r'>\s*核心问题[：:]\s*(.+?)\n', text)
    if m:
        return m.group(1).strip()
    # Pattern 3: 锚点事件
    m = re.search(r'>\s*锚点事件[：:]\s*(.+?)\n', text)
    if m:
        return m.group(1).strip()
    # Pattern 4: 内容类型 (often contains topic description)
    m = re.search(r'>\s*内容类型[：:]\s*(.+?)\n', text)
    if m:
        return m.group(1).strip()
    # Pattern 5: 核心观点
    topic = extract_table_row(text, '核心观点')
    if topic:
        return topic
    return ""

def extract_audience(text):
    """Extract 目标人群"""
    audience = extract_table_row(text, '目标人群')
    if audience:
        # Split by 连接词
        parts = re.split(r'[/／、]', audience)
        return [p.strip() for p in parts if p.strip()]
    return []

def extract_persona(text):
    """Extract 人设"""
    persona = extract_table_row(text, '人设')
    if persona:
        return persona
    m = re.search(r'\*\*人设定位[：:]\*\*\s*(.+?)(?:\n|（)', text)
    if m:
        return m.group(1).strip()
    return ""

def extract_publish_date(filepath):
    """Get date from file modification time or content"""
    # Try to find date in content
    try:
        with open(filepath, 'r') as f:
            text = f.read(3000)
        m = re.search(r'日期[：:]\s*(\d{4}-\d{2}-\d{2})', text)
        if m:
            return m.group(1)
        m = re.search(r'生成日期[：:]\s*(\d{4}-\d{2}-\d{2})', text)
        if m:
            return m.group(1)
        m = re.search(r'>\s*(\d{4}-\d{2}-\d{2})\s*[|｜]', text)
        if m:
            return m.group(1)
    except:
        pass
    # Fall back to file modification date
    import datetime
    mtime = os.path.getmtime(filepath)
    return datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

def process_file(filepath, filename):
    try:
        with open(filepath, 'r') as f:
            text = f.read()
    except:
        return None

    fm = extract_frontmatter(text)
    content_type = classify_type(filename)

    return {
        "id": "",
        "title": extract_title(text, filename, fm),
        "contentType": content_type,
        "topic": extract_topic(text, content_type),
        "audience": extract_audience(text),
        "keywords": extract_seo_keywords(text),
        "tags": extract_tags_structured(text),
        "persona": extract_persona(text),
        "publishedDate": extract_publish_date(filepath),
        "metrics": {
            "views": 0, "likes": 0, "comments": 0,
            "shares": 0, "saves": 0, "followers": 0
        },
        "metricHistory": []
    }

def main():
    files = sorted(os.listdir(DIR))
    posts = []

    skip = {'Canva制作任务单_四张B型图文.md', '金字塔图_prompt.md',
            '口播_WorkBuddy行业日报.md'}

    for filename in files:
        if not filename.endswith('.md'):
            continue
        if filename in skip:
            continue

        content_type = classify_type(filename)
        if content_type is None:
            continue  # skip Gamma, 摩尔生图, etc.

        filepath = os.path.join(DIR, filename)
        post = process_file(filepath, filename)
        if post:
            posts.append(post)

    # Assign IDs
    for i, post in enumerate(posts):
        post["id"] = f"post-{i+1:03d}"

    registry = {
        "version": 1,
        "lastUpdated": "2026-06-20",
        "posts": posts
    }

    # Pretty print but keep arrays compact
    print(json.dumps(registry, ensure_ascii=False, indent=2))

    # Stats
    types = {}
    for p in posts:
        t = p['contentType']
        types[t] = types.get(t, 0) + 1
    print(f"\n// {len(posts)} posts extracted", file=sys.stderr)
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"//   {t}: {c}", file=sys.stderr)

if __name__ == '__main__':
    main()
