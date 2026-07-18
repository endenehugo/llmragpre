# LLM RAG Agent 智能问答平台

> **独立开发** | 2025.02 — 2025.06
>
> 基于 LangChain + Flask 的 Agent 驱动问答系统，实现 ReAct 范式的工具调用链路、多模态 Agent 与 RAG 增强检索，已部署至阿里云 ECS 生产环境。
>
> **GitHub**：`<你的仓库链接>`
>
> **线上地址**：`http://47.92.74.156`

---

## 技术栈

`Python` `LangChain` `LangChain-Core` `Pydantic` `FAISS` `DashScope API` `Flask` `MySQL` `SQLAlchemy` `Gunicorn` `Nginx` `Linux`

---

## 项目详情

### 1. Agent 架构与 ReAct 推理循环

- 基于 LangChain **`bind_tools`** 实现 Function Calling Agent，LLM 根据用户意图自主决策工具选择与参数生成
- 手写 **ReAct 推理循环**（最多 3 轮迭代）：模型推理 → 返回 `tool_calls` → 执行工具 → `ToolMessage` 回传上下文 → 继续推理 → 输出最终答案
- 流程终止条件：模型返回的 `tool_calls` 为空 → 认为信息充分 → 输出最终回答；超过 3 轮 → 兜底返回

```
用户提问 → System Prompt（含工具描述 + RAG 上下文）
    ↓
LLM 推理 → 返回 AIMessage（含 tool_calls？）
    ├── 无 tool_calls → 输出最终答案 ✅
    └── 有 tool_calls → 遍历执行工具
                            ↓
                    ToolMessage 回传消息列表
                            ↓
                    下一轮 LLM 推理（继续上述判断）
```

### 2. 工具设计与开发

三个自定义工具，均继承 LangChain `BaseTool`，使用 **Pydantic `BaseModel`** 定义 `args_schema` 参数校验：

| 工具 | 能力 | 关键实现 |
|---|---|---|
| `WebSearchTool` | 调用秘塔搜索 API，联网获取网页信息 | 结构化提取标题/摘要/链接/日期，Top-5 去噪；处理网络超时、API 错误码、空结果等异常路径 |
| `WordDocumentTool` | 将内容整理输出为 .docx 文档 | 使用 `python-docx` 自动排版（Heading + 段落拆分），输出到指定目录并返回保存路径 |
| `MultiplyTool` | 乘法计算 | 简单工具，用于验证多工具并行调用的正确性 |

**工具注册方式**：

```python
tools = [MultiplyTool(), WebSearchTool(), WordDocumentTool()]
self.tool_dic = {tool.name: tool for tool in tools}  # 按 name 快速查找
self.agent_llm = self.qa_llm.bind_tools(tools)        # 绑定到模型
```

每个工具定义三要素：
- `name`：模型匹配工具的唯一标识
- `description`：自然语言描述，引导模型判断何时使用
- `args_schema`：Pydantic 模型，`Field(description=...)` 让模型准确理解参数语义

### 3. Agent + RAG 混合架构

- Agent 模式下**自动注入检索上下文**：调用前先用用户 query 从 FAISS 向量库召回知识片段，拼入 System Prompt 的 `context` 字段
- 检索设计了**双层兜底策略**：
  - 第一层：`similarity_score_threshold`（阈值 0.35）检索
  - 第二层：阈值检索为空时，回退到无阈值 `similarity` 检索，解决短文本概述/文件名提问场景下召回失败的问题
- 文档上传后**自动重建会话级 FAISS 索引**：文本分块（chunk_size=700, overlap=120）+ 文件名锚点注入，确保 `"总结 test.docx 内容"` 这类 query 能准确命中

### 4. 多模态 Agent

- 检测到 `image_urls` 参数时，**自动切换多模态路由**：跳过纯文本 Agent 链路，构造多模态消息
- 图片以 `{"image": local_path}` 格式塞入 `HumanMessage` content 列表，同时注入 RAG 检索文本与对话历史
- 历史消息中的图片 Markdown（`![image](url)`）被解析并**重建为多模态格式**，保证跨轮对话中图片上下文不丢失
- 使用 **`qwen-vl-plus`** 视觉模型，响应内容兼容 `str` / `list[dict]` 两种格式的解析

### 5. 工程设计与部署

