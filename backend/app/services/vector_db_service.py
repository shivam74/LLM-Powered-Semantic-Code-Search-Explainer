"""
Updated VectorDB Service.

Key changes from the original:
  - Stores ENRICHED text as the ChromaDB document (used for embeddings).
  - Stores RAW code in metadata field "raw_content" (returned to users).
  - Extended metadata: function_name, class_name, start_line, end_line, etc.
  - delete_by_file uses filename-prefix chunk_ids for reliable cleanup.
  - Lazy initialisation via VectorDBProxy (unchanged from before).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from langchain_core.documents import Document

from app.services.observability import log_error


class VectorDBService:

    def __init__(self):
        from langchain_community.vectorstores import Chroma
        from langchain_huggingface import HuggingFaceEndpointEmbeddings
        from app.core.config import settings

        # Embed via HF Inference API — no local model download
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY,
        )
        self.persist_directory = "./chroma_data"

        self.vector_store = Chroma(
            collection_name="code_chunks",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory,
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_enriched_chunks(
        self,
        enriched_texts: List[str],
        metadatas: List[dict],
        ids: List[str],
    ):
        """
        Add pre-enriched chunks to ChromaDB.

        enriched_texts: the text to embed (context header + raw code).
        metadatas:      flat dicts with all chunk metadata including raw_content.
        ids:            stable unique IDs per chunk (used for dedup & deletion).
        """
        # ChromaDB requires all metadata values to be str/int/float/bool.
        # Ensure raw_content is stored but truncated to avoid hitting limits.
        clean_metas = []
        for m in metadatas:
            clean = {k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                     for k, v in m.items()}
            if "raw_content" in clean:
                clean["raw_content"] = clean["raw_content"][:4000]
            clean_metas.append(clean)

        # ChromaDB upserts by id — safe to call multiple times
        self.vector_store.add_texts(
            texts=enriched_texts,
            metadatas=clean_metas,
            ids=ids,
        )

    # Legacy: accept LangChain Document objects (backward compat with old pipeline)
    def add_documents(self, documents: List[Document]):
        """Backward-compatible method for old-style Document objects."""
        texts = [d.page_content for d in documents]
        metas = [d.metadata for d in documents]
        # Generate stable ids from filename + chunk_index
        ids = [
            f"{m.get('filename','f')}_{m.get('chunk_index', i)}"
            for i, m in enumerate(metas)
        ]
        self.add_enriched_chunks(texts, metas, ids)

    # ── Read ──────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        top_k: int = 20,
    ) -> List[Tuple[Document, float]]:
        """
        Dense vector search. Returns (Document, distance_score) pairs.
        Document.page_content = raw_content (swapped for display).
        """
        filter_dict = {"project_id": project_id} if project_id else None
        results = self.vector_store.similarity_search_with_score(
            query, k=top_k, filter=filter_dict
        )

        # Swap page_content back to raw_content for display
        display_results = []
        for doc, score in results:
            raw = doc.metadata.get("raw_content", doc.page_content)
            display_doc = Document(page_content=raw, metadata=doc.metadata)
            display_results.append((display_doc, score))

        return display_results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[dict]:
        """Fetch a single chunk's metadata by its stable ID."""
        try:
            result = self.vector_store._collection.get(ids=[chunk_id])
            if result["ids"]:
                return {
                    "id": result["ids"][0],
                    "metadata": result["metadatas"][0] if result["metadatas"] else {},
                    "content": result["documents"][0] if result["documents"] else "",
                }
        except Exception as e:
            log_error("vector_db.get_chunk", error=str(e))
        return None

    def list_chunks(self, project_id: str) -> List[dict]:
        """List all chunk metadata for a project (no embeddings returned)."""
        try:
            result = self.vector_store._collection.get(
                where={"project_id": project_id},
                include=["metadatas", "documents"],
            )
            chunks = []
            for cid, meta, doc in zip(
                result.get("ids", []),
                result.get("metadatas", []),
                result.get("documents", []),
            ):
                chunks.append({"id": cid, "metadata": meta})
            return chunks
        except Exception as e:
            log_error("vector_db.list_chunks", error=str(e))
            return []

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_by_project(self, project_id: str):
        try:
            collection = self.vector_store._collection
            results = collection.get(where={"project_id": project_id})
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
        except Exception as e:
            log_error("vector_db.delete_project", error=str(e))

    def delete_by_file(self, project_id: str, filename: str):
        try:
            collection = self.vector_store._collection
            results = collection.get(
                where={"$and": [{"project_id": project_id}, {"filename": filename}]}
            )
            ids = results.get("ids", [])
            if ids:
                collection.delete(ids=ids)
        except Exception as e:
            log_error("vector_db.delete_file", error=str(e))


# ── Lazy proxy (unchanged pattern) ───────────────────────────────────────────

class VectorDBProxy:
    _instance: Optional[VectorDBService] = None

    @property
    def instance(self) -> VectorDBService:
        if self._instance is None:
            self._instance = VectorDBService()
        return self._instance

    def add_enriched_chunks(self, enriched_texts, metadatas, ids):
        return self.instance.add_enriched_chunks(enriched_texts, metadatas, ids)

    def add_documents(self, documents):
        return self.instance.add_documents(documents)

    def search(self, query, project_id=None, top_k=20):
        return self.instance.search(query, project_id, top_k)

    def get_chunk_by_id(self, chunk_id):
        return self.instance.get_chunk_by_id(chunk_id)

    def list_chunks(self, project_id):
        return self.instance.list_chunks(project_id)

    def delete_by_project(self, project_id):
        return self.instance.delete_by_project(project_id)

    def delete_by_file(self, project_id, filename):
        return self.instance.delete_by_file(project_id, filename)


vector_db = VectorDBProxy()
