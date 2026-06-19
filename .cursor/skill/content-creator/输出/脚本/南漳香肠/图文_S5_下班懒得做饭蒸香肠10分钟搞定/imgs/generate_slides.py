#!/usr/bin/env python3
"""
生成小红书图文笔记5张9:16 HTML页面
选题：下班懒得做饭？蒸一截香肠，10分钟搞定
品牌：南漳黄姐灌香肠
风格：warm（温暖亲和）+ fresh（清新自然）
"""

import os
from pathlib import Path

OUTPUT_DIR = Path("/Volumes/增元/项目/douyin/.cursor/skill/content-creator/输出/脚本/南漳香肠/图文_S5_下班懒得做饭蒸香肠10分钟搞定/imgs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {
    'primary': '#8D6E63',
    'secondary': '#FFFFFF',
    'accent': '#FF9800',
    'trust': '#4CAF50',
    'text_dark': '#333333',
    'text_light': '#FFFFFF',
    'warm_orange': '#FF6B35',
    'soft_brown': '#D4A574',
    'cream': '#FFF9F5',
}

def get_base_css():
    return f"""
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; background: #2D2B55; display: flex; justify-content: center; align-items: center; min-height: 100vh; }}
    .page {{ width: 1080px; height: 1920px; background: {COLORS['cream']}; overflow: hidden; position: relative; flex-shrink: 0; }}
    """


