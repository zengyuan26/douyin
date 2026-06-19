#!/usr/bin/env python3
"""生成优化版小红书图文笔记HTML页面"""
from pathlib import Path

OUTPUT_DIR = Path("/Volumes/增元/项目/douyin/.cursor/skill/content-creator/输出/脚本/南漳香肠/图文_S5_下班懒得做饭蒸香肠10分钟搞定/imgs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

C = {
    'primary': '#8D6E63',
    'accent': '#FF9800',
    'trust': '#4CAF50',
    'warm_orange': '#FF6B35',
    'soft_brown': '#D4A574',
    'text_dark': '#333333',
    'cream': '#FFF9F5',
}

def base_css():
    return f"""* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans CJK SC",sans-serif; background:#2D2B55; display:flex; justify-content:center; align-items:center; min-height:100vh; }}
.page {{ width:1080px; height:1920px; background:{C['cream']}; overflow:hidden; position:relative; flex-shrink:0; }}"""

# ===== 封面 =====
def gen_cover():
    css = base_css() + f"""
.page {{ background:linear-gradient(160deg,#FFF8F0 0%,#FFEDE0 40%,#FFE4CC 100%); }}
.scene-bg {{ position:absolute;inset:0; background:radial-gradient(ellipse at 30% 85%,rgba(139,109,83,0.1) 0%,transparent 55%), radial-gradient(ellipse at 75% 25%,rgba(255,152,0,0.07) 0%,transparent 45%); }}
.header-bar {{ position:absolute;top:0;left:0;right:0;height:5px; background:linear-gradient(90deg,{C['primary']},{C['warm_orange']}); }}
.brand {{ position:absolute;top:36px;left:50px; display:flex;align-items:center;gap:10px; background:rgba(139,109,83,0.1);padding:8px 20px;border-radius:22px; }}
.brand-dot {{ width:9px;height:9px;border-radius:50%;background:{C['primary']}; }}
.content {{ position:absolute;top:220px;left:0;right:0;text-align:center;padding:0 60px; }}
.hook {{ display:inline-block; background:linear-gradient(135deg,{C['accent']},{C['warm_orange']}); color:white; font-size:22px;font-weight:700; padding:10px 36px;border-radius:30px;margin-bottom:28px;letter-spacing:4px; }}
.title {{ font-size:70px;font-weight:800;color:{C['text_dark']};line-height:1.2;margin-bottom:16px;letter-spacing:2px; }}
.title em {{ font-style:normal;color:{C['primary']}; }}
.sub {{ font-size:30px;color:{C['text_dark']};margin-bottom:12px;font-weight:400; }}
.divider {{ width:120px;height:3px;background:linear-gradient(90deg,transparent,{C['primary']},transparent);margin:28px auto; }}
.time {{ display:flex;align-items:center;justify-content:center;gap:12px;margin:36px 0; }}
.num {{ font-size:96px;font-weight:900;color:{C['accent']};line-height:1; text-shadow:3px 5px 0 rgba(255,152,0,0.12); }}
.unit {{ font-size:34px;font-weight:700;color:{C['accent']};align-self:flex-end;padding-bottom:14px; }}
.desc {{ font-size:26px;color:{C['text_dark']};font-weight:500; }}
.sausage {{ position:absolute;bottom:400px;left:50%;transform:translateX(-50%); width:320px;height:70px;border-radius:50px; background:linear-gradient(145deg,{C['warm_orange']},{C['primary']}); box-shadow:0 18px 50px rgba(139,109,83,0.28); }}
.sausage::after {{ content:"";position:absolute;inset:0;border-radius:50px;background:repeating-linear-gradient(90deg,transparent,transparent 28px,rgba(255,255,255,0.06) 28px,rgba(255,255,255,0.06) 34px); }}
.steam {{ position:absolute;bottom:490px;left:50%;transform:translateX(-50%);display:flex;gap:50px; }}
.steam span {{ width:4px;height:55px;background:linear-gradient(to top,rgba(139,109,83,0.22),transparent);border-radius:4px; animation:rise 2.5s ease-in-out infinite; }}
.steam span:nth-child(2) {{ animation-delay:0.6s;height:45px; }}
.steam span:nth-child(3) {{ animation-delay:1.2s;height:50px; }}
@keyframes rise {{ 0%,100%{{transform:translateY(0) scaleX(1);opacity:0.4}} 50%{{transform:translateY(-15px) scaleX(1.4);opacity:0.1}} }}
.bottom {{ position:absolute;bottom:70px;left:50px;right:50px;background:rgba(255,255,255,0.93);border-radius:20px;padding:24px 32px; box-shadow:0 4px 20px rgba(139,109,83,0.1);border:1px solid rgba(139,109,83,0.07); }}
.cta {{ display:flex;align-items:center;justify-content:space-between; }}
.cta-l {{ display:flex;align-items:center;gap:12px;font-size:23px;color:{C['text_dark']}; }}
.cta-icon {{ width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,{C['accent']},{C['warm_orange']});display:flex;align-items:center;justify-content:center;color:white;font-size:16px;font-weight:700;flex-shrink:0; }}
.tag {{ background:linear-gradient(135deg,{C['primary']},{C['soft_brown']});color:white;font-size:22px;font-weight:600;padding:9px 26px;border-radius:25px; }}
.corner {{ position:absolute;width:80px;height:80px;opacity:0.1; }}
.corner.tl {{ top:16px;left:16px;border-top:3px solid {C['primary']};border-left:3px solid {C['primary']}; }}
.corner.tr {{ top:16px;right:16px;border-top:3px solid {C['primary']};border-right:3px solid {C['primary']}; }}
.corner.bl {{ bottom:16px;left:16px;border-bottom:3px solid {C['primary']};border-left:3px solid {C['primary']}; }}
.corner.br {{ bottom:16px;right:16px;border-bottom:3px solid {C['primary']};border-right:3px solid {C['primary']}; }}"""
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>封面</title><style>{css}</style></head><body>
<div class="page">
  <div class="scene-bg"></div>
  <div class="header-bar"></div>
  <div class="corner tl"></div><div class="corner tr"></div><div class="corner bl"></div><div class="corner br"></div>
  <div class="brand"><div class="brand-dot"></div><span style="font-size:20px;color:#8D6E63;font-weight:600;">南漳黄姐灌香肠</span></div>
  <div class="content">
    <div class="hook">10分钟快手家常菜</div>
    <h1 class="title">下班懒得做饭？</h1>
    <p class="sub">蒸一截香肠</p>
    <div class="divider"></div>
    <div class="time"><span class="num">10</span><span class="unit">分钟</span></div>
    <p class="desc">比外卖快，比外卖香，比外卖省钱</p>
  </div>
  <div class="steam"><span></span><span></span><span></span></div>
  <div class="sausage"></div>
  <div class="bottom">
    <div class="cta">
      <div class="cta-l"><div class="cta-icon">藏</div><span>收藏起来，下班不知道吃什么时用得上</span></div>
      <div class="tag">懒人必备</div>
    </div>
  </div>
</div></body></html>"""
    (OUTPUT_DIR / "slide01_cover.html").write_text(html, encoding='utf-8')
    print("slide01_cover.html")

# ===== 痛点 =====
def gen_pain():
    css = base_css() + f"""
.page {{ background:linear-gradient(170deg,#FFF8F0 0%,#F5EDE5 60%,#EDE4DA 100%); }}
.header {{ padding:50px 60px 0; }}
.tag {{ display:inline-block;font-size:20px;font-weight:600;padding:8px 22px;border-radius:20px;margin-right:12px;margin-bottom:8px; }}
.tq {{ background:rgba(139,109,83,0.1);color:{C['primary']}; }}
.ts {{ background:rgba(255,152,0,0.1);color:{C['accent']}; }}
.h1 {{ font-size:56px;font-weight:800;color:{C['text_dark']};line-height:1.25;margin-bottom:10px; }}
.sub {{ font-size:30px;color:#888;margin-bottom:34px; }}
.div {{ width:80px;height:4px;background:linear-gradient(90deg,{C['primary']},{C['accent']});border-radius:2px;margin-bottom:34px; }}
.scene {{ background:rgba(139,109,83,0.08);border-radius:20px;padding:26px 34px;margin:0 50px 28px;text-align:center; }}
.scene p {{ font-size:30px;color:{C['text_dark']};line-height:1.6; }}
.hl {{ color:{C['accent']};font-weight:700; }}
.pain {{ padding:0 50px; }}
.item {{ display:flex;align-items:center;gap:18px;margin-bottom:20px;background:white;border-radius:16px;padding:22px 26px;box-shadow:0 2px 12px rgba(139,109,83,0.06);border-left:5px solid #E8DDD5; }}
.item:nth-child(1) {{ border-left-color:#E57373; }}
.item:nth-child(2) {{ border-left-color:#FFB74D; }}
.item:nth-child(3) {{ border-left-color:#FF8A65; }}
.item:nth-child(4) {{ border-left-color:#A1887F; }}
.item:nth-child(5) {{ border-left-color:#90A4AE; }}
.icon {{ width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;flex-shrink:0; }}
.t {{ font-size:27px;color:{C['text_dark']};font-weight:500;line-height:1.4; }}
.sol {{ margin:28px 50px 0;background:linear-gradient(135deg,{C['primary']},{C['soft_brown']});border-radius:20px;padding:28px 34px;color:white; }}
.sol p {{ font-size:22px;opacity:0.85;margin-bottom:8px; }}
.sol h3 {{ font-size:28px;font-weight:700; }}
.note {{ position:absolute;bottom:58px;left:50px;right:50px;text-align:center;padding:20px;background:rgba(255,152,0,0.08);border-radius:16px;border:1px dashed {C['accent']}; }}
.note p {{ font-size:25px;color:{C['accent']};font-weight:600; }}"""
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>痛点</title><style>{css}</style></head><body>
<div class="page">
  <div class="header">
    <div>
      <span class="tag tq">打工人日常</span><span class="tag ts">下班后的纠结</span>
    </div>
    <h1 class="h1">下班后最大的难题来了</h1>
    <p class="sub">上了一天班，拖着疲惫的身体回家</p>
    <div class="div"></div>
  </div>
  <div class="scene">
    <p>上了一天班，拖着<strong class="hl">疲惫的身体</strong>回家</p>
    <p style="margin-top:10px;font-size:25px;color:#999;">每天都在纠结这几件事：</p>
  </div>
  <div class="pain">
    <div class="item"><div class="icon" style="background:#FFEBEE;color:#E57373;">?</div><p class="t">外卖吧，吃腻了还贵</p></div>
    <div class="item"><div class="icon" style="background:#FFF3E0;color:#FFB74D;">?</div><p class="t">自己做吧，不知道做什么</p></div>
    <div class="item"><div class="icon" style="background:#FBE9E7;color:#FF8A65;">?</div><p class="t">随便对付一口，又觉得委屈自己</p></div>
    <div class="item"><div class="icon" style="background:#EFEBE9;color:#A1887F;">?</div><p class="t">菜市场不想去，冰箱里也没存货</p></div>
    <div class="item"><div class="icon" style="background:#ECEFF1;color:#90A4AE;">?</div><p class="t">想吃点好的，但实在没精力折腾</p></div>
  </div>
  <div class="sol">
    <p>其实不用那么复杂</p>
    <h3>冰箱里有截香肠就够了</h3>
  </div>
  <div class="note"><p>香肠不是大菜才吃，日常一餐也合适</p></div>
</div></body></html>"""
    (OUTPUT_DIR / "slide02_pain.html").write_text(html, encoding='utf-8')
    print("slide02_pain.html")

# ===== 做法 =====
def gen_method():
    css = base_css() + f"""
.page {{ background:linear-gradient(170deg,#FFFBF5 0%,#FFF5EC 50%,#FFEDE0 100%); }}
.header {{ padding:50px 60px 0; }}
.bar {{ display:flex;align-items:center;gap:16px;margin-bottom:8px; }}
.icon {{ width:54px;height:54px;border-radius:15px;background:linear-gradient(135deg,{C['accent']},{C['warm_orange']});display:flex;align-items:center;justify-content:center; }}
.inner {{ width:34px;height:34px;background:white;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:15px;color:{C['accent']};font-weight:700; }}
.h1 {{ font-size:50px;font-weight:800;color:{C['text_dark']}; }}
.sub {{ font-size:27px;color:#888;margin-bottom:28px; }}
.steps {{ padding:0 50px;display:flex;flex-direction:column;gap:16px; }}
.card {{ background:white;border-radius:20px;padding:26px 30px;box-shadow:0 3px 14px rgba(139,109,83,0.08);position:relative;overflow:hidden; }}
.card::before {{ content:"";position:absolute;left:0;top:0;bottom:0;width:5px;border-radius:3px 0 0 3px; }}
.card:nth-child(1)::before {{ background:linear-gradient(180deg,{C['accent']},{C['warm_orange']}); }}
.card:nth-child(2)::before {{ background:linear-gradient(180deg,{C['primary']},{C['soft_brown']}); }}
.card:nth-child(3)::before {{ background:linear-gradient(180deg,{C['trust']},#81C784); }}
.num {{ display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:12px;font-size:22px;font-weight:800;color:white;margin-bottom:10px; }}
.card:nth-child(1) .num {{ background:linear-gradient(135deg,{C['accent']},{C['warm_orange']}); }}
.card:nth-child(2) .num {{ background:linear-gradient(135deg,{C['primary']},{C['soft_brown']}); }}
.card:nth-child(3) .num {{ background:linear-gradient(135deg,{C['trust']},#81C784); }}
.title {{ font-size:29px;font-weight:700;color:{C['text_dark']};margin-bottom:10px; }}
.detail {{ font-size:23px;color:#777;line-height:1.7; }}
.detail strong {{ color:{C['accent']};font-weight:700; }}
.detail .g {{ color:{C['trust']};font-weight:700; }}
.compare {{ margin:18px 50px;background:linear-gradient(135deg,rgba(255,152,0,0.08),rgba(139,109,83,0.08));border-radius:20px;padding:22px 28px;border:1px solid rgba(255,152,0,0.2); }}
.ctitle {{ font-size:21px;color:{C['accent']};font-weight:700;margin-bottom:14px;text-align:center; }}
.grid {{ display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center; }}
.item {{ text-align:center;padding:12px;border-radius:14px;font-size:20px;font-weight:700; }}
.slow {{ background:rgba(229,115,115,0.1);color:#E57373; }}
.fast {{ background:rgba(76,175,80,0.1);color:{C['trust']}; }}
.vs {{ font-size:22px;color:#bbb;font-weight:800; }}
.bottom {{ position:absolute;bottom:58px;left:50px;right:50px;background:linear-gradient(135deg,{C['accent']},{C['warm_orange']});border-radius:20px;padding:22px 34px;text-align:center; }}
.bottom p {{ font-size:29px;color:white;font-weight:800; }}
.bottom .s {{ font-size:21px;font-weight:400;opacity:0.9;margin-top:4px; }}"""
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>做法</title><style>{css}</style></head><body>
<div class="page">
  <div class="header">
    <div class="bar"><div class="icon"><div class="inner">10'</div></div><h1 class="h1">香肠蒸着吃</h1></div>
    <p class="sub">方法超级简单，3步出锅</p>
  </div>
  <div class="steps">
    <div class="card">
      <div class="num">1</div>
      <p class="title">香肠洗净切片</p>
      <p class="detail">不用多，<strong>两三片够吃</strong><br>嫌麻烦整根蒸也行<br>冷冻的提前放冷藏解冻</p>
    </div>
    <div class="card">
      <div class="num">2</div>
      <p class="title">放蒸锅里</p>
      <p class="detail">冷水上锅，水开蒸 <strong>15分钟</strong><br>热水上锅，蒸 <strong>10分钟</strong><br>懒人的话：微波炉<strong class="g">高火3分钟</strong>也行</p>
    </div>
    <div class="card">
      <div class="num">3</div>
      <p class="title">出锅开吃</p>
      <p class="detail">配一碗白米饭<br>或者下碗面条<br>一个人吃得很满足</p>
    </div>
  </div>
  <div class="compare">
    <p class="ctitle">时间对比</p>
    <div class="grid">
      <div class="item slow">蒸香肠<br><span style="font-size:26px;">10分钟</span></div>
      <div class="vs">VS</div>
      <div class="item fast">等外卖<br><span style="font-size:26px;">30分钟+</span></div>
    </div>
  </div>
  <div class="bottom">
    <p>10分钟，比等外卖还快</p>
    <p class="s">配碗白米饭，吃得又香又满足</p>
  </div>
</div></body></html>"""
    (OUTPUT_DIR / "slide03_method.html").write_text(html, encoding='utf-8')
    print("slide03_method.html")

# ===== 搭配 =====
def gen_combo():
    css = base_css() + f"""
.page {{ background:linear-gradient(160deg,#FFFBF7 0%,#FFF8F0 50%,#FFF3E8 100%); }}
.header {{ padding:50px 60px 0; }}
.tag {{ display:inline-block;font-size:20px;font-weight:600;padding:8px 22px;border-radius:20px;margin-right:12px;margin-bottom:8px; }}
.tg {{ background:rgba(76,175,80,0.1);color:{C['trust']}; }}
.to {{ background:rgba(255,152,0,0.1);color:{C['accent']}; }}
.h1 {{ font-size:48px;font-weight:800;color:{C['text_dark']};line-height:1.3;margin-bottom:10px; }}
.sub {{ font-size:27px;color:#888;margin-bottom:28px; }}
.div {{ width:80px;height:4px;background:linear-gradient(90deg,{C['trust']},{C['accent']});border-radius:2px;margin-bottom:22px; }}
.list {{ padding:0 50px;display:flex;flex-direction:column;gap:14px; }}
.card {{ background:white;border-radius:20px;padding:24px 28px;box-shadow:0 3px 14px rgba(139,109,83,0.07);display:flex;align-items:center;gap:22px; }}
.ci {{ width:70px;height:70px;border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:700;flex-shrink:0; }}
.c1 {{ background:linear-gradient(135deg,rgba(139,109,83,0.12),rgba(212,165,116,0.2));color:{C['primary']}; }}
.c2 {{ background:linear-gradient(135deg,rgba(255,152,0,0.12),rgba(255,107,53,0.2));color:{C['accent']}; }}
.c3 {{ background:linear-gradient(135deg,rgba(76,175,80,0.12),rgba(129,199,132,0.2));color:{C['trust']}; }}
.name {{ font-size:29px;font-weight:700;color:{C['text_dark']};margin-bottom:6px; }}
.desc {{ font-size:21px;color:#888;line-height:1.5; }}
.badge {{ font-size:17px;font-weight:600;padding:6px 15px;border-radius:12px;flex-shrink:0; }}
.c1 .badge {{ background:rgba(139,109,83,0.1);color:{C['primary']}; }}
.c2 .badge {{ background:rgba(255,152,0,0.1);color:{C['accent']}; }}
.c3 .badge {{ background:rgba(76,175,80,0.1);color:{C['trust']}; }}
.extra {{ margin:18px 50px;background:linear-gradient(135deg,rgba(76,175,80,0.08),rgba(139,109,83,0.06));border-radius:20px;padding:22px 28px;border:1px solid rgba(76,175,80,0.15); }}
.el {{ font-size:21px;color:{C['trust']};font-weight:700;margin-bottom:12px; }}
.items {{ display:flex;gap:12px;flex-wrap:wrap; }}
.item {{ background:white;border-radius:14px;padding:12px 20px;font-size:23px;color:{C['text_dark']};font-weight:500;box-shadow:0 2px 8px rgba(139,109,83,0.06); }}
.bottom {{ position:absolute;bottom:58px;left:50px;right:50px;text-align:center;padding:22px;background:linear-gradient(135deg,{C['primary']},{C['soft_brown']});border-radius:20px; }}
.bottom p {{ font-size:27px;color:white;font-weight:700; }}"""
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>搭配</title><style>{css}</style></head><body>
<div class="page">
  <div class="header">
    <div><span class="tag tg">快手搭配</span><span class="tag to">一学就会</span></div>
    <h1 class="h1">香肠配一配<br>一顿像样的晚餐就有了</h1>
    <p class="sub">三种经典搭配，总有一款适合你</p>
    <div class="div"></div>
  </div>
  <div class="list">
    <div class="card">
      <div class="ci c1">米饭</div>
      <div style="flex:1"><p class="name">香肠 + 白米饭</p><p class="desc">最经典的吃法，最简单的满足<br>上班族一人食首选</p></div>
      <div class="badge">最经典</div>
    </div>
    <div class="card">
      <div class="ci c2">面条</div>
      <div style="flex:1"><p class="name">香肠 + 面条</p><p class="desc">香肠切片铺在面上，或者香肠丁煮面<br>吃得饱又有滋味</p></div>
      <div class="badge">碳水爆炸</div>
    </div>
    <div class="card">
      <div class="ci c3">白粥</div>
      <div style="flex:1"><p class="name">香肠 + 白粥</p><p class="desc">早上晚上都适合，清淡解腻<br>香肠配粥比配饭还香</p></div>
      <div class="badge">清淡解腻</div>
    </div>
  </div>
  <div class="extra">
    <p class="el">再配一个：</p>
    <div class="items">
      <span class="item">蒜苗炒鸡蛋</span>
      <span class="item">烫个青菜</span>
      <span class="item">一饭有肉有菜</span>
    </div>
  </div>
  <div class="bottom"><p>不用大鱼大肉，日常一餐很满足</p></div>
</div></body></html>"""
    (OUTPUT_DIR / "slide04_combo.html").write_text(html, encoding='utf-8')
    print("slide04_combo.html")

# ===== 结尾 =====
def gen_ending():
    css = base_css() + f"""
.page {{ background:linear-gradient(170deg,#FFFBF5 0%,#FFF8F0 50%,#FFEDE0 100%); }}
.header {{ padding:55px 60px 0;text-align:center; }}
.icon {{ width:96px;height:96px;border-radius:26px;background:linear-gradient(135deg,{C['primary']},{C['soft_brown']});display:flex;align-items:center;justify-content:center;margin:0 auto 28px;box-shadow:0 8px 28px rgba(139,109,83,0.2);font-size:42px;color:white;font-weight:700; }}
.h1 {{ font-size:54px;font-weight:800;color:{C['text_dark']};line-height:1.3;margin-bottom:14px; }}
.sub {{ font-size:30px;color:#888;margin-bottom:14px; }}
.div {{ width:100px;height:4px;background:linear-gradient(90deg,transparent,{C['primary']},transparent);margin:0 auto 28px;border-radius:2px; }}
.points {{ display:flex;justify-content:center;gap:16px;flex-wrap:wrap;margin:0 50px 28px; }}
.point {{ background:white;border-radius:16px;padding:16px 26px;font-size:25px;font-weight:600;color:{C['text_dark']};box-shadow:0 3px 12px rgba(139,109,83,0.08); }}
.myth {{ margin:0 50px 28px;background:linear-gradient(135deg,rgba(139,109,83,0.08),rgba(255,152,0,0.06));border-radius:20px;padding:26px 32px; }}
.mtitle {{ font-size:23px;color:{C['primary']};font-weight:700;margin-bottom:14px; }}
.mitem {{ font-size:25px;color:{C['text_dark']};line-height:1.9;position:relative;padding-left:20px; }}
.mitem::before {{ content:"- ";position:absolute;left:0;color:{C['accent']};font-weight:700; }}
.ixt {{ margin:0 50px 28px;background:linear-gradient(135deg,{C['accent']},{C['warm_orange']});border-radius:20px;padding:28px 34px;text-align:center; }}
.il {{ font-size:21px;color:rgba(255,255,255,0.85);margin-bottom:10px; }}
.iq {{ font-size:30px;font-weight:700;color:white;margin-bottom:6px; }}
.iq2 {{ font-size:24px;color:rgba(255,255,255,0.9);margin-bottom:14px; }}
.ia {{ display:inline-block;background:white;color:{C['accent']};font-size:23px;font-weight:700;padding:13px 34px;border-radius:28px; }}
.col {{ margin:0 50px;text-align:center;padding:20px;background:rgba(76,175,80,0.08);border-radius:16px;border:1px dashed {C['trust']}; }}
.col p {{ font-size:23px;color:{C['trust']};font-weight:600; }}"""
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=1080,height=1920"><title>结尾</title><style>{css}</style></head><body>
<div class="page">
  <div class="header">
    <div class="icon">肠</div>
    <h1 class="h1">香肠不是大菜才吃</h1>
    <p class="sub">日常一餐也合适</p>
    <div class="div"></div>
  </div>
  <div class="points">
    <span class="point">10分钟出锅</span>
    <span class="point">比外卖快</span>
    <span class="point">比外卖香</span>
  </div>
  <div class="myth">
    <p class="mtitle">打破一个误区</p>
    <p class="mitem">以前总觉得香肠是冬天灌的</p>
    <p class="mitem">是过年才吃的大菜</p>
    <p class="mitem">其实备好在冰箱里</p>
    <p class="mitem">下班随时蒸一截，比什么都方便</p>
  </div>
  <div class="ixt">
    <p class="il">互动时间</p>
    <p class="iq">你们家香肠一般怎么吃？</p>
    <p class="iq2">有没有什么懒人神仙搭配？</p>
    <span class="ia">评论区分享一下</span>
  </div>
  <div class="col"><p>收藏起来，下班不知道吃什么时用得上</p></div>
</div></body></html>"""
    (OUTPUT_DIR / "slide05_ending.html").write_text(html, encoding='utf-8')
    print("slide05_ending.html")

def main():
    gen_cover()
    gen_pain()
    gen_method()
    gen_combo()
    gen_ending()
    print("All done!")

if __name__ == "__main__":
    main()
