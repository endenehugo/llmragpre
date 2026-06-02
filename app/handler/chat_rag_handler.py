from dataclasses import dataclass
from injector import inject
from flask import request
from app.response import json, Response
import logging
from operator import itemgetter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.output_parsers import StrOutputParser
from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from app.utils import UniqueComputerUtils, ResourceUtils
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import dashscope

logger = logging.getLogger(__name__)


@inject
@dataclass
class ChatRagHandler:
    uniqueComputerUtils: UniqueComputerUtils

    def __post_init__(self):
        self.llm = None
        self.embeddings = None
        self.db = None
        self.retriever = None
        self.prompt = None
        self.memory = None
        self.contextualize_q = None
        self.chain = None

    def _ensure_initialized(self):
        if self.chain is not None:
            return

        # 初始化LLM模型
        self.llm = ChatTongyi(
            streaming=True,
            model="qwen-plus",
            temperature=0.8,
            top_p=0.7,
        )

        # 定义embedding组件
        self.embeddings = dashscope.DashScopeEmbeddings(model="text-embedding-v3")

        # 加载向量数据库
        self.db = FAISS.load_local(
            ResourceUtils.get_resource_path("faiss_index"),
            self.embeddings,
            allow_dangerous_deserialization=True
        )

        # 构建向量数据库查询器
        self.retriever = self.db.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 3, "score_threshold": 0.4},
        )

        # 定义RAG系统提示和对话模板
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的问答机器人。
            你将获得以下信息：
            1. 相关文档内容
            2. 聊天历史记录
            3. 用户当前问题

            请基于这些信息，以专业、友好的方式回答用户问题。如果相关文档内容对回答有帮助，请参考使用，但要用自然的方式融入回答中。
            如果文档内容与问题无关，则可以基于自身知识回答。"""),
            MessagesPlaceholder("history"),
            ("human", """相关文档内容：{context}

            用户问题：{query}"""),
        ])

        # 定义记忆模块
        self.memory = ConversationBufferMemory(
            input_key="query",
            output_key="output",
            return_messages=True
        )

        # 构建RAG链
        # 1. 准备上下文
        self.contextualize_q = RunnablePassthrough.assign(
            context=lambda x: self._get_context(x["query"])
        )

        # 2. 构建完整的链
        self.chain = (
                self.contextualize_q
                | RunnablePassthrough.assign(
            history=RunnableLambda(self.memory.load_memory_variables) | itemgetter("history")
        )
                | self.prompt
                | self.llm
                | StrOutputParser()
        )

    def _get_context(self, query: str) -> str:
        """获取相关文档内容"""
        docs = self.retriever.get_relevant_documents(query)
        # 将所有相关文档内容拼接在一起
        return "\n".join(doc.page_content for doc in docs)

    def chat_rag_args(self):
        self._ensure_initialized()
        # 接收页面参数
        query = request.args.get('query', default=None, type=str)

        # 调用链处理问题
        chain_output = self.chain.invoke({"query": query})

        # 获取langchain的history
        langchain_history = self.prompt.format_messages(
            query=query,
            context=self._get_context(query),
            history=self.memory.load_memory_variables({})["history"]
        )

        # 保存本轮对话到记忆
        self.memory.save_context(
            {"query": query},
            {"output": chain_output}
        )

        # 格式化历史记录用于返回
        history = [{"role": item.type, "content": item.content} for item in langchain_history]

        # 返回响应
        response = Response(
            message=f"亲爱的，{chain_output}",  # 确保回复以"亲爱的"开头
            data={
                "history": history,
                "host_name": self.uniqueComputerUtils.get_host_name(),
                "mac_address": self.uniqueComputerUtils.get_mac_address()
            }
        )
        return json(response)

    def chat_rag(self):
        try:
            self._ensure_initialized()
            # 接收页面参数
            data = request.get_json()
            logger.info(f"收到请求数据: {data}")
            
            query = data.get('query', '') if data else ''
            if not query:
                logger.error("query参数为空")
                return json(Response(message="query参数不能为空", code="fail"))
            
            logger.info(f"用户问题: {query}")

            # 调用链处理问题
            chain_output = self.chain.invoke({"query": query})

            # 获取langchain的history
            langchain_history = self.prompt.format_messages(
                query=query,
                context=self._get_context(query),
                history=self.memory.load_memory_variables({})["history"]
            )

            # 保存本轮对话到记忆
            self.memory.save_context(
                {"query": query},
                {"output": chain_output}
            )

            # 格式化历史记录用于返回
            history = [{"role": item.type, "content": item.content} for item in langchain_history]
            response = Response(
                message=f"亲爱的，{chain_output}",  # 确保回复以"亲爱的"开头
                data={
                    "history": history,
                    "host_name": self.uniqueComputerUtils.get_host_name(),
                    "mac_address": self.uniqueComputerUtils.get_mac_address()
                }
            )
            return json(response)
            
        except Exception as e:
            logger.error(f"chat_rag处理出错: {str(e)}", exc_info=True)
            return json(Response(message=f"服务器错误: {str(e)}", code="fail"))