"""
公式要素管理模块测试用例

使用方法：
1. 启动服务器：python3 app.py
2. 登录获取 cookie
3. 运行测试：python3 test_formula_elements_api.py

或者使用 curl 命令手动测试
"""
import json
import requests
from urllib.parse import urljoin

# 配置
BASE_URL = "http://localhost:5001"
LOGIN_URL = f"{BASE_URL}/auth/login"
API_BASE = f"{BASE_URL}/knowledge"

# 测试账号
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"

# 保存 session
session = requests.Session()
session.headers.update({'Content-Type': 'application/json'})


def login():
    """登录获取 cookie"""
    # 先获取登录页面获取 csrf token
    resp = session.get(LOGIN_URL)
    
    # 尝试登录（根据实际表单调整）
    login_data = {
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD
    }
    resp = session.post(LOGIN_URL, data=login_data, allow_redirects=False)
    print(f"登录状态: {resp.status_code}")
    return resp.status_code in [200, 302]


def test_get_elements():
    """1. 获取所有要素"""
    print("\n" + "=" * 60)
    print("测试 1: 获取所有要素")
    print("=" * 60)
    
    resp = session.get(f"{API_BASE}/api/formula-elements/")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)[:200]}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 0, f"期望 code=0, 实际 {data.get('code')}"
    print("✓ 通过")


def test_get_elements_by_category():
    """2. 按分类获取要素"""
    print("\n" + "=" * 60)
    print("测试 2: 按分类获取要素")
    print("=" * 60)
    
    resp = session.get(f"{API_BASE}/api/formula-elements/?sub_category=nickname_analysis")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回数量: {len(data.get('data', []))}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    print("✓ 通过")


def test_create_element_success():
    """3. 成功创建要素"""
    print("\n" + "=" * 60)
    print("测试 3: 成功创建要素")
    print("=" * 60)
    
    payload = {
        'sub_category': 'nickname_analysis',
        'name': '测试产品词',
        'code': 'test_product_api',
        'description': '测试描述',
        'examples': '测试1|测试2',
        'priority': 1,
        'usage_tips': '测试技巧'
    }
    
    resp = session.post(
        f"{API_BASE}/api/formula-elements/",
        json=payload
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    print("✓ 通过")


def test_create_element_duplicate():
    """4. 创建重复编码（应失败）"""
    print("\n" + "=" * 60)
    print("测试 4: 创建重复编码（应失败）")
    print("=" * 60)
    
    # 先创建一个
    payload1 = {
        'sub_category': 'nickname_analysis',
        'name': '重复测试',
        'code': 'duplicate_test'
    }
    session.post(f"{API_BASE}/api/formula-elements/", json=payload1)
    
    # 再创建相同的
    payload2 = {
        'sub_category': 'nickname_analysis',
        'name': '重复测试2',
        'code': 'duplicate_test'
    }
    resp = session.post(f"{API_BASE}/api/formula-elements/", json=payload2)
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 400
    assert '已存在' in data.get('message', '')
    print("✓ 通过（正确拒绝重复编码）")


def test_create_element_missing_required():
    """5. 缺少必填字段（应失败）"""
    print("\n" + "=" * 60)
    print("测试 5: 缺少必填字段（应失败）")
    print("=" * 60)
    
    payload = {
        'sub_category': 'nickname_analysis',
        'name': '测试'
        # 缺少 code
    }
    
    resp = session.post(f"{API_BASE}/api/formula-elements/", json=payload)
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 400
    assert data['code'] == 400
    print("✓ 通过")


def test_update_element():
    """6. 更新要素"""
    print("\n" + "=" * 60)
    print("测试 6: 更新要素")
    print("=" * 60)
    
    # 先创建一个
    create_payload = {
        'sub_category': 'nickname_analysis',
        'name': '更新测试',
        'code': 'update_test',
        'description': '原始描述'
    }
    create_resp = session.post(f"{API_BASE}/api/formula-elements/", json=create_payload)
    element_id = create_resp.json()['data']['id']
    
    # 更新
    update_payload = {
        'name': '更新后名称',
        'description': '更新后描述',
        'usage_tips': '更新后技巧'
    }
    
    resp = session.put(
        f"{API_BASE}/api/formula-elements/{element_id}",
        json=update_payload
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    print("✓ 通过")


def test_delete_element():
    """7. 删除要素"""
    print("\n" + "=" * 60)
    print("测试 7: 删除要素")
    print("=" * 60)
    
    # 先创建一个
    create_payload = {
        'sub_category': 'nickname_analysis',
        'name': '删除测试',
        'code': 'delete_test'
    }
    create_resp = session.post(f"{API_BASE}/api/formula-elements/", json=create_payload)
    element_id = create_resp.json()['data']['id']
    
    # 删除
    resp = session.delete(f"{API_BASE}/api/formula-elements/{element_id}")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    print("✓ 通过")


def test_init_elements():
    """8. 初始化要素"""
    print("\n" + "=" * 60)
    print("测试 8: 初始化要素")
    print("=" * 60)
    
    resp = session.post(f"{API_BASE}/api/formula-elements/init")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    
    # 验证创建了要素
    resp2 = session.get(f"{API_BASE}/api/formula-elements/?sub_category=nickname_analysis")
    elements = resp2.json()['data']
    print(f"昵称要素数量: {len(elements)}")
    
    assert len(elements) >= 9
    print("✓ 通过")


def test_export_elements():
    """9. 导出要素"""
    print("\n" + "=" * 60)
    print("测试 9: 导出要素")
    print("=" * 60)
    
    resp = session.get(f"{API_BASE}/api/formula-elements/export")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)[:300]}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    assert 'nickname_analysis' in data['data']
    print("✓ 通过")


def test_import_elements():
    """10. 导入要素"""
    print("\n" + "=" * 60)
    print("测试 10: 导入要素")
    print("=" * 60)
    
    payload = {
        'nickname_analysis': [
            {
                'name': '导入测试词',
                'code': 'import_test_api',
                'description': '导入测试描述',
                'priority': 1
            }
        ]
    }
    
    resp = session.post(f"{API_BASE}/api/formula-elements/import", json=payload)
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200
    print("✓ 通过")


def test_get_suggestions():
    """11. 获取建议列表"""
    print("\n" + "=" * 60)
    print("测试 11: 获取建议列表")
    print("=" * 60)
    
    resp = session.get(f"{API_BASE}/api/formula-elements/suggestions")
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)[:200]}")
    
    assert resp.status_code == 200
    assert data['code'] == 0
    print("✓ 通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("公式要素管理模块 API 测试")
    print("=" * 60)
    
    # 登录
    if not login():
        print("❌ 登录失败，请检查账号密码")
        return False
    
    print("✓ 登录成功")
    
    # 运行测试
    tests = [
        test_get_elements,
        test_get_elements_by_category,
        test_create_element_success,
        test_create_element_duplicate,
        test_create_element_missing_required,
        test_update_element,
        test_delete_element,
        test_init_elements,
        test_export_elements,
        test_import_elements,
        test_get_suggestions,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ 失败: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ 错误: {e}")
            failed += 1
    
    # 总结
    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