# ============ 封面页 ============
def generate_cover():
    css = get_base_css() + f"""
    .page {{
        background: linear-gradient(160deg, #FFF8F0 0%, #FFEDE0 40%, #FFE4CC 100%);
    }}
    .scene-bg {{
        position: absolute; inset: 0;
        background:
            radial-gradient(ellipse at 30% 80%, rgba(139,109,83,0.12) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 20%, rgba(255,152,0,0.08) 0%, transparent 40%);
    }}
    .header-bar {{
        position: absolute; top: 0; left: 0; right: 0; height: 6px;
        background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['warm_orange']});
    }}
    .brand-badge {{
        position: absolute; top: 40px; left: 50px;
        display: flex; align-items: center; gap: 8px;
        background: rgba(139,109,83,0.1); padding: 8px 18px; border-radius: 20px;
    }}
    .brand-dot {{
        width: 8px; height: 8px; border-radius: 50%; background: {COLORS['primary']};
    }}
    .main-content {{
        position: absolute; top: 240px; left: 0; right: 0;
        text-align: center; padding: 0 60px;
    }}
    .hook-label {{
        display: inline-block;
        background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']});
        color: white; font-size: 22px; font-weight: 700;
        padding: 10px 32px; border-radius: 30px; margin-bottom: 30px; letter-spacing: 4px;
    }}
    .main-title {{
        font-size: 72px; font-weight: 800; color: {COLORS['text_dark']};
        line-height: 1.2; margin-bottom: 20px; letter-spacing: 2px;
    }}
    .main-title em {{ font-style: normal; color: {COLORS['primary']}; }}
    .subtitle-line {{
        font-size: 32px; color: {COLORS['text_dark']};
        margin-bottom: 16px; font-weight: 400;
    }}
    .divider-line {{
        width: 120px; height: 3px;
        background: linear-gradient(90deg, transparent, {COLORS['primary']}, transparent);
        margin: 30px auto;
    }}
    .time-highlight {{
        display: flex; align-items: center; justify-content: center; gap: 16px; margin: 40px 0;
    }}
    .time-number {{
        font-size: 96px; font-weight: 900; color: {COLORS['accent']};
        line-height: 1; text-shadow: 2px 4px 0 rgba(255,152,0,0.15);
    }}
    .time-unit {{
        font-size: 36px; font-weight: 700; color: {COLORS['accent']};
        align-self: flex-end; padding-bottom: 16px;
    }}
    .time-desc {{
        font-size: 28px; color: {COLORS['text_dark']}; font-weight: 500;
    }}
    .sausage-circle {{
        position: absolute; bottom: 420px; left: 50%;
        transform: translateX(-50%);
        width: 300px; height: 80px; border-radius: 60px;
        background: linear-gradient(145deg, {COLORS['warm_orange']}, {COLORS['primary']});
        box-shadow: 0 20px 60px rgba(139,109,83,0.3);
    }}
    .sausage-circle::after {{
        content: ""; position: absolute; inset: 0; border-radius: 60px;
        background: repeating-linear-gradient(90deg, transparent, transparent 30px, rgba(255,255,255,0.08) 30px, rgba(255,255,255,0.08) 35px);
    }}
    .steam-lines {{
        position: absolute; bottom: 520px; left: 50%;
        transform: translateX(-50%); display: flex; gap: 50px;
    }}
    .steam {{
        width: 4px; height: 60px;
        background: linear-gradient(to top, rgba(139,109,83,0.25), transparent);
        border-radius: 4px;
        animation: steam-rise 2.5s ease-in-out infinite;
    }}
    .steam:nth-child(2) {{ animation-delay: 0.7s; height: 50px; }}
    .steam:nth-child(3) {{ animation-delay: 1.4s; height: 55px; }}
    @keyframes steam-rise {{
        0%, 100% {{ transform: translateY(0) scaleX(1); opacity: 0.4; }}
        50% {{ transform: translateY(-15px) scaleX(1.5); opacity: 0.1; }}
    }}
    .bottom-card {{
        position: absolute; bottom: 80px; left: 50px; right: 50px;
        background: rgba(255,255,255,0.92); border-radius: 20px;
        padding: 28px 36px; box-shadow: 0 4px 20px rgba(139,109,83,0.1);
        border: 1px solid rgba(139,109,83,0.08);
    }}
    .cta-row {{
        display: flex; align-items: center; justify-content: space-between;
    }}
    .cta-text {{
        font-size: 24px; color: {COLORS['text_dark']};
        display: flex; align-items: center; gap: 12px;
    }}
    .cta-icon {{
        width: 44px; height: 44px; border-radius: 50%;
        background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']});
        display: flex; align-items: center; justify-content: center;
        color: white; font-size: 18px; font-weight: 700; flex-shrink: 0;
    }}
    .cta-tag {{
        background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['soft_brown']});
        color: white; font-size: 22px; font-weight: 600;
        padding: 10px 28px; border-radius: 25px; flex-shrink: 0;
    }}
    .corner-accent {{
        position: absolute; width: 80px; height: 80px; opacity: 0.12;
    }}
    .corner-accent.tl {{ top: 20px; left: 20px; border-top: 3px solid {COLORS['primary']}; border-left: 3px solid {COLORS['primary']}; }}
    .corner-accent.tr {{ top: 20px; right: 20px; border-top: 3px solid {COLORS['primary']}; border-right: 3px solid {COLORS['primary']}; }}
    .corner-accent.bl {{ bottom: 20px; left: 20px; border-bottom: 3px solid {COLORS['primary']}; border-left: 3px solid {COLORS['primary']}; }}
    .corner-accent.br {{ bottom: 20px; right: 20px; border-bottom: 3px solid {COLORS['primary']}; border-right: 3px solid {COLORS['primary']}; }}
    """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>下班懒得做饭？蒸一截香肠，10分钟搞定</title>
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="scene-bg"></div>
    <div class="header-bar"></div>
    <div class="corner-accent tl"></div>
    <div class="corner-accent tr"></div>
    <div class="corner-accent bl"></div>
    <div class="corner-accent br"></div>

    <div class="brand-badge">
        <div class="brand-dot"></div>
        <span style="font-size:20px; color:#8D6E63; font-weight:600;">南漳黄姐灌香肠</span>
    </div>

    <div class="main-content">
        <div class="hook-label">10分钟快手家常菜</div>
        <h1 class="main-title">下班懒得做饭？</h1>
        <p class="subtitle-line">蒸一截香肠</p>
        <div class="divider-line"></div>
        <div class="time-highlight">
            <span class="time-number">10</span>
            <span class="time-unit">分钟</span>
        </div>
        <p class="time-desc">比外卖快，比外卖香，比外卖省钱</p>
    </div>

    <div class="steam-lines">
        <div class="steam"></div>
        <div class="steam"></div>
        <div class="steam"></div>
    </div>
    <div class="sausage-circle"></div>

    <div class="bottom-card">
        <div class="cta-row">
            <div class="cta-text">
                <div class="cta-icon">藏</div>
                <span>收藏起来，下班不知道吃什么时用得上</span>
            </div>
            <div class="cta-tag">懒人必备</div>
        </div>
    </div>
