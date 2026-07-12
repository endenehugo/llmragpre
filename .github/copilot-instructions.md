# Copilot Instructions

## 本地安装、启动与测试

```powershell
pip install -r requirements.txt
python run.py
```

仓库里还保留了更轻量的生产依赖清单，但日常开发默认使用 `requirements.txt`。

单个 Python 测试优先直接用 `unittest` 运行对应模块：

```powershell
python -m unittest app.test_tools.test_document_index_service
python -m unittest app.test_tools.test_image_multimodal_service
```

前端回归脚本是独立的 Node 脚本：

```powershell
node test_tools/test_frontend_message_render.js
```

## 高层架构

- 应用入口在 `app/__init__.py`：先加载 `.env` 与 `FLASK_ENV` 对应配置，再初始化 CORS、注入环境变量、初始化 `ResourceUtils`，最后通过 `app.router.Router` 注册所有 Flask 路由。
- `run.py` 是本地开发入口，启动前会先执行 `app.utils.api_key_checker.check_all()`；如果本地启动异常，先看 Key 检测输出，而不是只盯 Flask 日志。
- 请求主链路基本是 `router -> handler -> service -> repository/utils`：
  - `app/handler/` 负责 HTTP 参数校验与统一响应格式。
  - `app/services/` 负责对话编排、文档解析、索引重建、会话存储。
  - `app/repository/` 负责 MySQL 持久化，`DatabaseManager.ensure_tables()` 会在首次建 session 时自动建表。
- 这个仓库同时存在两套问答入口：
  - `/chat/*` 是较早的单轮/多轮/RAG/Agent 接口。
  - `/conversation/*` 是当前更完整的会话流，带 MySQL 持久化、历史消息、文档绑定、图片上传与多模态问答。
  后续改功能时，优先确认改的是哪一套链路，不要只改 `/chat/*` 而漏掉 `/conversation/*`。
- 会话文档问答的核心链路是：
  1. `DocumentHandler.upload` 保存文件并调用 `DocumentParserService`
  2. 解析后的纯文本落到 `resources/parsed_docs`
  3. `DocumentIndexService.rebuild_conversation_index` 为该会话重建 `resources/faiss_index_uploads/<conversation_id>` 下的 FAISS 索引
  4. `ConversationChatService.chat` 在 `agent/rag` 模式下先取会话索引上下文，再决定调用普通问答链还是工具链
- 公共知识库与会话知识库是分开的：
  - 会话上传文档优先走 `resources/faiss_index_uploads`
  - 没有召回到会话文档时，才回退到公共 `resources/faiss_index`
- 图片问答走单独分支：`/conversation/chat` 只要 `image_urls` 非空，就会切到 `ConversationChatService._invoke_multimodal()`，使用多模态模型回答，不再走 Agent 工具调用链。

## 关键约定

- `ResourceUtils` 是资源目录访问的统一入口，所有索引、上传文件、解析文本、生成文档都应通过它定位到 `resources/`；在未执行 `ResourceUtils.init_app(app)` 前不要直接使用。
- 文档“上传成功/状态为 indexed”不代表问答一定能命中文档内容。这个仓库已经在 `DocumentIndexService` 里固化了两条检索约定：
  - 会话检索先走 `similarity_score_threshold`，空结果时再回退到无阈值 `similarity`
  - 写入向量库的文本会带上 `文件名：xxx` 前缀，支持用户按文件名提问
  如果修改文档索引策略，要同时检查这两条行为是否仍然成立。
- `ConversationChatService` 会把带图消息存成 Markdown 形式的 `![image](...)`；文本模式构建历史时再把图片 Markdown 去掉。改历史拼接、标题生成、消息展示时要注意这个约定，否则容易把图片占位符误当正文。
- `ConversationHandler` 对 `conversation_id`、图片文件名、`image_urls` 做了比较严格的白名单校验；新增图片相关接口时，复用现有安全规则，不要绕开 `/conversation/image/<conversation_id>/<filename>` 这一路径约定。
- 配置切换完全依赖 `FLASK_ENV`，并统一从 `config/config_{env}.py` 读取；开发时如果需要复现配置差异，优先切环境而不是在代码里写死分支。
- Windows 开发环境下，`app/__init__.py` 会在 `dev/test` 环境自动设置 `KMP_DUPLICATE_LIB_OK=TRUE`，这是为了减少本地 FAISS / OpenMP 相关冲突。涉及向量检索或本地调试问题时，先确认当前环境是否走到了这段初始化逻辑。
- 前端没有完整的打包流程；`test_tools/test_frontend_message_render.js` 是对静态脚本行为的回归检查。修改 `app/static/js/index.js`、`conversation_index.js`、`credentials.js` 后，记得跑这条脚本。
