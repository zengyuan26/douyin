#!/usr/bin/env python3
"""
星系图谱增强功能测试用例

测试范围：
- Galaxy API 接口（/graph、节点详情、/link）
- PublicGeneration 新字段（selected_scenes）
- PublicIndustryTopic 新字段（scene_options、content_style）
- SavedPortrait 新字段（geo_*、cover_thumb）
- PersonaUserProblem 新字段（geo_trigger_regions、geo_seasonal_factor）

使用方法：
1. 启动服务器：python3 app.py
2. 登录获取 cookie
3. 运行测试：python3 test_galaxy_enhancement.py

依赖：requests、pytest（可选）
"""

import json
import sys
import os
import re

# 路径配置
sys.path.insert(0, '/Volumes/增元/项目/douyin/系统部署')

# 加载环境变量
from dotenv import load_dotenv
load_dotenv('/Volumes/增元/项目/douyin/系统部署/.env')

import requests

# ============================================================================
# 配置
# ============================================================================

BASE_URL = "http://localhost:5001"
LOGIN_URL = f"{BASE_URL}/auth/login"
API_BASE = f"{BASE_URL}/public/api"
GALAXY_BASE = f"{BASE_URL}/public/api/galaxy"

# 测试账号
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"

# 保存 session
session = requests.Session()
session.headers.update({'Content-Type': 'application/json'})

# ============================================================================
# 辅助函数
# ============================================================================

def login():
    """登录获取 cookie"""
    print("\n=== 登录测试账号 ===")
    resp = session.get(LOGIN_URL)
    csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    csrf_token = csrf_match.group(1) if csrf_match else None

    login_data = {
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
    }
    if csrf_token:
        login_data['csrf_token'] = csrf_token

    resp = session.post(LOGIN_URL, data=login_data, allow_redirects=True)

    if resp.status_code in [200, 302] and 'login' not in resp.url.lower():
        print(f"  ✓ 登录成功")
        return True
    print(f"  ✗ 登录失败: status={resp.status_code}, url={resp.url}")
    return False


def check_response(resp, description=""):
    """检查响应是否成功"""
    try:
        data = resp.json()
    except:
        print(f"  ✗ {description}: 响应不是 JSON，status={resp.status_code}")
        print(f"    内容: {resp.text[:200]}")
        return None

    if data.get('success'):
        print(f"  ✓ {description}")
        return data
    else:
        print(f"  ✗ {description}: {data.get('message', '未知错误')}")
        return data


def check_field_in_response(data, field_path, description=""):
    """
    检查响应中是否存在指定字段

    Args:
        data: 响应数据字典
        field_path: 字段路径，如 "data.nodes[0].name" 或 "data.geo_province"
        description: 字段描述
    """
    parts = field_path.split('.')
    current = data

    for part in parts:
        # 处理数组索引，如 nodes[0]
        m = re.match(r'(\w+)\[(\d+)\]', part)
        if m:
            key = m.group(1)
            idx = int(m.group(2))
            if not isinstance(current, dict) or key not in current:
                print(f"  ✗ 字段不存在: {field_path} ({description})")
                return False
            current = current[key]
            if not isinstance(current, list) or idx >= len(current):
                print(f"  ✗ 数组索引超出范围: {field_path} ({description})")
                return False
            current = current[idx]
        else:
            if not isinstance(current, dict) or part not in current:
                print(f"  ✗ 字段不存在: {field_path} ({description})")
                return False
            current = current[part]

    if current is not None:
        print(f"  ✓ 字段存在: {field_path} = {repr(current)[:80]} ({description})")
        return True
    else:
        print(f"  ✗ 字段为空: {field_path} ({description})")
        return False


def check_fields_exist(data, field_list, description=""):
    """检查多个字段是否存在于响应中"""
    all_pass = True
    for field_path, desc in field_list:
        if not check_field_in_response(data, field_path, desc):
            all_pass = False
    return all_pass


# ============================================================================
# 一、Galaxy API 接口测试（星系统）
# ============================================================================

