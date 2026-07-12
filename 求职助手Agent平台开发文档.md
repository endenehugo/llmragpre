# 求职助手 Agent 平台开发文档

## 1. 项目定位

### 1.1 项目名称

求职助手 Agent 平台（Job Copilot Agent Platform）

### 1.2 项目一句话描述

一个面向求职场景的智能助手平台，支持职位 JD 解析、简历评分、项目经历匹配、模拟面试、会话追踪与结果沉淀，底层基于 Flask、MySQL、RAG、Tool Calling 和多轮会话能力构建。

### 1.3 项目目标

把当前 `llmrag` 项目从“通用聊天 / 文档问答系统”升级为“面向求职场景的垂直 Agent 应用”，同时满足两个目标：

1. **对外展示效果强**：页面上可以直接演示“上传简历 → 粘贴 JD → 自动分析 → 给出优化建议 / 模拟面试”。
2. **对内技术深度够**：能讲清楚 Flask 接口设计、MySQL 持久化、RAG 检索、Agent 工具调用、会话管理、文档索引与业务编排。

### 1.4 求职价值

这个项目适合作为简历主项目，原因有三点：

- 业务场景明确，面试官很容易理解价值。
- 技术栈贴近后端实习与 Agent 实习岗位要求。
- 可同时展示“工程实现能力”和“AI 应用落地能力”。

---

## 2. 目标用户与使用场景

### 2.1 目标用户

- 准备投递实习的学生
- 想优化简历和项目表达的求职者
- 想做面试前自测的人

### 2.2 核心使用场景

#### 场景 A：JD 匹配分析

用户输入目标岗位 JD，上传自己的简历，系统输出：

- 岗位关键词提取
- 技能要求拆分
- 简历命中点与缺失点
- 匹配得分
- 优化建议

#### 场景 B：项目经历优化

用户输入“我要投 Python 后端 / Agent 实习”，系统根据简历中的项目内容，生成：

- 项目亮点重写建议
- STAR 风格表达
- 面试可讲版本
- 简历 bullet point 优化稿

#### 场景 C：模拟面试

系统根据 JD + 简历内容生成面试题，并支持多轮追问：

- 基础八股题
- 项目深挖题
- 场景题
- 自我介绍改写

#### 场景 D：历史记录与复盘

用户可查看历史分析结果：

- 某个 JD 的匹配历史
- 某版简历的评分趋势
- 某次模拟面试的问答记录

---

## 3. 产品功能设计

## 3.1 MVP 功能

建议先做以下 5 个功能，组成一个 2-3 周可完成的中型项目。

### 功能 1：JD 解析

输入：岗位描述文本  
输出：

- 岗位名称
- 技能关键词
- 学历 / 年限 /职责要求
- 加分项
- 适合的项目关键词

用途：

- 为后续“简历匹配”和“模拟面试”提供结构化输入

### 功能 2：简历上传与解析

支持上传：

- PDF
- DOCX
- TXT

解析后：

- 保存原始文件
- 提取纯文本
- 绑定到用户会话
- 建立会话级索引

用途：

- 复用现有 `DocumentParserService` 与 `DocumentIndexService`

### 功能 3：简历评分与匹配分析

输入：JD + 当前会话中的简历  
输出：

- 总分（如 100 分制）
- 技能匹配度
- 项目匹配度
- 缺失点列表
- 优化建议列表

建议分 4 个维度：

1. 技能命中
2. 项目相关性
3. 表达质量
4. 实习岗位适配度

### 功能 4：项目经历优化助手

用户选择某一段项目经历后，系统输出：

- 原文问题
- 优化版本
- 后端实习面向版本
- Agent 实习面向版本

这个功能非常适合简历展示，因为它能直接体现“你的项目本身就服务于求职场景”。

### 功能 5：模拟面试 Agent

输入：JD + 简历 + 目标岗位方向  
输出：

- 5~10 个面试问题
- 每题参考答题点
- 用户回答后的追问
- 本轮表现总结

这个功能复用现有多轮会话能力，能很好展示“会话持久化 + 角色化 Agent”。

---

## 3.2 第二阶段增强功能

如果时间允许，可补以下增强项：

- 结果落库：保存每次 JD 分析与评分记录
- 历史版本对比：比较不同简历版本得分变化
- 职位收藏：保存多个目标岗位
- 模板导出：导出优化后的简历建议
- 图片识别：上传岗位截图或聊天截图后自动识别并分析

---

## 4. 基于现有 llmrag 项目的二开思路

## 4.1 可以直接复用的能力

当前项目已有以下能力，可直接迁移：

- Flask 路由与 Handler/Service 分层
- 会话创建、详情查询、历史记录持久化
- 文档上传、解析、索引构建、会话级 RAG
- Agent 工具调用
- 图片上传与多模态问答
- MySQL 持久化

这意味着你不用从零开始做一个 Agent 项目，而是可以基于现有骨架改造成垂直业务应用。

