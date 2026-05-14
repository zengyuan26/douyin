"""
决策成本诊断系统 - 测试用例

测试范围：
1. 知识图谱 - 业务匹配与评分
2. API接口 - 诊断与内容生成
3. LLM集成 - 深度分析
4. 搜索增强 - 真实性验证
5. 蓝海对接 - 数据流转
"""

import sys
import os
import time
import json

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================== 测试运行器 ====================

class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []

    def assert_true(self, condition, message):
        if condition:
            self.passed += 1
            self.results.append(('✅', message))
        else:
            self.failed += 1
            self.results.append(('❌', message))

    def assert_equal(self, actual, expected, message):
        if actual == expected:
            self.passed += 1
            self.results.append(('✅', message))
        else:
            self.failed += 1
            self.results.append(('❌', f'{message}: 期望 {expected}, 实际 {actual}'))

    def assert_in(self, item, container, message):
        if item in container:
            self.passed += 1
            self.results.append(('✅', message))
        else:
            self.failed += 1
            self.results.append(('❌', f'{message}: {item} 不在 {container}'))

    def assert_range(self, value, min_val, max_val, message):
        if min_val <= value <= max_val:
            self.passed += 1
            self.results.append(('✅', message))
        else:
            self.failed += 1
            self.results.append(('❌', f'{message}: {value} 不在范围 [{min_val}, {max_val}]'))

    def print_summary(self):
        print('\n' + '=' * 60)
        print(f'测试结果: {self.passed} 通过, {self.failed} 失败')
        print('=' * 60)
        for status, msg in self.results:
            print(f'{status} {msg}')
        return self.failed == 0


# ==================== 1. 知识图谱测试 ====================

def test_knowledge_graph(t):
    """知识图谱测试"""
    print('\n【1. 知识图谱测试】')
    print('-' * 40)

    from services.decision_cost_service import BUSINESS_KNOWLEDGE_GRAPH

    # 测试所有业务类型都有必需字段
    required_fields = ['基础特征', '成本评分', '核心焦虑', '内容方向']
    for business_name, business_data in BUSINESS_KNOWLEDGE_GRAPH.items():
        for field in required_fields:
            t.assert_in(field, business_data, f'{business_name} 有 {field} 字段')

    # 测试7维度评分
    required_dimensions = ['金钱成本', '时间成本', '信息获取', '信息辨识', '信任构建', '风险成本', '心理成本']
    for business_name, business_data in BUSINESS_KNOWLEDGE_GRAPH.items():
        scores = business_data['成本评分']
        for dim in required_dimensions:
            t.assert_in(dim, scores, f'{business_name} 有 {dim} 评分')
            t.assert_range(scores[dim], 1, 10, f'{business_name}.{dim} 评分在1-10范围')

    # 测试内容方向
    for business_name, business_data in BUSINESS_KNOWLEDGE_GRAPH.items():
        content_directions = business_data['内容方向']
        t.assert_true(len(content_directions) >= 3, f'{business_name} 有至少3个内容方向')

        for cd in content_directions:
            t.assert_in('type', cd, f'{business_name} 内容方向有 type')
            t.assert_in('weight', cd, f'{business_name} 内容方向有 weight')
            t.assert_range(cd['weight'], 0, 1, f'{business_name}.{cd["type"]} 权重在0-1范围')

    # 测试核心焦虑
    for business_name, business_data in BUSINESS_KNOWLEDGE_GRAPH.items():
        anxieties = business_data['核心焦虑']
        t.assert_true(len(anxieties) >= 3, f'{business_name} 有至少3个核心焦虑点')


# ==================== 2. 业务匹配测试 ====================

def test_business_matching(t):
    """业务匹配测试"""
    print('\n【2. 业务匹配测试】')
    print('-' * 40)

    from services.decision_cost_service import DecisionCostService
    service = DecisionCostService()

    # 精确匹配
    exact_tests = [
        ('医美整形', '医美整形'),
        ('装修', '装修'),
        ('金融投资', '金融投资'),
        ('高考志愿', '高考志愿'),
        ('留学中介', '留学中介'),
        ('婚恋相亲', '婚恋相亲'),
        ('房产买卖', '房产买卖'),
        ('儿童教育', '儿童教育'),
    ]
    for keyword, expected in exact_tests:
        t.assert_equal(service.match_business(keyword), expected, f'精确匹配: {keyword}')

    # 模糊匹配
    fuzzy_tests = [
        ('整形', '医美整形'),
        ('整容', '医美整形'),
        ('美容', '医美整形'),
        ('医美', '医美整形'),
        ('高考', '高考志愿'),
        ('志愿', '高考志愿'),
        ('填报', '高考志愿'),
        ('买房', '房产买卖'),
        ('卖房', '房产买卖'),
        ('购房', '房产买卖'),
        ('理财', '金融投资'),
        ('投资', '金融投资'),
        ('股票', '金融投资'),
        ('基金', '金融投资'),
        ('留学', '留学中介'),
        ('移民', '留学中介'),
        ('培训', '儿童教育'),
        ('补习', '儿童教育'),
        ('相亲', '婚恋相亲'),
        ('婚恋', '婚恋相亲'),
    ]
    for keyword, expected in fuzzy_tests:
        t.assert_equal(service.match_business(keyword), expected, f'模糊匹配: {keyword}')

    # 空字符串（strip后）返回None
    t.assert_true(service.match_business('   ') is None, '纯空白字符串返回None')

    # 大小写不敏感
    t.assert_equal(service.match_business('医美整形'.upper()), '医美整形', '大写匹配')


