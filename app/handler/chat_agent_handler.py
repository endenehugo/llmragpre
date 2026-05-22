from dataclasses import dataclass
from flask import request
from langchain_community.vectorstores import FAISS
from app.tools import MultiplyTool, WebSearchTool
from injector import inject
from langchain_community.chat_models import ChatTongyi
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder
from langchain_core.messages import ToolMessage
import logging
from app.response import Response,json
from langchain_community.embeddings import dashscope
from app.utils import ResourceUtils,UniqueComputerUtils

logger = logging.getLogger(__name__)

@inject
@dataclass
class ChatAgentHandler:
    uniqueComputerUtils: UniqueComputerUtils

    def __post_init__(self):
        self.llm=ChatTongyi(
            streaming = True,
            model = "qwen-plus",
            temperature = 0.8,
            top_p =0.7,
        )
        tools = [MultiplyTool(), WebSearchTool()]
        self.tool_dic = {tool.name: tool for tool in tools}

        self.llm = self.llm.bind_tools(tools)

        self.embeddings = dashscope.DashScopeEmbeddings(model = "text-embedding-v3")

        self.db =FAISS.load_local(
            ResourceUtils.get_resource_path("faiss_index"),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )

        self.retriever = self.db.as_retriever(
            search_type = "similarity_score_threshold",
            search_kwargs = {"k": 3, "score_threshold": 0.4},
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个问答机器人。
            你将获得以下信息：
            1. 相关文档内容
            2. 聊天历史记录
            3. 用户当前问题

            请基于这些信息，以专业、友好的方式回答用户问题。如果相关文档内容对回答有帮助，请参考使用，但要用自然的方式融入回答中。
            如果文档内容与问题无关，则可以基于自身知识回答。
            当用户的问题需要最新信息、外部网页资料、官网说明、新闻动态或互联网检索时，请主动调用 web_search_tool。
            使用搜索结果回答时，优先整合摘要，并在回答中保留关键来源链接。"""),
            MessagesPlaceholder("history"),
            ("human", """相关的文档内容：{context}
            用户的问题：{query}
            """),
        ])

        self.memory = ConversationBufferMemory(
            input_key="query",
            output_key="output",
            return_messages=True
        )

    def _get_context(self,query:str) -> str:
        docs = self.retriever.get_relevant_documents(query)
        return "".join([doc.page_content for doc in docs])

    def chat_agent(self):
        try:
            data = request.get_json()
            logger.info(f"收到请求数据: {data}")
            
            query = data.get("query")
            if not query:
                logger.error("query参数为空")
                return json(Response(message="query参数不能为空", code=400))
            
            logger.info(f"用户问题: {query}")
            
            message = self.prompt.invoke({
                "query":query,
                "history":self.memory.load_memory_variables({})["history"],
                "context":self._get_context(query)
            }).to_messages()

            cur = len(message)-1
            chain_output = ""
            
            for attempt in range(3):
                resp = self.llm.invoke(message)
                message.append(resp)
                tool_calls = resp.tool_calls
                if tool_calls:
                    for tool_call in tool_calls:
                        tool = self.tool_dic.get(tool_call.get("name"))
                        if tool is None:
                            content = f"工具不存在：{tool_call.get('name')}"
                            logger.error(content)
                        else:
                            logger.info(f"正在执行的工具：{tool.name}")
                            content = tool.invoke(tool_call.get("args"))
                        logger.info(f"工具执行结果：{content}")
                        tool_call_id = tool_call.get("id")
                        message.append(ToolMessage(tool_call_id=tool_call_id, content=content))
                else:
                    chain_output = resp.content
                    break

            if not chain_output:
                chain_output = "抱歉，我无法生成回答"
                logger.warning("未能生成有效回答")

            langchain_history = self.prompt.format_messages(
                query=query,
                context=self._get_context(query),
                history=self.memory.load_memory_variables({})["history"]
            )

            # 记录本次会话
            self.memory.chat_memory.add_messages(message[cur:])

            history = [{"role": item.type, "content": item.content} for item in langchain_history]
            response = Response(
                message=f"答案，{chain_output}",
                data={
                    "history": history,
                    "host_name": self.uniqueComputerUtils.get_host_name(),
                    "mac_address": self.uniqueComputerUtils.get_mac_address()
                }
            )
            return json(response)
            
        except Exception as e:
            logger.error(f"chat_agent处理出错: {str(e)}", exc_info=True)
            return json(Response(message=f"服务器错误: {str(e)}", code=500))
