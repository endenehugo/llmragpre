from __future__ import annotations

import os
import re
from dataclasses import dataclass

from flask import current_app
from injector import inject
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.services.conversation_store_service import ConversationStoreService
from app.services.document_index_service import DocumentIndexService
from app.tools import MultiplyTool, WebSearchTool, WordDocumentTool
from app.utils import ResourceUtils


@inject
@dataclass
class ConversationChatService:
    conversation_store_service: ConversationStoreService
    document_index_service: DocumentIndexService

    _IMAGE_MARKDOWN_PATTERN = re.compile(r"!\[[^\]]*\]\((/conversation/image/[^)\s]+)\)")

    def __post_init__(self):
        self.qa_llm = None
        self.agent_llm = None
        self.vl_llm = None
        self.tool_dic = None
        self.qa_prompt = None
        self.agent_prompt = None
        self.multimodal_system_prompt = None

    def chat(self, conversation_id: str, query: str, mode: str = "agent", image_urls: list[str] | None = None) -> dict:
        normalized_mode = mode if mode in {"agent", "rag", "memory"} else "agent"
        effective_query = (query or "").strip() or "请描述图片内容。"
        normalized_image_urls = [item for item in (image_urls or []) if item]
        self.conversation_store_service.ensure_conversation_exists(conversation_id)
        self._ensure_initialized()

        history = self.conversation_store_service.get_conversation_messages(conversation_id)
        context = "" if normalized_mode == "memory" else self.document_index_service.get_context(conversation_id, effective_query)
        user_content = self._compose_user_content(effective_query, normalized_image_urls)

        if normalized_image_urls:
            answer = self._invoke_multimodal(history, context, effective_query, normalized_image_urls)
        else:
            prompt = self.agent_prompt if normalized_mode == "agent" else self.qa_prompt
            prompt_messages = prompt.invoke({
                "query": effective_query,
                "history": self._build_history(history),
                "context": context,
            }).to_messages()

            if normalized_mode == "agent":
                answer = self._invoke_agent(prompt_messages)
            else:
                answer = self.qa_llm.invoke(prompt_messages).content

        answer = answer or "抱歉，我暂时无法生成回答。"
        self.conversation_store_service.append_message_pair(conversation_id, user_content, answer, normalized_mode)
        detail = self.conversation_store_service.get_conversation_detail(conversation_id)
        return {
            "answer": answer,
            "conversation": detail,
        }

    def _ensure_initialized(self):
        if self.qa_llm is not None:
            return

        self.qa_llm = ChatTongyi(
            streaming=True,
            model="qwen-plus",
            temperature=0.8,
            top_p=0.7,
        )
        multimodal_model = "qwen-vl-plus"
        try:
            multimodal_model = current_app.config.get("MULTIMODAL_MODEL", multimodal_model)
        except RuntimeError:
            pass
        self.vl_llm = ChatTongyi(
            model=multimodal_model,
            temperature=0.7,
        )
        tools = [MultiplyTool(), WebSearchTool(), WordDocumentTool()]
        self.tool_dic = {tool.name: tool for tool in tools}
        self.agent_llm = self.qa_llm.bind_tools(tools)

        self.qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的问答助手。你将收到聊天历史、会话文档上下文和用户问题。请优先基于当前会话文档回答；如果上下文为空或不足，可以明确说明并结合通用知识补充。"),
            MessagesPlaceholder("history"),
            ("human", "相关文档内容：{context}\n\n用户问题：{query}"),
        ])

        self.agent_prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的问答机器人。你将获得当前会话的相关文档、聊天历史和用户问题。请优先利用当前会话文档回答。需要最新网页信息时主动调用 web_search_tool，需要生成 Word 文档时主动调用 word_document_tool。"),
            MessagesPlaceholder("history"),
            ("human", "相关的文档内容：{context}\n\n用户的问题：{query}"),
        ])
        self.multimodal_system_prompt = (
            "你是一个专业的多模态问答助手。你将获得当前会话的聊天历史、相关文档上下文、"
            "以及用户上传的图片和问题。请优先结合图片与当前会话文档回答；如果文档上下文不足，"
            "请明确说明后再给出基于图片本身的判断。"
        )

    def _invoke_agent(self, messages: list) -> str:
        chain_output = ""
        for _ in range(3):
            response = self.agent_llm.invoke(messages)
            messages.append(response)
            tool_calls = response.tool_calls or []
            if not tool_calls:
                chain_output = response.content
                break

            for tool_call in tool_calls:
                tool = self.tool_dic.get(tool_call.get("name"))
                if tool is None:
                    content = f"工具不存在：{tool_call.get('name')}"
                else:
                    content = tool.invoke(tool_call.get("args"))
                messages.append(ToolMessage(tool_call_id=tool_call.get("id"), content=content))
        return chain_output

    def _invoke_multimodal(self, history: list[dict], context: str, query: str, image_urls: list[str]) -> str:
        content_parts = []
        for image_url in image_urls:
            content_parts.append({
                "image": self._resolve_image_path(image_url),
            })

        content_parts.append({
            "text": f"相关文档内容：{context}\n\n用户问题：{query}",
        })

        messages = [SystemMessage(content=[{"text": self.multimodal_system_prompt}])]
        messages.extend(self._build_multimodal_history(history))
        messages.append(HumanMessage(content=content_parts))
        response = self.vl_llm.invoke(messages)
        return response.content

    def _resolve_image_path(self, image_url: str) -> str:
        conversation_id, filename = self._parse_image_url(image_url)
        image_dir = ResourceUtils.get_resource_path(os.path.join("uploads", "images", conversation_id))
        image_path = os.path.join(image_dir, filename)
        if not os.path.isfile(image_path):
            raise ValueError(f"图片文件不存在: {image_url}")
        return image_path

    @classmethod
    def _parse_image_url(cls, image_url: str) -> tuple[str, str]:
        parts = image_url.strip("/").split("/")
        if len(parts) != 4 or parts[0] != "conversation" or parts[1] != "image":
            raise ValueError("非法图片地址")
        conversation_id, filename = parts[2], parts[3]
        if re.fullmatch(r"[A-Za-z0-9_.-]+", conversation_id) is None:
            raise ValueError("非法图片地址")
        if re.fullmatch(r"[A-Za-z0-9_.-]+", filename) is None:
            raise ValueError("非法图片地址")
        return conversation_id, filename

    @classmethod
    def _compose_user_content(cls, query: str, image_urls: list[str]) -> str:
        lines = [f"![image]({image_url})" for image_url in image_urls]
        if query:
            lines.append(query)
        return "\n".join(lines)

    @classmethod
    def _extract_image_urls(cls, content: str) -> list[str]:
        return cls._IMAGE_MARKDOWN_PATTERN.findall(content or "")

    @classmethod
    def _strip_image_markdown(cls, content: str) -> str:
        return cls._IMAGE_MARKDOWN_PATTERN.sub("", content or "").strip()

    def _build_multimodal_history(self, history: list[dict]) -> list:
        messages = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                image_urls = self._extract_image_urls(content)
                clean_text = self._strip_image_markdown(content)
                if image_urls:
                    parts = []
                    for image_url in image_urls:
                        try:
                            parts.append({
                                "image": self._resolve_image_path(image_url),
                            })
                        except Exception:
                            continue
                    if clean_text:
                        parts.append({"type": "text", "text": clean_text})
                    if parts:
                        messages.append(HumanMessage(content=parts))
                        continue
                    content = clean_text

            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages

    @staticmethod
    def _build_history(history: list[dict]) -> list:
        messages = []
        for item in history:
            role = item.get("role")
            content = ConversationChatService._strip_image_markdown(item.get("content", ""))
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages