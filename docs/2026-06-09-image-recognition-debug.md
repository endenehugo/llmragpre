# 图片识别能力联调修复记录

## 背景

按 [2026-06-09-image-recognition-development.md](./2026-06-09-image-recognition-development.md) 完成图片识别能力编码后，在浏览器联调过程中触发了四层问题。本文记录每个问题的表象、根因定位过程和最终修复方案。

## 问题总览

| # | 问题表象 | 层级 | 根因 |
|:---|:---|:---|:---|
| 1 | 新建会话后无法上传图片 | 前端 JS | `ensureConversationReady` 未等待 `pendingConversationPromise` |
| 2 | `error` — 后端返回泛化错误 | 后端服务 | 传给通义的消息格式是 OpenAI 风格，DashScope 需要原生 `image`/`text` 结构 |
| 3 | 中文文件名图片被拒 | 后端 Handler | `secure_filename` 先清洗了中文名，扩展名提取失败 |
| 4 | `dict can not be used as parameter` | 后端服务 | 多模态返回 `[{"text":"..."}]`，`AIMessage.content` 把 list 原样返回 |

以下按时间线记录定位和修复过程。

---

## 问题 1：新建会话后无法上传图片

### 表现

页面加载后点击"新建"，在输入区点"图片"并选择文件，提示区域显示"仅支持 png..."或提示消失后没有预览出现。

### 定位过程

查看 `conversation_index.js` 中的 `uploadImage` 函数，它先调用 `ensureConversationReady`。当时的实现：

```javascript
function ensureConversationReady() {
    if (state.currentConversationId) {
        return $.Deferred().resolve(state.currentConversationId).promise();
    }
    return createConversation().then(function (conversationId) {
        return conversationId || state.currentConversationId;
    });
}
```

问题在于 `createConversation` 会异步执行以下步骤：

1. POST `/conversation/create` 拿到 `conversation_id`
2. 把 `conversation_id` 写入 `state.currentConversationId`
3. 调用 `openConversation` → 其 `.then` 回调中执行 `state.pendingImageUrls = []`

与此同时 `uploadImage` 调用的 `ensureConversationReady` 发现 `state.currentConversationId` 已经有值，立即返回了。但此时 `openConversation` 还没执行完——它会在回调中**清空** `pendingImageUrls`。

结果是：图片被加入 `pendingImageUrls` → 紧接着被 `openConversation` 清空 → 预览消失。

### 修复

[app/static/js/conversation_index.js](app/static/js/conversation_index.js)：在 `ensureConversationReady` 开头优先检查 `pendingConversationPromise`，如果有未完成的创建 Promise 就等待它完成。

```javascript
function ensureConversationReady() {
    if (state.pendingConversationPromise) {
        return state.pendingConversationPromise.then(function (conversationId) {
            return conversationId || state.currentConversationId;
        });
    }
    if (state.currentConversationId) {
        return $.Deferred().resolve(state.currentConversationId).promise();
    }
    return createConversation().then(function (conversationId) {
        return conversationId || state.currentConversationId;
    });
}
```

同时确保新建会话和切换会话时清空 `pendingImageUrls` 并更新预览。

---

## 问题 2：`error` — 后端返回泛化错误

### 表现

图片上传成功，输入框中出现了图片预览。发送问题后，助手返回一个单字 `error`，没有任何其他异常信息。后端没有任何异常栈输出到终端。

### 定位过程

通过浏览器中的会话详情 API确认该轮提问根本没有写入数据库，说明错误发生在 `append_message_pair` 之前——也就是多模态模型调用阶段。

猜测问题在传给 DashScope 的消息格式。搜了 `dashscope` 和 `langchain_community` 的源码后发现：

- `ChatTongyi(model="qwen-vl-plus")` 底层会切换到 `dashscope.MultiModalConversation` 客户端
- `MultiModalConversation.call` 的文档示例是：

```python
messages = [
    {
        "role": "user",
        "content": [
            {"image": "http://XXX"},
            {"text": "这个图片是哪里？"},
        ]
    }
]
```

