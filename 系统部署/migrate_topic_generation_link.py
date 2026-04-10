# -*- coding: utf-8 -*-
"""
数据库迁移脚本：选题→内容 1:N 关系改造

运行方式：python migrate_topic_generation_link.py

迁移内容：
1. 创建 topic_generation_links 表
2. public_generations 表新增字段：link_id, version_number, parent_version_id, geo_mode_used, content_style, content_data
3. 回填现有 generation 记录到 links 表
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from app import create_app
from models.models import db
from models.public_models import PublicGeneration, TopicGenerationLink, SavedPortrait

app = create_app()


def migrate():
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()

        try:
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            existing_columns = {col['name'] for col in inspector.get_columns('public_generations')}

            print(f"[1/4] 检查现有表和字段...")

            # ── 1. 创建 topic_generation_links 表 ──
            if 'topic_generation_links' not in existing_tables:
                print("  → 创建 topic_generation_links 表")
                conn.execute(db.text("""
                    CREATE TABLE topic_generation_links (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        portrait_id INTEGER,
                        problem_id INTEGER,
                        topic_id VARCHAR(36) NOT NULL,
                        topic_title VARCHAR(255),
                        geo_mode VARCHAR(20),
                        geo_mode_name VARCHAR(50),
                        usage_count INTEGER DEFAULT 0,
                        generation_ids JSON,
                        first_generated_at DATETIME,
                        last_generated_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES public_users(id)
                    )
                """))
                conn.execute(db.text("""
                    CREATE UNIQUE INDEX uq_user_portrait_topic
                    ON topic_generation_links(user_id, portrait_id, topic_id)
                """))
                conn.execute(db.text("""
                    CREATE INDEX idx_link_user_portrait_topic
                    ON topic_generation_links(user_id, portrait_id, topic_id)
                """))
                print("  ✓ topic_generation_links 表创建完成")
            else:
                print("  ✓ topic_generation_links 表已存在，跳过")

            # ── 2. public_generations 新增字段 ──
            new_columns = {
                'link_id': 'INTEGER REFERENCES topic_generation_links(id)',
                'version_number': 'INTEGER DEFAULT 1',
                'parent_version_id': 'INTEGER',
                'geo_mode_used': 'VARCHAR(50)',
                'content_style': 'VARCHAR(50)',
                'content_data': 'JSON',
            }

            for col_name, col_def in new_columns.items():
                if col_name not in existing_columns:
                    print(f"  → 添加字段 {col_name}")
                    conn.execute(db.text(f"ALTER TABLE public_generations ADD COLUMN {col_name} {col_def}"))
                    print(f"  ✓ {col_name} 添加完成")
                else:
                    print(f"  ✓ {col_name} 已存在，跳过")

            # ── 3. 添加索引 ──
            existing_indexes = {idx['name'] for idx in inspector.get_indexes('public_generations')}
            if 'idx_generation_link' not in existing_indexes:
                conn.execute(db.text("""
                    CREATE INDEX idx_generation_link
                    ON public_generations(user_id, link_id)
                """))
                print("  ✓ idx_generation_link 索引创建完成")

            # ── 4. 回填现有数据 ──
            print("\n[2/4] 回填现有 generation 记录到 links 表...")

            # 查找所有有 topic_id 的 generation 记录
            gens = PublicGeneration.query.filter(
                PublicGeneration.topic_id.isnot(None),
                PublicGeneration.topic_id != ''
            ).all()
            print(f"  → 找到 {len(gens)} 条有效 generation 记录")

            link_map = {}  # (user_id, portrait_id, topic_id) -> link

            for gen in gens:
                key = (gen.user_id, gen.portrait_id, gen.topic_id)
                if key not in link_map:
                    # 查找或创建 link
                    link = TopicGenerationLink.query.filter_by(
                        user_id=gen.user_id,
                        portrait_id=gen.portrait_id,
                        topic_id=gen.topic_id
                    ).first()

                    if not link:
                        # 从选题库中获取标题快照
                        topic_title = gen.topic_id
                        if gen.portrait_id:
                            portrait = SavedPortrait.query.get(gen.portrait_id)
                            if portrait and portrait.topic_library:
                                for t in portrait.topic_library.get('topics', []):
                                    if t.get('id') == gen.topic_id:
                                        topic_title = t.get('title', gen.topic_id)
                                        break

                        link = TopicGenerationLink(
                            user_id=gen.user_id,
                            portrait_id=gen.portrait_id,
                            problem_id=gen.problem_id,
                            topic_id=gen.topic_id,
                            topic_title=topic_title,
                            usage_count=0,
                            generation_ids=[],
                            first_generated_at=None,
                            last_generated_at=None,
                            created_at=datetime.utcnow(),
                        )
                        db.session.add(link)
                        db.session.flush()
                        print(f"    新建 link: user={gen.user_id}, portrait={gen.portrait_id}, topic={gen.topic_id[:8]}...")

                    link_map[key] = link

                # 更新 link
                link.add_generation(gen.id)
                link.last_generated_at = max(
                    link.last_generated_at or datetime.min,
                    gen.created_at or datetime.min
                )
                if link.first_generated_at is None:
                    link.first_generated_at = gen.created_at

                # 更新 generation
                gen.link_id = link.id
                gen.version_number = link.usage_count

            db.session.commit()
            print(f"  ✓ 回填完成，共处理 {len(link_map)} 个选题链接")

            # ── 5. content → content_data 迁移 ──
            print("\n[3/4] 迁移 content 字段到 content_data...")

            gens_text = PublicGeneration.query.filter(
                PublicGeneration.content.isnot(None),
                PublicGeneration.content != '',
                PublicGeneration.content_data.is_(None)
            ).all()
            print(f"  → 找到 {len(gens_text)} 条需要迁移的记录")

            for gen in gens_text:
                if isinstance(gen.content, str) and gen.content.strip():
                    # 简单的文本内容，包装成 body 字段
                    gen.content_data = {'body': gen.content}
                else:
                    gen.content_data = {'body': ''}

            db.session.commit()
            print("  ✓ content 字段迁移完成")

            # ── 6. 验证 ──
            print("\n[4/4] 数据验证...")
            total_gens = PublicGeneration.query.count()
            linked_gens = PublicGeneration.query.filter(PublicGeneration.link_id.isnot(None)).count()
            total_links = TopicGenerationLink.query.count()

            print(f"  → 总 generation 记录: {total_gens}")
            print(f"  → 已关联 link 的记录: {linked_gens} ({linked_gens/total_gens*100:.1f}%)")
            print(f"  → 总 link 记录: {total_links}")

            trans.commit()
            print("\n✅ 迁移完成！")

        except Exception as e:
            trans.rollback()
            print(f"\n❌ 迁移失败: {e}")
            raise


if __name__ == '__main__':
    migrate()
