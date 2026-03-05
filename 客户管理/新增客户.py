#!/usr/bin/env python3
"""
客户文件夹自动生成脚本
用法: python 新增客户.py [行业] [业务范围] [客户名称]

示例:
    python 新增客户.py 食品行业 灌香肠 张三香肠
    python 新增客户.py 本地服务 家政 好好家政
"""

import os
import sys
import json
from datetime import datetime

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def create_client_folders(industry, business_scope, client_name):
    """创建客户文件夹结构"""
    
    # 构建路径
    client_path = os.path.join(BASE_DIR, industry, business_scope, client_name)
    
    # 需要创建的子文件夹
    subfolders = [
        "品牌资料",      # logo、slogan、品牌故事
        "产品资料",      # 产品图片、参数、价格表
        "包装设计",      # 包装图片、材质说明
        "人物形象",      # 代言人照片、视频、形象描述
        "场景素材",      # 店铺、车间、集市、家庭场景
        "宣传物料",      # 宣传册、单页、视频素材
        "参考案例",      # 同行案例、优秀作品参考
    ]
    
    # 创建客户文件夹
    os.makedirs(client_path, exist_ok=True)
    
    # 创建子文件夹
    for folder in subfolders:
        os.makedirs(os.path.join(client_path, folder), exist_ok=True)
    
    # 生成客户档案模板
    client_id = f"CLIENT-{industry[:2]}-{datetime.now().strftime('%Y%m%d')}-{client_name[:3]}"
    
    profile_template = {
        "client_id": client_id,
        "client_name": client_name,
        "industry": industry,
        "business_scope": business_scope,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        
        "basic_info": {
            "client_type": "product/service",
            "geographic_scope": "local",
            "brand_type": "personal/company",
            "description": "请填写客户描述",
            "target_cities": ["城市"],
            "language_style": "普通话/方言"
        },
        
        "contact": {
            "owner": "负责人姓名",
            "phone": "电话",
            "wechat": "微信"
        },
        
        "brand": {
            "brand_name": client_name,
            "slogan": "品牌 slogan",
            "logo": {
                "has": True,
                "path": "品牌资料/logo.png",
                "description": "Logo 描述"
            },
            "spokesperson": {
                "has": False,
                "name": "代言人姓名",
                "type": "owner/celebrity/staff",
                "description": "代言人描述"
            }
        },
        
        "products": [
            {
                "name": "产品名称",
                "sku": "SKU-001",
                "price": "价格",
                "features": ["特点1", "特点2"],
                "images": ["产品资料/产品1.jpg"],
                "packaging": {
                    "type": "包装类型",
                    "size": "规格",
                    "materials": ["包装设计/包装.jpg"]
                }
            }
        ],
        
        "marketing_materials": {
            "catalog": ["宣传物料/产品目录.jpg"],
            "flyer": ["宣传物料/宣传单.jpg"],
            "video_intro": ["宣传物料/品牌介绍.mp4"],
            "case_studies": ["参考案例/好评.jpg"]
        },
        
        "assets_for_content": {
            "design_reference": {
                "style": "设计风格",
                "color_scheme": ["主色调"],
                "fonts": ["字体"],
                "mood": "氛围关键词",
                "references": ["参考案例/"]
            },
            
            "product_images": {
                "finished_products": ["产品资料/"],
                "raw_materials": ["产品资料/原料/"],
                "production_process": ["产品资料/制作过程/"]
            },
            
            "persona": {
                "spokesperson": {
                    "name": "人物名称",
                    "age": "年龄",
                    "appearance": "外貌描述",
                    "personality": "性格特点",
                    "voice": "声音特点",
                    "images": ["人物形象/照片.jpg"],
                    "videos": ["人物形象/视频.mp4"]
                }
            },
            
            "scene_images": {
                "shop": ["场景素材/店铺.jpg"],
                "production_workshop": ["场景素材/车间.jpg"],
                "market": ["场景素材/集市.jpg"],
                "home_kitchen": ["场景素材/家庭.jpg"]
            }
        },
        
        "content_needs": {
            "primary_keywords": ["关键词1", "关键词2"],
            "content_types": ["图文", "短视频"],
            "posting_frequency": "daily/weekly",
            "main_platforms": ["抖音", "小红书"]
        },
        
        "notes": "备注信息"
    }
    
    # 写入客户档案模板
    profile_path = os.path.join(client_path, "客户档案.json")
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile_template, f, ensure_ascii=False, indent=2)
    
    # 更新行业索引
    update_industry_index(industry, business_scope, client_name)
    
    print(f"✅ 客户文件夹已创建: {client_path}")
    print(f"✅ 客户档案模板已生成: {profile_path}")
    print(f"\n请将客户资料放到对应文件夹，然后填写 {profile_path}")

def update_industry_index(industry, business_scope, client_name):
    """更新行业索引文件"""
    index_path = os.path.join(BASE_DIR, "行业索引.json")
    
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)
    else:
        index_data = {"version": "1.0.0", "last_updated": "", "industries": {}}
    
    # 更新行业索引
    if industry not in index_data["industries"]:
        index_data["industries"][industry] = {"business_scopes": [], "clients": []}
    
    if business_scope not in index_data["industries"][industry]["business_scopes"]:
        index_data["industries"][industry]["business_scopes"].append(business_scope)
    
    if client_name not in index_data["industries"][industry]["clients"]:
        index_data["industries"][industry]["clients"].append(client_name)
    
    index_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 行业索引已更新: {index_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    
    industry = sys.argv[1]
    business_scope = sys.argv[2]
    client_name = sys.argv[3]
    
    create_client_folders(industry, business_scope, client_name)
