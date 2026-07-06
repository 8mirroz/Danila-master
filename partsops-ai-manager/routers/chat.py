from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & LLM"])


class ChatMessagePayload(BaseModel):
    role: str
    content: str


class ChatCompletionPayload(BaseModel):
    model: str = "default"
    messages: list[ChatMessagePayload]
    stream: bool = False


@router.post("/completions")
async def chat_completions(payload: ChatCompletionPayload):
    user_messages = [message for message in payload.messages if message.role == "user" and message.content.strip()]
    if not user_messages:
        raise HTTPException(status_code=400, detail="At least one user message is required")

    system_prompt = next((message.content for message in payload.messages if message.role == "system"), "You are a helpful assistant")
    user_prompt = "\n".join(message.content for message in user_messages)

    from llm import call_llm_async

    content = await call_llm_async(
        prompt=user_prompt,
        system_prompt=system_prompt,
        model=payload.model,
    )
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