# ==================== 3. 评分计算测试 ====================

def test_score_calculation(t):
    """评分计算测试"""
    print('\n【3. 评分计算测试】')
    print('-' * 40)

    from services.decision_cost_service import decision_cost_service

    for business in ['医美整形', '高考志愿', '装修', '金融投资', '留学中介', '婚恋相亲', '房产买卖', '儿童教育']:
        result = decision_cost_service.diagnose(business)

        # 验证平均分计算正确
        scores = list(result['scores'].values())
        expected_avg = round(sum(scores) / len(scores), 1)
        t.assert_equal(result['avg_score'], expected_avg, f'{business} 平均分计算正确')

        # 验证评分范围
        t.assert_range(result['avg_score'], 1, 10, f'{business} 综合评分在1-10范围')

        # 验证维度数量
        t.assert_equal(len(result['dimensions']), 7, f'{business} 有7个维度')

        # 验证内容价值分类
        if result['avg_score'] >= 8:
            t.assert_in(result['content_value'], ['极高价值', '高价值'], f'{business} 高分业务价值分类正确')

        print(f'   {result["content_emoji"]} {business}: {result["avg_score"]}/10 ({result["content_value"]})')


# ==================== 4. 用户调整测试 ====================

def test_user_adjustments(t):
    """用户调整测试"""
    print('\n【4. 用户调整测试】')
    print('-' * 40)

    from services.decision_cost_service import decision_cost_service

    # 正常调整
    adjustments = {'金钱成本': 10, '风险成本': 10}
    result = decision_cost_service.diagnose('装修', adjustments)
    t.assert_equal(result['scores']['金钱成本'], 10, '金钱成本调整为10')
    t.assert_equal(result['scores']['风险成本'], 10, '风险成本调整为10')

    # 超范围调整应该被忽略
    original_scores = result['scores'].copy()
    bad_adjustments = {'金钱成本': 15}
    result2 = decision_cost_service.diagnose('装修', bad_adjustments)
    t.assert_true(result2['scores']['金钱成本'] != 15, '超范围调整被忽略')

    # 空调整
    result3 = decision_cost_service.diagnose('医美整形', {})
    t.assert_true(result3['success'], '空调整不报错')


# ==================== 5. 内容方向测试 ====================

def test_content_directions(t):
    """内容方向测试"""
    print('\n【5. 内容方向测试】')
    print('-' * 40)

    from services.decision_cost_service import decision_cost_service

    result = decision_cost_service.diagnose('医美整形')

    for direction in result['content_directions']:
        t.assert_true(len(direction['title_templates']) >= 3, f'{direction["type"]} 至少3个标题模板')
        t.assert_true(len(direction['keywords']) >= 3, f'{direction["type"]} 至少3个关键词')
        t.assert_true('XX' in direction['title_templates'][0], f'{direction["type"]} 标题模板有占位符')

        print(f'   {direction["icon"]} {direction["type"]}: {len(direction["title_templates"])}个模板, {len(direction["keywords"])}个关键词')


# ==================== 6. LLM集成测试 ====================

def test_llm_integration(t):
    """LLM集成测试"""
    print('\n【6. LLM集成测试】')
    print('-' * 40)

    # 测试LLM服务可用性
    try:
        from services.llm import llm_service
        if llm_service is not None:
            t.assert_true(True, 'LLM服务可用')
            print('   ✅ LLM服务已配置')
        else:
            print('   ⚠️ LLM服务未配置')
    except (ImportError, Exception) as e:
        print(f'   ⚠️ LLM服务未配置: {e}')

    # 测试提示词生成
    from services.decision_cost_service import decision_cost_service
    from routes.decision_cost_api import _build_content_prompt

    diagnosis = decision_cost_service.diagnose('医美整形')
    direction = diagnosis['content_directions'][0]

    prompt = _build_content_prompt(diagnosis, direction)
    t.assert_in('医美整形', prompt, '提示词包含业务类型')
    t.assert_in(direction['type'], prompt, '提示词包含内容方向')
    t.assert_in('标题', prompt, '提示词包含标题要求')
    t.assert_in('脚本', prompt, '提示词包含脚本要求')
    print('   ✅ 提示词生成正确')