- **分层架构**：`handler → service → repository`，核心 Agent 逻辑集中在 `ConversationChatService`
- **依赖注入**：Flask-Injector 管理服务实例，松耦合便于测试
- **多环境配置**：`FLASK_ENV` 环境变量切换 dev/test/pre/prod，敏感信息通过环境变量注入
- **会话持久化**：MySQL 三表设计（conversation / message / document），支持历史会话列表、详情查看、跨会话切换
- **生产部署**：阿里云 ECS（Ubuntu 24.04）+ Gunicorn（gthread）+ Nginx 反向代理 + systemd 进程守护
- 针对 LLM 长响应场景：Gunicorn `timeout=180s`，Nginx `proxy_read_timeout=300s`

---

## 面试准备：Agent 高频问题

### Q1：你项目的 Agent 是怎么实现的？ReAct 流程是怎样的？

使用 LangChain 的 `bind_tools` 将三个自定义 Tool 绑定到 `qwen-plus` 模型。用户提问后，System Prompt 告知模型可用工具及其使用场景，模型推理返回 `tool_calls`（JSON：工具名 + 参数）。核心循环：

1. `llm.invoke(messages)` → 返回 `AIMessage`
2. 检查 `response.tool_calls`：为空则输出答案，非空则继续
3. 遍历 tool_calls，从 `tool_dic` 按 name 查找工具，执行 `tool.invoke(args)`
4. 结果封装为 `ToolMessage(tool_call_id=..., content=...)` append 到消息列表
5. 回到步骤 1，最多 3 轮

### Q2：工具是怎么设计注册的？参数校验怎么做？

继承 LangChain `BaseTool`，定义 `name`、`description`、`args_schema`。`args_schema` 用 Pydantic `BaseModel` + `Field(description=...)`，模型根据 description 理解参数语义并生成合法 JSON。注册时 `llm.bind_tools(tools)`，LangChain 自动将工具定义转为模型 API 的 functions 格式。

### Q3：为什么最多 3 轮？遇到过死循环吗？

3 轮是经验值——大部分问题 1-2 轮工具调用就够。上限防止模型在"搜不到→再搜→还搜不到"之间反复消耗 token，同时控制单次请求延迟。实际使用中模型在信息充足时会自然停止（无 tool_calls），未出现死循环。

### Q4：Agent 怎么和 RAG 结合的？

在构造 prompt 前先走 RAG 检索：query → FAISS 召回 Top-K 文本 → 拼入 System Prompt 的 `context` 字段。这样 Agent 做工具调用决策时已具备领域知识——比如用户问"这个产品的竞品是谁"，Agent 先看到业务文档内容，再决定是否需要联网补充。

### Q5：多模态是怎么处理的？

检测到 `image_urls` 非空时，跳过纯文本 Agent 链路，改为构造多模态消息：`[{"image": path}, {"text": "文档上下文+用户问题"}]` 放入 `HumanMessage.content`，调用 `qwen-vl-plus`。历史消息中的图片标记（`![image](url)`）也会解析并重建为多模态格式，保证上下文连续。

### Q6：如果要优化这个 Agent，你会怎么做？

1. 引入 **LangGraph** 替代手写 for 循环，用状态图管理推理→工具调用分支，可观测性更好
2. 加入**工具调用结果缓存**，相同 query + 相同工具短期内不重复请求
3. 支持**并行工具调用**——当模型一次返回多个无关 tool_calls 时并发执行
4. 加入 **Human-in-the-loop**，高风险操作（如覆盖文件）先确认
5. 接入 **LangFuse / LangSmith** 追踪每次 Agent 的 token 消耗、延迟、工具调用链

---

## 自我评价 / 技能标签

```
- Agent 开发：LangChain Function Calling / ReAct 推理循环 / Tool 设计与注册 / ToolMessage 上下文回传
- RAG：FAISS 向量检索 / Embedding / 分块策略 / 相似度阈值 + 兜底召回
- 多模态：qwen-vl-plus 图文混合输入 / 多模态消息构造 / 历史图片上下文重建
- 工程：Flask 分层架构 / MySQL + SQLAlchemy / Gunicorn + Nginx / 阿里云部署
```

---

## 一句话介绍

独立开发 Agent 驱动的 RAG 智能问答平台，实现 ReAct 工具调用链路与多模态 Agent，已部署至阿里云生产环境。
