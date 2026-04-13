"""
修复已有 generation 记录的 titles 和 tags 字段（长文结构 content_data.article 中的数据未回填）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models.public_models import PublicGeneration

with app.app_context():
    # 查找所有 titles 为空列表或包含空字符串的记录
    fixed_count = 0
    total = 0

    gens = PublicGeneration.query.filter(
        db.or_(
            PublicGeneration.titles == [],  # type: ignore
            db.and_(
                db.func.json_array_length(PublicGeneration.titles) == 1,  # type: ignore
                # titles[0] == '' 这种用 SQL 不好表达，改用 Python 过滤
            )
        )
    ).all()

    # 也包括那些 titles 第一项为空字符串的
    all_gens = PublicGeneration.query.all()

    for gen in all_gens:
        total += 1
        if not gen.content_data:
            continue

        # 检查是否需要修复：titles 为空或第一项为空字符串
        needs_fix = False
        if not gen.titles or (isinstance(gen.titles, list) and (len(gen.titles) == 0 or gen.titles[0] == '')):
            needs_fix = True

        if not needs_fix:
            continue

        content_data = gen.content_data or {}

        # 长文结构：title 在 article.title，tags 在 article.hashtags
        title = ''
        tags = []

        if isinstance(content_data, dict):
            title = content_data.get('title', '') or ''
            tags = content_data.get('tags', []) or []

            # 长文结构
            article = content_data.get('article') or {}
            if not title:
                title = article.get('title', '') or ''
            if not tags:
                tags = article.get('hashtags', []) or []

        if title:
            gen.titles = [title]
            gen.tags = tags
            db.session.commit()
            fixed_count += 1
            print(f"[修复] gen_id={gen.id}, content_type={gen.content_type}, titles=[{title[:30]}...]")
        else:
            print(f"[跳过] gen_id={gen.id}, content_type={gen.content_type}, 无有效标题")

    print(f"\n修复完成: 共 {fixed_count}/{total} 条记录已修复")
