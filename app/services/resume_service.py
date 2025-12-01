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
