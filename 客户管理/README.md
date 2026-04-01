# 📁 客户资产管理系统

## 目录结构

```
客户管理/
├── 行业索引.json              # 行业分类索引
├── README.md                  # 使用说明
├── 食品行业/
│   ├── 灌香肠/
│   │   └── 南漳香肠/           # 👉 每个客户一个专属文件夹
│   │       ├── 客户档案.json  # 客户信息
│   │       ├── 品牌资料/      # logo、slogan、品牌故事
│   │       ├── 产品资料/      # 产品图片、参数、价格
│   │       ├── 包装设计/      # 包装图片、材质
│   │       ├── 人物形象/      # 代言人/店主照片、视频
│   │       ├── 场景素材/      # 店铺、车间、集市、家庭场景
│   │       ├── 宣传物料/      # 宣传册、单页、视频
│   │       └── 参考案例/      # 客户案例、好评截图
│   └── 桶装水/
│       └── 龙眼山天然涌泉/
│           └── ...
└── 本地服务/
    └── 家政/
        └── XX家政/
            └── ...
```

---

## 每个客户专属文件夹内容

```
客户名称/
├── 客户档案.json      # 必填：客户基础信息
├── 品牌资料/          # logo.png, slogan.txt, 品牌故事.md
├── 产品资料/          # 产品图片、价格表
├── 包装设计/          # 包装图片、材质说明
├── 人物形象/          # 代言人照片、视频、声音
├── 场景素材/          # 店铺/车间/集市/家庭场景图
├── 宣传物料/          # 宣传册、单页、视频
└── 参考案例/          # 客户案例、好评截图
```

---

## 客户档案字段说明

### 基础信息

| 字段 | 说明 | 示例 |
|------|------|------|
| `client_id` | 客户唯一ID | CLIENT-食品-2026-001 |
| `client_name` | 客户名称 | 南漳香肠 |
| `industry` | 行业 | 食品行业 |
| `business_scope` | 业务范围 | 灌香肠 |

### 品牌信息

| 字段 | 说明 |
|------|------|
| `brand.brand_name` | 品牌名称 |
| `brand.slogan` | 品牌 slogan |
| `brand.logo` | logo 图片信息 |
| `brand.spokesperson` | 代言人信息 |

### 产品信息

| 字段 | 说明 |
|------|------|
| `products[].name` | 产品名称 |
| `products[].sku` | 产品SKU |
| `products[].price` | 价格 |
| `products[].features` | 产品特点 |
| `products[].images` | 产品图片 |
| `products[].packaging` | 包装信息 |

### 营销素材

| 字段 | 说明 |
|------|------|
| `marketing_materials.catalog` | 产品目录/宣传册 |
| `marketing_materials.flyer` | 宣传单页 |
| `marketing_materials.video_intro` | 品牌介绍视频 |
| `marketing_materials.case_studies` | 客户案例/好评截图 |

### 内容创作素材（生成图文时调用）

| 字段 | 说明 |
|------|------|
| `assets_for_content.design_reference` | 设计风格参考（配色、字体、氛围） |
| `assets_for_content.product_images` | 产品图片（成品、原料、制作过程） |
| `assets_for_content.persona` | 人物形象（代言人/店员外观、声音、性格） |
| `assets_for_content.scene_images` | 场景图片（店铺/车间/集市/家庭） |

---

## 新增客户

### 方法一：运行脚本（推荐）

```bash
cd 客户管理
python 新增客户.py [行业] [业务范围] [客户名称]
```

**示例**：

```bash
# 新增食品行业-灌香肠-张三香肠
python 新增客户.py 食品行业 灌香肠 张三香肠

# 新增本地服务-家政-好好家政
python 新增客户.py 本地服务 家政 好好家政
```

**脚本会自动**：
1. ✅ 创建客户专属文件夹（7个子文件夹）
2. ✅ 生成客户档案模板（`客户档案.json`）
3. ✅ 自动更新行业索引（`行业索引.json`）

---

### 方法二：手动创建

```
1. 在对应行业/子行业目录下创建客户文件夹
2. 创建以下子文件夹：
   - 品牌资料/
   - 产品资料/
   - 包装设计/
   - 人物形象/
   - 场景素材/
   - 宣传物料/
   - 参考案例/
3. 创建客户档案.json 并填写信息
4. 行业索引会自动更新（也可手动编辑）
```

### 2. 调用客户档案

```python
# 在 skill 中读取客户档案
client_id = "CLIENT-食品-2026-001"
client_data = read_json(f"客户管理/食品行业/灌香肠/南漳香肠/客户档案.json")

# 获取关键信息
logo_path = client_data["brand"]["logo"]["path"]
products = client_data["products"]
spokesperson = client_data["brand"]["spokesperson"]["name"]
```

---

## 自动化脚本

后续可开发自动脚本：
- 根据 `客户档案.json` 自动填充内容模板
- 自动提取产品图片生成图文
- 自动匹配品牌调性生成文案
