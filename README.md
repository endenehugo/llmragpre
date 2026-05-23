# LLM RAG 项目

这是一个基于 Flask、LangChain 和 LangGraph 的中文问答项目，集成了单轮对话、多轮记忆对话、RAG 检索增强问答，以及带工具调用能力的 Agent。项目自带一个简单前端页面，可直接在浏览器中进行交互。

## 功能概览

- 单轮对话：通过 `/chat/single` 直接调用大模型完成一次问答。
- 多轮记忆对话：通过 `/chat/memory` 保存上下文历史，适合连续追问。
- RAG 检索问答：通过 `/chat/rag` 从本地 FAISS 索引中召回知识片段后再生成回答。
- Agent 智能问答：通过 `/chat/agent` 结合大模型、检索上下文和工具调用完成更复杂的问题处理。
- Web 页面入口：通过 `/` 渲染前端页面，便于本地调试和手工验证接口。

## 当前使用的模型与能力

- 对话模型：阿里云通义千问 `qwen-plus`
- 向量模型：DashScope Embedding `text-embedding-v3`
- 向量库：FAISS
- Agent 工具：
	- `MultiplyTool`：简单乘法计算
	- `WebSearchTool`：联网搜索公开网页信息
	- `WordDocumentTool`：生成或整理 Word 文档

## 项目结构

```text
.
├── app/
│   ├── handler/                # 路由处理器：单轮、记忆、RAG、Agent、首页、测试
│   ├── response/               # 统一响应封装
│   ├── router/                 # Flask 路由注册
│   ├── static/                 # 前端静态资源
│   ├── templates/              # 前端页面模板
│   ├── tools/                  # Agent 工具实现
│   ├── utils/                  # 资源路径、设备信息等工具
│   ├── __init__.py             # Flask app 初始化与配置加载
│   └── module.py               # Injector 模块
├── config/                     # dev / test / pre / prod 配置
├── resources/
│   ├── faiss_index/            # 当前 RAG 使用的向量索引
│   ├── faiss_index_steffen/    # 备用或历史向量索引
│   ├── 电商产品数据.txt         # RAG 基础业务文本
│   ├── chat_history.json       # 对话历史数据
│   └── memory.txt              # 记忆相关资源
├── test_tools/                 # 工具级测试脚本
├── run.py                      # 本地启动入口
└── requirements.txt            # Python 依赖
```

## 运行环境

- Python 3.8 及以上
- 建议使用虚拟环境
- 需要可用的 DashScope API Key

## 安装依赖

```bash
pip install -r requirements.txt
```

如果你使用虚拟环境，推荐先创建再安装：

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 配置说明

当前项目不是通过 `.env` 自动加载配置，而是通过环境变量 `FLASK_ENV` 选择对应配置文件：

- `dev` 对应 `config/config_dev.py`
- `test` 对应 `config/config_test.py`
- `pre` 对应 `config/config_pre.py`
- `prod` 对应 `config/config_prod.py`

应用启动时会在 `app/__init__.py` 中执行：

```python
env = os.environ.get("FLASK_ENV", "dev")
app.config.from_object(f"config.config_{env}")
```

因此你需要先设置 `FLASK_ENV`，再启动服务。

Windows PowerShell:

```powershell
$env:FLASK_ENV = "dev"
python run.py
```

Linux / macOS:

```bash
export FLASK_ENV=dev
python run.py
```

配置项至少包括：

```python
PORT = 5000
DASHSCOPE_API_KEY = "your_key"
METASO_API_KEY = "optional"
```

说明：

- `DASHSCOPE_API_KEY` 为当前项目的核心配置。
- `METASO_API_KEY` 为可选配置，存在时会在应用启动时写入环境变量。
- 生产环境不要把真实密钥提交到仓库中，建议改为环境变量或独立配置注入。

## 启动项目

本地启动：

```bash
python run.py
```

默认监听地址：

```text
http://0.0.0.0:5000
```

浏览器访问首页：

```text
http://127.0.0.1:5000/
```

说明：

- 当前 `run.py` 以 Flask 开发模式启动，并开启 `debug=True`。
- 线上部署建议使用 Gunicorn 或 uWSGI，不建议直接执行 `python run.py`。

## API 接口

### 1. 首页

- 方法：`GET`
- 路径：`/`
- 说明：渲染前端页面 `templates/index.html`

### 2. 测试接口

- 方法：`GET`
- 路径：`/test/test`
- 参数：`user_name`

示例：

```text
GET /test/test?user_name=Tom
```

### 3. 单轮对话

- 方法：`GET`
- 路径：`/chat/single`
- 参数：`query`

示例：

```text
GET /chat/single?query=你好
```

### 4. 多轮记忆对话

- 方法：`POST`
- 路径：`/chat/memory`
- 请求体：JSON

```json
{
	"query": "帮我总结一下昨天的对话"
}
```

### 5. RAG 检索问答

- 方法：`POST`
- 路径：`/chat/rag`
- 请求体：JSON

```json
{
	"query": "这款电商产品的主要卖点是什么？"
}
```

说明：

- 默认加载 `resources/faiss_index/` 作为向量索引。
- 检索内容来自本地业务知识库，适合固定领域问答。

### 6. Agent 智能问答

- 方法：`POST`
- 路径：`/chat/agent`
- 请求体：JSON

```json
{
	"query": "帮我搜索一下某品牌官网，并整理成 Word 文档"
}
```

说明：

- Agent 会结合历史上下文、本地知识检索结果和工具调用结果作答。
- 当问题涉及实时信息、官网资料或网页内容时，会优先尝试调用 `WebSearchTool`。
- 当问题涉及文档导出时，会尝试调用 `WordDocumentTool`。

## 知识库与资源说明

- RAG 默认读取 `resources/faiss_index/` 下的本地向量索引。
- 原始业务数据示例位于 `resources/电商产品数据.txt`。
- 如果你更新了业务文本，但没有重建索引，那么 `/chat/rag` 和 `/chat/agent` 读取到的仍然会是旧知识。

## 工具测试

仓库中提供了工具测试脚本：

- `test_tools/test_web_search_tool.py`
- `test_tools/test_word_document_tool.py`

可用于单独验证工具是否可用。

## 部署建议

如果部署到 Ubuntu 服务器，推荐使用 Gunicorn + Nginx：

```bash
pip install gunicorn
export FLASK_ENV=prod
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

建议做法：

- Gunicorn 监听 `127.0.0.1:5000`
- Nginx 对外监听 `80`
- 阿里云安全组放行 `22` 和 `80`

## 已知注意事项

- 当前配置文件中如果直接写入真实密钥，存在泄露风险。
- 当前启动入口适合开发调试，不适合作为生产启动命令。
- `requirements.txt` 如在 Windows 下以 Unicode 编码保存，上传到 Linux 后建议先确认编码和换行符正常。