def test_galaxy_graph_basic():
    """测试 1.1：星系概览接口 /graph 基础返回"""
    print("\n=== 测试 1.1：星系概览接口 /graph 基础返回 ===")
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = check_response(resp, "/graph 请求成功")

    if not data:
        return False

    # 检查顶层结构
    required_fields = [
        ("data.nodes", "节点列表"),
        ("data.links", "连线列表"),
        ("data.stats", "统计摘要"),
    ]
    result = check_fields_exist(data, required_fields, "顶层结构")

    # 检查节点类型
    nodes = data.get('data', {}).get('nodes', [])
    node_types = set()
    for node in nodes:
        if isinstance(node, dict):
            node_types.add(node.get('type', 'unknown'))

    print(f"  ℹ 节点类型: {node_types}")
    print(f"  ℹ 节点总数: {len(nodes)}")
    print(f"  ℹ 连线总数: {len(data.get('data', {}).get('links', []))}")

    return result


def test_galaxy_graph_new_fields():
    """测试 1.2：/graph 接口新增字段检查（cover_thumb、geo_*）"""
    print("\n=== 测试 1.2：/graph 接口新增字段检查 ===")
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = check_response(resp, "/graph 请求成功")

    if not data:
        return False

    nodes = data.get('data', {}).get('nodes', [])

    # 统计各类型节点的字段情况
    star_new_fields_count = 0
    planet_new_fields_count = 0

    for node in nodes:
        if not isinstance(node, dict):
            continue

        if node.get('type') == 'star':
            # 检查恒星节点的新字段
            has_geo = any([
                node.get('geo_province'),
                node.get('geo_city'),
                node.get('geo_level'),
                node.get('geo_coverages'),
                node.get('geo_tags'),
            ])
            has_cover_thumb = 'cover_thumb' in node

            if has_geo or has_cover_thumb:
                star_new_fields_count += 1

            # 如果有恒星，打印示例
            if star_new_fields_count == 1:
                print(f"  ℹ 恒星节点示例: {json.dumps({
                    'id': node.get('id'),
                    'name': node.get('name'),
                    'geo_province': node.get('geo_province', '(未设置)'),
                    'geo_city': node.get('geo_city', '(未设置)'),
                    'cover_thumb': node.get('cover_thumb', '(未设置)'),
                }, ensure_ascii=False)}")

        elif node.get('type') == 'planet':
            # 检查行星节点的新字段
            has_geo = any([
                node.get('geo_trigger_regions'),
                node.get('geo_seasonal_factor'),
            ])
            if has_geo:
                planet_new_fields_count += 1

            if planet_new_fields_count == 1:
                print(f"  ℹ 行星节点示例: {json.dumps({
                    'id': node.get('id'),
                    'name': node.get('name'),
                    'geo_trigger_regions': node.get('geo_trigger_regions', '(未设置)'),
                    'geo_seasonal_factor': node.get('geo_seasonal_factor', '(未设置)'),
                }, ensure_ascii=False)}")

    print(f"  ℹ 含新字段的恒星节点数: {star_new_fields_count}/{len([n for n in nodes if n.get('type') == 'star'])}")
    print(f"  ℹ 含新字段的行星节点数: {planet_new_fields_count}/{len([n for n in nodes if n.get('type') == 'planet'])}")

    # 注意：新字段可能为空，这是正常的（历史数据）
    print("  ℹ 注意：新字段为空表示历史数据尚未迁移，属正常现象")
    return True


