from __future__ import annotations

import logging
from dataclasses import dataclass

from flask import request
from injector import inject

from app.response import Response, json as response_json
from app.services.builtin_knowledge_service import BuiltinKnowledgeService

logger = logging.getLogger(__name__)


@inject
@dataclass
class KnowledgeHandler:
    builtin_knowledge_service: BuiltinKnowledgeService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def rebuild(self):
        """POST /knowledge/rebuild - 重建内置知识库索引"""
        try:
            result = self.builtin_knowledge_service.rebuild_index()
            return response_json(Response(
                message=f"知识库索引重建完成，共 {result['chunk_count']} 个文本块",
                data=result,
            ))
        except Exception as exc:
            return self._error_response(exc)

    def query(self):
        """GET /knowledge/query - 检索内置知识库"""
        try:
            query = (request.args.get("query") or "").strip()
            k = request.args.get("k", default=3, type=int)
            category = (request.args.get("category") or "").strip() or None

            if not query:
                return response_json(Response(code=400, message="query 参数不能为空"))

            results = self.builtin_knowledge_service.retrieve(query, k=k, category=category)
            return response_json(Response(data={
                "results": results,
                "total": len(results),
            }))

        except Exception as exc:
            return self._error_response(exc)

    def list_categories(self):
        """GET /knowledge/categories - 列出知识库分类"""
        try:
            categories = self.builtin_knowledge_service.list_categories()
            return response_json(Response(data={"categories": categories}))
        except Exception as exc:
            return self._error_response(exc)

    def status(self):
        """GET /knowledge/status - 知识库状态"""
        try:
            import os
            from app.utils import ResourceUtils

            index_dir = ResourceUtils.get_resource_path("faiss_index_knowledge")
            exists = os.path.isdir(index_dir)
            has_files = False
            if exists:
                has_files = any(name.endswith(".faiss") for name in os.listdir(index_dir))

            from app.services.builtin_knowledge_service import BUILTIN_KNOWLEDGE
            categories = {}
            for item in BUILTIN_KNOWLEDGE:
                cat = item.get("category", "other")
                categories[cat] = categories.get(cat, 0) + 1

            return response_json(Response(data={
                "index_exists": exists and has_files,
                "total_documents": len(BUILTIN_KNOWLEDGE),
                "categories": categories,
            }))
        except Exception as exc:
            return self._error_response(exc)
