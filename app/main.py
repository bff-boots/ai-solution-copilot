from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.rag import answer

BASE_DIR = Path(__file__).resolve().parent
sessions: dict[str, list[dict[str, str]]] = {}
app = FastAPI(title="AI Solution Copilot", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = None


class SolutionRequest(BaseModel):
    industry: str = Field(min_length=1, max_length=80)
    scenario: str = Field(min_length=1, max_length=500)
    budget: str = Field(default="未说明", max_length=80)
    compute_scale: str = Field(default="未说明", max_length=80)
    session_id: str | None = None


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict:
    session_id = payload.session_id or str(uuid4())
    history = sessions.setdefault(session_id, [])
    try:
        result = answer(payload.question.strip(), history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    history.extend([{"role": "user", "content": payload.question.strip()}, {"role": "assistant", "content": result["answer"]}])
    return {"session_id": session_id, **result}


@app.post("/api/solution")
def solution(payload: SolutionRequest) -> dict:
    session_id = payload.session_id or str(uuid4())
    history = sessions.setdefault(session_id, [])
    question = (
        f"请为以下企业客户输出可执行的 AI 方案建议。行业：{payload.industry}；"
        f"业务场景：{payload.scenario}；预算：{payload.budget}；"
        f"部署规模：{payload.compute_scale}。"
        "请按需求判断、推荐架构、实施步骤、风险与下一步行动五部分回答。"
    )
    try:
        result = answer(question, history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": result["answer"]}])
    return {"session_id": session_id, **result}


@app.delete("/api/sessions/{session_id}")
def clear_session(session_id: str) -> dict[str, bool]:
    sessions.pop(session_id, None)
    return {"cleared": True}
