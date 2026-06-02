# LLM RAG 文档上传与会话管理开发文档

## 1. 背景与目标

当前项目已经具备以下能力：

- Flask 路由和 Handler 分层结构已经稳定，可继续沿用。
- Agent、Memory、RAG 三类问答入口已经存在，但会话记忆仍是进程内状态，服务重启后丢失。
- 前端页面只有单个聊天面板，没有“新建对话”“历史对话列表”“文档上传区”。
- 项目已经具备 Word 文档生成功能，但没有“接收并解析用户上传文档”的能力。

本次开发目标是让项目支持以下四类用户能力：

- 上传并解析 Word、PDF、TXT 文档。
- 将上传文档纳入检索上下文，支持基于文档内容问答。
- 支持新建对话。
- 支持查看历史对话并切换会话继续聊天。

本阶段采用“MySQL 持久化会话数据 + 本地文件存储 + 本地向量索引 + Flask API”的方案，以保证历史会话可持久化、可查询、可扩展，同时控制对现有项目结构的改造范围。

## 2. 现状评估

结合当前代码，已有可复用基础如下：

- 路由注册统一在 app/router/router.py 中完成，新增接口可以继续放在这里。
- 各能力通过 app/handler 下的 Handler 暴露，适合继续新增 upload、conversation、history 相关 Handler。
- app/utils/ResourceUtils 已经用于 resources 路径管理，适合继续管理上传文件、解析文本和向量索引目录。
- app/handler/chat_agent_handler.py 和 app/handler/chat_rag_handler.py 已经具备向量检索链路，可复用“文档入库后的检索能力”。
- resources/generated_docs 已经用于输出 Word，说明项目已经接受“本地文件作为资源目录”的组织方式。

当前主要缺口如下：

- 没有文件上传接口。
- 没有文档解析层。
- 没有会话持久化层。
- 没有会话列表接口。
- 前端没有会话侧边栏与上传控件。
- 现有 MemoryHandler、RagHandler、AgentHandler 都把 memory 放在单实例里，无法按 conversation_id 隔离。

## 3. 方案选型

### 方案 A：MySQL 持久化会话 + 本地文件存储 + 本地 FAISS 索引

- 上传文件保存到 resources/uploads。
- 解析后的纯文本保存到 resources/parsed_docs。
- 会话、消息、文档元数据保存到 MySQL。
- 文档切片后写入单独的 FAISS 索引目录。
- 适合当前项目，改造成本最低。

优点：

- 历史会话和消息查询稳定，服务重启不丢数据。
- 便于后续增加分页、搜索、筛选和用户维度扩展。
- 文件资源和结构化数据边界清晰。

缺点：

- 需要新增数据库连接、表结构和初始化流程。
- 需要处理事务、一致性和连接池配置。

### 方案 B：本地文件持久化会话 + 本地 FAISS 索引

- 会话和消息继续写本地 JSON 文件。
- 文档文件仍保存本地。
- 文档向量仍使用 FAISS。

优点：

- 改造最少。
- 不依赖数据库环境。

缺点：

- 并发能力弱。
- 不利于后续扩展多用户和复杂查询。

### 方案 C：对象存储 + MySQL + 向量数据库 + 独立会话服务

- 适合中长期平台化。
- 不适合作为当前版本的第一步。

推荐结论：

- 第一阶段采用方案 A。
- 如果部署环境暂时无法提供 MySQL，再退回方案 B 作为临时过渡。

## 4. 范围定义

本次开发范围包含：

- 支持上传 .txt、.pdf、.docx。
- 支持兼容 .doc 文件名，但第一阶段不承诺原生解析旧版 .doc 二进制文档。
- 支持创建、列出、查看、继续会话。
- 支持把某个会话绑定到一个或多个上传文档。
- 支持基于会话下的文档进行 RAG 问答。
- 前端支持新建对话、历史列表、文档上传、切换会话。

本次开发范围不包含：

- 多用户登录鉴权。
- 云端对象存储。
- 大规模向量索引分片。
- 复杂权限模型。

## 5. 文档格式支持策略

### TXT

