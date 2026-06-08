import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.document_index_service import DocumentIndexService


class FakeRetriever:
    def __init__(self, docs):
        self.docs = docs

    def get_relevant_documents(self, query):
        return self.docs


class FakeConversationDb:
    def __init__(self, threshold_docs, fallback_docs):
        self.threshold_docs = threshold_docs
        self.fallback_docs = fallback_docs
        self.calls = []

    def as_retriever(self, search_type, search_kwargs):
        self.calls.append((search_type, search_kwargs))
        if search_type == "similarity_score_threshold":
            return FakeRetriever(self.threshold_docs)
        if search_type == "similarity":
            return FakeRetriever(self.fallback_docs)
        raise AssertionError(f"unexpected search_type: {search_type}")


class DocumentIndexServiceTest(unittest.TestCase):
    def test_get_context_falls_back_to_similarity_when_threshold_returns_nothing(self):
        service = DocumentIndexService()
        conversation_db = FakeConversationDb(
            threshold_docs=[],
            fallback_docs=[SimpleNamespace(page_content="test.txt里面有说明")],
        )
        service._load_conversation_db = lambda conversation_id: conversation_db
        service._load_public_retriever = lambda: None

        context = service.get_context("conv_1", "test.txt里面有什么")

        self.assertEqual(context, "test.txt里面有说明")
        self.assertEqual(
            conversation_db.calls,
            [
                ("similarity_score_threshold", {"k": 4, "score_threshold": 0.35}),
                ("similarity", {"k": 4}),
            ],
        )

    def test_rebuild_conversation_index_includes_original_name_in_indexed_text(self):
        service = DocumentIndexService()
        documents = [{
            "document_id": "doc_1",
            "original_name": "test.docx",
            "parsed_text_path": "F:\\code\\llmrag\\resources\\parsed_docs\\conv_20260602155711_9a32c3\\doc_bd607ab4716741ec.txt",
        }]

        with patch("app.services.document_index_service.FAISS.from_texts") as mocked_from_texts, patch.object(service, "_ensure_embeddings", return_value="embeddings"), patch.object(service, "_get_conversation_index_dir", return_value="F:\\code\\llmrag\\resources\\faiss_index_uploads\\conv_test"), patch.object(service, "_chunk_text", return_value=["123"]):
            mocked_from_texts.return_value = SimpleNamespace(save_local=lambda index_dir: None)

            service.rebuild_conversation_index("conv_test", documents)

        indexed_texts = mocked_from_texts.call_args.args[0]
        self.assertEqual(indexed_texts, ["文件名：test.docx\n123"])


if __name__ == "__main__":
    unittest.main()