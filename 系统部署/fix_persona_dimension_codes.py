"""
迁移：为 analysis_dimensions 表中超级定位·人群画像的维度修正 code，
使其与代码/API 中使用的标准 key（development_stage、region 等）一致。

运行：cd 系统部署 && python fix_persona_dimension_codes.py
"""
from models.models import db, AnalysisDimension
from app import app

# name → 标准 code 映射（与分析维度管理后台的逻辑保持一致）
CODE_MAP = {
    '发展阶段': 'development_stage',
    '营收规模': 'revenue_scale',
    '团队规模': 'team_size',
    '工作年限': 'work_years',
    '行业背景': 'industry_background',
    '地域':      'region',
    '年龄段':    'age_group',
    '职位角色':  'job_role',
    '痛点状态':  'pain_status',
    '目标诉求':  'goal',
}


def run():
    with app.app_context():
        dims = AnalysisDimension.query.filter_by(
            category='super_positioning',
            sub_category='persona',
        ).all()

        updated = 0
        for dim in dims:
            new_code = CODE_MAP.get(dim.name)
            if new_code and dim.code != new_code:
                # 检查目标 code 是否已被占用
                conflict = AnalysisDimension.query.filter_by(code=new_code).first()
                if conflict:
                    print(f'  ⚠️  id={dim.id} name={dim.name!r} 目标 code={new_code!r} 已被 id={conflict.id} ({conflict.name}) 占用，跳过')
                    continue
                print(f'  ✅ id={dim.id}  {dim.code!r:25s} → {new_code!r}  ({dim.name})')
                dim.code = new_code
                updated += 1
            else:
                print(f'  ⏭️  id={dim.id} code={dim.code!r} 无需修改')

        db.session.commit()
        print(f'\n完成，共更新 {updated} 条记录')


if __name__ == '__main__':
    run()