# ==================== 7. 搜索增强测试 ====================

def test_search_enhancement(t):
    """搜索增强测试"""
    print('\n【7. 搜索增强测试】')
    print('-' * 40)

    from services.decision_cost_service import DIMENSIONS_CONFIG

    # 需要搜索增强的维度
    search_dimensions = [
        dim for dim, config in DIMENSIONS_CONFIG.items()
        if config.get('search_needed')
    ]
    t.assert_in('金钱成本', search_dimensions, '金钱成本需要搜索增强')
    t.assert_in('时间成本', search_dimensions, '时间成本需要搜索增强')

    # 不需要搜索增强的维度
    no_search = [
        dim for dim, config in DIMENSIONS_CONFIG.items()
        if not config.get('search_needed')
    ]
    t.assert_in('心理成本', no_search, '心理成本不需要搜索增强')

    print(f'   需要搜索增强: {", ".join(search_dimensions)}')
    print(f'   不需要搜索增强: {", ".join(no_search)}')


# ==================== 8. 蓝海对接测试 ====================

def test_blue_ocean_integration(t):
    """蓝海对接测试"""
    print('\n【8. 蓝海对接测试】')
    print('-' * 40)

    from services.decision_cost_service import decision_cost_service

    # 测试数据转换
    dc_result = decision_cost_service.diagnose('医美整形')

    blue_ocean_input = {
        'business_type': dc_result['business_type'],
        'content_value': dc_result['content_value'],
        'avg_score': dc_result['avg_score'],
        'content_directions': [
            {'type': d['type'], 'weight': d['weight']}
            for d in dc_result['content_directions']
        ],
        'core_anxieties': dc_result['core_anxieties'],
        'target_users': dc_result['target_users'],
        'risk_level': dc_result['risk_level'],
    }

    t.assert_equal(blue_ocean_input['business_type'], '医美整形', '业务类型转换正确')
    t.assert_equal(blue_ocean_input['avg_score'], dc_result['avg_score'], '评分转换正确')
    t.assert_true(len(blue_ocean_input['content_directions']) > 0, '内容方向转换正确')
    t.assert_true(len(blue_ocean_input['core_anxieties']) > 0, '核心焦虑转换正确')
    t.assert_true(len(blue_ocean_input['target_users']) > 0, '目标用户转换正确')

    # 测试JSON序列化
    json_str = json.dumps(blue_ocean_input, ensure_ascii=False)
    parsed = json.loads(json_str)
    t.assert_equal(parsed['business_type'], '医美整形', 'JSON序列化/反序列化正确')

    print('   ✅ 数据格式转换成功')
    print(f'   业务类型: {blue_ocean_input["business_type"]}')
    print(f'   内容价值: {blue_ocean_input["content_value"]}')
    print(f'   综合评分: {blue_ocean_input["avg_score"]}')
    print(f'   推荐方向: {len(blue_ocean_input["content_directions"])}个')


# ==================== 9. 性能测试 ====================

def test_performance(t):
    """性能测试"""
    print('\n【9. 性能测试】')
    print('-' * 40)

    from services.decision_cost_service import decision_cost_service

    # 100次诊断性能
    start = time.time()
    for _ in range(100):
        decision_cost_service.diagnose('医美整形')
    elapsed = time.time() - start

    t.assert_true(elapsed < 1, f'100次诊断在1秒内完成: {elapsed:.3f}秒')
    print(f'   ✅ 100次诊断耗时: {elapsed*1000:.1f}ms (平均 {elapsed*10:.2f}ms/次)')

    # 并发测试
    from concurrent.futures import ThreadPoolExecutor
    businesses = ['医美整形', '装修', '高考志愿', '留学中介', '金融投资']

    def diagnose(business):
        return decision_cost_service.diagnose(business)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(diagnose, businesses))

    t.assert_equal(len(results), 5, '并发诊断完成5个业务')
    t.assert_true(all(r['success'] for r in results), '所有并发诊断成功')
    print(f'   ✅ 5线程并发诊断成功')


# ==================== 运行所有测试 ====================

def run_all_tests():
    """运行所有测试"""
    print('=' * 60)
    print('决策成本诊断系统 - 测试报告')
    print('=' * 60)

    t = TestRunner()

    test_knowledge_graph(t)
    test_business_matching(t)
    test_score_calculation(t)
    test_user_adjustments(t)
    test_content_directions(t)
    test_llm_integration(t)
    test_search_enhancement(t)
    test_blue_ocean_integration(t)
    test_performance(t)

    t.print_summary()

    return t.failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
