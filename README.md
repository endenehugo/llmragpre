# LLM RAG 项目

本项目是一个基于 Flask 和 LangChain 构建的 LLM 应用，旨在提供单一对话、多轮对话（记忆）、RAG（检索增强生成）以及基于 Agent 的智能问答功能。项目还包含一个简单的前端界面以供交互使用。

## 🌟 功能特性

- **单轮对话 (`/chat/single`)**: 基本的 LLM 问答功能。
- **多轮对话 (`/chat/memory`)**: 带有上下文记忆功能的对话接口。
- **RAG 检索增强生成 (`/chat/rag`)**: 结合 FAISS 本地向量数据库以及自定义业务数据（例如 `电商产品数据.txt`）回答具体领域的问题。
- **Agent 智能体问答 (`/chat/agent`)**: 具备工具调用能力的代理对话模式（集成了 LangGraph 及外部工具），现已支持 Web Search Tool 自动联网搜索公开网页信息。
- **前端交互界面 (`/`)**: 包含 `index.html` 以及配套静态资源（CSS/JS），支持 Firebase 集成。

## 🛠️ 技术栈

- **后端框架**: Flask, Flask-Cors
- **依赖注入**: Injector
- **大模型框架**: LangChain, LangGraph
- **向量数据库**: FAISS (`faiss-cpu`)
- **模型接口**: OpenAI, DashScope 等
- **文档解析**: Unstructured, python-docx, docx2txt

## 📁 目录结构

```
.
├── app/                  # Flask 应用核心逻辑
│   ├── handler/          # 各种模式的聊天处理器（单点/记忆/RAG/代理）
│   ├── response/         # API 统一响应封装
│   ├── router/           # 路由注册与蓝图管理
│   ├── static/           # 前端静态文件 (JS, CSS, 图片)
│   ├── templates/        # 前端 HTML 模板
│   ├── tools/            # Agent 可用的外部工具
│   └── utils/            # 通用工具类
├── config/               # 配置文件 (开发、预发、生产、测试环境)
├── resources/            # 数据资源与向量索引
│   ├── faiss_index/      # FAISS 向量数据库
│   ├── chat_history.json # 本地聊天记录保存
│   └── 电商产品数据.txt   # 用于 RAG 的基础文本数据
├── requirements.txt      # Python 依赖包列表
└── run.py                # 项目启动入口
```

## 🚀 快速开始

### 1. 环境准备

确保你已经安装了 Python 3.8 或更高版本。

克隆或进入项目目录，创建并激活虚拟环境：
```bash
# 激活你的虚拟环境 (例如使用 conda 或 venv)
# conda activate myenv
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 环境配置

在项目根目录创建 `.env` 文件，并根据需要配置大模型的 API 密钥（例如 OpenAI API Key 或 DashScope API Key 等相关环境变量配置）：

```ini
OPENAI_API_KEY=your_openai_api_key
# 其他需要的环境变量配置...
```

### 4. 运行服务

通过下面命令启动 Flask 开发服务器：

```bash
python run.py
```
默认通常会运行在 `http://0.0.0.0:端口号`，具体端口见配置项。打开浏览器即可访问自带的前端界面。

## 📡 API 接口说明

- `GET /` : 渲染首页 HTML 交互界面。
- `GET /test/test` : 接口测试端点。
- `GET /chat/single` : 单轮对话接口。
- `POST /chat/memory` : 带上下文记忆的对话接口。
- `POST /chat/agent` : 基于智能 Agent 的请求端点（支持工具调用链路）。
- `POST /chat/rag` : 基于本地知识库（FAISS）的检索增强生成对话。

### Agent 工具能力补充

- **MultiplyTool**: 处理简单数值乘法计算。
- **WebSearchTool**: 当问题需要最新资讯、网页资料或官网信息时，Agent 会自动调用 DuckDuckGo 搜索并结合搜索结果生成回答。

## 📝 备注

- 相关的本地向量索引存放在 `resources/faiss_index/` 路径下。如果本地业务数据（如 `电商产品数据.txt`）发生变动，需要更新向量索引以在 RAG 模型下生效。
