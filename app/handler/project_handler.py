from __future__ import annotations

import json
from dataclasses import dataclass

from flask import request
from injector import inject

from app.response import Response, json as response_json
from app.services import ConversationStoreService, ProjectRewriteService


@inject
@dataclass
class ProjectHandler:
    conversation_store_service: ConversationStoreService
    project_rewrite_service: ProjectRewriteService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def rewrite(self):
        """POST /resume/project/rewrite - 优化项目经历描述"""
        try:
            data = request.get_json(silent=True) or {}
            conversation_id = (data.get("conversation_id") or "").strip()
            project_description = (data.get("project_description") or "").strip()

            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))
            if not project_description:
                return response_json(Response(code=400, message="project_description 参数不能为空"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)

            # 收集简历上下文（可选，用于更精准的优化）
            context = None
            documents = self.conversation_store_service.get_conversation_documents(conversation_id)
            if documents:
                latest_doc = documents[-1]
                parsed_text_path = latest_doc.get("parsed_text_path")
                if parsed_text_path:
                    import os
                    if os.path.exists(parsed_text_path):
                        with open(parsed_text_path, "r", encoding="utf-8") as f:
                            resume_text = f.read().strip()
                        if resume_text:
                            context = resume_text[:2000]  # 取前 2000 字作为上下文

            result = self.project_rewrite_service.rewrite(project_description, context)

            return response_json(Response(message="优化完成", data=result))

        except Exception as exc:
            return self._error_response(exc)