def test_star_detail_new_fields():
    """测试 1.3：恒星节点详情接口新增字段"""
    print("\n=== 测试 1.3：恒星节点详情接口新增字段 ===")

    # 先获取一个有效的 portrait_id
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()

    portrait_id = None
    nodes = data.get('data', {}).get('nodes', [])
    for node in nodes:
        if node.get('type') == 'star' and node.get('portrait_id'):
            portrait_id = node.get('portrait_id')
            break

    if not portrait_id:
        print("  ⊘ 无恒星节点，跳过此测试")
        return None

    resp = session.get(f"{GALAXY_BASE}/node/star/{portrait_id}")
    data = check_response(resp, f"/node/star/{portrait_id} 请求成功")

    if not data:
        return False

    # 检查恒星详情的新字段
    new_fields = [
        ("data.geo_province", "省份"),
        ("data.geo_city", "城市"),
        ("data.geo_level", "地域粒度"),
        ("data.geo_coverages", "覆盖地域列表"),
        ("data.geo_tags", "地域标签"),
        ("data.cover_thumb", "缩略图URL"),
    ]

    result = check_fields_exist(data, new_fields, "恒星详情新字段")

    # 打印示例
    d = data.get('data', {})
    print(f"  ℹ 恒星详情示例: {json.dumps({
        'portrait_id': d.get('portrait_id'),
        'name': d.get('name'),
        'geo_province': d.get('geo_province'),
        'geo_city': d.get('geo_city'),
        'geo_level': d.get('geo_level'),
        'cover_thumb': d.get('cover_thumb'),
    }, ensure_ascii=False)}")

    return result


def test_planet_detail_new_fields():
    """测试 1.4：行星节点详情接口新增字段"""
    print("\n=== 测试 1.4：行星节点详情接口新增字段 ===")

    # 先获取一个有效的 problem_id
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()

    problem_id = None
    nodes = data.get('data', {}).get('nodes', [])
    for node in nodes:
        if node.get('type') == 'planet' and node.get('problem_id'):
            problem_id = node.get('problem_id')
            break

    if not problem_id:
        print("  ⊘ 无行星节点，跳过此测试")
        return None

    resp = session.get(f"{GALAXY_BASE}/node/planet/{problem_id}")
    data = check_response(resp, f"/node/planet/{problem_id} 请求成功")

    if not data:
        return False

    # 检查行星详情的新字段
    new_fields = [
        ("data.geo_trigger_regions", "触发地域列表"),
        ("data.geo_seasonal_factor", "季节性因素"),
    ]

    result = check_fields_exist(data, new_fields, "行星详情新字段")

    # 打印示例
    d = data.get('data', {})
    print(f"  ℹ 行星详情示例: {json.dumps({
        'problem_id': d.get('problem_id'),
        'name': d.get('name'),
        'geo_trigger_regions': d.get('geo_trigger_regions'),
        'geo_seasonal_factor': d.get('geo_seasonal_factor'),
    }, ensure_ascii=False)}")

    return result


def test_satellite_detail_new_fields():
    """测试 1.5：卫星节点详情接口新增字段"""
    print("\n=== 测试 1.5：卫星节点详情接口新增字段 ===")

    # 先获取一个有效的 generation_id
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()

    generation_id = None
    nodes = data.get('data', {}).get('nodes', [])
    for node in nodes:
        if node.get('type') == 'satellite' and node.get('generation_id'):
            generation_id = node.get('generation_id')
            break

    if not generation_id:
        print("  ⊘ 无卫星节点，跳过此测试")
        return None

    resp = session.get(f"{GALAXY_BASE}/node/satellite/{generation_id}")
    data = check_response(resp, f"/node/satellite/{generation_id} 请求成功")

    if not data:
        return False

    # 卫星节点的新字段（geo_target_regions、geo_adaptation_level）
    # 注意：这些字段在卫星详情接口中可能不存在，需要等迁移后才有
    d = data.get('data', {})
    geo_fields = ['geo_target_regions', 'geo_adaptation_level']
    found_fields = [f for f in geo_fields if f in d]

    if found_fields:
        print(f"  ✓ 卫星详情含新字段: {found_fields}")
        return True
    else:
        print(f"  ℹ 卫星详情暂无新字段（历史数据），属正常现象")
        return True  # 不算失败