- 直接按 UTF-8 优先读取。
- 如果 UTF-8 失败，尝试 GBK。
- 解析结果直接进入文本切片流程。

### PDF

- 建议引入 pypdf。
- 逐页提取文本并合并。
- 对空白页、扫描版 PDF 返回明确错误信息。

### DOCX

- 优先复用项目已存在依赖 docx2txt。
- 如需更稳定结构化读取，也可使用 python-docx 读取段落。

### DOC

- 第一阶段建议策略是“识别扩展名但返回明确提示：请另存为 .docx 后上传”。
- 原因是旧版 .doc 解析在 Windows 环境下通常依赖额外组件，接入复杂度明显高于当前项目需要。
- 如果业务必须支持 .doc，再单独增加 LibreOffice 转换链路或专门解析组件。

结论：

- 当前版本实际落地支持 .txt、.pdf、.docx。
- 对 .doc 做友好降级提示，而不是伪支持。

## 6. 目标目录结构

建议新增或扩展如下目录：

- resources/uploads 用于保存原始上传文件。
- resources/parsed_docs 用于保存解析后的纯文本。
- resources/faiss_index_uploads 用于保存上传文档专用索引。
- app/services 用于承载上传解析、会话存储、索引服务。
- app/repository 用于承载 MySQL 数据访问。
- app/handler/document_handler.py 用于上传接口。
- app/handler/conversation_handler.py 用于会话接口。

建议的文件组织如下：

- app/services/document_parser_service.py
- app/services/document_index_service.py
- app/services/conversation_store_service.py
- app/services/conversation_chat_service.py
- app/repository/mysql_base.py
- app/repository/conversation_repository.py
- app/repository/message_repository.py
- app/repository/document_repository.py
- app/handler/document_handler.py
- app/handler/conversation_handler.py

## 7. 数据模型设计

### 会话对象 conversation

```json
{
  "id": "conv_20260602_001",
  "title": "新对话",
  "mode": "agent",
  "created_at": "2026-06-02T10:00:00+08:00",
  "updated_at": "2026-06-02T10:15:00+08:00",
  "document_ids": ["doc_001", "doc_002"],
  "message_count": 6,
  "last_message_preview": "请总结这份文档的主要结论"
}
```

### 消息对象 message

```json
{
  "id": "msg_001",
  "role": "user",
  "content": "请总结上传文档",
  "created_at": "2026-06-02T10:16:00+08:00"
}
```

### 文档对象 document

```json
{
  "id": "doc_001",
  "conversation_id": "conv_20260602_001",
  "original_name": "方案说明.pdf",
  "stored_name": "conv_20260602_001_doc_001.pdf",
  "file_type": "pdf",
  "status": "indexed",
  "char_count": 18240,
  "created_at": "2026-06-02T10:05:00+08:00"
}
```

### MySQL 表设计建议

建议使用以下三张核心表：

- conversations
- conversation_messages
- conversation_documents

建议字段如下。

conversations：

```sql
CREATE TABLE conversations (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  conversation_id VARCHAR(64) NOT NULL UNIQUE,
  title VARCHAR(255) NOT NULL,
  mode VARCHAR(32) NOT NULL DEFAULT 'agent',
  message_count INT NOT NULL DEFAULT 0,
  last_message_preview VARCHAR(500) NOT NULL DEFAULT '',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_conversations_updated_at (updated_at)
);
```

conversation_messages：

```sql
CREATE TABLE conversation_messages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  message_id VARCHAR(64) NOT NULL UNIQUE,
  conversation_id VARCHAR(64) NOT NULL,
  role VARCHAR(32) NOT NULL,
  content LONGTEXT NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX idx_messages_conversation_id_created_at (conversation_id, created_at)
);
```

conversation_documents：

```sql
CREATE TABLE conversation_documents (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  document_id VARCHAR(64) NOT NULL UNIQUE,
  conversation_id VARCHAR(64) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  stored_name VARCHAR(255) NOT NULL,
  stored_path VARCHAR(500) NOT NULL,
  parsed_text_path VARCHAR(500) NOT NULL,
  file_type VARCHAR(16) NOT NULL,
  status VARCHAR(32) NOT NULL,
  char_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  INDEX idx_documents_conversation_id_created_at (conversation_id, created_at)
);
```