</div>
</body>
</html>"""
    path = OUTPUT_DIR / "slide01_cover.html"
    path.write_text(html, encoding='utf-8')
    print(f"Generated: {path}")


# ============ 痛点页 ============
def generate_pain_point():
    css = get_base_css() + f"""
    .page {{ background: linear-gradient(170deg, #FFF8F0 0%, #F5EDE5 60%, #EDE4DA 100%); }}
    .header {{ padding: 50px 60px 0; }}
    .tag-row {{ display: flex; gap: 14px; margin-bottom: 28px; }}
    .tag {{ font-size: 20px; font-weight: 600; padding: 8px 22px; border-radius: 20px; }}
    .tag-question {{ background: rgba(139,109,83,0.1); color: {COLORS['primary']}; }}
    .tag-scenario {{ background: rgba(255,152,0,0.1); color: {COLORS['accent']}; }}
    .main-title {{ font-size: 58px; font-weight: 800; color: {COLORS['text_dark']}; line-height: 1.25; margin-bottom: 10px; }}
    .sub {{ font-size: 30px; color: #888; margin-bottom: 36px; }}
    .divider {{ width: 80px; height: 4px; background: linear-gradient(90deg, {COLORS['primary']}, {COLORS['accent']}); border-radius: 2px; margin-bottom: 36px; }}
    .scene-intro {{ background: rgba(139,109,83,0.08); border-radius: 20px; padding: 28px 36px; margin: 0 50px 30px; text-align: center; }}
    .scene-intro p {{ font-size: 30px; color: {COLORS['text_dark']}; line-height: 1.6; }}
    .scene-intro .highlight {{ color: {COLORS['accent']}; font-weight: 700; }}
    .pain-list {{ padding: 0 50px; }}
    .pain-item {{ display: flex; align-items: flex-start; gap: 20px; margin-bottom: 22px; background: white; border-radius: 16px; padding: 24px 28px; box-shadow: 0 2px 12px rgba(139,109,83,0.06); border-left: 4px solid #E8DDD5; }}
    .pain-item:nth-child(1) {{ border-left-color: #E57373; }}
    .pain-item:nth-child(2) {{ border-left-color: #FFB74D; }}
    .pain-item:nth-child(3) {{ border-left-color: #FF8A65; }}
    .pain-item:nth-child(4) {{ border-left-color: #A1887F; }}
    .pain-item:nth-child(5) {{ border-left-color: #90A4AE; }}
    .pain-icon {{ width: 48px; height: 48px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 22px; flex-shrink: 0; margin-top: 2px; }}
    .pain-text {{ font-size: 28px; color: {COLORS['text_dark']}; line-height: 1.5; font-weight: 500; }}
    .solution-section {{ margin: 30px 50px 0; background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['soft_brown']}); border-radius: 20px; padding: 30px 36px; color: white; }}
    .solution-label {{ font-size: 22px; opacity: 0.85; margin-bottom: 10px; }}
    .solution-label::before {{ content: ">>> "; }}
    .solution-text {{ font-size: 28px; font-weight: 700; }}
    .bottom-note {{ position: absolute; bottom: 60px; left: 50px; right: 50px; text-align: center; padding: 22px; background: rgba(255,152,0,0.08); border-radius: 16px; border: 1px dashed {COLORS['accent']}; }}
    .bottom-note p {{ font-size: 26px; color: {COLORS['accent']}; font-weight: 600; }}
    """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>痛点揭示</title>
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="header">
        <div class="tag-row">
            <span class="tag tag-question">打工人日常</span>
            <span class="tag tag-scenario">下班后的纠结</span>
        </div>
        <h1 class="main-title">下班后最大的难题来了</h1>
        <p class="sub">上了一天班，拖着疲惫的身体回家</p>
        <div class="divider"></div>
    </div>
    <div class="scene-intro">
        <p>上了一天班，拖着<strong class="highlight">疲惫的身体</strong>回家</p>
        <p style="margin-top:12px;font-size:26px;color:#999;">每天都在纠结这几件事：</p>
    </div>
    <div class="pain-list">
        <div class="pain-item">
            <div class="pain-icon" style="background:#FFEBEE;color:#E57373;">?</div>
            <p class="pain-text">外卖吧，吃腻了还贵</p>
        </div>
        <div class="pain-item">
            <div class="pain-icon" style="background:#FFF3E0;color:#FFB74D;">?</div>
            <p class="pain-text">自己做吧，不知道做什么</p>
        </div>
        <div class="pain-item">
            <div class="pain-icon" style="background:#FBE9E7;color:#FF8A65;">?</div>
            <p class="pain-text">随便对付一口，又觉得委屈自己</p>
        </div>
        <div class="pain-item">
            <div class="pain-icon" style="background:#EFEBE9;color:#A1887F;">?</div>
            <p class="pain-text">菜市场不想去，冰箱里也没存货</p>
        </div>
        <div class="pain-item">
            <div class="pain-icon" style="background:#ECEFF1;color:#90A4AE;">?</div>
            <p class="pain-text">想吃点好的，但实在没精力折腾</p>
        </div>
    </div>
    <div class="solution-section">
        <p class="solution-label">其实不用那么复杂</p>
        <p class="solution-text">冰箱里有截香肠就够了</p>
    </div>
    <div class="bottom-note">
        <p>香肠不是大菜才吃，日常一餐也合适</p>
    </div>
</div>
</body>
</html>"""
    path = OUTPUT_DIR / "slide02_pain.html"
    path.write_text(html, encoding='utf-8')
    print(f"Generated: {path}")


# ============ 做法页 ============
def generate_method():
    css = get_base_css() + f"""
    .page {{ background: linear-gradient(170deg, #FFFBF5 0%, #FFF5EC 50%, #FFEDE0 100%); }}
    .header {{ padding: 50px 60px 0; }}
    .title-bar {{ display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }}
    .title-icon {{ width: 56px; height: 56px; border-radius: 16px; background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']}); display: flex; align-items: center; justify-content: center; }}
    .title-icon-inner {{ width: 36px; height: 36px; background: white; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; color: {COLORS['accent']}; font-weight: 700; }}
    .main-title {{ font-size: 52px; font-weight: 800; color: {COLORS['text_dark']}; }}
    .sub {{ font-size: 28px; color: #888; margin-bottom: 30px; padding-left: 4px; }}
    .steps-container {{ padding: 0 50px; display: flex; flex-direction: column; gap: 18px; }}
    .step-card {{ background: white; border-radius: 20px; padding: 28px 32px; box-shadow: 0 3px 16px rgba(139,109,83,0.08); position: relative; overflow: hidden; }}
    .step-card::before {{ content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px; border-radius: 3px 0 0 3px; }}
    .step-card:nth-child(1)::before {{ background: linear-gradient(180deg, {COLORS['accent']}, {COLORS['warm_orange']}); }}
    .step-card:nth-child(2)::before {{ background: linear-gradient(180deg, {COLORS['primary']}, {COLORS['soft_brown']}); }}
    .step-card:nth-child(3)::before {{ background: linear-gradient(180deg, {COLORS['trust']}, #81C784); }}
    .step-num {{ display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 12px; font-size: 22px; font-weight: 800; color: white; margin-bottom: 10px; }}
    .step-card:nth-child(1) .step-num {{ background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']}); }}
    .step-card:nth-child(2) .step-num {{ background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['soft_brown']}); }}
    .step-card:nth-child(3) .step-num {{ background: linear-gradient(135deg, {COLORS['trust']}, #81C784); }}
    .step-title {{ font-size: 30px; font-weight: 700; color: {COLORS['text_dark']}; margin-bottom: 12px; }}
    .step-detail {{ font-size: 24px; color: #777; line-height: 1.7; }}
    .step-detail strong {{ color: {COLORS['accent']}; font-weight: 700; }}
    .step-detail .green {{ color: {COLORS['trust']}; font-weight: 700; }}
    .time-compare {{ margin: 20px 50px; background: linear-gradient(135deg, rgba(255,152,0,0.08), rgba(139,109,83,0.08)); border-radius: 20px; padding: 24px 30px; border: 1px solid rgba(255,152,0,0.2); }}
    .time-compare-title {{ font-size: 22px; color: {COLORS['accent']}; font-weight: 700; margin-bottom: 16px; text-align: center; }}
    .compare-grid {{ display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: center; }}
    .compare-item {{ text-align: center; padding: 14px; border-radius: 14px; font-size: 22px; font-weight: 700; }}
    .compare-slow {{ background: rgba(229,115,115,0.1); color: #E57373; }}
    .compare-fast {{ background: rgba(76,175,80,0.1); color: {COLORS['trust']}; }}
    .compare-vs {{ font-size: 24px; color: #bbb; font-weight: 800; }}
    .bottom-bar {{ position: absolute; bottom: 60px; left: 50px; right: 50px; background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']}); border-radius: 20px; padding: 24px 36px; text-align: center; }}
    .bottom-bar p {{ font-size: 30px; color: white; font-weight: 800; }}
    .bottom-bar .small {{ font-size: 22px; font-weight: 400; opacity: 0.9; margin-top: 6px; }}
    """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>香肠蒸着吃，10分钟出锅</title>
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="header">
        <div class="title-bar">
            <div class="title-icon"><div class="title-icon-inner">10'</div></div>
            <h1 class="main-title">香肠蒸着吃</h1>
        </div>
        <p class="sub">方法超级简单，3步出锅</p>
    </div>
    <div class="steps-container">
        <div class="step-card">
            <div class="step-num">1</div>
            <p class="step-title">香肠洗净切片</p>
            <p class="step-detail">不用多，<strong>两三片够吃</strong><br>嫌麻烦整根蒸也行<br>冷冻的提前放冷藏解冻</p>
        </div>
        <div class="step-card">
            <div class="step-num">2</div>
            <p class="step-title">放蒸锅里</p>
            <p class="step-detail">冷水上锅，水开蒸 <strong>15分钟</strong><br>热水上锅，蒸 <strong>10分钟</strong><br>懒人的话：微波炉<strong class="green">高火3分钟</strong>也行</p>
        </div>
        <div class="step-card">
            <div class="step-num">3</div>
            <p class="step-title">出锅开吃</p>
            <p class="step-detail">配一碗白米饭<br>或者下碗面条<br>一个人吃得很满足</p>
        </div>
    </div>
    <div class="time-compare">
        <p class="time-compare-title">时间对比</p>
        <div class="compare-grid">
            <div class="compare-item compare-slow">蒸香肠<br><span style="font-size:28px;">10分钟</span></div>
            <div class="compare-vs">VS</div>
            <div class="compare-item compare-fast">等外卖<br><span style="font-size:28px;">30分钟+</span></div>
        </div>
    </div>
    <div class="bottom-bar">
        <p>10分钟，比等外卖还快</p>
        <p class="small">配碗白米饭，吃得又香又满足</p>
    </div>
</div>
</body>
</html>"""
    path = OUTPUT_DIR / "slide03_method.html"
    path.write_text(html, encoding='utf-8')
    print(f"Generated: {path}")


# ============ 搭配页 ============
def generate_combo():
    css = get_base_css() + f"""
    .page {{ background: linear-gradient(160deg, #FFFBF7 0%, #FFF8F0 50%, #FFF3E8 100%); }}
    .header {{ padding: 50px 60px 0; }}
    .tag-row {{ display: flex; gap: 14px; margin-bottom: 28px; }}
    .tag {{ font-size: 20px; font-weight: 600; padding: 8px 22px; border-radius: 20px; }}
    .tag-green {{ background: rgba(76,175,80,0.1); color: {COLORS['trust']}; }}
    .tag-orange {{ background: rgba(255,152,0,0.1); color: {COLORS['accent']}; }}
    .main-title {{ font-size: 50px; font-weight: 800; color: {COLORS['text_dark']}; line-height: 1.3; margin-bottom: 10px; }}
    .sub {{ font-size: 28px; color: #888; margin-bottom: 30px; }}
    .divider {{ width: 80px; height: 4px; background: linear-gradient(90deg, {COLORS['trust']}, {COLORS['accent']}); border-radius: 2px; margin-bottom: 24px; }}
    .combo-list {{ padding: 0 50px; display: flex; flex-direction: column; gap: 16px; }}
    .combo-card {{ background: white; border-radius: 20px; padding: 26px 30px; box-shadow: 0 3px 16px rgba(139,109,83,0.07); display: flex; align-items: center; gap: 24px; }}
    .combo-icon-wrap {{ width: 72px; height: 72px; border-radius: 20px; display: flex; align-items: center; justify-content: center; font-size: 40px; flex-shrink: 0; }}
    .combo-card:nth-child(1) .combo-icon-wrap {{ background: linear-gradient(135deg, rgba(139,109,83,0.12), rgba(212,165,116,0.2)); }}
    .combo-card:nth-child(2) .combo-icon-wrap {{ background: linear-gradient(135deg, rgba(255,152,0,0.12), rgba(255,107,53,0.2)); }}
    .combo-card:nth-child(3) .combo-icon-wrap {{ background: linear-gradient(135deg, rgba(76,175,80,0.12), rgba(129,199,132,0.2)); }}
    .combo-content {{ flex: 1; }}
    .combo-name {{ font-size: 30px; font-weight: 700; color: {COLORS['text_dark']}; margin-bottom: 6px; }}
    .combo-desc {{ font-size: 22px; color: #888; line-height: 1.5; }}
    .combo-badge {{ font-size: 18px; font-weight: 600; padding: 6px 16px; border-radius: 12px; flex-shrink: 0; }}
    .combo-card:nth-child(1) .combo-badge {{ background: rgba(139,109,83,0.1); color: {COLORS['primary']}; }}
    .combo-card:nth-child(2) .combo-badge {{ background: rgba(255,152,0,0.1); color: {COLORS['accent']}; }}
    .combo-card:nth-child(3) .combo-badge {{ background: rgba(76,175,80,0.1); color: {COLORS['trust']}; }}
    .extra-section {{ margin: 20px 50px; background: linear-gradient(135deg, rgba(76,175,80,0.08), rgba(139,109,83,0.06)); border-radius: 20px; padding: 24px 30px; border: 1px solid rgba(76,175,80,0.15); }}
    .extra-label {{ font-size: 22px; color: {COLORS['trust']}; font-weight: 700; margin-bottom: 14px; }}
    .extra-label::before {{ content: "再配一个："; }}
    .extra-items {{ display: flex; gap: 14px; flex-wrap: wrap; }}
    .extra-item {{ background: white; border-radius: 14px; padding: 14px 22px; font-size: 24px; color: {COLORS['text_dark']}; font-weight: 500; box-shadow: 0 2px 8px rgba(139,109,83,0.06); }}
    .bottom-bar {{ position: absolute; bottom: 60px; left: 50px; right: 50px; text-align: center; padding: 24px; background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['soft_brown']}); border-radius: 20px; }}
    .bottom-bar p {{ font-size: 28px; color: white; font-weight: 700; }}
    """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>香肠配一配，一顿像样的晚餐就有了</title>
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="header">
        <div class="tag-row">
            <span class="tag tag-green">快手搭配</span>
            <span class="tag tag-orange">一学就会</span>
        </div>
        <h1 class="main-title">香肠配一配<br>一顿像样的晚餐就有了</h1>
        <p class="sub">三种经典搭配，总有一款适合你</p>
        <div class="divider"></div>
    </div>
    <div class="combo-list">
        <div class="combo-card">
            <div class="combo-icon-wrap"><span style="font-size:36px;">[米]</span></div>
            <div class="combo-content">
                <p class="combo-name">香肠 + 白米饭</p>
                <p class="combo-desc">最经典的吃法，最简单的满足<br>上班族一人食首选</p>
            </div>
            <span class="combo-badge">最经典</span>
        </div>
        <div class="combo-card">
            <div class="combo-icon-wrap"><span style="font-size:36px;">[面]</span></div>
            <div class="combo-content">
                <p class="combo-name">香肠 + 面条</p>
                <p class="combo-desc">香肠切片铺在面上，或者香肠丁煮面<br>吃得饱又有滋味</p>
            </div>
            <span class="combo-badge">碳水爆炸</span>
        </div>
        <div class="combo-card">
            <div class="combo-icon-wrap"><span style="font-size:36px;">[粥]</span></div>
            <div class="combo-content">
                <p class="combo-name">香肠 + 白粥</p>
                <p class="combo-desc">早上晚上都适合，清淡解腻<br>香肠配粥比配饭还香</p>
            </div>
            <span class="combo-badge">清淡解腻</span>
        </div>
    </div>
    <div class="extra-section">
        <p class="extra-label"></p>
        <div class="extra-items">
            <span class="extra-item">蒜苗炒鸡蛋</span>
            <span class="extra-item">烫个青菜</span>
            <span class="extra-item">一饭有肉有菜</span>
        </div>
    </div>
    <div class="bottom-bar">
        <p>不用大鱼大肉，日常一餐很满足</p>
    </div>
</div>
</body>
</html>"""
    path = OUTPUT_DIR / "slide04_combo.html"
    path.write_text(html, encoding='utf-8')
    print(f"Generated: {path}")


# ============ 结尾页 ============
def generate_ending():
    css = get_base_css() + f"""
    .page {{ background: linear-gradient(170deg, #FFFBF5 0%, #FFF8F0 50%, #FFEDE0 100%); }}
    .header {{ padding: 60px 60px 0; text-align: center; }}
    .icon-wrap {{ width: 100px; height: 100px; border-radius: 28px; background: linear-gradient(135deg, {COLORS['primary']}, {COLORS['soft_brown']}); display: flex; align-items: center; justify-content: center; margin: 0 auto 30px; box-shadow: 0 8px 30px rgba(139,109,83,0.2); }}
    .icon-inner {{ font-size: 48px; }}
    .main-title {{ font-size: 56px; font-weight: 800; color: {COLORS['text_dark']}; line-height: 1.3; margin-bottom: 16px; }}
    .sub {{ font-size: 32px; color: #888; margin-bottom: 16px; }}
    .divider {{ width: 100px; height: 4px; background: linear-gradient(90deg, transparent, {COLORS['primary']}, transparent); margin: 0 auto 30px; border-radius: 2px; }}
    .core-points {{ display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; margin: 0 50px 30px; }}
    .core-point {{ background: white; border-radius: 16px; padding: 18px 28px; font-size: 26px; font-weight: 600; color: {COLORS['text_dark']}; box-shadow: 0 3px 14px rgba(139,109,83,0.08); }}
    .误区-section {{ margin: 0 50px 30px; background: linear-gradient(135deg, rgba(139,109,83,0.08), rgba(255,152,0,0.06)); border-radius: 20px; padding: 28px 34px; }}
    .误区-title {{ font-size: 24px; color: {COLORS['primary']}; font-weight: 700; margin-bottom: 16px; display: flex; align-items: center; gap: 10px; }}
    .误区-item {{ font-size: 26px; color: {COLORS['text_dark']}; line-height: 2; position: relative; padding-left: 24px; }}
    .误区-item::before {{ content: "- "; position: absolute; left: 0; color: {COLORS['accent']}; font-weight: 700; }}
    .互动-section {{ margin: 0 50px 30px; background: linear-gradient(135deg, {COLORS['accent']}, {COLORS['warm_orange']}); border-radius: 20px; padding: 30px 36px; text-align: center; }}
    .互动-label {{ font-size: 22px; color: rgba(255,255,255,0.85); margin-bottom: 12px; }}
    .互动-q {{ font-size: 32px; font-weight: 700; color: white; margin-bottom: 8px; }}
    .互动-q2 {{ font-size: 26px; color: rgba(255,255,255,0.9); margin-bottom: 16px; }}
    .互动-action {{ display: inline-block; background: white; color: {COLORS['accent']}; font-size: 24px; font-weight: 700; padding: 14px 36px; border-radius: 30px; }}
    .收藏-section {{ margin: 0 50px; text-align: center; padding: 22px; background: rgba(76,175,80,0.08); border-radius: 16px; border: 1px dashed {COLORS['trust']}; }}
    .收藏-section p {{ font-size: 24px; color: {COLORS['trust']}; font-weight: 600; }}
    """
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=1080, height=1920">
<title>结尾引导</title>
<style>{css}</style>
</head>
<body>
<div class="page">
    <div class="header">
        <div class="icon-wrap"><div class="icon-inner">[肠]</div></div>
        <h1 class="main-title">香肠不是大菜才吃</h1>
        <p class="sub">日常一餐也合适</p>
        <div class="divider"></div>
    </div>
    <div class="core-points">
        <span class="core-point">10分钟出锅</span>
        <span class="core-point">比外卖快</span>
        <span class="core-point">比外卖香</span>
    </div>
    <div class="误区-section">
        <p class="误区-title">打破一个误区</p>
        <p class="误区-item">以前总觉得香肠是冬天灌的</p>
        <p class="误区-item">是过年才吃的大菜</p>
        <p class="误区-item">其实备好在冰箱里</p>
        <p class="误区-item">下班随时蒸一截，比什么都方便</p>
    </div>
    <div class="互动-section">
        <p class="互动-label">互动时间</p>
        <p class="互动-q">你们家香肠一般怎么吃？</p>
        <p class="互动-q2">有没有什么懒人神仙搭配？</p>
        <span class="互动-action">评论区分享一下</span>
    </div>
    <div class="收藏-section">
        <p>收藏起来，下班不知道吃什么时用得上</p>
    </div>
</div>
</body>
</html>"""
    path = OUTPUT_DIR / "slide05_ending.html"
    path.write_text(html, encoding='utf-8')
    print(f"Generated: {path}")


def main():
    print("=" * 60)
    print("生成图文笔记HTML页面")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)
    generate_cover()
    generate_pain_point()
    generate_method()
    generate_combo()
    generate_ending()
    print("=" * 60)
    print("所有5个HTML文件生成完成！")
    print(f"请用浏览器打开并截图，尺寸: 1080x1920px")
    print("=" * 60)


if __name__ == "__main__":
    main()
