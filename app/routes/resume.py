from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import FileResponse
from app.services.resume_service import generate_html_resume_service, parse_resume_file
from app.services.analysis_service import analyze_resume_service
from app.services.export_service import html_to_pdf_bytes, html_to_docx_bytes
from app.services.upload_service import upload_resume_service
from app.utils.supabase_client import supabase
import tempfile
import os
from pydantic import BaseModel

import json
import uuid

router = APIRouter()


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
    pdf_bytes = await file.read()
    return analyze_resume_service(pdf_bytes, parsed, target_job)

class ExportHTMLRequest(BaseModel):
    html: str

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
    result = upload_resume_service(file, user_id)
    return result

@router.get("/preview/{resume_id}")
def preview_resume(resume_id: str):

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
                media_type="application/pdf"
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
    


    