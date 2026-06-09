from dataclasses import dataclass
import os
import re
import uuid

from flask import current_app, request, send_from_directory
from injector import inject
from werkzeug.utils import secure_filename

from app.response import Response, json
from app.services import ConversationStoreService, ConversationChatService
from app.utils import ResourceUtils
from app.utils.api_key_checker import check_all


@inject
@dataclass
class ConversationHandler:
    conversation_store_service: ConversationStoreService
    conversation_chat_service: ConversationChatService

    _SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

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
            raw_image_urls = data.get("image_urls") or []

            if not conversation_id:
                return json(Response(code=400, message="conversation_id 参数不能为空"))
            if not isinstance(raw_image_urls, list):
                return json(Response(code=400, message="image_urls 参数必须是数组"))

            image_urls = []
            for item in raw_image_urls:
                if not isinstance(item, str):
                    return json(Response(code=400, message="image_urls 中的元素必须是字符串"))
                value = item.strip()
                if value:
                    image_urls.append(value)

            if not query and not image_urls:
                return json(Response(code=400, message="query 参数不能为空"))

            result = self.conversation_chat_service.chat(conversation_id, query, mode, image_urls)
            return json(Response(message=result["answer"], data=result))
        except Exception as exc:
            return self._error_response(exc)

    def upload_image(self):
        try:
            conversation_id = (request.form.get("conversation_id") or "").strip()
            upload_file = request.files.get("file")
            original_filename = (upload_file.filename or "") if upload_file is not None else ""
            if not conversation_id:
                return json(Response(code=400, message="conversation_id 参数不能为空"))
            if upload_file is None:
                return json(Response(code=400, message="缺少上传文件"))
            if not self._is_safe_segment(conversation_id):
                return json(Response(code=400, message="conversation_id 非法"))

            if not original_filename.strip():
                return json(Response(code=400, message="文件名不能为空"))

            ext = os.path.splitext(original_filename)[1].lower().lstrip(".")
            allowed_extensions = set(current_app.config.get("IMAGE_ALLOWED_EXTENSIONS", ["png", "jpg", "jpeg", "webp"]))
            if ext not in allowed_extensions:
                return json(Response(code=400, message="仅支持上传 png、jpg、jpeg、webp 格式的图片"))
            if not (upload_file.mimetype or "").startswith("image/"):
                return json(Response(code=400, message="上传文件不是合法图片"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)
            relative_dir = os.path.join("uploads", "images", conversation_id)
            save_dir = ResourceUtils.ensure_resource_dir(relative_dir)
            stored_name = f"img_{uuid.uuid4().hex[:12]}.{ext}"
            save_path = os.path.join(save_dir, stored_name)
            upload_file.save(save_path)

            image_url = f"/conversation/image/{conversation_id}/{stored_name}"
            return json(Response(message="图片上传成功", data={
                "image_url": image_url,
                "filename": stored_name,
                "mime_type": upload_file.mimetype or f"image/{ext}",
            }))
        except Exception as exc:
            return self._error_response(exc)

    def serve_image(self, conversation_id: str, filename: str):
        if not self._is_safe_segment(conversation_id):
            return json(Response(code=400, message="conversation_id 非法"))
        if secure_filename(filename) != filename or not self._is_safe_segment(filename):
            return json(Response(code=400, message="filename 非法"))

        image_dir = ResourceUtils.get_resource_path(os.path.join("uploads", "images", conversation_id))
        return send_from_directory(image_dir, filename)

    @classmethod
    def _is_safe_segment(cls, value: str) -> bool:
        return bool(value) and bool(cls._SAFE_SEGMENT_PATTERN.fullmatch(value))

    @staticmethod
    def api_key_check():
        """GET /api/keycheck → 返回 DashScope Key 检测报告"""
        report = check_all()
        return json(Response(
            message="所有检测通过" if report.all_passed else "存在检测失败项，请检查配置。",
            data={
                "all_passed": report.all_passed,
                "results": [
                    {"name": r.name, "passed": r.passed, "message": r.message}
                    for r in report.results
                ],
            },
        ))