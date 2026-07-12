from __future__ import annotations

from dataclasses import dataclass

from flask import request
from injector import inject

from app.response import Response, json as response_json
from app.services.export_service import ExportService


@inject
@dataclass
class ExportHandler:
    export_service: ExportService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def export_analysis(self):
        """GET /export/analysis - 导出 JD 分析报告 (Markdown)"""
        try:
            analysis_id = request.args.get("analysis_id", default=0, type=int)
            if not analysis_id:
                return response_json(Response(code=400, message="analysis_id 参数不能为空"))

            markdown = self.export_service.export_analysis_markdown(analysis_id)
            return response_json(Response(data={"markdown": markdown, "format": "markdown"}))

        except Exception as exc:
            return self._error_response(exc)

    def export_interview(self):
        """GET /export/interview - 导出面试回顾 (Markdown)"""
        try:
            session_id = (request.args.get("session_id") or "").strip()
            if not session_id:
                return response_json(Response(code=400, message="session_id 参数不能为空"))

            markdown = self.export_service.export_interview_markdown(session_id)
            return response_json(Response(data={"markdown": markdown, "format": "markdown"}))

        except Exception as exc:
            return self._error_response(exc)

    def export_project_rewrite(self):
        """POST /export/project-rewrite - 导出项目优化结果 (Markdown)"""
        try:
            data = request.get_json(silent=True) or {}
            result = data.get("result")
            if not result:
                return response_json(Response(code=400, message="result 参数不能为空"))

            markdown = self.export_service.export_project_rewrite_markdown(result)
            return response_json(Response(data={"markdown": markdown, "format": "markdown"}))

        except Exception as exc:
            return self._error_response(exc)
