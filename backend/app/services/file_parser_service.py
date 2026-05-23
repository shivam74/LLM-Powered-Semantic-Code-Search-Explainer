import os
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List

class FileParserService:
    def __init__(self):
        # Map file extensions to Langchain Language Enums
        self.extension_to_lang = {
            ".py": Language.PYTHON,
            ".js": Language.JS,
            ".jsx": Language.JS,
            ".ts": Language.TS,
            ".tsx": Language.TS,
            ".cpp": Language.CPP,
            ".java": Language.JAVA,
            ".go": Language.GO,
            ".rs": Language.RUST,
            ".php": Language.PHP,
        }

    def parse_and_chunk(self, file_content: str, filename: str, project_id: str) -> List[Document]:
        """Parse file content and split into chunks based on language structure."""
        ext = os.path.splitext(filename)[1].lower()
        
        # Default to generic recursive splitter if language is not supported
        lang = self.extension_to_lang.get(ext)
        
        if lang:
            splitter = RecursiveCharacterTextSplitter.from_language(
                language=lang,
                chunk_size=1000,
                chunk_overlap=200
            )
        else:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200
            )
            
        chunks = splitter.split_text(file_content)
        
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "filename": filename,
                    "project_id": project_id,
                    "chunk_index": i,
                    "extension": ext
                }
            )
            documents.append(doc)
            
        return documents

file_parser = FileParserService()
