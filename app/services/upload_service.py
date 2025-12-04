import tempfile
import os
from app.utils.supabase_client import supabase
from chatbot import extract_resume_text, parse_doc_text
from app.utils.openai_client import get_openai


def upload_resume_service(file, user_id):
    # Save file temporarily
    ext = file.filename.lower().split(".")[-1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as temp:
        temp.write(file.file.read())
        temp_path = temp.name

    # Extract text from PDF/DOCX
    text = extract_resume_text(temp_path)

    # Parse resume using OpenAI
    client = get_openai()
    parsed = parse_doc_text(text, client)

    # Upload original file into Supabase Storage "resumes" bucket
    file_bytes = open(temp_path, "rb").read()

    storage_path = f"{user_id}/{file.filename}"

    supabase.storage.from_("resumes").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream"}
    )

    # Insert metadata and parsed JSON into DB
    result = supabase.table("resumes").insert({
        "user_id": user_id,
        "resume_json": parsed,
        "resume_name": file.filename,
        "resume_html": None,
        "preferences": None,
        "original_file_path": storage_path,
        "source_type": "upload"
    }).execute()

    resume_id = result.data[0]["id"]

    # Clean up temp file
    os.remove(temp_path)

    return {
        "message": "Resume uploaded successfully.",
        "resume_id": resume_id,
        "parsed_json": parsed
    }
