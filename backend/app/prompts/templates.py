from langchain_core.prompts import PromptTemplate

EXPLAIN_CODE_PROMPT = PromptTemplate(
    input_variables=["code", "context"],
    template="""You are an expert AI software engineer. 
Your task is to explain the following code snippet. 

Context (from the rest of the codebase):
{context}

Code to explain:
{code}

Please provide a clear, concise explanation of:
1. What the code does conceptually.
2. The logic and flow of the code.
3. Time and Space complexity (if applicable).
"""
)

DETECT_BUGS_PROMPT = PromptTemplate(
    input_variables=["code", "context"],
    template="""You are an expert AI software security researcher and bug hunter.
Analyze the following code for bugs, edge cases, and security vulnerabilities.

Context (from the rest of the codebase):
{context}

Code to analyze:
{code}

Please provide:
1. Any bugs or edge cases found.
2. Potential security vulnerabilities.
3. Suggestions on how to fix them with code examples.
"""
)

OPTIMIZE_CODE_PROMPT = PromptTemplate(
    input_variables=["code", "context"],
    template="""You are an expert AI software performance engineer.
Analyze the following code for performance optimizations.

Context (from the rest of the codebase):
{context}

Code to analyze:
{code}

Please provide:
1. Current bottlenecks.
2. Step-by-step optimization strategies.
3. The refactored and optimized code.
"""
)

GENERAL_CHAT_PROMPT = PromptTemplate(
    input_variables=["query", "context"],
    template="""You are a helpful AI programming assistant.
Use the following context from the user's codebase to answer their question.
If the answer is not in the context, use your general programming knowledge, but state that you are answering based on general knowledge.

Context:
{context}

Question:
{query}

Answer:"""
)
