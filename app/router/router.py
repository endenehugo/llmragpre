from dataclasses import dataclass
from flask import Flask,Blueprint
from injector import inject
from app.handler import TestHandler,ChatSingleHandler,ChatMemoryHandler,IndexHandler,ChatAgentHandler,ChatRagHandler



@inject
@dataclass
class Router:
    test_handler: TestHandler
    chat_single_handler: ChatSingleHandler
    chat_memory_handler: ChatMemoryHandler
    index_handler: IndexHandler
    chat_agent_handler: ChatAgentHandler
    chat_rag_handler: ChatRagHandler

    def register_router(self, app: Flask):
        bp = Blueprint('llmrag', __name__, url_prefix='')
        bp.add_url_rule('/', view_func=self.index_handler.index)


        bp.add_url_rule('/test/test', view_func=self.test_handler.test, methods=['GET'])
        bp.add_url_rule('/chat/single', view_func=self.chat_single_handler.chat_single, methods=['GET'])
        bp.add_url_rule('/chat/memory', view_func=self.chat_memory_handler.chat_memory, methods=['POST'])
        bp.add_url_rule('/chat/agent', view_func=self.chat_agent_handler.chat_agent, methods=['POST'])
        bp.add_url_rule('/chat/rag', view_func=self.chat_rag_handler.chat_rag, methods=['POST'])

        app.register_blueprint(bp)
