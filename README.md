# LLM RAG 项目

这是一个基于 Flask、LangChain 和 LangGraph 的中文问答项目，集成了单轮对话、多轮记忆对话、RAG 检索增强问答，以及带工具调用能力的 Agent。项目当前还支持会话持久化、历史会话切换，以及按会话上传 txt、pdf、docx 文档后进行文档问答。项目自带一个简单前端页面，可直接在浏览器中进行交互。

## 功能概览

- 单轮对话：通过 `/chat/single` 直接调用大模型完成一次问答。
- 多轮记忆对话：通过 `/chat/memory` 保存上下文历史，适合连续追问。
- RAG 检索问答：通过 `/chat/rag` 从本地 FAISS 索引中召回知识片段后再生成回答。
- Agent 智能问答：通过 `/chat/agent` 结合大模型、检索上下文和工具调用完成更复杂的问题处理。
- 会话持久化：通过 `/conversation/*` 接口创建、列出、查看和继续历史会话。
- 文档上传问答：支持把 txt、pdf、docx 文档绑定到某个会话，并基于会话内文档进行问答。
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
│   ├── repository/             # MySQL 持久化访问层
│   ├── response/               # 统一响应封装
│   ├── router/                 # Flask 路由注册
│   ├── services/               # 会话存储、文档解析、索引构建、对话编排
│   ├── static/                 # 前端静态资源
│   ├── templates/              # 前端页面模板
│   ├── tools/                  # Agent 工具实现
│   ├── utils/                  # 资源路径、设备信息等工具
│   ├── __init__.py             # Flask app 初始化与配置加载
│   └── module.py               # Injector 模块
├── config/                     # dev / test / pre / prod 配置
├── docs/                       # 设计文档与问题复盘
├── resources/
│   ├── faiss_index/            # 当前 RAG 使用的向量索引
│   ├── faiss_index_steffen/    # 备用或历史向量索引
│   ├── faiss_index_uploads/    # 按会话生成的上传文档向量索引
│   ├── parsed_docs/            # 上传文档解析后的纯文本
│   ├── uploads/                # 上传原始文件
│   ├── 电商产品数据.txt         # RAG 基础业务文本
│   ├── chat_history.json       # 对话历史数据
│   └── memory.txt              # 记忆相关资源
├── app/test_tools/             # 服务与工具的窄测试脚本
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

如果是 Linux 生产环境，建议使用单独的最小依赖清单：

