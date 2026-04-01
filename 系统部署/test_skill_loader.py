"""
测试 SkillLoader - 按需加载测试
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.skill_loader import SkillLoader, get_skill_loader


def test_skill_loader():
    """测试 SkillLoader"""

    print("=" * 60)
    print("测试 SkillLoader - 按需加载")
    print("=" * 60)

    # 创建 SkillLoader
    loader = SkillLoader()

    print(f"\n📁 Skills 目录: {loader.skills_dir}")

    # 测试 1: 获取所有 Skills
    print("\n" + "=" * 60)
    print("测试 1: 获取所有可用专家")
    print("=" * 60)

    skills = loader.get_all_skills()
    for skill in skills:
        print(f"\n📌 {skill['name']} ({skill['title']})")
        print(f"   命令: {skill['command']}")
        print(f"   类型: {skill['type']}")
        print(f"   描述: {skill['description']}")

    # 测试 2: 解析命令
    print("\n" + "=" * 60)
    print("测试 2: 解析命令")
    print("=" * 60)

    test_messages = [
        "/seo",
        "/运营",
        "/市场",
        "/舆情",
        "/内容",
        "/心理",
        "帮我做SEO优化",
        "我是卖奶粉的"
    ]

    for msg in test_messages:
        skill_name = loader.parse_command(msg)
        skill_info = loader.get_skill_info(skill_name) if skill_name else None
        result = f"'{msg}' → {skill_info['name'] if skill_info else '无匹配'}"
        print(f"  {result}")

    # 测试 3: 按需加载 Skill
    print("\n" + "=" * 60)
    print("测试 3: 按需加载 Skill")
    print("=" * 60)

    test_skills = ['geo-master', 'geo-seo', 'operations-expert']

    for skill_name in test_skills:
        print(f"\n📥 加载 Skill: {skill_name}")

        # 第一次加载（从文件）
        content1 = loader.load_skill(skill_name)
        if content1:
            print(f"   ✓ 首次加载: {len(content1)} 字符")
        else:
            print(f"   ✗ 加载失败")
            continue

        # 第二次加载（从缓存）
        content2 = loader.load_skill(skill_name)
        print(f"   ✓ 缓存加载: {len(content2)} 字符")

        # 获取 Skill 信息
        info = loader.get_skill_info(skill_name)
        print(f"   ℹ 信息: {info['title']} - {info['description']}")

    # 测试 4: 构建 System Prompt
    print("\n" + "=" * 60)
    print("测试 4: 构建 System Prompt")
    print("=" * 60)

    client_info = {
        'client_name': '龙眼山天然涌泉',
        'industry': '食品饮料',
        'business_description': '桶装水批发配送',
        'business_type': '卖货类',
        'geographic_scope': '本地',
        'brand_type': '公司品牌',
        'core_advantage': '30年水源地直供'
    }

    prompt = loader.build_system_prompt('geo-seo', client_info)
    print(f"\n📝 System Prompt (前500字符):\n")
    print(prompt[:500])
    print("...")

    # 测试 5: 缓存管理
    print("\n" + "=" * 60)
    print("测试 5: 缓存管理")
    print("=" * 60)

    print(f"\n缓存键: {list(loader._skill_cache.keys())}")
    loader.clear_cache()
    print("✓ 缓存已清空")
    print(f"缓存键: {list(loader._skill_cache.keys())}")

    # 测试单例
    print("\n" + "=" * 60)
    print("测试 6: 单例模式")
    print("=" * 60)

    loader1 = get_skill_loader()
    loader2 = get_skill_loader()
    print(f"  单例测试: {loader1 is loader2}")

    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)


if __name__ == '__main__':
    test_skill_loader()
