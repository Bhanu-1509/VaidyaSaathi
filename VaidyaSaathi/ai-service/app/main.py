import logging
import time
from collections import defaultdict, deque
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from app import fallback, gemini
from app.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_HISTORY, REQUESTS_PER_MINUTE

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="VaidyaSaathi AI Assistant", version="1.0.0")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


_hits: dict[str, deque] = defaultdict(deque)


def _rate_limit(ip: str) -> None:
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= REQUESTS_PER_MINUTE:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many messages. Wait a minute and try again.")
    q.append(now)


@app.post("/ai/chat")
def chat(data: ChatRequest, request: Request):
    _rate_limit(request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?"))
    history = [m.model_dump() for m in data.messages][-MAX_HISTORY:]
    while history and history[0]["role"] != "user":   # Gemini needs a user turn first
        history.pop(0)
    if not history or history[-1]["role"] != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The last message must be from the user")
    if not GEMINI_API_KEY:
        return {**fallback.reply(history), "mode": "basic"}
    try:
        return {**gemini.chat(history), "mode": "ai"}
    except gemini.AiError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@app.get("/ai/status")
def ai_status():
    return {"mode": "ai" if GEMINI_API_KEY else "basic", "model": GEMINI_MODEL if GEMINI_API_KEY else None}


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-service"}
