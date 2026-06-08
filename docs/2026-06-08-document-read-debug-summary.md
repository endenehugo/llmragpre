# 文档上传后无法读取内容问题复盘

## 1. 背景

在当前项目中，用户可以把 txt、pdf、docx 文档上传到某个会话下，后端会完成以下链路：

- 保存原始文件到 resources/uploads。
- 解析文本并保存到 resources/parsed_docs。
- 基于解析后的文本重建该会话的 FAISS 索引。
- 在会话问答时，通过会话索引召回上下文，再交给大模型生成答案。

本次连续出现了两类看起来相似、但根因不同的“文档无法读取”问题：

- 上传 txt 后，询问“test.txt 里面有什么”，系统没有回答文档内容。
- 上传 docx 后，询问“简单将一下 test.docx 里的内容”，系统仍然回答无法访问文件内容。

两次问题表面上都表现为“模型没读到文件”，但实际并不是文档解析失败，而是检索阶段没有把正确的上下文召回出来。

## 2. 第一次问题：txt 上传成功，但问答读不到内容

### 2.1 现象

- 前端显示文档上传成功，状态为 indexed。
- 解析后的 txt 文件实际已经写入 resources/parsed_docs。
- 当用户提问“test.txt 里面有什么”时，模型返回的是一段通用话术，声称无法直接访问本地文件。

### 2.2 排查过程

先检查了文档上传、文档解析和会话问答三段代码：

- app/handler/document_handler.py 负责上传后绑定文档并重建索引。
- app/services/document_parser_service.py 已经明确支持 txt、pdf、docx，其中 txt 会按 UTF-8 和 GBK 兜底读取。
- app/services/conversation_chat_service.py 会在会话模式下调用 app/services/document_index_service.py 获取上下文。

进一步检查后发现，txt 文件其实已经成功解析并入库，问题出在会话索引检索逻辑：

- get_context 只使用 similarity_score_threshold 检索。
- 当用户问的是“这个文件里有什么”这类概述性问题，或者文档正文极短时，向量相似度可能低于阈值。
- 一旦没有召回到任何分片，后续大模型就只能回退到自己的泛化回答，从而表现为“无法访问文件”。

### 2.3 根因

根因不是 txt 无法解析，而是：

- 会话文档检索过于依赖相似度阈值。
- 对于短文本或概述性提问，阈值检索容易返回空结果。

### 2.4 修复方案

在 app/services/document_index_service.py 中增加了会话检索兜底逻辑：

- 先按原有 similarity_score_threshold 检索。
- 如果当前会话索引没有召回结果，则再做一次无阈值的 similarity 检索。

这样可以确保：

- 对精准语义问题，仍优先走原有高质量召回。
- 对“这份文件写了什么”“请概述一下内容”这类问题，即使相似度不够高，也至少能返回最相关分片，而不是空上下文。

### 2.5 验证方式

新增测试文件：app/test_tools/test_document_index_service.py

覆盖场景：

- similarity_score_threshold 没有召回结果时，是否会自动回退到 similarity 检索。

验证命令：

```powershell
D:\conda\python.exe -m unittest app.test_tools.test_document_index_service
```

## 3. 第二次问题：docx 上传成功，但按文件名提问时读不到内容

### 3.1 现象

- 前端显示 docx 文档已上传，状态同样为 indexed。
- 解析后的文本文件中实际有内容，例如某个样例的 parsed_docs 文件内容为 123。
- 但当用户直接问“简单讲一下 test.docx 里的内容”时，模型仍然回答没有拿到该文件内容。

### 3.2 排查过程

这次优先怀疑不是 docx 解析失败，而是“按文件名提问”无法命中检索。

检查现有索引构建逻辑后发现：

- rebuild_conversation_index 会把每个文档切片后写入向量库。
- metadata 中保存了 original_name，但真正进入向量索引的 text 只有 chunk 本身。
- 也就是说，test.docx 这个文件名虽然存在于 metadata 中，但不会参与向量相似度计算。

