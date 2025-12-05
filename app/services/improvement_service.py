# app/services/improvement_service.py

import uuid
import json
from typing import Dict, Any
from datetime import datetime

from app.utils.supabase_client import supabase
from app.utils.openai_client import get_openai
from app.services.analysis_service import analyze_resume_service
from chatbot import (
    get_resume_json,
    get_resume_preferences,
    normalize_descriptions,
)
from render_resume import generate_html_from_template
from app.services.resume_service import generate_unique_resume_name

# In-memory improvement sessions
IMPROVE_SESSIONS: Dict[str, Dict[str, Any]] = {}

def _get_resume_file_bytes_and_ext(resume: dict):
    source_type = resume.get("source_type")
    original_path = resume.get("original_file_path")
    file_bytes = None
    file_ext = None

    if source_type == "upload" and original_path:
        try:
            file_bytes = supabase.storage.from_("resumes").download(original_path)
            if file_bytes:
                path_lower = original_path.lower()
                if path_lower.endswith(".pdf"):
                    file_ext = ".pdf"
                elif path_lower.endswith(".docx"):
                    file_ext = ".docx"
        except Exception as e:
            print(f"Warning: could not download original file for analysis: {e}")

    return file_bytes, file_ext


def start_improvement_session(resume_id: str, user_id: str):
    # Load resume from Supabase
    row = (
        supabase.table("resumes")
        .select("*")
        .eq("id", resume_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not row.data:
        raise ValueError("Resume not found")

    resume = row.data
    parsed_resume = resume.get("resume_json") or {}

    file_bytes, file_ext = _get_resume_file_bytes_and_ext(resume)

    session_id = str(uuid.uuid4())
    IMPROVE_SESSIONS[session_id] = {
        "resume_id": resume_id,
        "user_id": user_id,
        "parsed_resume": parsed_resume,
        "file_bytes": file_bytes,
        "file_ext": file_ext,  # ".pdf", ".docx", or None
        "target_job": None,
        "analysis": None,
        "messages": [],   # improvement chat messages
        "stage": "awaiting_target_job",
    }

    assistant_reply = (
        "Before we get started, what job title or industry are you targeting with this resume?"
    )

    return {
        "session_id": session_id,
        "assistant_message": assistant_reply,
    }


def _build_improvement_system_prompt(target_job: str, analysis: str, parsed_resume: dict):
    """
    Take the long system_context string you already have in chatbot.py
    for the improvement flow and adapt it here.

    You can literally copy your big f-string system_context from the
    original `analyze_resume_with_industry_context` improvement section
    and just plug in target_job, analysis, and parsed_resume.
    """
    today = datetime.today().strftime("%B %Y")

    # THIS SHOULD BE YOUR EXISTING LONG SYSTEM PROMPT,
    # trimmed here for brevity – copy from your CLI version.
    system_context = f"""
    Today's date is {today}.
    You are a resume improvement assistant.
    The user is targeting a role in: {target_job}.
    You have already analyzed their resume and provided the following feedback:
    {analysis}

    You will work with this resume data in JSON format, following the schema below
    and starting with the user's parsed resume data below in JSON format.
    Schema:
                    {{
                    "full_name": "",
                    "email": "",
                    "phone": "",
                    "linkedin": "",
                    "summary": "",
                    "experience": [
                        {{
                            "job_title": "",
                            "company": "",
                            "location": "",
                            "start_date": "",
                            "end_date": "",
                            "description": []
                        }}
                    ],
                    "education": [...],
                    "skills": [...],
                    "certifications": [...],
                    "projects": [...],
                    "volunteer": [...]
                    }}

    Here is the current parsed resume data in JSON format to start with:
    {json.dumps(parsed_resume, indent=2)}

    Rules:
    - Keep this JSON updated internally whenever the user approves a change.
        - Never mention to the user that you are updating the internal JSON, just do so silently after they confirm.
    -After completing an improvement, you MUST propose the next most impactful improvement remaining.
        - Do NOT wait for the user to guess what to improve next.
        - Always say what the next potential improvement is (e.g., “Next, we could improve X, Y, or Z.”).
        - Present improvements one at a time in priority order: High → Moderate → Optional.
        - After each improvement, ask: “Would you like to apply this change?” 
        - Only move on when the user says “yes” or “no,” but ALWAYS tell them the next available improvement.
        - Continue until there are no more improvements left.
        - When no improvements remain, say: “All improvements are complete. I’m ready to generate the resume.”
    - Modify only existing fields; never invent new keys or reorder sections arbitrarily.
    - When suggesting edits, quote the original bullet, explain the rationale, and apply the edit only if the user confirms.
        - After confirmation, update your internal JSON immediately.
        - NEVER provide the JSON to the user unless they specifically request it, it should be kept internal and the backend may prompt for it at any time.
    - Do not lose prior changes — this JSON must always stay current.
    - If the user asks to view or generate the resume, return only the latest JSON.
    - Never insist on adding a professional summary unless it is STRONGLY encouraged for this industry/job type.
    - NEVER suggest bold, italics, underlining, or any selective highlighting of specific skills or keywords.
    - The resume must remain fully ATS-friendly and uniform with no emphasis styles.
    - If recommending the user include specific metrics, provide an example of how it could be phrased, but ask the user if they have any metrics they can provide.
        - Do not invent metrics for them, only help them phrase real metrics they provide if they have any. 
        - If they do not have metrics, try to help them strengthen impact in other ways if necessary.
        - Never use the example metrics if the user claims they do not have any relevant metrics.
    - If the industry/job type typically skips summaries, do not prompt the user for one.
    - Use the resume content already provided to inform your guidance - only ask for details that are clearly missing.
    - When suggesting improvements, focus on relevance, impact, and ATS optimization, not unnecessary sections.
    - Using this context, help the user improve their resume step by step.
    - Ask one focused question at a time.
    - Keep all context in memory.
    - When suggesting changes, explain why they matter from a recruiter's perspective.
    - Prioritize sections that have the highest impact for this industry first.
    - If a user refuses to implement a change, move on to the next suggestion without argument.
    - When finished, offer to generate an improved resume for this industry.
    - When the user confirms that all changes are complete or says "yes" to proceed with generation,
        respond only with the phrase: "Sounds good! I'm ready to generate the resume."
        - Do not include any other text or explanation.       
    """

    return system_context


def continue_improvement_session(session_id: str, user_message: str):
      # used inside _build_improvement_system_prompt

    session = IMPROVE_SESSIONS.get(session_id)
    if not session:
        raise ValueError("Improvement session not found")

    client = get_openai()

    # 1) First message: treat as target_job and run analysis
    if session["stage"] == "awaiting_target_job":
        target_job = user_message.strip()
        session["target_job"] = target_job

        # Run analysis depending on file_ext
        file_bytes = session.get("file_bytes")
        file_ext = (session.get("file_ext") or "").lower()
        parsed_resume = session["parsed_resume"]

        if file_ext == ".pdf" and file_bytes:
            # visual + text analysis
            analysis_result = analyze_resume_service(file_bytes, parsed_resume, target_job, file_ext)
        else:
            # text-only analysis fallback (DOCX or chatbot resume)
            # We'll reuse the analysis_service but pass None,
            # and let it do a text-only branch.
            analysis_result = analyze_resume_service(None, parsed_resume, target_job, file_ext)

        if "error" in analysis_result:
            analysis_text = f"Analysis failed: {analysis_result['error']}"
        else:
            analysis_text = analysis_result["analysis"]

        session["analysis"] = analysis_text

        # Build system prompt for improvement chatbot (from your CLI)
        system_context = _build_improvement_system_prompt(
            target_job=target_job,
            analysis=analysis_text,
            parsed_resume=parsed_resume,
        )

        messages = [
            {"role": "system", "content": system_context},
        ]

        # Same as your CLI:
        assistant_intro = f"Let's start improving your resume for a {target_job} position. Ready to begin?"
        messages.append({"role": "assistant", "content": assistant_intro})

        session["messages"] = messages
        session["stage"] = "improving"

        return {
            "assistant_message": assistant_intro,
            "ready_to_finalize": False,
        }

    # 2) Normal improvement turn
    messages = session["messages"]
    messages.append({"role": "user", "content": user_message})

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.5,
    )
    reply = completion.choices[0].message.content.strip()
    messages.append({"role": "assistant", "content": reply})

    ready = "i'm ready to generate the resume." in reply.lower()

    return {
        "assistant_message": reply,
        "ready_to_finalize": ready,
    }


def finalize_improvement_session(session_id: str):
    session = IMPROVE_SESSIONS.get(session_id)
    if not session:
        raise ValueError("Improvement session not found")

    client = get_openai()
    messages = session["messages"]

    # Get final JSON + preferences from AI
    resume_json = get_resume_json(messages, client)
    resume_json = normalize_descriptions(resume_json)
    preferences = get_resume_preferences(messages, client)

    html_resume = generate_html_from_template(resume_json, preferences)

    # Fetch original resume name
    row = (
        supabase.table("resumes")
        .select("resume_name")
        .eq("id", session["resume_id"])
        .single()
        .execute()
    )
    base_name = row.data["resume_name"] if row.data else "Improved Resume"

    # Use your unique-name helper so we don't hit unique constraint
    improved_base = f"{base_name} (Improved)"
    final_name = generate_unique_resume_name(session["user_id"], improved_base)

    data = {
        "user_id": session["user_id"],
        "resume_json": resume_json,
        "resume_name": final_name,
        "resume_html": html_resume,
        "preferences": preferences,
        "original_file_path": None,
        "source_type": "chatbot",  # improved AI-generated version
    }

    result = supabase.table("resumes").insert(data).execute()
    if not result.data:
        raise ValueError("Failed to save improved resume")

    new_id = result.data[0]["id"]

    # Clean up session
    IMPROVE_SESSIONS.pop(session_id, None)

    return {
        "resume_id": new_id,
        "resume_name": final_name,
        "html": html_resume,
    }
