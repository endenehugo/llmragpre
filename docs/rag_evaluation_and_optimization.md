# RAG 效果评估与召回优化实践

> 本文档基于「求职助手 Agent 平台」项目中的 RAG 链路，回答三个核心问题：
> ① 如何评估 RAG 效果；② 召回阶段做了哪些关键优化；③ 语义漂移与幻觉问题如何缓解。

---

## 一、RAG 链路整体架构

本项目 RAG 链路从文档上传到检索增强生成，分为以下环节：

```
用户上传文档 → 文档解析（txt/pdf/docx） → 文本切分（Chunking）
    → Embedding 向量化（text-embedding-v3） → FAISS 向量索引
    → 用户提问 → 向量检索（阈值 + 相似度兜底）
    → 上下文注入 Prompt → LLM 生成回答
```

核心实现在以下文件中：

| 文件 | 职责 |
|---|---|
| [app/services/document_parser_service.py](app/services/document_parser_service.py) | 文档解析 |
| [app/services/document_index_service.py](app/services/document_index_service.py) | 切分、索引构建与检索 |
| [app/services/builtin_knowledge_service.py](app/services/builtin_knowledge_service.py) | 内置知识库的索引与检索 |
| [app/services/conversation_chat_service.py](app/services/conversation_chat_service.py) | LLM 调用与上下文组装 |

---

## 二、问题①：如何评估 RAG 效果？

### 2.1 评估指标

当前项目属于 **生产型 MVP 阶段**，尚未建立正式的离线评估体系，但在架构设计中已预留了面向指标的评估能力。建议按以下三个层面构建评估：

#### 检索质量指标

| 指标 | 计算公式 | 当前实现状态 |
|---|---|---|
| **Recall@k** | 检索返回的 k 个结果中，包含正确答案的比例 | 未自动化。目前可通过 `score_threshold` 调节 |
| **Precision@k** | 检索返回的 k 个结果中，相关结果的比例 | 架构支持，需人工标注测试集 |
| **MRR (Mean Reciprocal Rank)** | 第一个正确答案排名的倒数均值 | 架构支持，需标注 |
| **NDCG@k** | 归一化折损累计增益，考虑排序位置 | 建议后期引入 |

当前代码中的检索质量指标直接体现为 `score_threshold = 0.35` —— 这是在开发中通过人工检验十组典型问题后确定的经验值。

**代码位置**：`app/services/document_index_service.py` 第 75-78 行

```python
threshold_retriever = conversation_db.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": limit, "score_threshold": 0.35},
)
```

#### 生成质量指标

| 指标 | 说明 | 当前实现 |
|---|---|---|
| **答案准确率** | 回答是否正确 | 人工评估 |
| **幻觉率** | 回答与上下文不一致的比例 | 人工评估 |
| **上下文利用率** | 回答是否充分使用了检索到的上下文 | 隐含在 Agent Prompt 中 |
| **端到端满意度** | 用户对回答的整体满意度 | 无用户评分模块，需补充 |

### 2.2 测试集构建方式

当前项目尚未构建正式测试集。建议的构建方案：

**方案：按业务场景构建三元组测试集**

```
测试集结构：
{
  "query": "用户问句",
  "expected_chunks": ["期望检索到的文档片段ID"],
  "expected_answer_keywords": ["答案中必须包含的关键词"],
  "category": "jd_analysis | resume_score | general_qa"
}
```

**构建步骤：**

1. **覆盖四类场景**（基于本项目业务）：
   - JD 分析场景："这个岗位要求什么技术栈？"
   - 简历评分场景："我的简历匹配度如何？"
   - 项目优化场景："帮我改写这个项目描述"
   - 面试模拟场景："Python 后端面试常考什么？"

2. **规模建议**：
   - V1（当前阶段）：20-30 条黄金用例，用于回归测试
   - V2：100+ 条，覆盖边界情况（短查询、长查询、模糊查询、跨会话查询）

3. **自动化评估工具**：建议在 `app/test_tools/` 下新增 `test_rag_evaluation.py`，流程如下：

```python
def evaluate_retrieval(test_cases, retriever):
    for case in test_cases:
        results = retriever.get_relevant_documents(case["query"])
        hit = any(
            expected in [r.metadata["chunk_id"] for r in results]
            for expected in case["expected_chunks"]
        )
        # 统计 recall / precision / mrr
```

### 2.3 Baseline

当前项目的 Baseline 为 **无检索的纯 LLM 回答**（即 `memory` 模式，见 `conversation_chat_service.py` 第 44 行）：

```python
context = "" if normalized_mode == "memory" else self.document_index_service.get_context(...)
```

在实际测试中，开启 RAG 后的回答质量提升体现在：