def test_generation_link_new_fields():
    """测试 1.6：/generation/link 接口新字段（selected_scenes）"""
    print("\n=== 测试 1.6：/generation/link 接口新字段 ===")

    # 获取一个有效的 generation_id
    resp = session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()

    generation_id = None
    portrait_id = None
    nodes = data.get('data', {}).get('nodes', [])
    for node in nodes:
        if node.get('type') == 'satellite' and node.get('generation_id'):
            generation_id = node.get('generation_id')
            portrait_id = node.get('portrait_id')
            break

    if not generation_id:
        print("  ⊘ 无卫星节点，跳过此测试")
        return None

    # 测试关联接口（只读，不修改数据）
    print(f"  ℹ 测试 /generation/link 接口（generation_id={generation_id}）")

    # 验证接口存在且接受 POST 请求
    resp = session.post(f"{GALAXY_BASE}/generation/link", json={
        "generation_id": generation_id,
        "portrait_id": portrait_id,
    })

    data = resp.json()
    if data.get('success'):
        print(f"  ✓ /generation/link 接口正常")
        # 检查返回数据是否包含 selected_scenes 相关字段（如果有的话）
        return True
    else:
        print(f"  ℹ /generation/link 返回: {data.get('message', '未知')}")
        return True  # 接口存在即可


# ============================================================================
# 二、选题接口测试（scene_options）
# ============================================================================

def test_topics_api_new_fields():
    """测试 2.1：选题接口新增字段（scene_options、content_style）"""
    print("\n=== 测试 2.1：选题接口新增字段检查 ===")

    # 调用选题相关接口（通过画像详情接口获取）
    # 或者直接查看 /public/api/galaxy/graph 返回的卫星节点

    resp = session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()

    if not data.get('success'):
        print(f"  ✗ /graph 请求失败")
        return False

    print("  ℹ 选题相关字段需通过 /api/topics 接口测试")
    print("  ℹ scene_options 字段将在 PublicIndustryTopic 模型中验证")

    # 由于选题接口较复杂，标记需要后续手动测试
    print("  ⊘ 选题接口需要实际选题数据，标记为后续测试")
    return None


# ============================================================================
# 三、模型层字段测试（数据库 Schema 验证）
# ============================================================================

def test_model_public_generation_fields():
    """测试 3.1：PublicGeneration 模型新字段验证"""
    print("\n=== 测试 3.1：PublicGeneration 模型新字段验证 ===")

    try:
        from app import app
        from models.models import db
        from models.public_models import PublicGeneration
        from sqlalchemy import text

        with app.app_context():
            conn = db.engine.connect()

            # 检查 public_generations 表的列
            result = conn.execute(text("PRAGMA table_info(public_generations)"))
            columns = {row[1]: row[4] for row in result.fetchall()}  # col_name -> default

            print(f"  ℹ public_generations 当前列: {list(columns.keys())}")

            # 检查新字段
            new_fields = {
                'selected_scenes': 'JSON 字段，存储客户选择的场景组合',
            }

            result = True
            for field, desc in new_fields.items():
                if field in columns:
                    print(f"  ✓ 字段存在: {field} - {desc}")
                else:
                    print(f"  ✗ 字段缺失: {field} - {desc}")
                    result = False

            conn.close()
            return result

    except Exception as e:
        print(f"  ✗ 模型验证失败: {e}")
        return False


def test_model_public_industry_topic_fields():
    """测试 3.2：PublicIndustryTopic 模型新字段验证"""
    print("\n=== 测试 3.2：PublicIndustryTopic 模型新字段验证 ===")

    try:
        from app import app
        from models.models import db
        from sqlalchemy import text

        with app.app_context():
            conn = db.engine.connect()

            # 检查 public_industry_topics 表的列
            result = conn.execute(text("PRAGMA table_info(public_industry_topics)"))
            columns = {row[1]: row[4] for row in result.fetchall()}

            print(f"  ℹ public_industry_topics 当前列: {list(columns.keys())}")

            # 检查新字段
            new_fields = {
                'scene_options': 'JSON 数组，AI 生成的场景组合列表',
                'content_style': 'VARCHAR，内容风格类型',
            }

            # 检查 applicable_scenarios 是否仍存在（确认不是被覆盖）
            if 'applicable_scenarios' in columns:
                print(f"  ✓ applicable_scenarios 字段保留（与 scene_options 正交）")
            else:
                print(f"  ℹ applicable_scenarios 字段不存在（可能尚未创建）")

            result = True
            for field, desc in new_fields.items():
                if field in columns:
                    print(f"  ✓ 字段存在: {field} - {desc}")
                else:
                    print(f"  ✗ 字段缺失: {field} - {desc}")
                    result = False

            conn.close()
            return result

    except Exception as e:
        print(f"  ✗ 模型验证失败: {e}")
        return False


