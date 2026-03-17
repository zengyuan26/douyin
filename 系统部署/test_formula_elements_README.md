# 公式要素管理模块测试用例

## 文件说明

### 1. test_formula_elements_api.py
基于 requests 的 API 测试脚本，需要服务器运行。

**使用方法：**
```bash
# 1. 启动服务器
cd 系统部署
python3 app.py

# 2. 另一个终端运行测试（根据实际账号密码修改）
python3 test_formula_elements_api.py
```

**测试覆盖：**
- ✓ 获取所有要素
- ✓ 按分类获取要素
- ✓ 成功创建要素
- ✓ 创建重复编码（应失败）
- ✓ 缺少必填字段（应失败）
- ✓ 更新要素
- ✓ 删除要素
- ✓ 初始化要素
- ✓ 导出要素
- ✓ 导入要素
- ✓ 获取建议列表

---

## 手动测试（curl）

如果不想写代码，可以用 curl 测试：

### 1. 获取要素列表
```bash
curl -X GET "http://localhost:5001/knowledge/api/formula-elements/" \
  -H "Cookie: your_session_cookie"
```

### 2. 按分类获取
```bash
curl -X GET "http://localhost:5001/knowledge/api/formula-elements/?sub_category=nickname_analysis" \
  -H "Cookie: your_session_cookie"
```

### 3. 创建要素
```bash
curl -X POST "http://localhost:5001/knowledge/api/formula-elements/" \
  -H "Content-Type: application/json" \
  -H "Cookie: your_session_cookie" \
  -d '{
    "sub_category": "nickname_analysis",
    "name": "测试要素",
    "code": "test_element",
    "description": "测试描述",
    "examples": "测试1|测试2",
    "priority": 1,
    "usage_tips": "测试技巧"
  }'
```

### 4. 更新要素
```bash
curl -X PUT "http://localhost:5001/knowledge/api/formula-elements/1" \
  -H "Content-Type: application/json" \
  -H "Cookie: your_session_cookie" \
  -d '{
    "name": "更新后的名称",
    "description": "更新后的描述"
  }'
```

### 5. 删除要素
```bash
curl -X DELETE "http://localhost:5001/knowledge/api/formula-elements/1" \
  -H "Cookie: your_session_cookie"
```

### 6. 初始化要素
```bash
curl -X POST "http://localhost:5001/knowledge/api/formula-elements/init" \
  -H "Cookie: your_session_cookie"
```

### 7. 导出要素
```bash
curl -X GET "http://localhost:5001/knowledge/api/formula-elements/export" \
  -H "Cookie: your_session_cookie"
```

### 8. 导入要素
```bash
curl -X POST "http://localhost:5001/knowledge/api/formula-elements/import" \
  -H "Content-Type: application/json" \
  -H "Cookie: your_session_cookie" \
  -d '{
    "nickname_analysis": [
      {
        "name": "新要素",
        "code": "new_element",
        "description": "描述",
        "priority": 1
      }
    ]
  }'
```

### 9. 获取建议列表
```bash
curl -X GET "http://localhost:5001/knowledge/api/formula-elements/suggestions" \
  -H "Cookie: your_session_cookie"
```

---

## 测试用例设计思路

### CRUD 测试
| 测试项 | 描述 |
|--------|------|
| 创建成功 | 正常创建要素，验证数据库 |
| 创建失败-缺字段 | 缺少必填字段返回 400 |
| 创建失败-重复 | 相同 code 返回 400 |
| 更新成功 | 修改字段验证 |
| 更新-不存在 | 返回 404 |
| 删除成功 | 验证已删除 |
| 删除-不存在 | 返回 404 |

### 业务功能测试
| 测试项 | 描述 |
|--------|------|
| 初始化 | 创建默认要素，验证数量 |
| 初始化幂等 | 重复调用不重复创建 |
| 导出 | 导出所有/分类数据 |
| 导入 | 导入并验证合并逻辑 |

### 权限测试
| 测试项 | 描述 |
|--------|------|
| 未登录 | 返回 401 |
