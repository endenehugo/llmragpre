from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from flask import request
from injector import inject

from app.repository import DatabaseManager
from app.repository.resume_version_repository import ResumeVersionRepository
from app.response import Response, json as response_json
from app.services import ConversationStoreService


@inject
@dataclass
class ResumeHandler:
    conversation_store_service: ConversationStoreService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def list_versions(self):
        """GET /resume/versions/list - 列出简历版本"""
        try:
            conversation_id = (request.args.get("conversation_id") or "").strip()
            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            db_manager = DatabaseManager()
            session = db_manager.get_session()
            try:
                versions = ResumeVersionRepository.list_by_conversation_id(session, conversation_id)
                return response_json(Response(data={
                    "versions": [
                        {
                            "version_id": v.version_id,
                            "document_id": v.document_id,
                            "version_number": v.version_number,
                            "original_name": v.original_name,
                            "char_count": v.char_count,
                            "total_score": v.total_score,
                            "dimensions": {
                                "skill_match": v.skill_match_score,
                                "project_relevance": v.project_relevance_score,
                                "expression_quality": v.expression_quality_score,
                                "job_fitness": v.job_fitness_score,
                            } if v.total_score is not None else None,
                            "created_at": v.created_at.isoformat() if v.created_at else "",
                        }
                        for v in versions
                    ],
                }))
            finally:
                session.close()

        except Exception as exc:
            return self._error_response(exc)

    def get_version(self):
        """GET /resume/versions/detail - 获取简历版本详情"""
        try:
            version_id = (request.args.get("version_id") or "").strip()
            if not version_id:
                return response_json(Response(code=400, message="version_id 参数不能为空"))

            db_manager = DatabaseManager()
            session = db_manager.get_session()
            try:
                version = ResumeVersionRepository.get_by_version_id(session, version_id)
                if version is None:
                    return response_json(Response(code=404, message="版本不存在"))

                return response_json(Response(data={
                    "version_id": version.version_id,
                    "conversation_id": version.conversation_id,
                    "document_id": version.document_id,
                    "version_number": version.version_number,
                    "original_name": version.original_name,
                    "char_count": version.char_count,
                    "total_score": version.total_score,
                    "dimensions": {
                        "skill_match": version.skill_match_score,
                        "project_relevance": version.project_relevance_score,
                        "expression_quality": version.expression_quality_score,
                        "job_fitness": version.job_fitness_score,
                    } if version.total_score is not None else None,
                    "created_at": version.created_at.isoformat() if version.created_at else "",
                }))
            finally:
                session.close()

        except Exception as exc:
            return self._error_response(exc)

    def compare_versions(self):
        """GET /resume/versions/compare - 对比简历版本分数变化"""
        try:
            conversation_id = (request.args.get("conversation_id") or "").strip()
            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            db_manager = DatabaseManager()
            session = db_manager.get_session()
            try:
                versions = ResumeVersionRepository.list_by_conversation_id(session, conversation_id)
                # 只保留有分数的版本
                scored = [v for v in versions if v.total_score is not None]
                # 按版本号排序
                scored.sort(key=lambda v: v.version_number)

                score_history = []
                for v in scored:
                    score_history.append({
                        "version_number": v.version_number,
                        "original_name": v.original_name,
                        "total_score": v.total_score,
                        "skill_match": v.skill_match_score,
                        "project_relevance": v.project_relevance_score,
                        "expression_quality": v.expression_quality_score,
                        "job_fitness": v.job_fitness_score,
                        "created_at": v.created_at.isoformat() if v.created_at else "",
                    })

                return response_json(Response(data={
                    "score_history": score_history,
                    "trend": _calc_trend(score_history),
                }))
            finally:
                session.close()

        except Exception as exc:
            return self._error_response(exc)


def _calc_trend(score_history: list[dict]) -> str:
    """计算分数趋势"""
    if len(score_history) < 2:
        return "stable"
    first = score_history[0].get("total_score", 0) or 0
    last = score_history[-1].get("total_score", 0) or 0
    if last - first > 5:
        return "up"
    if first - last > 5:
        return "down"
    return "stable"
