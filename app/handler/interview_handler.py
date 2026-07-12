from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from flask import request
from injector import inject

from app.handler.job_handler import JobHandler
from app.repository import DatabaseManager, InterviewSessionRepository, InterviewMessageRepository
from app.repository.interview_repository import InterviewSession, InterviewMessage
from app.response import Response, json as response_json
from app.services import ConversationStoreService, ResumeScoringService
from app.services.interview_simulation_service import InterviewSimulationService


@inject
@dataclass
class InterviewHandler:
    conversation_store_service: ConversationStoreService
    interview_simulation_service: InterviewSimulationService
    resume_scoring_service: ResumeScoringService

    @staticmethod
    def _error_response(exc: Exception):
        code = 400 if isinstance(exc, ValueError) else 500
        return response_json(Response(code=code, message=str(exc)))

    def start(self):
        """POST /interview/start - 开始模拟面试"""
        try:
            data = request.get_json(silent=True) or {}
            conversation_id = (data.get("conversation_id") or "").strip()
            direction = (data.get("direction") or "general").strip()
            jd_text = (data.get("jd_text") or "").strip()

            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            self.conversation_store_service.ensure_conversation_exists(conversation_id)

            # 读取简历
            documents = self.conversation_store_service.get_conversation_documents(conversation_id)
            if not documents:
                return response_json(Response(code=400, message="当前会话未上传简历，请先上传简历"))

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

            # 如果没有传入 JD，尝试从最新分析中获取
            if not jd_text:
                db_manager = DatabaseManager()
                session = db_manager.get_session()
                try:
                    from app.repository.job_analysis_repository import JobAnalysisRepository
                    latest_analysis = JobAnalysisRepository.get_latest_by_conversation_id(session, conversation_id)
                    if latest_analysis:
                        jd_text = latest_analysis.jd_text
                finally:
                    session.close()

            if not jd_text:
                return response_json(Response(code=400, message="请先分析 JD 或提供 JD 文本"))

            # 生成面试题
            result = self.interview_simulation_service.start_interview(jd_text, resume_text)
            questions = result.get("questions", [])

            if not questions:
                return response_json(Response(code=500, message="面试题生成失败"))

            # 保存面试会话
            now = datetime.now()
            session_id = f"iv_{now.strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"

            db_manager = DatabaseManager()
            db_session = db_manager.get_session()
            try:
                with db_session.begin():
                    interview_session = InterviewSessionRepository.create(
                        db_session,
                        session_id=session_id,
                        conversation_id=conversation_id,
                        job_role="",
                        direction=direction,
                        status="in_progress",
                        round_count=0,
                        initial_questions=json.dumps(questions, ensure_ascii=False),
                        created_at=now,
                        updated_at=now,
                    )

                    # 保存第一题
                    first_question = questions[0]
                    InterviewMessageRepository.create(
                        db_session,
                        message_id=f"imsg_{uuid.uuid4().hex[:16]}",
                        session_id=session_id,
                        role="assistant",
                        content=first_question.get("question", ""),
                        score=None,
                        evaluation="",
                        msg_type="question",
                        created_at=now,
                    )

                return response_json(Response(message="面试已开始", data={
                    "session_id": session_id,
                    "questions": questions,
                    "current_question": questions[0],
                    "question_index": 0,
                    "total_questions": len(questions),
                }))
            finally:
                db_session.close()

        except Exception as exc:
            return self._error_response(exc)

    def answer(self):
        """POST /interview/answer - 提交回答并获取下一题"""
        try:
            data = request.get_json(silent=True) or {}
            session_id = (data.get("session_id") or "").strip()
            answer = (data.get("answer") or "").strip()
            question_index = data.get("question_index", 0)

            if not session_id:
                return response_json(Response(code=400, message="session_id 参数不能为空"))
            if not answer:
                return response_json(Response(code=400, message="answer 参数不能为空"))

            db_manager = DatabaseManager()
            db_session = db_manager.get_session()
            try:
                interview_session = InterviewSessionRepository.get_by_session_id(db_session, session_id)
                if interview_session is None:
                    return response_json(Response(code=404, message="面试会话不存在"))

                if interview_session.status == "completed":
                    return response_json(Response(code=400, message="面试已结束"))

                conversation_id = interview_session.conversation_id
                direction = interview_session.direction

                # 获取简历文本
                documents = self.conversation_store_service.get_conversation_documents(conversation_id)
                resume_text = ""
                if documents:
                    latest_doc = documents[-1]
                    parsed_text_path = latest_doc.get("parsed_text_path")
                    if parsed_text_path:
                        import os
                        if os.path.exists(parsed_text_path):
                            with open(parsed_text_path, "r", encoding="utf-8") as f:
                                resume_text = f.read().strip()

                # 获取 JD 文本
                from app.repository.job_analysis_repository import JobAnalysisRepository
                latest_analysis = JobAnalysisRepository.get_latest_by_conversation_id(db_session, conversation_id)
                jd_text = latest_analysis.jd_text if latest_analysis else ""

                # 获取面试历史
                messages = InterviewMessageRepository.list_by_session_id(db_session, session_id)
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                ]

                # 获取当前题目
                current_question = ""
                for msg in reversed(messages):
                    if msg.msg_type == "question" and msg.role == "assistant":
                        current_question = msg.content
                        break

                if not current_question:
                    return response_json(Response(code=500, message="无法找到当前题目"))

                round_number = interview_session.round_count + 1

                # 保存用户回答
                now = datetime.now()
                InterviewMessageRepository.create(
                    db_session,
                    message_id=f"imsg_{uuid.uuid4().hex[:16]}",
                    session_id=session_id,
                    role="user",
                    content=answer,
                    score=None,
                    evaluation="",
                    msg_type="answer",
                    created_at=now,
                )

                # 调用 LLM 评估
                eval_result = self.interview_simulation_service.evaluate_answer(
                    jd_text=jd_text,
                    resume_text=resume_text or "",
                    history=history,
                    current_question=current_question,
                    user_answer=answer,
                    round_number=round_number,
                )

                score = eval_result.get("score", 0)
                evaluation = eval_result.get("evaluation", "")
                next_action = eval_result.get("next_action", "continue")
                follow_up = eval_result.get("follow_up")
                overall_summary = eval_result.get("overall_summary")

                # 保存评估消息
                InterviewMessageRepository.create(
                    db_session,
                    message_id=f"imsg_{uuid.uuid4().hex[:16]}",
                    session_id=session_id,
                    role="assistant",
                    content=evaluation,
                    score=score,
                    evaluation=evaluation,
                    msg_type="evaluation",
                    created_at=now,
                )

                if next_action == "summary":
                    # 结束面试
                    InterviewSessionRepository.update(
                        db_session,
                        interview_session,
                        status="completed",
                        round_count=round_number,
                        total_score=score,
                        overall_summary=overall_summary or evaluation,
                        updated_at=now,
                    )

                    return response_json(Response(message="面试结束", data={
                        "session_id": session_id,
                        "action": "summary",
                        "evaluation": evaluation,
                        "score": score,
                        "overall_summary": overall_summary or evaluation,
                        "question_index": question_index,
                        "total_rounds": round_number,
                    }))
                else:
                    # 继续面试，保存下一题
                    next_question = follow_up or ""
                    if next_question:
                        InterviewMessageRepository.create(
                            db_session,
                            message_id=f"imsg_{uuid.uuid4().hex[:16]}",
                            session_id=session_id,
                            role="assistant",
                            content=next_question,
                            score=None,
                            evaluation="",
                            msg_type="question",
                            created_at=now,
                        )

                    InterviewSessionRepository.update(
                        db_session,
                        interview_session,
                        round_count=round_number,
                        updated_at=now,
                    )

                    return response_json(Response(message="回答已记录", data={
                        "session_id": session_id,
                        "action": "continue",
                        "evaluation": evaluation,
                        "score": score,
                        "next_question": next_question,
                        "question_index": question_index + 1,
                        "total_rounds": round_number,
                    }))

            finally:
                db_session.close()

        except Exception as exc:
            return self._error_response(exc)

    def list_sessions(self):
        """GET /interview/list - 列出面试会话"""
        try:
            conversation_id = (request.args.get("conversation_id") or "").strip()
            if not conversation_id:
                return response_json(Response(code=400, message="conversation_id 参数不能为空"))

            db_manager = DatabaseManager()
            db_session = db_manager.get_session()
            try:
                sessions = InterviewSessionRepository.list_by_conversation_id(db_session, conversation_id)
                return response_json(Response(data={
                    "sessions": [
                        {
                            "session_id": s.session_id,
                            "job_role": s.job_role,
                            "direction": s.direction,
                            "status": s.status,
                            "round_count": s.round_count,
                            "total_score": s.total_score,
                            "created_at": s.created_at.isoformat() if s.created_at else "",
                            "updated_at": s.updated_at.isoformat() if s.updated_at else "",
                        }
                        for s in sessions
                    ],
                }))
            finally:
                db_session.close()

        except Exception as exc:
            return self._error_response(exc)

    def detail(self):
        """GET /interview/detail - 获取面试会话详情"""
        try:
            session_id = (request.args.get("session_id") or "").strip()
            if not session_id:
                return response_json(Response(code=400, message="session_id 参数不能为空"))

            db_manager = DatabaseManager()
            db_session = db_manager.get_session()
            try:
                interview_session = InterviewSessionRepository.get_by_session_id(db_session, session_id)
                if interview_session is None:
                    return response_json(Response(code=404, message="面试会话不存在"))

                messages = InterviewMessageRepository.list_by_session_id(db_session, session_id)

                return response_json(Response(data={
                    "session": {
                        "session_id": interview_session.session_id,
                        "conversation_id": interview_session.conversation_id,
                        "job_role": interview_session.job_role,
                        "direction": interview_session.direction,
                        "status": interview_session.status,
                        "round_count": interview_session.round_count,
                        "total_score": interview_session.total_score,
                        "overall_summary": interview_session.overall_summary,
                        "initial_questions": json.loads(interview_session.initial_questions) if interview_session.initial_questions else [],
                        "created_at": interview_session.created_at.isoformat() if interview_session.created_at else "",
                        "updated_at": interview_session.updated_at.isoformat() if interview_session.updated_at else "",
                    },
                    "messages": [
                        {
                            "message_id": msg.message_id,
                            "role": msg.role,
                            "content": msg.content,
                            "score": msg.score,
                            "evaluation": msg.evaluation,
                            "msg_type": msg.msg_type,
                            "created_at": msg.created_at.isoformat() if msg.created_at else "",
                        }
                        for msg in messages
                    ],
                }))
            finally:
                db_session.close()

        except Exception as exc:
            return self._error_response(exc)
