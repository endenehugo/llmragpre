from __future__ import annotations

import json
import os
from dataclasses import dataclass

from flask import request
from injector import inject

from app.handler.job_handler import JobHandler
from app.response import Response, json as response_json
from app.services import ConversationStoreService
from app.services.image_analysis_service import ImageAnalysisService
from app.services.job_description_service import JobDescriptionService
from app.services.resume_scoring_service import ResumeScoringService
from app.repository import DatabaseManager, JobAnalysisRepository
from app.repository.job_analysis_repository import JobAnalysis


@inject
@dataclass
class ImageHandler:
    conversation_store_service: ConversationStoreService
    image_analysis_service: ImageAnalysisService
    job_description_service: JobDescriptionService
    resume_scoring_service: ResumeScoringService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def analyze_screenshot(self):
        """POST /job/analyze-from-screenshot - 从招聘截图分析 JD 并评分"""
        try:
            data = request.get_json(silent=True) or {}
            conversation_id = (data.get("conversation_id") or "").strip()
            image_url = (data.get("image_url") or "").strip()

            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))
            if not image_url:
                return response_json(Response(code=400, message="image_url 参数不能为空"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)

            # 解析图片 URL 为本地路径
            from app.services.conversation_chat_service import ConversationChatService
            try:
                conv_id, filename = ConversationChatService._parse_image_url(image_url)
            except ValueError as e:
                return response_json(Response(code=400, message=f"图片地址非法: {e}"))

            from app.utils import ResourceUtils
            image_dir = ResourceUtils.get_resource_path(os.path.join("uploads", "images", conv_id))
            image_path = os.path.join(image_dir, filename)

            if not os.path.isfile(image_path):
                return response_json(Response(code=400, message="图片文件不存在"))

            # 1. 从截图中提取 JD 文本
            jd_text = self.image_analysis_service.extract_jd_from_screenshot(image_path)
            if not jd_text or len(jd_text.strip()) < 20:
                return response_json(Response(code=500, message="无法从截图识别出有效的 JD 文本，请确认图片清晰度"))

            # 2. 获取简历
            documents = self.conversation_store_service.get_conversation_documents(conversation_id)
            if not documents:
                return response_json(Response(code=400, message="当前会话未上传简历，请先上传简历"))

            latest_doc = documents[-1]
            parsed_text_path = latest_doc.get("parsed_text_path")
            resume_text = ""
            if parsed_text_path and os.path.exists(parsed_text_path):
                with open(parsed_text_path, "r", encoding="utf-8") as f:
                    resume_text = f.read().strip()

            if not resume_text:
                return response_json(Response(code=500, message="无法读取简历解析文本"))

            # 3. 解析 JD
            jd_analysis = self.job_description_service.analyze(jd_text)

            # 4. 评分
            scoring_result = self.resume_scoring_service.score(resume_text, jd_text, jd_analysis)

            # 5. 落库
            save_analysis(
                conversation_id=conversation_id,
                jd_text=jd_text,
                jd_analysis=jd_analysis,
                scoring_result=scoring_result,
            )

            # 6. 组装返回
            response_data = {
                "jd_analysis": jd_analysis,
                "scoring": {
                    "total_score": scoring_result.get("total_score", 0),
                    "dimensions": scoring_result.get("dimensions", {}),
                    "strengths": scoring_result.get("strengths", []),
                    "gaps": scoring_result.get("gaps", []),
                    "suggestions": scoring_result.get("suggestions", []),
                },
                "extracted_jd_preview": jd_text[:500] + ("..." if len(jd_text) > 500 else ""),
            }

            return response_json(Response(message="截图分析完成", data=response_data))

        except Exception as exc:
            return self._error_response(exc)


def save_analysis(
    conversation_id: str,
    jd_text: str,
    jd_analysis: dict,
    scoring_result: dict,
) -> None:
    """保存分析结果到数据库"""
    from datetime import datetime

    now = datetime.now()
    dimensions = scoring_result.get("dimensions", {}) or {}

    db_manager = DatabaseManager()
    session = db_manager.get_session()
    try:
        with session.begin():
            JobAnalysisRepository.create(
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
    finally:
        session.close()
