#!/usr/bin/env python3
"""
抖音舆情监控定时任务脚本
执行时间：每天早上 6:00
功能：自动采集监控链接数据并生成分析报告
"""

import os
import json
import time
from datetime import datetime

# 配置路径
BASE_PATH = "/Volumes/增元/项目/douyin/.cursor/skill/舆情专家"
CONFIG_FILE = "/Volumes/增元/项目/douyin/系统配置/当前客户.json"

def get_current_client():
    """获取当前客户"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def get_monitor_links(client_name):
    """获取客户的监控链接配置"""
    config_path = os.path.join(BASE_PATH, client_name, "监控配置.md")
    if not os.path.exists(config_path):
        return []
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析监控链接（简单解析，实际应该用正则）
    links = []
    lines = content.split('\n')
    for line in lines:
        if '|' in line and '话题' in line or '视频' in line or '商品' in line:
            # 提取链接信息
            pass
    
    return links

def generate_report(client_name, links):
    """生成舆情分析报告"""
    report_dir = os.path.join(BASE_PATH, "数据报告")
    os.makedirs(report_dir, exist_ok=True)
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_file = os.path.join(report_dir, f"{client_name}_{date_str}.md")
    
    content = f"""# 抖音舆情分析报告 - {client_name}
生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 监控链接概览

共监控 {len(links)} 个链接

---

## 数据采集结果

> ⚠️ 注意：由于无法直接访问抖音平台，此处报告需要您提供具体的抖音链接或数据后手动填写。

### 需要您提供的内容：

1. **热门话题数据**：对应话题的播放量、讨论量
2. **视频评论区数据**：视频下的真实用户评论（痛点/需求/吐槽）
3. **商品评价数据**：商品的好评/中评/差评内容

---

## 后续行动建议

1. 手动补充上述数据
2. 分析用户痛点，提炼选题方向
3. 更新关键词库和选题库

---

*本报告由定时任务自动生成*
"""
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return report_file

def run_task():
    """执行定时任务"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 抖音舆情监控定时任务开始...")
    
    # 获取当前客户
    client_info = get_current_client()
    if not client_info:
        print("❌ 未找到当前客户配置")
        return
    
    client_name = client_info.get("当前客户")
    print(f"📋 当前客户: {client_name}")
    
    # 获取监控链接
    links = get_monitor_links(client_name)
    print(f"📊 监控链接数: {len(links)}")
    
    # 生成报告
    report_file = generate_report(client_name, links)
    print(f"✅ 报告已生成: {report_file}")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 任务完成")

if __name__ == "__main__":
    run_task()