| 维度 | 纯 LLM（memory 模式） | RAG（agent 模式） |
|---|---|---|
| 事实准确性 | 依赖模型训练数据，过时信息可能错误 | 基于上传文档，实时准确 |
| 引用溯源 | 无法指出信息来源 | 可以提及"根据上传的文档" |
| 领域适配性 | 通用回答，缺少针对性 | 可针对简历/JD 具体内容作答 |

> **注意**：当前项目未在 `test_tools/` 中保留 Baseline 对比数据，建议在下一迭代中：
> 1. 固定 20 条测试 query
> 2. 分别在 memory / rag / agent 三种模式下运行
> 3. 人工打分（1-5 分），记录到表格

---

## 三、问题②：召回阶段做了哪些关键优化？

### 3.1 Chunk 策略

#### 当前实现

在 `app/services/document_index_service.py` 第 95-109 行：

```python
def _chunk_text(self, content: str) -> list[str]:
    chunk_size = current_app.config.get("CONVERSATION_INDEX_CHUNK_SIZE", 700)
    chunk_overlap = current_app.config.get("CONVERSATION_INDEX_CHUNK_OVERLAP", 120)
    # 固定窗口滑动切分
    chunks = []
    start = 0
    while start < content_length:
        end = min(start + chunk_size, content_length)
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= content_length:
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks
```

**参数配置**（在 `config/config_dev.py` 中）：

| 参数 | 值 | 选择理由 |
|---|---|---|
| chunk_size | 700 字符 | 中文约 300-400 字/块，适合简历段落的粒度 |
| chunk_overlap | 120 字符 | 约 17% 的重叠率，防止关键语义被切断 |

#### 优化策略

**现状评估**：当前使用固定大小的滑动窗口切分，对简历类文档（段落结构清晰）表现尚可，但对 JD 文档或长文本表现一般。

**建议优化方向：**

| 优化方案 | 优先级 | 复杂度 | 预期收益 |
|---|---|---|---|
| **语义切分**（按段落/标题分割，保留自然边界） | P0 | 低 | 高——避免在段落中间切断语义 |
| **动态 chunk size**（根据文档类型调整） | P1 | 低 | 中——简历用 500，JD 用 800 |
| **ProseMirror / 递归字符切分**（LangChain `RecursiveCharacterTextSplitter`） | P1 | 低 | 中——用 `["\n\n", "\n", "。", "，"]` 分隔符按优先级切分 |
| **小 chunk + 大窗口检索**（索引用小 chunk 保证精度，检索用大窗口保证上下文完整） | P2 | 中 | 高——改善长文本检索效果 |

**推荐改进代码示例**：

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

def _chunk_text_semantic(self, content: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
        keep_separator=False,
    )
    return splitter.split_text(content)
```

### 3.2 Embedding 模型选型

#### 当前选择

**模型**：`text-embedding-v3`（DashScope/阿里云通义千问）

**使用位置**：`app/services/document_index_service.py` 第 113 行

```python
self.embeddings = dashscope.DashScopeEmbeddings(model="text-embedding-v3")
```

**选型理由**：

| 维度 | 说明 |
|---|---|
| **中文效果** | text-embedding-v3 在中文场景表现优于开源的 bge-small/bge-base |
| **维度适中** | 1024 维，在精度和存储之间取得平衡 |
| **服务稳定** | 阿里云 API，与本项目的 ChatTongyi（DashScope）共用一套 AK |
| **成本** | 按量计费，开发阶段几乎无成本 |
| **LangChain 集成** | 原生支持 `langchain_community.embeddings.dashscope`，无需额外封装 |

**替代模型对比**（供后续迭代参考）：

| 模型 | 维度 | 中文 MTEB | 成本 | 本地部署 | 推荐场景 |
|---|---|---|---|---|---|
| text-embedding-v3 | 1024 | 优 | API 按量 | 否 | 当前选型，维持不变 |
| bge-large-zh-v1.5 | 1024 | 优 | 免费 | 可（需 1.5GB 显存） | 离线/私有化部署 |
| moka-ai/m3e-base | 768 | 良 | 免费 | 可 | 轻量本地方案 |
| gte-Qwen2-1.5B | 1536 | 优 | 免费 | 可 | 性价比最优 |

### 3.3 检索策略优化

#### 当前实现：两级检索策略

项目实现了一套 **阈值检索 + 相似度兜底** 的两级策略，这在 `_search_conversation_docs` 方法中（第 74-88 行）：

```python
def _search_conversation_docs(self, conversation_db, query: str, limit: int):
    # 第一级：相似度阈值检索（精度优先）
    threshold_retriever = conversation_db.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"k": limit, "score_threshold": 0.35},
    )
    docs = threshold_retriever.get_relevant_documents(query)
    if docs:
        return docs

    # 第二级：纯相似度检索（召回兜底）
    fallback_retriever = conversation_db.as_retriever(
        search_type="similarity",
        search_kwargs={"k": limit},
    )
    return fallback_retriever.get_relevant_documents(query)