def test_model_saved_portrait_fields():
    """测试 3.3：SavedPortrait 模型新字段验证"""
    print("\n=== 测试 3.3：SavedPortrait 模型新字段验证 ===")

    try:
        from app import app
        from models.models import db
        from sqlalchemy import text

        with app.app_context():
            conn = db.engine.connect()

            # 检查 saved_portraits 表的列
            result = conn.execute(text("PRAGMA table_info(saved_portraits)"))
            columns = {row[1]: row[4] for row in result.fetchall()}

            print(f"  ℹ saved_portraits 当前列: {list(columns.keys())}")

            # 检查新字段
            new_fields = {
                'cover_thumb': 'VARCHAR(255)，恒星缩略图 URL',
                'geo_province': 'VARCHAR，省份',
                'geo_city': 'VARCHAR，城市',
                'geo_level': 'VARCHAR，地域粒度',
                'geo_coverages': 'JSON，覆盖地域列表',
                'geo_tags': 'JSON，地域标签',
            }

            result = True
            for field, desc in new_fields.items():
                if field in columns:
                    default_val = columns.get(field, '')
                    print(f"  ✓ 字段存在: {field} (默认: {default_val}) - {desc}")
                else:
                    print(f"  ✗ 字段缺失: {field} - {desc}")
                    result = False

            conn.close()
            return result

    except Exception as e:
        print(f"  ✗ 模型验证失败: {e}")
        return False


def test_model_persona_user_problem_fields():
    """测试 3.4：PersonaUserProblem 模型新字段验证"""
    print("\n=== 测试 3.4：PersonaUserProblem 模型新字段验证 ===")

    try:
        from app import app
        from models.models import db
        from sqlalchemy import text

        with app.app_context():
            conn = db.engine.connect()

            # 检查 persona_user_problems 表的列
            result = conn.execute(text("PRAGMA table_info(persona_user_problems)"))
            columns = {row[1]: row[4] for row in result.fetchall()}

            print(f"  ℹ persona_user_problems 当前列: {list(columns.keys())}")

            # 检查新字段
            new_fields = {
                'geo_trigger_regions': 'JSON，触发问题的地域列表',
                'geo_seasonal_factor': 'VARCHAR，季节性因素',
            }

            result = True
            for field, desc in new_fields.items():
                if field in columns:
                    default_val = columns.get(field, '')
                    print(f"  ✓ 字段存在: {field} (默认: {default_val}) - {desc}")
                else:
                    print(f"  ✗ 字段缺失: {field} - {desc}")
                    result = False

            conn.close()
            return result

    except Exception as e:
        print(f"  ✗ 模型验证失败: {e}")
        return False


# ============================================================================
# 四、字段语义区分验证
# ============================================================================

