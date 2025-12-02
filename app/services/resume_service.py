import tempfile
from render_resume import generate_html_from_template
from chatbot import parse_doc_text, extract_resume_text
from app.utils.openai_client import get_openai

def generate_html_resume_service(body: dict):
    resume_json = body["resume_json"]
    preferences = body["preferences"]
    html = generate_html_from_template(resume_json, preferences)
    return {"html": html}

def parse_resume_file(upload):
    ext = upload.filename.lower().split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp:
        temp.write(upload.file.read())
        temp_path = temp.name

    client = get_openai()
    text = extract_resume_text(temp_path)
    parsed = parse_doc_text(text, client)
    return parsed

def get_resume_html_by_id(supabase, resume_id):
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