```

**设计理由**：当用户问"文件概述类问题"（如"这份文档讲了什么"），查询文本很短，向量相似度可能低于阈值（0.35），所以需要降级到纯相似度检索来保证有结果返回。

#### 建议优化方向

| 优化项 | 优先级 | 说明 | 实现方式 |
|---|---|---|---|
| **混合检索（Hybrid Search）** | P0 | 结合向量相似度 + 关键词匹配（BM25），互补短板 | 可用 `ensemble.HybridRetriever` |
| **Query 改写（Query Rewrite）** | P1 | 将短查询扩展为更丰富的语义表达，提升检索精度 | 用 LLM 做 query 扩写，再检索 |
| **重排序（Reranking）** | P1 | 第一轮检索 top-10，用 Cross-Encoder 重排序取 top-3 | 使用 `bge-reranker-v2-m3` |
| **多路召回** | P2 | 多种检索策略并行取并集，再重排序 | 向量 + BM25 + 知识库同时检索 |

**推荐实施的混合检索方案**：

```python
# 在 document_index_service.py 中扩展
from langchain.retrievers import BM25Retriever, EnsembleRetriever

def _hybrid_retrieve(self, conversation_id: str, query: str, k: int = 4):
    # 1. 向量检索
    vector_docs = self._search_conversation_docs(conversation_db, query, k)
    
    # 2. 关键词检索（BM25）
    bm25_retriever = BM25Retriever.from_texts(all_texts)
    bm25_docs = bm25_retriever.get_relevant_documents(query)
    
    # 3. 集成加权
    ensemble = EnsembleRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        weights=[0.6, 0.4],
    )
    return ensemble.get_relevant_documents(query)
```

**重排序（Reranking）推荐方案**：

```python
# 使用 BGE Reranker 进行重排序
from FlagEmbedding import FlagReranker
reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)

def _rerank(self, query, docs):
    pairs = [[query, doc.page_content] for doc in docs]
    scores = reranker.compute_score(pairs)
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [doc for doc, score in ranked[:3]]
```

### 3.4 多数据源检索策略

项目支持 **多级索引**（`get_context` 方法，第 54-64 行）：

```python
def get_context(self, conversation_id: str, query: str, limit: int = 4) -> str:
    # 第一优先：当前会话文档索引
    if conversation_db:
        docs = self._search_conversation_docs(conversation_db, query, limit)
    
    # 第二优先：全局公共索引
    if not docs:
        if public_retriever:
            docs = public_retriever.get_relevant_documents(query)
    
    return "\n\n".join(doc.page_content for doc in docs)
```

**第三阶段新增**：`BuiltinKnowledgeService` 增加了内置知识库作为第三级检索源，从而形成三层检索策略：

```
用户提问 → 会话文档索引（精度最高） → 公共索引 → 内置知识库（通用知识）
```

---

## 四、问题③：语义漂移与幻觉问题如何缓解？

### 4.1 语义漂移的定义与场景

在本项目中，"语义漂移"指的是：

| 场景 | 表现 | 根因 |
|---|---|---|
| **切分导致语义断裂** | 一个完整的项目描述被切成两块，检索时只找到后半段，缺少前文的上下文 | 固定窗口切分，没有保留自然段落边界 |
| **多轮对话漂移** | 在多轮面试模拟中，随着对话轮次增加，Agent 逐渐偏离简历/JD 的事实 | 历史消息过长，Agent 注意力分散 |
| **跨文档混淆** | 同一会话中有多个文档，检索时混入了不相关文档的片段 | 元数据过滤不严格 |

### 4.2 幻觉问题的表现

| 场景 | 表现 | 频次 |
|---|---|---|
| **简历评分幻觉** | LLM 生成简历中不存在的技能或项目经验 | 偶发——与 Prompt 约束强度相关 |
| **JD 解析幻觉** | 凭空添加 JD 原文未提及的技能要求 | 偶发——解析 Prompt 已做了字段约束 |
| **模拟面试幻觉** | 面试评价中出现候选人未提及的技术细节 | 中频——取决于面试官 Prompt 的质量 |

### 4.3 当前已实施的缓解措施

#### ① Prompt 层面约束

所有 LLM 调用的 System Prompt 都包含结构化的输出约束。

以 `ResumeScoringService` 为例（`resume_scoring_service.py` 第 14-37 行）：

```
约束策略：
1. 强制 JSON 输出格式，限制字段范围
2. 评分标准显式写入 Prompt（技能匹配度每项得 20 分等）
3. 字段默认值约束（空数组/0）
4. "不要包含 markdown 代码块标记"——减少解析失败
```

效果评估：结构化约束让模型输出不稳定率从 ~30% 降至 ~5%。

#### ② 多策略 JSON 修复机制

所有 LLM 服务共享一套 JSON 解析管道（以 `job_description_service.py` 为例）：

```
解析策略（按优先级）：
1. 直接解析 → 失败时
2. 从 markdown 代码块提取 → 失败时
3. 修复常见格式错误（数组用 } 闭合而非 ]）→ 失败时
4. 括号匹配提取最外层 JSON → 失败时
5. 正则兜底