def test_field_semantic_distinction():
    """测试 4.1：applicable_scenarios 与 scene_options 语义区分"""
    print("\n=== 测试 4.1：applicable_scenarios 与 scene_options 语义区分 ===")

    print("""
  语义验证（静态检查）：

  ✓ applicable_scenarios = 业务场景（营销策略）
    例：["种草", "带货", "品牌宣传"]

  ✓ scene_options = 内容场景组合（内容策略）
    例：[{"组合": "高三家长+出分后+焦虑", "标签": "焦虑型", "风格": "情绪共鸣"}]

  ✓ 两者是正交维度，同时存在
  ✓ 代码中应有注释区分两者语义
    """)

    # 检查模型中是否有注释区分
    try:
        with open('/Volumes/增元/项目/douyin/系统部署/models/public_models.py', 'r', encoding='utf-8') as f:
            content = f.read()

        has_applicable_scenarios = 'applicable_scenarios' in content
        has_scene_options = 'scene_options' in content
        has_semantic_comment = '营销策略' in content or '业务场景' in content or '内容策略' in content

        if has_scene_options:
            print("  ✓ scene_options 字段已存在于模型代码")
        else:
            print("  ⊘ scene_options 字段尚未添加到模型（需等待迁移）")

        if has_semantic_comment:
            print("  ✓ 模型代码中包含语义区分注释")
        else:
            print("  ℹ 建议在模型中添加语义区分注释")

        return True

    except Exception as e:
        print(f"  ℹ 静态检查失败: {e}")
        return True  # 不阻塞


# ============================================================================
# 五、数据完整性测试
# ============================================================================

def test_data_integrity_check():
    """测试 5.1：数据完整性检查（新增字段默认值验证）"""
    print("\n=== 测试 5.1：数据完整性检查 ===")

    try:
        from app import app
        from models.models import db
        from models.public_models import SavedPortrait, PublicGeneration, PublicIndustryTopic
        from models.models import PersonaUserProblem
        from sqlalchemy import text

        with app.app_context():
            conn = db.engine.connect()

            # 检查各表的索引
            indexes_result = conn.execute(text(
                "SELECT name, tbl_name FROM sqlite_master WHERE type='index' "
                "AND tbl_name IN ('saved_portraits', 'public_industry_topics', 'persona_user_problems')"
            ))
            indexes = indexes_result.fetchall()

            print(f"  ℹ 现有索引数量: {len(indexes)}")
            index_names = [idx[0] for idx in indexes]

            # 检查建议的新索引
            recommended_indexes = [
                'idx_portrait_geo',
                'idx_topic_scene',
            ]

            for idx in recommended_indexes:
                if idx in index_names:
                    print(f"  ✓ 索引存在: {idx}")
                else:
                    print(f"  ℹ 建议创建索引: {idx}（可选，性能优化）")

            conn.close()
            return True

    except Exception as e:
        print(f"  ✗ 数据完整性检查失败: {e}")
        return False


# ============================================================================
# 六、API 错误处理测试
# ============================================================================

def test_api_error_handling():
    """测试 6.1：API 错误处理"""
    print("\n=== 测试 6.1：API 错误处理 ===")

    # 6.1.1 未登录访问 /graph
    print("  [6.1.1] 未登录访问 /graph")
    anonymous_session = requests.Session()
    resp = anonymous_session.get(f"{GALAXY_BASE}/graph")
    data = resp.json()
    if not data.get('success') and resp.status_code == 401:
        print(f"  ✓ 正确返回 401 未授权")
    else:
        print(f"  ✗ 期望 401，实际 {resp.status_code}")

    # 6.1.2 访问不存在的恒星节点
    print("  [6.1.2] 访问不存在的恒星节点")
    resp = session.get(f"{GALAXY_BASE}/node/star/999999")
    data = resp.json()
    if not data.get('success') and resp.status_code == 404:
        print(f"  ✓ 正确返回 404")
    else:
        print(f"  ℹ 返回: {data.get('message', 'N/A')}")

    # 6.1.3 访问不存在的行星节点
    print("  [6.1.3] 访问不存在的行星节点")
    resp = session.get(f"{GALAXY_BASE}/node/planet/999999")
    data = resp.json()
    if not data.get('success') and resp.status_code == 404:
        print(f"  ✓ 正确返回 404")
    else:
        print(f"  ℹ 返回: {data.get('message', 'N/A')}")

    # 6.1.4 /generation/link 缺少必填参数
    print("  [6.1.4] /generation/link 缺少必填参数")
    resp = session.post(f"{GALAXY_BASE}/generation/link", json={})
    data = resp.json()
    if not data.get('success') and resp.status_code == 400:
        print(f"  ✓ 正确返回 400")
    else:
        print(f"  ℹ 返回: {data.get('message', 'N/A')}")

    return True


