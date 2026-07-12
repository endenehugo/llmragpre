import os
import uuid
from dataclasses import dataclass
from datetime import datetime

from flask import request
from injector import inject

from app.repository import DatabaseManager
from app.repository.resume_version_repository import ResumeVersionRepository
from app.response import Response, json
from app.services import ConversationStoreService, DocumentParserService, DocumentIndexService


@inject
@dataclass
class DocumentHandler:
    conversation_store_service: ConversationStoreService
    document_parser_service: DocumentParserService
    document_index_service: DocumentIndexService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return json(Response(code=code, message=str(exc)))

    def upload(self):
        try:
            conversation_id = (request.form.get("conversation_id") or "").strip()
            upload_file = request.files.get("file")
            if not conversation_id:
                return json(Response(code=400, message="conversation_id 参数不能为空"))
            if upload_file is None:
                return json(Response(code=400, message="缺少上传文件"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)
            parsed_document = self.document_parser_service.save_and_parse(conversation_id, upload_file)
            document = self.conversation_store_service.bind_document(conversation_id, parsed_document, status="parsed")
            try:
                documents = self.conversation_store_service.get_conversation_documents(conversation_id)
                self.document_index_service.rebuild_conversation_index(conversation_id, documents)
                document = self.conversation_store_service.update_document_status(document["document_id"], "indexed")
            except Exception:
                self.conversation_store_service.update_document_status(document["document_id"], "failed")
                raise
            # 创建简历版本记录
            self._create_resume_version(conversation_id, document, parsed_document)

            return json(Response(message="上传成功", data={"document": document}))
        except Exception as exc:
            return self._error_response(exc)

    def delete(self):
        try:
            data = request.get_json(silent=True) or {}
            document_id = (data.get("document_id") or "").strip()
            if not document_id:
                return json(Response(code=400, message="document_id 参数不能为空"))

            document = self.conversation_store_service.remove_document(document_id)
            self._safe_delete(document.get("stored_path"))
            self._safe_delete(document.get("parsed_text_path"))

            remaining_documents = self.conversation_store_service.get_conversation_documents(document["conversation_id"])
            if remaining_documents:
                self.document_index_service.rebuild_conversation_index(document["conversation_id"], remaining_documents)
            else:
                self.document_index_service.delete_conversation_index(document["conversation_id"])

            return json(Response(message="删除成功", data={"document_id": document_id}))
        except Exception as exc:
            return self._error_response(exc)

    @staticmethod
    def _safe_delete(path: str | None) -> None:
        if path and os.path.exists(path):
            os.remove(path)

    @staticmethod
    def _create_resume_version(conversation_id: str, document: dict, parsed_document: dict) -> None:
        """创建简历版本记录"""
        db_manager = DatabaseManager()
        session = db_manager.get_session()
        now = datetime.now()
        try:
            max_ver = ResumeVersionRepository.get_max_version_number(session, conversation_id)
            with session.begin():
                ResumeVersionRepository.create(
                    session,
                    version_id=f"rv_{uuid.uuid4().hex[:12]}",
                    conversation_id=conversation_id,
                    document_id=document["document_id"],
                    version_number=max_ver + 1,
                    original_name=document.get("original_name", ""),
                    char_count=parsed_document.get("char_count", 0),
                    created_at=now,
                )
        finally:
            session.close()