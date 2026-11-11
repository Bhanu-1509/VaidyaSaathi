"""Gemini chat loop with function calling (REST, no SDK)."""
import logging

import httpx

from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_URL, MAX_TOOL_ROUNDS
from app.tools import DECLARATIONS, Toolbox, system_prompt

log = logging.getLogger("ai")


class AiError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _call(contents: list[dict]) -> dict:
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt()}]},
        "contents": contents,
        "tools": [{"functionDeclarations": DECLARATIONS}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024},
    }
    try:
        r = httpx.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json=body,
            timeout=45.0,
        )
    except httpx.RequestError as exc:
        raise AiError("Could not reach Gemini. Check the internet connection.", 503) from exc
    if r.status_code == 429:
        raise AiError("The AI assistant is busy (free-tier limit reached). Try again in a minute.", 429)
    if r.status_code in (400, 403) and "API key" in r.text:
        raise AiError("The Gemini API key is not valid. Check GEMINI_API_KEY in .env.", 503)
    if r.status_code == 404:
        raise AiError(f"Gemini model '{GEMINI_MODEL}' was not found. Check GEMINI_MODEL in .env.", 503)
    if r.status_code != 200:
        log.error("Gemini error %s: %s", r.status_code, r.text[:500])
        raise AiError("The AI assistant had a problem. Please try again.", 502)
    return r.json()


def chat(history: list[dict]) -> dict:
    """history: [{"role": "user"|"assistant", "text": str}] -> {"reply", "cards", "memo"}"""
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["text"]}]}
        for m in history
    ]
    tools = Toolbox()

    for _ in range(MAX_TOOL_ROUNDS):
        data = _call(contents)
        candidates = data.get("candidates") or []
        if not candidates:
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise AiError("I can't help with that message." if reason else "No answer from the AI. Try again.", 422)
        content = candidates[0].get("content") or {"role": "model", "parts": []}
        parts = content.get("parts") or []
        calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if not calls:
            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if not text and tools.cards:
                text = "Here you go."
            return {"reply": text or "Sorry, I didn't catch that. Could you rephrase?",
                    "cards": tools.cards, "memo": "; ".join(tools.memo)}

        # Send the model turn back unchanged (it carries thought signatures),
        # then all function responses together in one user turn.
        contents.append({"role": "model", "parts": parts})
        responses = []
        for call in calls:
            result = tools.run(call.get("name", ""), call.get("args") or {})
            fr = {"name": call.get("name", ""), "response": {"result": result}}
            if "id" in call:
                fr["id"] = call["id"]
            responses.append({"functionResponse": fr})
        contents.append({"role": "user", "parts": responses})

    return {"reply": "That took too many steps. Could you tell me a bit more simply what you need?",
            "cards": tools.cards, "memo": "; ".join(tools.memo)}