说明：

- 第一阶段可以不强制加外键，优先保证部署简单和迁移直接。
- 如果后续需要更强一致性，可为 messages 和 documents 增加 conversations 的外键约束。
- conversation_id 保留业务主键，便于前后端直接交互，不暴露自增 id。

## 8. API 设计

### 8.1 新建会话

- 方法：POST
- 路径：/conversation/create

请求体：

```json
{
  "title": "产品知识库对话",
  "mode": "agent"
}
```

返回：

```json
{
  "code": 200,
  "message": "创建成功",
  "data": {
    "conversation_id": "conv_20260602_001"
  }
}
```

### 8.2 查询会话列表

- 方法：GET
- 路径：/conversation/list

返回最近会话摘要列表，不返回全部消息正文。数据来源改为 MySQL conversations 表，按 updated_at 倒序查询。

### 8.3 查询单个会话详情

- 方法：GET
- 路径：/conversation/detail
- 参数：conversation_id

返回指定会话的元信息、文档列表和消息列表。后端分别查询 conversations、conversation_documents、conversation_messages 三张表并聚合返回。

### 8.4 上传文档

- 方法：POST
- 路径：/document/upload
- Content-Type：multipart/form-data

表单字段：

- conversation_id
- file

返回：

- 文档元数据
- 解析状态
- 入索引状态
- 失败时的明确错误原因

### 8.5 基于会话对话

- 方法：POST
- 路径：/conversation/chat

请求体：

```json
{
  "conversation_id": "conv_20260602_001",
  "query": "请总结刚上传的 PDF 核心观点",
  "mode": "agent"
}
```

说明：

- conversation_id 用于定位历史消息和绑定文档。
- mode 可选 agent、rag、memory，默认 agent。
- 后端应优先从会话绑定的上传文档索引中检索，再补充公共知识库。

### 8.6 删除文档

- 方法：POST
- 路径：/document/delete

说明：

- 从会话元数据中解除绑定。
- 删除原始文件、解析文本和对应索引记录。
- 第一阶段可先不做物理索引增量删除，采用“重建该会话索引”的简单策略。

## 9. 后端设计

### 9.1 文档解析服务

DocumentParserService 负责：

- 校验扩展名。
- 保存原始文件。
- 根据类型调用 parse_txt、parse_pdf、parse_docx。
- 输出纯文本。
- 返回字符数、错误信息、解析耗时。
- 在文档解析成功后，将文档元数据写入 MySQL。

建议接口：

```python
class DocumentParserService:
    def save_and_parse(self, conversation_id: str, storage_file) -> dict:
        ...
```

返回结构至少包含：

- document_id
- original_name
- stored_path
- parsed_text_path
- file_type
- content
- char_count

### 9.2 索引服务

DocumentIndexService 负责：

- 将解析后的文本切分为 chunk。
- 使用 DashScopeEmbeddings 生成向量。
- 按 conversation_id 维度维护 FAISS 索引。
- 检索时只命中当前会话绑定的上传文档。

推荐策略：

- 每个会话一个索引目录，例如 resources/faiss_index_uploads/conv_xxx。
- 这样最容易做删除、重建和隔离。
- 文档是否已入索引由 conversation_documents.status 字段标记。

切片参数建议：

- chunk_size: 500 到 800
- chunk_overlap: 100 到 150

### 9.3 会话存储服务

ConversationStoreService 负责：

- create_conversation
- list_conversations
- get_conversation
- append_message
- bind_document
- update_summary_fields

关键要求：

- 基于 MySQL 事务写入，避免消息落库一半成功一半失败。
- append_message 时同步更新 conversations.updated_at、message_count、last_message_preview。
- 会话列表按 updated_at 倒序返回。
- 上传文档成功后插入 conversation_documents 记录，并更新 conversations.updated_at。

建议接口进一步细化为：

```python
class ConversationStoreService:
  def create_conversation(self, title: str, mode: str) -> dict:
    ...

  def list_conversations(self, limit: int = 50) -> list[dict]:
    ...

  def get_conversation_detail(self, conversation_id: str) -> dict:
    ...

  def append_message_pair(self, conversation_id: str, user_content: str, assistant_content: str) -> None:
    ...
```