## 4.2 推荐保留的主链路

建议继续以 `/conversation/*` 这套接口为主，而不是旧的 `/chat/*`。

原因：

- `/conversation/*` 已经有完整的持久化和历史记录能力
- 更适合承载“求职分析记录”
- 更利于后续做结果复盘、历史对比和多轮模拟面试

## 4.3 推荐新增业务模块

建议新增以下服务：

- `JobDescriptionService`：JD 文本解析与结构化
- `ResumeScoringService`：简历打分与建议生成
- `ProjectRewriteService`：项目经历优化
- `InterviewSimulationService`：模拟面试生成与追问
- `AnalysisHistoryService`：分析结果持久化与查询

---

## 5. 后端架构设计

建议沿用当前项目的分层风格：

```text
router -> handler -> service -> repository
```

### 5.1 模块划分建议

#### handler 层

新增：

- `job_handler.py`
- `resume_handler.py`
- `interview_handler.py`

职责：

- 接收请求
- 参数校验
- 返回统一 JSON 响应

#### service 层

新增：

- `job_description_service.py`
- `resume_scoring_service.py`
- `project_rewrite_service.py`
- `interview_simulation_service.py`
- `analysis_history_service.py`

职责：

- 封装业务编排逻辑
- 调用 LLM / 检索 / 工具
- 组织持久化流程

#### repository 层

新增表对应的 repository：

- `job_analysis_repository.py`
- `resume_score_repository.py`
- `interview_session_repository.py`

职责：

- 只负责 CRUD
- 不写业务逻辑

---

## 6. 数据模型设计

## 6.1 推荐新增表

### 表 1：job_analysis

记录一次 JD 解析与简历匹配结果。

核心字段建议：

- `analysis_id`
- `conversation_id`
- `jd_text`
- `job_role`
- `keywords_json`
- `match_score`
- `strengths_json`
- `gaps_json`
- `suggestions_json`
- `created_at`

### 表 2：resume_versions

记录同一会话下上传过的简历版本。

核心字段建议：

- `resume_version_id`
- `conversation_id`
- `document_id`
- `version_name`
- `source_type`
- `created_at`

### 表 3：interview_sessions

记录模拟面试会话。

核心字段建议：

- `interview_session_id`
- `conversation_id`
- `target_role`
- `difficulty`
- `status`
- `summary`
- `created_at`
- `updated_at`

### 表 4：interview_messages

记录模拟面试过程中的追问与回答。

核心字段建议：

- `message_id`
- `interview_session_id`
- `role`
- `content`
- `created_at`

---

## 7. API 设计建议

以下接口足够支撑 MVP。

### 7.1 JD 解析

`POST /job/analyze`

请求：

```json
{
  "conversation_id": "conv_xxx",
  "jd_text": "岗位描述文本"
}
```

返回：

```json
{
  "job_role": "Python后端实习生",
  "keywords": ["Flask", "MySQL", "Linux"],
  "requirements": ["熟悉 Web 开发", "了解数据库"],
  "bonus_points": ["了解大模型应用"],
  "suggested_project_angles": ["后端服务设计", "Agent 工程化"]
}
```

### 7.2 简历评分

`POST /resume/score`

请求：

```json
{
  "conversation_id": "conv_xxx",
  "jd_text": "岗位描述文本"
}
```

返回：

```json
{
  "score": 82,
  "dimensions": {
    "skill_match": 85,
    "project_relevance": 88,
    "expression_quality": 75,
    "role_fit": 80
  },
  "strengths": ["项目经历匹配度较高"],
  "gaps": ["缺少性能优化或数据库调优表述"],
  "suggestions": ["补充接口设计、数据建模、异常处理相关表述"]
}
```

### 7.3 项目优化

`POST /resume/project/rewrite`

请求：

```json
{
  "conversation_id": "conv_xxx",
  "project_text": "原项目描述",
  "target_role": "python_backend"
}
```

### 7.4 创建模拟面试

`POST /interview/start`

### 7.5 模拟面试追问

`POST /interview/chat`

### 7.6 历史结果

`GET /analysis/history?conversation_id=conv_xxx`

---

## 8. Agent 设计建议

## 8.1 角色划分

建议不要一开始就做复杂多 Agent，而是先做“主 Agent + 专用工具”的轻量方案。

### 主 Agent

负责：

- 理解用户当前任务
- 决定调用哪个服务
- 拼装上下文

### 可调用工具

建议增加 4 个工具：

1. `jd_parser_tool`
2. `resume_score_tool`
3. `project_rewrite_tool`
4. `mock_interview_tool`

这样既保留“Tool Calling”亮点，又不会把工程复杂度拉得过高。

## 8.2 推荐调用顺序

例如用户输入：

> 这是一个 Python 后端实习 JD，请结合我上传的简历帮我分析匹配度，并给出项目优化建议。

建议流程：

