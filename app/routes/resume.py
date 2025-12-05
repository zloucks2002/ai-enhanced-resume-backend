from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse
from app.services.resume_service import generate_html_resume_service, parse_resume_file
from app.services.analysis_service import analyze_resume_service
from app.services.export_service import html_to_pdf_bytes, html_to_docx_bytes
from app.services.upload_service import upload_resume_service
from app.services.improvement_service import start_improvement_session, continue_improvement_session, finalize_improvement_session
from app.utils.supabase_client import supabase
import os
from pydantic import BaseModel

import json
import uuid

router = APIRouter()

def generate_unique_resume_name(user_id: str, base_name: str):
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
        return base_name  # available

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



# Generate HTML resume
@router.post("/generate")
async def generate_resume(body: dict):
    return generate_html_resume_service(body)

# Parse uploaded PDF/DOCX
@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    return parse_resume_file(file)

# Analyze with context
@router.post("/analyze-with-context")
async def analyze_with_context(
    file: UploadFile = File(...),
    parsed_json: str = Form(...),
    target_job: str = Form(...),
):
    parsed = json.loads(parsed_json)
    file_bytes = await file.read()

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1]

    if ext not in [".pdf", ".docx"]:
        raise HTTPException(status_code=400, detail="Unsupported file type. Only PDF and DOCX resumes are supported.")

    return analyze_resume_service(file_bytes, parsed, target_job, ext)

# Export PDF file
@router.post("/export/pdf")
async def export_pdf(file: UploadFile = File(...)):
    try:
        html_bytes = await file.read()
        html = html_bytes.decode("utf-8")

        pdf_bytes = await html_to_pdf_bytes(html)
        return Response(content=pdf_bytes, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

# Export DOCX file
@router.post("/export/docx")
async def export_docx(file: UploadFile = File(...)):
    html_content = (await file.read()).decode("utf-8")
    try:
        docx_bytes = await html_to_docx_bytes(html_content)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to generate DOCX: {e}")
    

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...),
):
    try:
        result = await upload_resume_service(file, user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{resume_id}")
async def preview_resume(resume_id: str):

    result = supabase.table("resumes").select("*").eq("id", resume_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume = result.data
    source_type = resume.get("source_type")

    if source_type == "upload":
        file_path = resume.get("original_file_path")
        if not file_path:
            raise HTTPException(status_code=500, detail="No original file stored.")
        
        res = supabase.storage.from_("resumes").download(file_path)

        if res is None:
            raise HTTPException(status_code=500, detail="Failed to download file.")
        
        ext = file_path.split(".")[-1]

        if ext == "pdf":
            return Response(
                content=res,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{os.path.basename(file_path)}"'
                }
            )
        else:
            return Response(
                content=res,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={
                    "Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"'
                }
            )
    else:
        html = resume.get("resume_html")
        if not html:
            raise HTTPException(status_code=500, detail="Resume HTML missing.")

        return Response(
            content=html, 
            media_type="text/html; charset=utf-8",
            headers={
                "Content-Disposition": "inline; filename=resume.html"
            })
    
@router.delete("/{resume_id}")
async def delete_resume(resume_id: str):
    row = supabase.table("resumes").select("*").eq("id", resume_id).single().execute()

    if not row.data:
        raise HTTPException(404, "Resume not found")

    resume = row.data

    supabase.table("resumes").delete().eq("id", resume_id).execute()

    if resume["source_type"] == "upload" and resume["original_file_path"]:
        supabase.storage.from_("resumes").remove([resume["original_file_path"]])

    return {"message": "Deleted"}


@router.post("/rename/{resume_id}")
async def rename_resume(resume_id: str, new_name: str = Form(...)):
    new_name = new_name.strip()

    row = (
        supabase.table("resumes")
        .select("user_id")
        .eq("id", resume_id)
        .single()
        .execute()
    )
    if not row.data:
        raise HTTPException(404, "Resume not found")
    
    user_id = row.data["user_id"]
    
    final_name = generate_unique_resume_name(user_id, new_name)

    supabase.table("resumes").update({"resume_name": new_name}).eq("id", resume_id).execute()
    return {"message": "Renamed", "new_name": final_name}


@router.post("/save-generated")
def save_generated_resume(
    resume_json: str = Form(...),
    preferences: str = Form(...),
    resume_html: str = Form(...),
    resume_name: str = Form(...),
    user_id: str = Form(...)
):

    try:
        parsed_json = json.loads(resume_json)
    except:
        raise HTTPException(status_code=400, detail="Invalid resume_json format")
    try:
        parsed_preferences = json.loads(preferences)
    except:
        raise HTTPException(status_code=400, detail="Invalid preferences format")
    
    final_name = generate_unique_resume_name(user_id, resume_name)

    data = {
        "user_id": user_id,
        "resume_json": parsed_json,
        "resume_name": final_name,
        "resume_html": resume_html,
        "preferences": parsed_preferences,
        "original_file_path": None,
        "source_type": "chatbot"
    }

    supabase.table("resumes").insert(data).execute()


    fetch = (
        supabase.table("resumes")
        .select("id")
        .eq("user_id", user_id)
        .eq("resume_name", final_name)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if fetch.data is None:
        raise HTTPException(status_code=500, detail="Supabase returned no data after insert")

    return {"resume_id": fetch.data[0]["id"], "resume_name": final_name}


@router.get("/improve/start")
async def improve_start(
    resume_id: str = Form(...),
    user_id: str = Form(...),
):
    try:
        return start_improvement_session(resume_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/improve/message")
async def improve_message(
    session_id: str = Form(...),
    message: str = Form(...),
):
    try:
        return continue_improvement_session(session_id, message)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/improve/finalize")
async def improve_finalize(
    session_id: str = Form(...),
):
    try:
        return finalize_improvement_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



    


    