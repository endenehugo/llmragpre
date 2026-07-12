from dataclasses import dataclass
from flask import Flask,Blueprint
from injector import inject
from app.handler import TestHandler,ChatSingleHandler,ChatMemoryHandler,IndexHandler,ChatAgentHandler,ChatRagHandler,ConversationHandler,DocumentHandler,JobHandler,ProjectHandler,InterviewHandler



@inject
@dataclass
class Router:
    test_handler: TestHandler
    chat_single_handler: ChatSingleHandler
    chat_memory_handler: ChatMemoryHandler
    index_handler: IndexHandler
    chat_agent_handler: ChatAgentHandler
    chat_rag_handler: ChatRagHandler
    conversation_handler: ConversationHandler
    document_handler: DocumentHandler
    job_handler: JobHandler
    project_handler: ProjectHandler
    interview_handler: InterviewHandler

    def register_router(self, app: Flask):
        bp = Blueprint('llmrag', __name__, url_prefix='')
        bp.add_url_rule('/', view_func=self.index_handler.index)


        bp.add_url_rule('/test/test', view_func=self.test_handler.test, methods=['GET'])
        bp.add_url_rule('/chat/single', view_func=self.chat_single_handler.chat_single, methods=['GET'])
        bp.add_url_rule('/chat/memory', view_func=self.chat_memory_handler.chat_memory, methods=['POST'])
        bp.add_url_rule('/chat/agent', view_func=self.chat_agent_handler.chat_agent, methods=['POST'])
        bp.add_url_rule('/chat/rag', view_func=self.chat_rag_handler.chat_rag, methods=['POST'])
        bp.add_url_rule('/conversation/create', view_func=self.conversation_handler.create, methods=['POST'])
        bp.add_url_rule('/conversation/list', view_func=self.conversation_handler.list, methods=['GET'])
        bp.add_url_rule('/conversation/detail', endpoint='conversation_detail', view_func=self.conversation_handler.detail, methods=['GET'])
        bp.add_url_rule('/conversation/chat', view_func=self.conversation_handler.chat, methods=['POST'])
        bp.add_url_rule('/conversation/image/upload', view_func=self.conversation_handler.upload_image, methods=['POST'])
        bp.add_url_rule('/conversation/image/<conversation_id>/<filename>', view_func=self.conversation_handler.serve_image, methods=['GET'])
        bp.add_url_rule('/api/keycheck', view_func=self.conversation_handler.api_key_check, methods=['GET'])
        bp.add_url_rule('/document/upload', view_func=self.document_handler.upload, methods=['POST'])
        bp.add_url_rule('/document/delete', view_func=self.document_handler.delete, methods=['POST'])
        bp.add_url_rule('/job/analyze', view_func=self.job_handler.analyze, methods=['POST'])
        bp.add_url_rule('/job/analysis/latest', view_func=self.job_handler.get_latest_analysis, methods=['GET'])
        bp.add_url_rule('/job/analysis/list', view_func=self.job_handler.list_analysis, methods=['GET'])

        # 第二阶段：项目经历优化 & 模拟面试
        bp.add_url_rule('/resume/project/rewrite', view_func=self.project_handler.rewrite, methods=['POST'])
        bp.add_url_rule('/interview/start', view_func=self.interview_handler.start, methods=['POST'])
        bp.add_url_rule('/interview/answer', view_func=self.interview_handler.answer, methods=['POST'])
        bp.add_url_rule('/interview/list', view_func=self.interview_handler.list_sessions, methods=['GET'])
        bp.add_url_rule('/interview/detail', endpoint='interview_detail', view_func=self.interview_handler.detail, methods=['GET'])

        app.register_blueprint(bp)
