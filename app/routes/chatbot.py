from fastapi import APIRouter
from pydantic import BaseModel
from app.services.chatbot_service import (
    start_chat_session,
    send_chat_message,
    get_resume_json_from_session,
    get_preferences_from_session
)

router = APIRouter()

class ChatStartRequest(BaseModel):
    user_id: str | None = None

class ChatMessageRequest(BaseModel):
    message: str
    session_id: str

@router.post("/start")
def start_chat(req: ChatStartRequest):
    return start_chat_session(req.user_id)

@router.post("/message")
def send_message(req: ChatMessageRequest):
    return send_chat_message(req.session_id, req.message)

@router.get("/json/{session_id}")
def get_resume_json_api(session_id: str):
    """Return the resume_json extracted from the chatbot session."""
    return get_resume_json_from_session(session_id)

@router.get("/preferences/{session_id}")
def get_preferences_api(session_id: str):
    """Return the resume preferences extracted from the chatbot session."""
    return get_preferences_from_session(session_id)
