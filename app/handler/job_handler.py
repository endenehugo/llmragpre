from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from flask import request
from injector import inject

from app.repository import DatabaseManager, JobAnalysisRepository, ResumeVersionRepository
from app.repository.job_analysis_repository import JobAnalysis
from app.response import Response, json as response_json
from app.services import ConversationStoreService, JobDescriptionService, ResumeScoringService


@inject
@dataclass
class JobHandler:
    conversation_store_service: ConversationStoreService
    job_description_service: JobDescriptionService
    resume_scoring_service: ResumeScoringService

    _SCORE_MAP = {
        "skill_match": "skill_match_score",
        "project_relevance": "project_relevance_score",
        "expression_quality": "expression_quality_score",
        "job_fitness": "job_fitness_score",
    }

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def analyze(self):
        """POST /job/analyze - 分析 JD 并对当前会话的简历进行评分"""
        try:
            data = request.get_json(silent=True) or {}
            conversation_id = (data.get("conversation_id") or "").strip()
            jd_text = (data.get("jd_text") or "").strip()

            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))
            if not jd_text:
                return response_json(Response(code=400, message="jd_text 参数不能为空"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)

            # 1. 获取当前会话的简历文档
            documents = self.conversation_store_service.get_conversation_documents(conversation_id)
            if not documents:
                return response_json(Response(code=400, message="当前会话未上传简历，请先上传简历"))

            # 取最新简历的解析文本
            latest_doc = documents[-1]
            parsed_text_path = latest_doc.get("parsed_text_path")
            resume_text = ""
            if parsed_text_path:
                import os
                if os.path.exists(parsed_text_path):
                    with open(parsed_text_path, "r", encoding="utf-8") as f:
                        resume_text = f.read().strip()

            if not resume_text:
                return response_json(Response(code=500, message="无法读取简历解析文本"))

            # 2. 解析 JD
            jd_analysis = self.job_description_service.analyze(jd_text)

            # 3. 简历评分
            scoring_result = self.resume_scoring_service.score(resume_text, jd_text, jd_analysis)

            # 4. 落库
            self._save_analysis(
                conversation_id=conversation_id,
                jd_text=jd_text,
                jd_analysis=jd_analysis,
                scoring_result=scoring_result,
            )

            # 5. 组装返回
            response_data = self._build_response(jd_analysis, scoring_result)

            return response_json(Response(message="分析完成", data=response_data))

        except Exception as exc:
            return self._error_response(exc)

    def get_latest_analysis(self):
        """GET /job/analysis/latest - 获取最新分析结果"""
        try:
            conversation_id = (request.args.get("conversation_id") or "").strip()
            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            db_manager = DatabaseManager()
            session = db_manager.get_session()
            try:
                analysis = JobAnalysisRepository.get_latest_by_conversation_id(session, conversation_id)
                if analysis is None:
                    return response_json(Response(code=404, message="暂无分析记录"))
                return response_json(Response(data=self._entity_to_dict(analysis)))
            finally:
                session.close()

        except Exception as exc:
            return self._error_response(exc)

    def list_analysis(self):
        """GET /job/analysis/list - 获取分析历史列表"""
        try:
            conversation_id = (request.args.get("conversation_id") or "").strip()
            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            db_manager = DatabaseManager()
            session = db_manager.get_session()
            try:
                analysis_list = JobAnalysisRepository.list_by_conversation_id(session, conversation_id)
                return response_json(Response(data={
                    "analyses": [self._entity_to_dict(item) for item in analysis_list],
                }))
            finally:
                session.close()

        except Exception as exc:
            return self._error_response(exc)

    def _save_analysis(
        self,
        conversation_id: str,
        jd_text: str,
        jd_analysis: dict,
        scoring_result: dict,
    ) -> None:
        now = datetime.now()
        dimensions = scoring_result.get("dimensions", {}) or {}

        db_manager = DatabaseManager()
        session = db_manager.get_session()
        try:
            with session.begin():
                job_analysis = JobAnalysisRepository.create(
                    session,
                    conversation_id=conversation_id,
                    jd_text=jd_text,
                    job_role=jd_analysis.get("job_role", ""),
                    keywords=json.dumps(jd_analysis.get("keywords", []), ensure_ascii=False),
                    requirements=json.dumps(jd_analysis.get("requirements", []), ensure_ascii=False),
                    bonus_points=json.dumps(jd_analysis.get("bonus_points", []), ensure_ascii=False),
                    total_score=float(scoring_result.get("total_score", 0) or 0),
                    skill_match_score=float(dimensions.get("skill_match", 0) or 0),
                    project_relevance_score=float(dimensions.get("project_relevance", 0) or 0),
                    expression_quality_score=float(dimensions.get("expression_quality", 0) or 0),
                    job_fitness_score=float(dimensions.get("job_fitness", 0) or 0),
                    strengths=json.dumps(scoring_result.get("strengths", []), ensure_ascii=False),
                    gaps=json.dumps(scoring_result.get("gaps", []), ensure_ascii=False),
                    suggestions=json.dumps(scoring_result.get("suggestions", []), ensure_ascii=False),
                    created_at=now,
                )

                # 同步更新最新简历版本的分数
                latest_version = ResumeVersionRepository.get_latest_by_conversation_id(session, conversation_id)
                if latest_version is not None:
                    ResumeVersionRepository.update_scores(
                        session, latest_version,
                        total_score=float(scoring_result.get("total_score", 0) or 0),
                        dimensions=dimensions,
                    )
        finally:
            session.close()

    @staticmethod
    def _build_response(jd_analysis: dict, scoring_result: dict) -> dict:
        return {
            "jd_analysis": jd_analysis,
            "scoring": {
                "total_score": scoring_result.get("total_score", 0),
                "dimensions": scoring_result.get("dimensions", {}),
                "strengths": scoring_result.get("strengths", []),
                "gaps": scoring_result.get("gaps", []),
                "suggestions": scoring_result.get("suggestions", []),
            },
        }

    @staticmethod
    def _entity_to_dict(entity: JobAnalysis) -> dict:
        def _safe_json_load(value: str) -> list:
            if not value:
                return []
            try:
                return json.loads(value) if isinstance(value, str) else value
            except (json.JSONDecodeError, TypeError):
                return []

        return {
            "id": entity.id,
            "conversation_id": entity.conversation_id,
            "job_role": entity.job_role,
            "total_score": entity.total_score,
            "dimensions": {
                "skill_match": entity.skill_match_score,
                "project_relevance": entity.project_relevance_score,
                "expression_quality": entity.expression_quality_score,
                "job_fitness": entity.job_fitness_score,
            },
            "keywords": _safe_json_load(entity.keywords),
            "requirements": _safe_json_load(entity.requirements),
            "bonus_points": _safe_json_load(entity.bonus_points),
            "strengths": _safe_json_load(entity.strengths),
            "gaps": _safe_json_load(entity.gaps),
            "suggestions": _safe_json_load(entity.suggestions),
            "created_at": entity.created_at.isoformat() if entity.created_at else "",
        }