### 9.4 会话聊天服务

ConversationChatService 负责：

- 读取会话历史消息。
- 读取当前会话的文档索引。
- 拼装 prompt。
- 调用 agent 或 rag。
- 将用户消息与助手消息落盘。

建议不要继续直接复用当前 Handler 内部的单例 memory 对象，而是改为：

- 从 MySQL 的 conversation_messages 表中取历史消息。
- 在调用模型前临时构造 MessagesPlaceholder 所需 history。
- 回答完成后通过事务写回 MySQL。

这样可以彻底解决“不同会话共享同一个内存上下文”的问题。

### 9.5 MySQL 连接与配置

建议新增以下配置项：

```python
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "your_password"
MYSQL_DATABASE = "llmrag"
MYSQL_CHARSET = "utf8mb4"
MYSQL_POOL_SIZE = 5
MYSQL_POOL_RECYCLE = 3600
```

建议技术选型：

- 使用 SQLAlchemy 作为数据库访问层。
- 使用 PyMySQL 作为 MySQL 驱动。

推荐连接串格式：

```text
mysql+pymysql://MYSQL_USER:MYSQL_PASSWORD@MYSQL_HOST:MYSQL_PORT/MYSQL_DATABASE?charset=utf8mb4
```

原因：

- 比直接拼接原生 SQL 更容易维护连接池和事务。
- 后续如果要增加用户表、标签表、权限表，扩展成本更低。

## 10. 前端设计

### 10.1 页面结构调整

当前页面左侧是静态介绍区，建议改为“会话侧边栏 + 上传入口”。

左侧区域应包含：

- 新建对话按钮。
- 历史对话列表。
- 当前会话绑定文档列表。
- 上传按钮。

右侧区域保留：

- 消息列表。
- 输入框。
- 发送按钮。

### 10.2 前端状态

index.js 需要新增以下状态：

- currentConversationId
- conversationList
- currentConversationMessages
- currentConversationDocuments

### 10.3 前端交互流程

首次进入页面：

- 调用 /conversation/list。
- 如果无会话，自动创建一个新会话。
- 如果有会话，默认打开最近一次会话。

点击“新建对话”：

- 调用 /conversation/create。
- 将新会话插入列表顶部。
- 清空当前聊天区并切换上下文。

点击历史会话：

- 调用 /conversation/detail。
- 渲染消息列表和文档列表。

上传文档：

- 选中文件后上传到 /document/upload。
- 成功后刷新当前会话文档列表。
- 提示“文档已入库，可直接提问”。

发送消息：

- 当前请求从 /chat/agent 改为 /conversation/chat。
- 请求体中携带 conversation_id。
- 成功后本地追加消息，并同步服务端返回的会话状态。

## 11. 代码改造点

### 必改文件

- app/router/router.py
- app/templates/index.html
- app/static/js/index.js
- app/static/css/style.css
- requirements.txt
- config/config_dev.py
- config/config_test.py
- config/config_pre.py
- config/config_prod.py

### 新增文件

- app/handler/document_handler.py
- app/handler/conversation_handler.py
- app/services/document_parser_service.py
- app/services/document_index_service.py
- app/services/conversation_store_service.py
- app/services/conversation_chat_service.py
- app/repository/mysql_base.py
- app/repository/conversation_repository.py
- app/repository/message_repository.py
- app/repository/document_repository.py

### 可能调整文件

- app/handler/chat_agent_handler.py
- app/handler/chat_rag_handler.py
- app/handler/chat_memory_handler.py
- app/utils/resouce_utils.py
- app/__init__.py
- README.md

改造原则：

- 尽量不要继续把“会话状态”存在 Handler 实例字段里。
- 会话状态全部下沉到 service 层和 MySQL。
- Handler 只负责参数校验、调用 service、封装响应。

## 12. 依赖建议

建议补充：

- pypdf 用于 PDF 解析。
- SQLAlchemy 用于 MySQL 访问。
- PyMySQL 用于 MySQL 驱动。