而我们当时组装的消息格式是 OpenAI 风格：

```python
content_parts = [
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    {"type": "text", "text": "用户问题"},
]
```

DashScope 不认识 `type`/`image_url` 这种字段，传入后静默失败，ChatTongyi 把异常转成了泛化 error。

同时追踪到 DashScope 的 `check_and_upload_local` 函数，它发现 `image` 字段的值不是 URL 时会自动识别本地文件路径并上传到 OSS，所以我们根本不需要自己转 data URL——直接传本地绝对路径即可。

### 修复

[app/services/conversation_chat_service.py](app/services/conversation_chat_service.py) 的 `_invoke_multimodal` 方法：

**改前（错误）：**

```python
content_parts.append({
    "type": "image_url",
    "image_url": {"url": self._encode_image_url_to_data_url(image_url)},
})
content_parts.append({
    "type": "text",
    "text": f"相关文档内容：{context}\n\n用户问题：{query}",
})
```

**改后（正确）：**

```python
content_parts.append({
    "image": self._resolve_image_path(image_url),
})
content_parts.append({
    "text": f"相关文档内容：{context}\n\n用户问题：{query}",
})
```

`_resolve_image_path` 把 `/conversation/image/conv_xxx/img_xxx.png` 转成 `resources/uploads/images/conv_xxx/img_xxx.png` 的绝对路径。DashScope 检测到本地路径后自动上传 OSS。

同时新增了 `_extract_multimodal_text` 方法（见问题 4）。

---

## 问题 3：中文文件名图片被拒

### 表现

用户上传 `D:/ASUS/生成数学等式图片.png` 时，后端返回 `400: 仅支持上传 png、jpg、jpeg、webp 格式的图片`。但文件明明是 `.png`。

### 定位过程

通过终端直接发 HTTP 请求复现：上传接口返回 `code=400`。查看 `upload_image` 代码：

```python
filename = secure_filename(upload_file.filename or "")
# 中文文件名 → secure_filename 后几乎只剩 "png"
ext = os.path.splitext(filename)[1].lower().lstrip(".")
# ext = "png"（没有前面的点）→ 不在白名单里
```

`secure_filename("生成数学等式图片.png")` 的结果接近空字符串，因为 `werkzeug` 的 `secure_filename` 会丢弃所有非 ASCII 字符。之后 `os.path.splitext` 从几乎为空的字符串里提取不到有效的扩展名。

### 修复

[app/handler/conversation_handler.py](app/handler/conversation_handler.py)：扩展名校验改为基于**原始文件名**，而不是 secure_filename 之后的文件名。

```python
original_filename = (upload_file.filename or "") if upload_file is not None else ""
# ...
ext = os.path.splitext(original_filename)[1].lower().lstrip(".")
```

`secure_filename` 仍然用于生成安全的存储文件名（`stored_name`），与扩展名校验分离。

---

## 问题 4：`dict can not be used as parameter`

### 表现

DashScope 日志显示多模态调用成功（HTTP 200），返回体中有正确的回答内容。但浏览器中 AI 回答显示为 `dict can not be used as parameter`。

### 定位过程

查看 DashScope 返回体：

```json
{
  "output": {
    "choices": [{
      "message": {
        "content": [{"text": "图片中显示的是一个简单的数学加法问题..."}],
        "role": "assistant"
      },
      "finish_reason": "stop"
    }]
  }
}
```

多模态接口的 assistant `content` 是 `[{"text": "..."}]` 而不是纯文本字符串。

追踪 `ChatTongyi` 源码发现：`_chat_generation_from_qwen_resp` → `convert_dict_to_message` → `AIMessage(content=content)`。`content` 就是 `[{"text": "..."}]` 这个列表，一字不改地赋给了 `AIMessage.content`。

当 `_invoke_multimodal` 返回 `response.content` 时，拿到的是 `[{"text": "..."}]` 而不是字符串。LangChain 在后续某处尝试把这个 dict 列表当作字符串参数使用时，触发了 `dict can not be used as parameter`。

