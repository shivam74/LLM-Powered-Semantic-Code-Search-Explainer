from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.schemas.chat import ChatRequest, ChatResponse, ChatAction
from app.services.llm_service import llm_service
from app.services.hybrid_retrieval_service import hybrid_retrieval

router = APIRouter()


async def _get_context(query: str, project_id: str) -> str:
    """Fetch relevant context using hybrid retrieval (vector + BM25)."""
    if not project_id:
        return ""
    results = await hybrid_retrieval.search(query=query, project_id=project_id, top_k=3)
    parts = []
    for r in results:
        filename = r.metadata.get("filename", "unknown")
        fn = r.metadata.get("function_name", "")
        label = f"{filename}" + (f" → {fn}" if fn else "")
        parts.append(f"--- {label} ---\n{r.raw_content}")
    return "\n\n".join(parts)


@router.post("/", response_model=ChatResponse)
async def chat_interaction(
    request: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    context = ""
    if request.project_id:
        search_query = request.code if request.action != ChatAction.GENERAL else request.query
        context = await _get_context(search_query, request.project_id)

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

        if hasattr(response_text, "content"):
            response_text = response_text.content

        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
