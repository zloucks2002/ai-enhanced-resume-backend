import uuid
from chatbot import (
    init_conversation,
    get_resume_json,
    get_resume_preferences,
)
from app.utils.openai_client import get_openai

# In-memory session storage
SESSIONS = {}

def start_chat_session(user_id=None):
    session_id = str(uuid.uuid4())
    messages = init_conversation()

    SESSIONS[session_id] = {
        "messages": messages,
        "user_id": user_id,
        "resume_json": {},           
        "preferences_json": {},      
    }

    # Return assistant greeting
    return {
        "session_id": session_id,
        "message": messages[-1]["content"],
    }


def send_chat_message(session_id: str, text: str):
    session = SESSIONS.get(session_id)
    if not session:
        return {"error": "Invalid session_id"}

    client = get_openai()

    # Append user message
    session["messages"].append({"role": "user", "content": text})

    # Get assistant reply
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=session["messages"],
            temperature=0.5,
        )
        reply = completion.choices[0].message.content
        session["messages"].append({"role": "assistant", "content": reply})
    except Exception as e:
        return {"error": str(e)}

    # Detect readiness
    ready = "i'm ready to generate the resume." in reply.lower()

    return {
        "reply": reply,
        "session_id": session_id,
        "ready_to_generate": ready
    }



def get_resume_json_from_session(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        return {"resume_json": {}}
    if not session.get("resume_json"):
        client = get_openai()
        resume_json = get_resume_json(session["messages"], client)
        session["resume_json"] = resume_json
    return {"resume_json": session["resume_json"]}

def get_preferences_from_session(session_id):
    session = SESSIONS.get(session_id)
    if not session:
        return {"preferences": {}}
    if not session.get("preferences_json"):
        client = get_openai()
        preferences = get_resume_preferences(session["messages"], client)
        session["preferences_json"] = preferences
    return {"preferences": session["preferences_json"]}