### 修复

[app/services/conversation_chat_service.py](app/services/conversation_chat_service.py)：新增 `_extract_multimodal_text` 方法，在 `_invoke_multimodal` 返回前把多模态响应内容展开为纯字符串。

```python
@classmethod
def _extract_multimodal_text(cls, content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "") or ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)
```

并在 `_invoke_multimodal` 中将 `return response.content` 改为 `return self._extract_multimodal_text(response.content)`。

---

## 附带改进

### 前端 MIME 校验放宽

在问题 1 的排查过程中发现部分本地 PNG 文件的 `File.type` 为空字符串或非标准值，被前端 MIME 校验误拦。修复方案：

[app/static/js/conversation_index.js](app/static/js/conversation_index.js)：`uploadImage` 改为双重校验——MIME 类型或文件后缀满足其一即放行。

```javascript
var hasSupportedMime = /^image\/(png|jpeg|webp)$/.test(mimeType);
var hasSupportedExtension = /\.(png|jpg|jpeg|webp)$/.test(fileName);
if (!hasSupportedMime && !hasSupportedExtension) {
    $('#uploadHint').text('仅支持 png、jpg、jpeg、webp 图片。');
    return;
}
```

### API Key 检测工具

在排查问题 2 的过程中需要反复确认 DashScope Key 是否有效、是否有多模态权限。因此创建了独立的检测工具：

[app/utils/api_key_checker.py](app/utils/api_key_checker.py)：可独立运行 `python -m app.utils.api_key_checker`，也可通过 `GET /api/keycheck` 在服务内调用。支持：

- 显示 Key 的来源（环境变量 / `.env` / `config_dev.py` 默认值）
- 测试 Embedding API
- 测试多模态 API

同时集成到 [run.py](run.py) 启动流程中，每次启动自动打印检测报告。

### 配置文件 Key 读取优化

四个环境的 `config_*.py` 全部改为优先读环境变量：

```python
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "sk-xxx...")
```

这样在 conda / VS Code 终端中 `$env:DASHSCOPE_API_KEY="..."` 即可切换 Key，无需改配置文件。

---

## 涉及文件

| 文件 | 改了什么 |
|:---|:---|
| [app/static/js/conversation_index.js](app/static/js/conversation_index.js) | 修复新建会话竞态、MIME 校验放宽、图片预览清空 |
| [app/services/conversation_chat_service.py](app/services/conversation_chat_service.py) | 修复通义消息格式、新增 `_extract_multimodal_text`、移除 data URL 编码 |
| [app/handler/conversation_handler.py](app/handler/conversation_handler.py) | 修复中文文件名扩展名提取 |
| [app/utils/api_key_checker.py](app/utils/api_key_checker.py) | 新增 Key 检测工具 |
| [app/router/router.py](app/router/router.py) | 新增 `/api/keycheck` 路由 |
| [config/*.py](config/) | Key 读取改为优先环境变量 |
| [run.py](run.py) | 启动时自动运行 Key 检测 |
| [app/test_tools/test_image_multimodal_service.py](app/test_tools/test_image_multimodal_service.py) | 更新测试用例适配修复 |
| [test_tools/test_frontend_message_render.js](test_tools/test_frontend_message_render.js) | 新增前端断言覆盖本次修复 |

---

## 最终验证结果

1. 后端 API Key 检测：全部通过（Embedding + 多模态）
2. 图片上传：支持中文文件名 + 任意 MIME 的 PNG/JPG/JPEG/WEBP
3. 图片问答：返回正常的多模态识别结果，不再有 `error` 或 `dict can not be used as parameter`
4. 新建会话后立即上传图片：不再被 `openConversation` 清空
5. 历史回放：刷新后再进入同一会话，图片消息正常显示
6. 单元测试：`test_image_multimodal_service.py` 6 个用例全部通过
7. 前端回归：`test_frontend_message_render.js` 通过
