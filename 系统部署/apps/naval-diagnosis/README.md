# 纳瓦尔商业诊断系统

基于纳瓦尔财富理念的商业模式诊断工具，帮助用户发现自己的赚钱能力。

## 功能特性

- 🎯 10道测试题快速诊断
- 🤖 AI智能分析商业模式
- 📊 可视化结果报告
- 🔗 一键分享结果

## 快速启动

### 1. 克隆项目

```bash
cd 系统部署/apps
```

### 2. 配置环境

```bash
# 复制环境配置
cp .env.example .env

# 编辑.env，填入API密钥
vim .env
```

### 3. 启动服务

```bash
# macOS/Linux
chmod +x start.sh
./start.sh

# 或手动启动
docker-compose up -d
```

### 4. 访问应用

- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 项目结构

```
naval-diagnosis/
├── backend/              # 后端
│   ├── main.py          # FastAPI入口
│   ├── config.py        # 配置
│   ├── schemas.py       # 数据模型
│   ├── routers/         # API路由
│   └── services/        # 业务服务
│       ├── ai_analyzer.py  # AI分析引擎
│       └── prompts.py      # LLM提示词
├── frontend/            # 前端
│   ├── src/
│   │   ├── views/       # 页面
│   │   ├── stores/     # 状态管理
│   │   └── router/     # 路由
│   └── ...
├── init.sql            # 数据库初始化
├── docker-compose.yml  # Docker编排
└── .env.example        # 环境变量示例
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue3 + Vite + TailwindCSS |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL |
| 缓存 | Redis |
| AI | OpenAI / 硅基流动 |

## 开发

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 前端
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
# 数据库测试
docker-compose exec db psql -U postgres -d naval_diagnosis

# API测试
curl http://localhost:8000/health
```

## 配置说明

### LLM配置

系统支持两种LLM提供商：

1. **OpenAI**（推荐国外用户）
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini
```

2. **硅基流动**（推荐国内用户）
```env
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=sk-xxx
SILICONFLOW_MODEL=THUDM/glm-4-flash
```

## License

MIT
