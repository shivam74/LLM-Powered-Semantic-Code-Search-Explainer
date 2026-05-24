import os
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from app.core.config import settings
from langchain_core.documents import Document
from typing import List

class VectorDBService:
    def __init__(self):
        # We use a lightweight open-source embedding model via the HF Inference API
        self.embeddings = HuggingFaceEndpointEmbeddings(
            model="sentence-transformers/all-MiniLM-L6-v2",
            huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY
        )
        self.persist_directory = "./chroma_data"
        
        # Initialize chroma db
        self.vector_store = Chroma(
            collection_name="code_chunks",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def add_documents(self, documents: List[Document]):
        """Add parsed documents to ChromaDB"""
        self.vector_store.add_documents(documents)
        
    def search(self, query: str, project_id: str = None, top_k: int = 5) -> List[Document]:
        """Search documents, optionally filtered by project_id"""
        filter_dict = {"project_id": project_id} if project_id else None
        
        # similarity_search_with_score returns List[Tuple[Document, float]]
        results = self.vector_store.similarity_search_with_score(
            query, 
            k=top_k, 
            filter=filter_dict
        )
        return results

    def delete_by_project(self, project_id: str):
        """Delete all vectors associated with a project_id from ChromaDB"""
        collection = self.vector_store._collection
        results = collection.get(where={"project_id": project_id})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)

    def delete_by_file(self, project_id: str, filename: str):
        """Delete all vectors for a specific file within a project"""
        collection = self.vector_store._collection
        results = collection.get(where={"$and": [{"project_id": project_id}, {"filename": filename}]})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)


class VectorDBProxy:
    _instance = None
    
    @property
    def instance(self):
        if self._instance is None:
            self._instance = VectorDBService()
        return self._instance

    def add_documents(self, documents):
        return self.instance.add_documents(documents)
        
    def search(self, query: str, project_id: str = None, top_k: int = 5):
        return self.instance.search(query, project_id, top_k)

    def delete_by_project(self, project_id: str):
        return self.instance.delete_by_project(project_id)

    def delete_by_file(self, project_id: str, filename: str):
        return self.instance.delete_by_file(project_id, filename)

# Singleton instance
vector_db = VectorDBProxy()