现有可复用：

- docx2txt
- python-docx
- langchain
- langchain-community
- faiss-cpu

## 13. 开发阶段拆分

### 第一阶段：会话持久化闭环

- 新增 conversation create、list、detail 接口。
- 完成 MySQL 连接配置、建表脚本和 repository 层。
- 前端支持新建会话和查看历史。
- 聊天接口切换到 conversation_id 驱动。

交付标准：

- 浏览器刷新后仍能看到历史会话。
- 不同会话不会串上下文。
- MySQL 中可以查询到 conversations 和 conversation_messages 数据。

### 第二阶段：文档上传与解析闭环

- 新增 document upload 接口。
- 支持 txt、pdf、docx。
- 文档解析结果保存为纯文本。

交付标准：

- 上传成功后能在会话内看到文档条目。
- 错误格式或空文档能返回明确提示。

### 第三阶段：会话级 RAG 检索闭环

- 建立会话级 FAISS 索引。
- conversation chat 优先检索会话文档。
- 保留公共知识库作为兜底上下文。

交付标准：

- 用户问“刚上传的文档讲了什么”时能命中文档内容。
- 不同会话上传不同文档时，检索结果相互隔离。

### 第四阶段：体验完善

- 文档上传进度和状态提示。
- 历史对话标题自动摘要。
- 删除文档和重建索引。

## 14. 测试方案

### 单元测试

- TXT 解析测试。
- PDF 解析测试。
- DOCX 解析测试。
- MySQL 会话读写测试。
- 会话列表排序测试。
- conversation_id 隔离测试。
- 事务回滚测试。

### 接口测试

- 创建会话。
- 列出会话。
- 查询会话详情。
- 上传 txt。
- 上传 pdf。
- 上传 docx。
- 使用 conversation_id 发起聊天。

### 前端测试

- 新建会话后列表即时刷新。
- 切换历史会话后消息区正确重绘。
- 上传文档后文档列表刷新。
- 刷新页面后仍能恢复最近会话。

### 验收测试

- 用户创建会话 A，上传产品手册 PDF，提问后命中手册内容。
- 用户再创建会话 B，上传另一份 TXT，提问时不应混入会话 A 的内容。
- 页面刷新后，会话 A 和 B 都能在历史列表中展示。

## 15. 风险与注意事项

- 当前项目使用单进程内存记忆，必须改为按 conversation_id 读取历史消息，否则会发生串话。
- PDF 解析质量取决于原文件是否可提取文本，扫描件需要 OCR，这不在本期范围内。
- .doc 旧格式不建议在本期直接承诺支持，应在产品文案里写清楚“建议上传 .docx”。
- FAISS 索引写入过程较重，上传后可以先串行处理，后续再考虑异步任务。
- MySQL 连接池、字符集和时区需要统一配置，否则容易出现中文乱码和时间排序异常。
- 上传文件写本地、元数据写 MySQL 属于跨介质操作，失败补偿逻辑必须明确，例如“文件已保存但数据库写入失败时自动清理文件”。
- 如果继续使用 Gunicorn 多 worker，MySQL 一致性问题较小，但 FAISS 索引写入仍需要串行控制或重建策略。

## 16. 推荐实施顺序

建议按以下顺序开发：

1. 先完成 conversation 持久化接口和前端历史列表。
2. 同步完成 MySQL 配置、建表脚本和基础 repository 层。
3. 再完成 document upload 和解析。
4. 然后把 conversation chat 接到会话级检索。
5. 最后补删除、重建索引和体验优化。

## 17. 里程碑验收口径

满足以下条件即可认为第一版完成：

- 页面可新建对话。
- 页面可查看并切换历史对话。
- 用户可上传 txt、pdf、docx。
- 系统能基于当前会话上传文档回答问题。
- 不同会话之间历史消息和文档上下文互不污染。
- 服务重启后历史会话仍可查看。
- MySQL 中可以查到完整的会话、消息、文档元数据记录。

## 18. 推荐下一步

基于当前仓库，建议下一步直接进入实现计划编写，输出更细的任务拆解，精确到每个文件怎么改、每步先写什么测试、每步如何验证。