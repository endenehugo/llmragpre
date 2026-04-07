from dataclasses import dataclass
from flask import request
from app.response import success_message
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatTongyi
from injector import inject
import logging
logger = logging.getLogger(__name__)

@inject
@dataclass
class ChatSingleHandler:

    def __init__(self):
        llm=ChatTongyi(
            streaming = True,
            model = "qwen-plus",
            temperature = 0.8,
            top_p =0.7,
        )
        prompt = ChatPromptTemplate.from_template(
            "你是一个专业的助手，你的回答必须符合中文的语法规范，用户的问题：{query}",
        )
        parser = StrOutputParser()
        self.chain = prompt|llm|parser
    def chat_single(self):
        query = request.args.get("query", default="None", type=str)
        result = self.chain.invoke({"query": query})
        return success_message(result)
