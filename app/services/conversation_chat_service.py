from __future__ import annotations

from dataclasses import dataclass

from injector import inject
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.services.conversation_store_service import ConversationStoreService
from app.services.document_index_service import DocumentIndexService
from app.tools import MultiplyTool, WebSearchTool, WordDocumentTool


@inject
@dataclass
class ConversationChatService:
    conversation_store_service: ConversationStoreService
    document_index_service: DocumentIndexService

    def __post_init__(self):
        self.qa_llm = None
        self.agent_llm = None
        self.tool_dic = None
        self.qa_prompt = None
        self.agent_prompt = None

    def chat(self, conversation_id: str, query: str, mode: str = "agent") -> dict:
        normalized_mode = mode if mode in {"agent", "rag", "memory"} else "agent"
        self.conversation_store_service.ensure_conversation_exists(conversation_id)
        self._ensure_initialized()

        history = self.conversation_store_service.get_conversation_messages(conversation_id)
        context = "" if normalized_mode == "memory" else self.document_index_service.get_context(conversation_id, query)
        prompt = self.agent_prompt if normalized_mode == "agent" else self.qa_prompt
        prompt_messages = prompt.invoke({
            "query": query,
            "history": self._build_history(history),
            "context": context,
        }).to_messages()

        if normalized_mode == "agent":
            answer = self._invoke_agent(prompt_messages)
        else:
            answer = self.qa_llm.invoke(prompt_messages).content

        answer = answer or "抱歉，我暂时无法生成回答。"
        self.conversation_store_service.append_message_pair(conversation_id, query, answer, normalized_mode)
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

    @staticmethod
    def _build_history(history: list[dict]) -> list:
        messages = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        return messages