1. Agent 识别任务类型为“JD 匹配 + 简历评分 + 项目优化”
2. 从会话文档索引中取出简历内容
3. 调用 `jd_parser_tool`
4. 调用 `resume_score_tool`
5. 调用 `project_rewrite_tool`
6. 汇总生成最终回答
7. 将结果落库

---

## 9. RAG 设计建议

当前项目已有会话级文档索引，这正好适合“简历问答”。

### 9.1 RAG 数据来源

建议分两类：

#### 类别 A：用户上传内容

- 简历
- 项目文档
- 岗位截图 OCR 文本

#### 类别 B：平台内置知识库

可新增一些固定知识：

- Python 后端常见面试题
- MySQL / Redis / Linux / Flask 高频问题
- Agent / RAG 基础知识问答素材

### 9.2 检索策略

建议：

- 用户简历优先
- 再查平台内置面试知识库
- 最后才回退到通用模型生成

这样更像一个“垂直领域助手”，不是普通聊天机器人。

---

## 10. 前端页面设计

当前项目已有前端页面，可继续沿用单页形式。

建议拆成 4 个主要区域：

### 10.1 左侧：会话列表

- 历史求职分析记录
- 不同岗位 / 不同简历版本的会话切换

### 10.2 中间：主对话区

- 输入 JD
- 提问“帮我模拟面试”
- 查看 Agent 输出

### 10.3 右侧：结构化分析面板

- 匹配得分
- 技能命中
- 缺失项
- 优化建议

### 10.4 上传区

- 上传简历
- 上传岗位截图
- 上传项目说明文档

---

## 11. 开发阶段拆分

## 第一阶段：完成 MVP 主链路

目标：能完整跑通“上传简历 + 输入 JD + 输出分析结果”。

任务：

- 新增 JD 解析接口
- 新增简历评分接口
- 在会话中读取简历内容
- 新增结果落库表
- 页面展示结构化评分结果

## 第二阶段：补项目优化与模拟面试

目标：把项目从“分析器”升级成“可持续交互的求职助手”。

任务：

- 新增项目优化接口
- 新增模拟面试会话
- 支持追问与历史记录
- 支持会话维度的复盘

## 第三阶段：补亮点功能

可选任务：

- 上传岗位截图后自动识别
- 简历版本对比
- 导出分析结果
- 内置面试知识库

---

## 12. 简历写法建议

### 12.1 项目标题

求职助手 Agent 平台｜Flask / MySQL / LangChain / RAG / Tool Calling

### 12.2 简历描述示例

- 基于 Flask 与 MySQL 开发求职助手 Agent 平台，支持简历上传、职位 JD 解析、岗位匹配评分与历史分析记录。
- 复用会话级 RAG 检索链路，实现对用户简历、项目材料与岗位描述的联合分析，提升简历匹配建议的上下文相关性。
- 设计 Tool Calling 机制，支持 JD 解析、项目经历优化与模拟面试等能力编排，形成多轮求职辅导流程。
- 实现会话持久化、文档索引与结果落库，支持按岗位维度追踪求职分析历史与复盘记录。

---

## 13. 面试讲解重点

建议重点讲这 5 个问题：

1. **为什么选这个题目？**  
   因为求职场景清晰、价值直观，而且能把通用 RAG/Agent 能力落到真实业务。

2. **和普通聊天机器人有什么不同？**  
   这个系统不是单纯聊天，而是围绕 JD、简历、项目经历、面试问题这几个结构化对象做分析和编排。

3. **RAG 在这里解决什么问题？**  
   主要解决“简历内容长、项目经历分散、用户希望结合上下文精准分析”的问题。

4. **为什么需要 MySQL 持久化？**  
   因为需要保存会话、分析历史、面试记录和简历版本，支持复盘与对比。

5. **为什么用 Tool Calling？**  
   因为 JD 解析、评分、项目优化和模拟面试是不同任务，拆成工具后更容易维护和扩展。

---

## 14. 风险与规避

### 风险 1：功能做太多，最后都不深

规避：

- 先把 “JD 解析 + 简历评分 + 项目优化 + 模拟面试” 跑通
- 不要一开始就做复杂多 Agent

### 风险 2：AI 输出太泛

规避：

- 强化结构化输出
- 提高会话文档检索权重
- 为 JD 解析和评分设计固定输出 schema

### 风险 3：项目像“套壳聊天”

规避：

- 必须加结果落库
- 必须有结构化评分面板
- 必须能展示历史记录或版本对比

---

## 15. 最终建议

这条二开方向非常适合你当前情况，因为它不是推倒重做，而是：

- **业务上**：从“通用问答”升级成“垂直求职助手”
- **技术上**：最大化复用 Flask、MySQL、RAG、Tool Calling、会话持久化
- **简历上**：同时覆盖 Python 后端实习与 Agent 实习两个叙事方向

如果后续还要继续加强，我建议优先加这两个点：

1. **结构化评分结果落库与历史对比**
2. **模拟面试追问链路**

这两个功能最能拉开你和普通 LLM Demo 项目的差距。