```bash
pip install -r requirements-prod.txt
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

当前项目会先加载 `.env`，再通过环境变量 `FLASK_ENV` 选择对应配置文件：

- `dev` 对应 `config/config_dev.py`
- `test` 对应 `config/config_test.py`
- `pre` 对应 `config/config_pre.py`
- `prod` 对应 `config/config_prod.py`

应用启动时会在 `app/__init__.py` 中执行：

```python
env = os.environ.get("FLASK_ENV", "dev")
load_dotenv()
app.config.from_object(f"config.config_{env}")
```

因此你可以把密钥和数据库连接信息写进 `.env`，同时通过 `FLASK_ENV` 切换配置文件。

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
- MySQL 相关配置默认从环境变量读取，未设置时会回落到各环境配置文件中的默认值。
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

### 7. 创建会话

- 方法：`POST`
- 路径：`/conversation/create`
- 请求体：JSON

```json
{
	"title": "新对话",
	"mode": "agent"
}
```

### 8. 查询会话列表

- 方法：`GET`
- 路径：`/conversation/list`

### 9. 查询会话详情

- 方法：`GET`
- 路径：`/conversation/detail`
- 参数：`conversation_id`

示例：

```text
GET /conversation/detail?conversation_id=conv_xxx
```

### 10. 会话问答

- 方法：`POST`
- 路径：`/conversation/chat`
- 请求体：JSON

```json
{
	"conversation_id": "conv_xxx",
	"query": "请总结我刚上传的文档",
	"mode": "agent"
}
```

说明：

- `mode` 支持 `agent`、`rag`、`memory`。
- `agent` 和 `rag` 会优先读取当前会话下已索引的文档上下文。
- 当前会话检索已支持两类兜底优化：短文本概述类问题的无阈值回退，以及按文件名提问时的文件名锚点召回。

### 11. 上传会话文档

- 方法：`POST`
- 路径：`/document/upload`
- 请求体：`multipart/form-data`
- 字段：`conversation_id`、`file`

说明：

- 当前支持 `txt`、`pdf`、`docx`。
- `doc` 会返回明确提示，要求先转换为 `docx`。
- 上传成功后，后端会自动解析文本并重建该会话对应的向量索引。

### 12. 删除会话文档

- 方法：`POST`
- 路径：`/document/delete`
- 请求体：JSON

```json
{
	"document_id": "doc_xxx"
}
```

## 知识库与资源说明

- RAG 默认读取 `resources/faiss_index/` 下的本地向量索引。
- 会话文档问答读取 `resources/faiss_index_uploads/` 下按会话生成的索引。
- 原始业务数据示例位于 `resources/电商产品数据.txt`。
- 如果你更新了业务文本，但没有重建索引，那么 `/chat/rag` 和 `/chat/agent` 读取到的仍然会是旧知识。
- 如果你修改了历史上传文档的索引策略，旧会话下的文档需要重新上传或重建索引后才会生效。

## 工具测试

仓库中提供了工具测试脚本：

- `test_tools/test_web_search_tool.py`
- `test_tools/test_word_document_tool.py`

另外还提供了会话文档检索的窄测试：

- `app/test_tools/test_document_index_service.py`

可用于单独验证工具是否可用。

示例：

```powershell
D:\conda\python.exe -m unittest app.test_tools.test_document_index_service
```

## 文档问答排查提示

如果出现“文档已上传并显示 indexed，但回答仍像没读到文件”的情况，优先按以下顺序排查：

- 先确认 `resources/parsed_docs/` 下是否已经生成了解析后的文本。
- 再确认会话索引是否已经写入 `resources/faiss_index_uploads/`。
- 如果问题是“这个文件里有什么”“请概述一下内容”，要优先怀疑召回阈值过严。
- 如果问题是“总结 test.docx 内容”这类按文件名提问，要优先检查索引文本是否包含文件名锚点。

更完整的排错复盘见：`docs/2026-06-08-document-read-debug-summary.md`

## 部署建议

如果部署到 Ubuntu 服务器，推荐使用 Gunicorn + Nginx：

```bash
export FLASK_ENV=prod
pip install -r requirements-prod.txt
gunicorn -c gunicorn.conf.py wsgi:app
```

建议做法：

- 生产环境使用全新的虚拟环境，不要复用本机 Windows 调试环境，也不要混用用户级 site-packages
- 生产安装优先使用 `requirements-prod.txt`，只保留当前运行路径真正需要的依赖
- 当前 Windows 环境里存在 `torch`，它会引入 `libiomp5md.dll`；而 `faiss-cpu` 会触发另一套 OpenMP，二者同进程可能冲突。生产环境应通过最小依赖隔离掉这类无关包，而不是继续依赖 `KMP_DUPLICATE_LIB_OK`
- 先使用仓库内的 `gunicorn.conf.py`，不要直接沿用 Gunicorn 默认 30 秒超时
- 当前多轮记忆保存在进程内，生产环境建议先保持单 worker；如果要扩容，需要把对话历史改到 Redis 或数据库
- Gunicorn 监听 `127.0.0.1:5000`
- Nginx 对外监听 `80`
- 阿里云安全组放行 `22` 和 `80`

一个更稳妥的启动示例：

```bash
cd /opt/llmrag
source .venv/bin/activate
export FLASK_ENV=prod
pip install -r requirements-prod.txt
gunicorn -c gunicorn.conf.py wsgi:app
```

如果页面上看到的是 `Internal Server Error`，先直接看 Gunicorn 日志，常见是以下两类：

- 请求超过 30 秒，被 Gunicorn 默认超时杀掉
- 服务器资源偏小，多 worker 重复加载向量索引后内存紧张或 worker 被回收

## 已知注意事项

- 当前配置文件中如果直接写入真实密钥，存在泄露风险。
- 当前启动入口适合开发调试，不适合作为生产启动命令。
- `requirements.txt` 如在 Windows 下以 Unicode 编码保存，上传到 Linux 后建议先确认编码和换行符正常。
