from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from flask import current_app
from langchain_community.embeddings import dashscope
from langchain_community.vectorstores import FAISS

from app.utils import ResourceUtils


@dataclass
class DocumentIndexService:
    def __post_init__(self):
        self.embeddings = None
        self.public_db = None

    def rebuild_conversation_index(self, conversation_id: str, documents: list[dict]) -> dict:
        index_dir = self._get_conversation_index_dir(conversation_id)
        texts = []
        metadatas = []

        for document in documents:
            parsed_text_path = document.get("parsed_text_path")
            if not parsed_text_path or not os.path.exists(parsed_text_path):
                continue
            with open(parsed_text_path, "r", encoding="utf-8") as text_file:
                content = text_file.read().strip()
            if not content:
                continue

            for chunk_index, chunk in enumerate(self._chunk_text(content)):
                texts.append(self._build_index_text(document, chunk))
                metadatas.append({
                    "conversation_id": conversation_id,
                    "document_id": document.get("document_id"),
                    "chunk_index": chunk_index,
                    "original_name": document.get("original_name", ""),
                })

        if os.path.isdir(index_dir):
            shutil.rmtree(index_dir)

        if not texts:
            os.makedirs(index_dir, exist_ok=True)
            return {"chunk_count": 0}

        db = FAISS.from_texts(texts, self._ensure_embeddings(), metadatas=metadatas)
        db.save_local(index_dir)
        return {"chunk_count": len(texts)}

    def get_context(self, conversation_id: str, query: str, limit: int = 4) -> str:
        docs = []
        conversation_db = self._load_conversation_db(conversation_id)
        if conversation_db is not None:
            docs = self._search_conversation_docs(conversation_db, query, limit)

        if not docs:
            public_retriever = self._load_public_retriever()
            if public_retriever is not None:
                docs = public_retriever.get_relevant_documents(query)

        return "\n\n".join(doc.page_content for doc in docs)

    @staticmethod
    def _build_index_text(document: dict, chunk: str) -> str:
        original_name = (document.get("original_name") or "").strip()
        if not original_name:
            return chunk
        return f"文件名：{original_name}\n{chunk}"

    def _search_conversation_docs(self, conversation_db, query: str, limit: int):
        threshold_retriever = conversation_db.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": limit, "score_threshold": 0.35},
        )
        docs = threshold_retriever.get_relevant_documents(query)
        if docs:
            return docs

        # 文件概述类问题与超短文本的向量相似度常常偏低，兜底返回最相关分片。
        fallback_retriever = conversation_db.as_retriever(
            search_type="similarity",
            search_kwargs={"k": limit},
        )
        return fallback_retriever.get_relevant_documents(query)

    def delete_conversation_index(self, conversation_id: str) -> None:
        index_dir = self._get_conversation_index_dir(conversation_id)
        if os.path.isdir(index_dir):
            shutil.rmtree(index_dir)

    def _chunk_text(self, content: str) -> list[str]:
        chunk_size = current_app.config.get("CONVERSATION_INDEX_CHUNK_SIZE", 700)
        chunk_overlap = current_app.config.get("CONVERSATION_INDEX_CHUNK_OVERLAP", 120)
        chunks = []
        start = 0
        content_length = len(content)
        while start < content_length:
            end = min(start + chunk_size, content_length)
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= content_length:
                break
            start = max(end - chunk_overlap, start + 1)
        return chunks

    def _ensure_embeddings(self):
        if self.embeddings is None:
            self.embeddings = dashscope.DashScopeEmbeddings(model="text-embedding-v3")
        return self.embeddings

    def _load_conversation_db(self, conversation_id: str):
        index_dir = self._get_conversation_index_dir(conversation_id)
        if not os.path.isdir(index_dir):
            return None
        if not any(name.endswith(".faiss") for name in os.listdir(index_dir)):
            return None
        return FAISS.load_local(
            index_dir,
            self._ensure_embeddings(),
            allow_dangerous_deserialization=True,
        )

    def _load_public_retriever(self):
        public_path = ResourceUtils.get_resource_path("faiss_index")
        if not os.path.isdir(public_path):
            return None
        if self.public_db is None:
            self.public_db = FAISS.load_local(
                public_path,
                self._ensure_embeddings(),
                allow_dangerous_deserialization=True,
            )
        return self.public_db.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 3, "score_threshold": 0.4},
        )

    @staticmethod
    def _get_conversation_index_dir(conversation_id: str) -> str:
        return ResourceUtils.get_resource_path(os.path.join("faiss_index_uploads", conversation_id))