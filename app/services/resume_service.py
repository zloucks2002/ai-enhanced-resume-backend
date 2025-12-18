import tempfile
from render_resume import generate_html_from_template
from chatbot import parse_doc_text, extract_resume_text
from app.utils.openai_client import get_openai
from app.utils.supabase_client import supabase

def generate_unique_resume_name(user_id: str, base_name: str):
    # Automatically generate a unique resume name to avoid conflicts
    base_name = base_name.strip()
    
    # First check if the name is free
    existing = (
        supabase.table("resumes")
        .select("resume_name")
        .eq("user_id", user_id)
        .eq("resume_name", base_name)
        .execute()
    )

    if existing.data in (None, [],):
        return base_name  # Name is available

    # Otherwise, increment suffixes
    suffix = 1
    while True:
        new_name = f"{base_name} ({suffix})"
        check = (
            supabase.table("resumes")
            .select("resume_name")
            .eq("user_id", user_id)
            .eq("resume_name", new_name)
            .execute()
        )
        if check.data in (None, [],):
            return new_name
        suffix += 1

def generate_html_resume_service(body: dict):
    # Calls generate_html_from_template with provided JSON and preferences
    resume_json = body["resume_json"]
    preferences = body["preferences"]
    html = generate_html_from_template(resume_json, preferences)
    return {"html": html}

def parse_resume_file(upload):
    # Parses either a PDF or DOCX resume file and returns structured JSON
    ext = upload.filename.lower().split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp:
        temp.write(upload.file.read())
        temp_path = temp.name

    client = get_openai()
    text = extract_resume_text(temp_path)
    parsed = parse_doc_text(text, client)
    return parsed

def get_resume_html_by_id(supabase, resume_id):
    # Fetches the stored HTML resume by its ID from Supabase
    try:
        response = (
            supabase.table("resumes")
            .select("resume_html")
            .eq("id", resume_id)
            .single()
            .execute()
        )

        if not response.data:
            return None
        return response.data["resume_html"]
    except Exception as e:
        print(f"Error fetching resume HTML: {e}")
        return None
