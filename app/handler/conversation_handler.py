from dataclasses import dataclass

from flask import request
from injector import inject

from app.response import Response, json
from app.services import ConversationStoreService, ConversationChatService


@inject
@dataclass
class ConversationHandler:
    conversation_store_service: ConversationStoreService
    conversation_chat_service: ConversationChatService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return json(Response(code=code, message=str(exc)))

    def create(self):
        try:
            data = request.get_json(silent=True) or {}
            conversation = self.conversation_store_service.create_conversation(
                title=data.get("title", "新对话"),
                mode=data.get("mode", "agent"),
            )
            return json(Response(message="创建成功", data=conversation))
        except Exception as exc:
            return self._error_response(exc)

    def list(self):
        try:
            limit = request.args.get("limit", default=50, type=int)
            conversations = self.conversation_store_service.list_conversations(limit=limit)
            return json(Response(message="查询成功", data={"conversations": conversations}))
        except Exception as exc:
            return self._error_response(exc)

    def detail(self):
        try:
            conversation_id = request.args.get("conversation_id", default="", type=str).strip()
            if not conversation_id:
                return json(Response(code=400, message="conversation_id 参数不能为空"))
            detail = self.conversation_store_service.get_conversation_detail(conversation_id)
            return json(Response(message="查询成功", data=detail))
        except Exception as exc:
            return self._error_response(exc)

    def chat(self):
        try:
            data = request.get_json(silent=True) or {}
            conversation_id = (data.get("conversation_id") or "").strip()
            query = (data.get("query") or "").strip()
            mode = (data.get("mode") or "agent").strip()

            if not conversation_id:
                return json(Response(code=400, message="conversation_id 参数不能为空"))
            if not query:
                return json(Response(code=400, message="query 参数不能为空"))

            result = self.conversation_chat_service.chat(conversation_id, query, mode)
            return json(Response(message=result["answer"], data=result))
        except Exception as exc:
            return self._error_response(exc)