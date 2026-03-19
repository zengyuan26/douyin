"""
账号分析 API 测试用例

使用方法：
1. 启动服务器：python3 app.py
2. 登录获取 cookie
3. 运行测试：python3 test_analyze_api.py
"""
import json
import requests

# 配置
BASE_URL = "http://localhost:5001"
LOGIN_URL = f"{BASE_URL}/auth/login"
API_BASE = f"{BASE_URL}/api/knowledge"

# 测试账号
TEST_USERNAME = "admin"
TEST_PASSWORD = "admin123"

# 保存 session
session = requests.Session()
session.headers.update({'Content-Type': 'application/json'})


def login():
    """登录获取 cookie"""
    print("=== 开始登录 ===")
    # 先获取登录页面，获取 CSRF token
    resp = session.get(LOGIN_URL)
    print(f"1. 获取登录页面状态: {resp.status_code}")
    
    # 尝试从页面提取 CSRF token
    import re
    csrf_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', resp.text)
    csrf_token = csrf_match.group(1) if csrf_match else None
    print(f"2. CSRF Token: {csrf_token[:20] if csrf_token else 'None'}...")
    
    login_data = {
        'username': TEST_USERNAME,
        'password': TEST_PASSWORD,
    }
    if csrf_token:
        login_data['csrf_token'] = csrf_token
    
    print(f"3. 准备登录, username={TEST_USERNAME}, password={TEST_PASSWORD}")
    
    # 登录是 form 提交，允许跟随重定向
    resp = session.post(LOGIN_URL, data=login_data, allow_redirects=True)
    print(f"4. 登录状态: {resp.status_code}")
    print(f"5. 响应 URL: {resp.url}")
    
    # 检查响应中是否包含成功或失败的线索
    print(f"6. 响应包含 '登录成功': {'登录成功' in resp.text}")
    print(f"7. 响应包含 '用户名或密码错误': {'用户名或密码错误' in resp.text}")
    print(f"8. 响应包含 '账号已被禁用': {'账号已被禁用' in resp.text}")
    print(f"9. 响应包含 '正在审核': {'审核' in resp.text}")
    
    # 如果返回 login 页面，打印响应内容中的错误信息
    if 'login' in resp.url.lower():
        # 检查是否有 flash 错误消息 - bootstrap alert 格式
        import re
        flashes = re.findall(r'<div[^>]*class="[^"]*alert[^"]*"[^>]*>.*?<i[^>]*>.*?</i>\s*(.+?)\s*</div>', resp.text)
        if flashes:
            print(f"Flash 错误: {flashes}")
        print("响应内容前 1500 字符:")
        print(resp.text[:1500])
    
    # 检查是否登录成功（返回首页或 200）
    if resp.status_code in [200, 302] and 'login' not in resp.url.lower():
        return True
    print(f"登录失败原因: status={resp.status_code}, url={resp.url}")
    return False


def get_test_account_id():
    """获取一个测试账号 ID"""
    resp = session.get(f"{API_BASE}/accounts/")
    print(f"获取账号列表状态: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"响应内容: {resp.text[:500]}")
        return None
    
    data = resp.json()
    
    accounts = data.get('data', {}).get('accounts', [])
    if accounts:
        return accounts[0]['id']
    return None


def test_analyze_nb():
    """测试 analyze-sub-categories with target=nb (昵称+简介)"""
    print("\n" + "=" * 60)
    print("测试: target=nb (昵称+简介)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    print(f"使用账号 ID: {account_id}")
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "nb", "force": True}
    )
    
    print(f"状态码: {resp.status_code}")
    if resp.status_code != 200:
        print(f"响应内容: {resp.text[:500]}")
        return
    
    data = resp.json()
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '昵称+简介' in data.get('message', ''), f"期望 message 包含'昵称+简介'"
    print("✓ 通过")


def test_analyze_positioning():
    """测试 analyze-sub-categories with target=positioning (账号定位)"""
    print("\n" + "=" * 60)
    print("测试: target=positioning (账号定位)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "positioning", "force": True}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '账号定位' in data.get('message', ''), f"期望 message 包含'账号定位'"
    print("✓ 通过")


def test_analyze_market():
    """测试 analyze-sub-categories with target=market (市场分析)"""
    print("\n" + "=" * 60)
    print("测试: target=market (市场分析)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "market", "force": True}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '市场分析' in data.get('message', ''), f"期望 message 包含'市场分析'"
    print("✓ 通过")


def test_analyze_operation():
    """测试 analyze-sub-categories with target=operation (运营规划)"""
    print("\n" + "=" * 60)
    print("测试: target=operation (运营规划)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "operation", "force": True}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '运营规划' in data.get('message', ''), f"期望 message 包含'运营规划'"
    print("✓ 通过")


def test_analyze_keyword():
    """测试 analyze-sub-categories with target=keyword (关键词库)"""
    print("\n" + "=" * 60)
    print("测试: target=keyword (关键词库)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "keyword", "force": True}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '关键词库' in data.get('message', ''), f"期望 message 包含'关键词库'"
    print("✓ 通过")


def test_analyze_all():
    """测试 analyze-sub-categories with target=all (全量分析)"""
    print("\n" + "=" * 60)
    print("测试: target=all (全量分析)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "all", "force": True}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    assert '全量分析' in data.get('message', ''), f"期望 message 包含'全量分析'"
    print("✓ 通过")


def test_analyze_auto():
    """测试 analyze-sub-categories with target=auto (智能增量)"""
    print("\n" + "=" * 60)
    print("测试: target=auto (智能增量分析)")
    print("=" * 60)
    
    account_id = get_test_account_id()
    if not account_id:
        print("✗ 找不到测试账号，跳过测试")
        return
    
    resp = session.post(
        f"{API_BASE}/accounts/{account_id}/analyze-sub-categories",
        json={"target": "auto"}
    )
    data = resp.json()
    
    print(f"状态码: {resp.status_code}")
    print(f"返回: {json.dumps(data, ensure_ascii=False)}")
    
    assert resp.status_code == 200, f"期望 200, 实际 {resp.status_code}"
    assert data['code'] == 200, f"期望 code=200, 实际 {data.get('code')}"
    print("✓ 通过")


if __name__ == '__main__':
    print("=" * 60)
    print("账号分析 API 测试")
    print("=" * 60)
    
    # 登录
    if not login():
        print("✗ 登录失败，请检查账号密码")
        exit(1)
    
    print("✓ 登录成功")
    
    # 运行测试
    try:
        test_analyze_nb()
        test_analyze_positioning()
        test_analyze_market()
        test_analyze_operation()
        test_analyze_keyword()
        test_analyze_all()
        test_analyze_auto()
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ 测试出错: {e}")
        exit(1)