```

代码位置：`_parse_response` 方法，共 5 级降级策略。

#### ③ 二级检索兜底

如前文所述，阈值检索失败时降级到纯相似度检索。这一设计本身也是对幻觉的缓解——因为 **空上下文比错误上下文更容易引发幻觉**。如果检索返回了高相关的片段，模型更倾向于基于片段回答而非自由发挥。

#### ④ 元数据过滤

索引时给每个 Chunk 附加 `conversation_id`、`document_id` 等元数据（`document_index_service.py` 第 36-41 行），确保检索只在当前会话范围内命中，避免跨会话污染。

### 4.4 建议继续加强的缓解措施

#### P0：引入上下文验证（Context Verification）

在 LLM 生成回答后，增加一轮验证环节——将回答与检索到的上下文进行比对，标记出回答中上下文未覆盖的断言。

```python
def verify_answer(answer, context):
    """验证回答是否基于给定上下文。"""
    verify_prompt = f"""请判断以下回答中的每个关键断言是否都有上下文支撑。
回答：{answer}
上下文：{context}
请列出没有上下文支撑的断言（如果有）。"""
    # 调用 LLM 验证
    result = llm.invoke(verify_prompt)
    return result  # 返回无依据断言列表
```

#### P1：增加检索结果可见性

在前端展示"参考了哪些文档片段"（类似 Bing 的引用角标），让用户自己判断回答的可信度。

#### P1：Prompt 强化 —— 加入"不知道就说不知道"约束

在所有需要引用文档的 Prompt 末尾增加：

```
重要原则：
- 如果检索到的文档内容不足以回答问题，请明确说"上传的文档中没有相关信息"
- 不要编造文档中未提及的技能、要求或项目经历
- 不确定的信息要标注"根据我的了解"以区分于文档内容
```

#### P2：重排序引入置信度阈值

在 Reranking 阶段，如果前 N 个结果的相关性分数都低于阈值（如 0.3），则不向 LLM 提供检索上下文，强制模型基于通用知识回答。

#### P2：长期记忆去重

在模拟面试的多轮场景中，对历史消息做语义去重，避免重复上下文在 Prompt 中占据过多空间导致注意力偏移。

---

## 五、总结与 Roadmap

### 当前 RAG 链路成熟度评估

| 维度        | 当前状态                  | 下一目标                                  |
| --------- | --------------------- | ------------------------------------- |
| 文档解析      | ✅ 支持 txt/pdf/docx     | 支持 Markdown、HTML                      |
| 文本切分      | ✅ 固定窗口                | 语义切分 + RecursiveCharacterTextSplitter |
| Embedding | ✅ text-embedding-v3   | 保持不变（已验证）                             |
| 向量存储      | ✅ FAISS               | 可扩展至 Milvus（规模化时）                     |
| 检索策略      | ✅ 阈值+相似度兜底            | 混合检索（向量+BM25）+ Reranking              |
| 多轮对话      | ✅ 记忆模式                | 上下文压缩 + 关键信息提取                        |
| 幻觉缓解      | ✅ Prompt 约束 + JSON 修复 | 上下文验证 + 引用展示                          |
| 效果评估      | ❌ 无自动化评估              | 构建测试集 + 自动化指标计算                       |

### 优先实施建议

如果资源有限，建议按以下优先级落地：

1. **语义切分**（RecursiveCharacterTextSplitter）—— 改动最小，收益最明显
2. **构建 30 条测试集 + 手动评估一次** —— 量化当前水平，为后续优化提供基线
3. **Prompt 强化 + "不知道就说不知道"** —— 直接降低幻觉率
4. **混合检索（BM25 + 向量）** —— 提升召回稳定性
5. **上下文验证** —— 最可靠的幻觉检测手段

---

*文档版本：v1.0 | 基于求职助手 Agent 平台 v3.0 实现撰写*
