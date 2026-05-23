from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.chat import ChatRequest, ChatResponse, ChatAction
from app.services.llm_service import llm_service
from app.services.vector_db_service import vector_db

router = APIRouter()

def get_context_for_query(query: str, project_id: str) -> str:
    """Helper to fetch relevant context from ChromaDB if project_id is provided"""
    if not project_id:
        return ""
    
    # Retrieve top 3 relevant chunks
    raw_results = vector_db.search(query, project_id, top_k=3)
    context_parts = []
    for doc, _ in raw_results:
        filename = doc.metadata.get('filename', 'unknown')
        context_parts.append(f"--- From {filename} ---\n{doc.page_content}")
        
    return "\n\n".join(context_parts)

@router.post("/", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    # Depending on the action, we decide how to build the context
    context = ""
    if request.project_id:
        search_query = request.code if request.action != ChatAction.GENERAL else request.query
        context = get_context_for_query(search_query, request.project_id)

    response_text = ""
    try:
        if request.action == ChatAction.EXPLAIN:
            response_text = llm_service.explain_code(request.code, context)
        elif request.action == ChatAction.DETECT_BUGS:
            response_text = llm_service.detect_bugs(request.code, context)
        elif request.action == ChatAction.OPTIMIZE:
            response_text = llm_service.optimize_code(request.code, context)
        elif request.action == ChatAction.GENERAL:
            response_text = llm_service.general_chat(request.query, context)
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        # Parse output for HuggingFace (it sometimes returns the prompt + output)
        if hasattr(response_text, "content"): # if it's an AIMessage (OpenAI)
            response_text = response_text.content
            
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
