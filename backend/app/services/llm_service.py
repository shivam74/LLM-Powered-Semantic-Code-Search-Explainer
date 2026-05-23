from langchain_huggingface import HuggingFaceEndpoint
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableSequence
from app.core.config import settings
from app.prompts.templates import EXPLAIN_CODE_PROMPT, DETECT_BUGS_PROMPT, OPTIMIZE_CODE_PROMPT, GENERAL_CHAT_PROMPT
from fastapi import HTTPException

class LLMService:
    def __init__(self):
        self.llm = None
        self._initialize_llm()

    def _initialize_llm(self):
        if settings.GROQ_API_KEY:
            # Free and extremely fast inference via Groq
            self.llm = ChatGroq(
                model_name="llama-3.1-8b-instant",
                temperature=0.3,
                groq_api_key=settings.GROQ_API_KEY
            )
        elif settings.OPENAI_API_KEY:
            self.llm = ChatOpenAI(
                model_name="gpt-3.5-turbo", 
                temperature=0.3, 
                openai_api_key=settings.OPENAI_API_KEY
            )
        elif settings.HUGGINGFACE_API_KEY:
            # Free option using HuggingFace Inference API (e.g., Llama 3 or Mistral)
            self.llm = HuggingFaceEndpoint(
                repo_id="mistralai/Mistral-7B-Instruct-v0.2", # Using Mistral as a reliable free alternative if Llama 3 is gated
                huggingfacehub_api_token=settings.HUGGINGFACE_API_KEY,
                temperature=0.3, max_new_tokens=1024
            )
        else:
            print("WARNING: No API keys set. AI features will fail.")

    def _get_chain(self, prompt_template) -> RunnableSequence:
        if not self.llm:
            raise HTTPException(status_code=500, detail="LLM is not configured on the server.")
        return prompt_template | self.llm

    def explain_code(self, code: str, context: str = "") -> str:
        chain = self._get_chain(EXPLAIN_CODE_PROMPT)
        return chain.invoke({"code": code, "context": context})

    def detect_bugs(self, code: str, context: str = "") -> str:
        chain = self._get_chain(DETECT_BUGS_PROMPT)
        return chain.invoke({"code": code, "context": context})

    def optimize_code(self, code: str, context: str = "") -> str:
        chain = self._get_chain(OPTIMIZE_CODE_PROMPT)
        return chain.invoke({"code": code, "context": context})

    def general_chat(self, query: str, context: str = "") -> str:
        chain = self._get_chain(GENERAL_CHAT_PROMPT)
        return chain.invoke({"query": query, "context": context})

llm_service = LLMService()