因此当用户问题中出现的是文件名 test.docx，而正文里没有这个词时，检索器几乎没有办法把问题和目标文档关联起来。

### 3.3 根因

根因不是 docx 无法解析，而是：

- 索引文本只包含正文，不包含原始文件名。
- 用户按文件名提问时，检索阶段没有锚点，导致召回失败。

### 3.4 修复方案

在 app/services/document_index_service.py 中补充索引文本构造逻辑：

- 为每个切片增加统一前缀，例如：文件名：test.docx。
- 让 original_name 既保留在 metadata 中，也真正进入 embedding 的文本内容。

修复后的索引文本格式示例：

```text
文件名：test.docx
123
```

这样用户提问：

- test.docx 里写了什么
- 请总结 test.docx
- 这个 docx 讲了什么

都更容易命中对应文档分片。

### 3.5 验证方式

同样在 app/test_tools/test_document_index_service.py 中补充测试：

- 验证 rebuild_conversation_index 写入向量库的文本是否包含 original_name。

验证命令仍为：

```powershell
D:\conda\python.exe -m unittest app.test_tools.test_document_index_service
```

## 4. 两次问题的共同点与差异

### 4.1 共同点

- 上传流程本身是成功的。
- 文档解析本身也是成功的。
- 前端看到的 indexed 状态并不代表后续问答一定能正确召回文档内容。
- 真正的问题都出在“检索阶段没有拿到合适上下文”，而不是“文件没被读取”。

### 4.2 差异

第一次 txt 问题的核心是：

- 有正文，但因为阈值过高或提问过泛，召回结果为空。

第二次 docx 问题的核心是：

- 用户按文件名提问，但索引文本没有包含文件名，导致根本没有检索锚点。

可以把两次问题理解为两个不同层面的召回失败：

- 第一次是“召回策略太保守”。
- 第二次是“召回语料不完整”。

## 5. 本次修改的代码位置

本次问题修复主要集中在以下文件：

- app/services/document_index_service.py
- app/test_tools/test_document_index_service.py

其中关键修改包括：

- 增加 _search_conversation_docs，在阈值召回为空时回退到 similarity 检索。
- 增加 _build_index_text，把 original_name 和正文 chunk 一起写入索引文本。
- 补充两个针对性测试，覆盖“检索空结果兜底”和“文件名进入索引文本”两个回归场景。

## 6. 经验总结

这两次排错带来的直接经验如下：

- 不要把“模型答不上来”直接等同于“文件解析失败”。
- 对 RAG 系统来说，上传成功、解析成功、索引成功、召回成功、生成成功是五个不同阶段，必须逐段排查。
- metadata 只适合做附加信息，不足以替代真正参与 embedding 的文本内容。
- 对文件概述类问题和短文本问题，单纯依赖 similarity_score_threshold 容易把有效上下文过滤掉。
- 当用户经常按文件名提问时，文件名本身必须成为索引文本的一部分。

## 7. 后续建议

为了避免类似问题再次出现，建议后续补充以下能力：

- 增加“重建已有会话索引”的管理脚本，避免历史文档必须删了重传。
- 在调试日志中打印每次问答实际召回的 chunk 数量和来源文档名，便于快速定位是解析问题还是检索问题。
- 后续如果引入多文档问答，可以进一步在 prompt 中显式展示命中的文档名，提高回答可解释性。
- 可考虑为“总结某个文件”“这个文件讲什么”这类问题增加规则化增强，例如优先用文件名做一次筛选，再做向量检索。

## 8. 结论

本次两次问题都不是“系统无法读取 txt 或 docx”，而是“当前 RAG 检索链路在特定提问方式下无法稳定召回正确上下文”。

修复后，系统在以下两类场景下都更稳了：

- 用户对短文本或概述类问题发问。
- 用户直接按文件名询问某个上传文档的内容。

这份复盘的核心价值在于把问题从“文件读取失败”重新定义为“检索召回失败”，后续再遇到类似现象时，应优先检查索引文本和召回策略，而不是先怀疑解析器。