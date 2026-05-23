import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from typing import List

class VectorDBService:
    def __init__(self):
        # We use a lightweight open-source embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
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

# Singleton instance
vector_db = VectorDBService()
