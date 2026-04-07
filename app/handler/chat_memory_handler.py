from dataclasses import dataclass
from flask import request
from injector import inject
from app.response import success_message
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter
from app.response import Response,json
import logging

logger = logging.getLogger(__name__)


class ChatMemoryHandler:
    def __init__(self):
        llm = ChatTongyi(
            streaming = True,
            model = "qwen-plus",
            temperature = 0.8,
            top_p =0.7,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的助手，你的回答必须符合中文的语法规范"),
            MessagesPlaceholder("history"),
            ("human", "用户的问题是：{query}"),
        ])
        self.memory = ConversationBufferMemory(
            input_key="query",
            output_key="output",
            return_messages=True,
        )
        self.chain = RunnablePassthrough.assign(
            history=RunnableLambda(self.memory.load_memory_variables)|itemgetter("history")
        ) | self.prompt | llm | StrOutputParser()

    def chat_memory(self):
        try:
            # 修复：从 POST 请求体获取数据，而不是 GET 参数
            data = request.get_json()
            logger.info(f"收到请求数据: {data}")
            
            query = data.get("query", "None") if data else "None"
            if not query or query == "None":
                logger.error("query参数为空")
                return json(Response(message="query参数不能为空", code="fail"))
            
            logger.info(f"用户问题: {query}")
            
            chain_input = {"query": query}
            chain_output = self.chain.invoke(chain_input)
            
            langchain_history = self.prompt.format_messages(
                query=query,
                history=self.memory.load_memory_variables({})["history"]
            )
            
            self.memory.save_context(
                {"query": self.prompt.format_messages(query=query, history=[])[-1].content},
                {"output": chain_output}
            )
            
            history = [{"role": item.type, "text": item.content} for item in langchain_history]
            response = Response(message=chain_output, data={"history": history})
            return json(response)
            
        except Exception as e:
            logger.error(f"chat_memory处理出错: {str(e)}", exc_info=True)
            return json(Response(message=f"服务器错误: {str(e)}", code="fail"))