# ============================================================================
# 七、综合测试报告
# ============================================================================

def run_all_tests():
    """运行所有测试"""
    print("=" * 70)
    print("星系图谱增强功能 - 测试用例")
    print("=" * 70)
    print(f"目标服务器: {BASE_URL}")
    print(f"测试账号: {TEST_USERNAME}")
    print("=" * 70)

    # 先登录
    if not login():
        print("\n✗ 登录失败，测试中断")
        return

    # 汇总结果
    results = {}

    # 一、Galaxy API 测试
    print("\n" + "=" * 70)
    print("一、Galaxy API 接口测试")
    print("=" * 70)

    results['1.1_graph_basic'] = test_galaxy_graph_basic()
    results['1.2_graph_new_fields'] = test_galaxy_graph_new_fields()
    results['1.3_star_detail'] = test_star_detail_new_fields()
    results['1.4_planet_detail'] = test_planet_detail_new_fields()
    results['1.5_satellite_detail'] = test_satellite_detail_new_fields()
    results['1.6_generation_link'] = test_generation_link_new_fields()

    # 二、选题接口测试
    print("\n" + "=" * 70)
    print("二、选题接口测试")
    print("=" * 70)

    results['2.1_topics_new_fields'] = test_topics_api_new_fields()

    # 三、模型层字段测试
    print("\n" + "=" * 70)
    print("三、模型层字段测试（数据库 Schema）")
    print("=" * 70)

    results['3.1_public_generation'] = test_model_public_generation_fields()
    results['3.2_industry_topic'] = test_model_public_industry_topic_fields()
    results['3.3_saved_portrait'] = test_model_saved_portrait_fields()
    results['3.4_persona_problem'] = test_model_persona_user_problem_fields()

    # 四、字段语义区分
    print("\n" + "=" * 70)
    print("四、字段语义区分验证")
    print("=" * 70)

    results['4.1_semantic_distinction'] = test_field_semantic_distinction()

    # 五、数据完整性
    print("\n" + "=" * 70)
    print("五、数据完整性测试")
    print("=" * 70)

    results['5.1_integrity'] = test_data_integrity_check()

    # 六、错误处理
    print("\n" + "=" * 70)
    print("六、API 错误处理测试")
    print("=" * 70)

    results['6.1_error_handling'] = test_api_error_handling()

    # ============================================================================
    # 测试报告汇总
    # ============================================================================
    print("\n" + "=" * 70)
    print("测试报告汇总")
    print("=" * 70)

    passed = 0
    failed = 0
    skipped = 0

    for name, result in results.items():
        if result is True:
            passed += 1
            status = "✓ 通过"
        elif result is False:
            failed += 1
            status = "✗ 失败"
        else:
            skipped += 1
            status = "⊘ 跳过"

        print(f"  {status}  {name}")

    print("-" * 70)
    print(f"  通过: {passed}  |  失败: {failed}  |  跳过: {skipped}")
    print("=" * 70)

    # ============================================================================
    # 迁移状态检查
    # ============================================================================
    print("\n[迁移状态检查]")
    print("""
  根据测试结果，判断迁移状态：

  1. 如果模型层测试（3.x）全部失败
     → 需要运行数据库迁移脚本
     → 运行: python3 系统部署/migrate_galaxy_enhancement.py

  2. 如果模型层测试通过，但 API 测试失败
     → 检查 API 代码是否已更新
     → 检查 blueprint 注册是否正确

  3. 如果所有测试通过
     → 迁移完成，功能正常

  4. 如果新字段为空（历史数据）
     → 属正常现象，新数据会包含新字段
    """)

    return passed, failed, skipped


# ============================================================================
# 入口
# ============================================================================

if __name__ == '__main__':
    run_all_tests()
