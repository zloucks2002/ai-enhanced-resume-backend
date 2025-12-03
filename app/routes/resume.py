from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse
from app.services.resume_service import generate_html_resume_service, parse_resume_file
from app.services.analysis_service import analyze_resume_service
from app.services.export_service import html_to_pdf_bytes, html_to_docx_bytes
from io import BytesIO
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

@router.post("/export/pdf")
async def export_pdf(file: UploadFile = File(...)):
    try:
        html_bytes = await file.read()
        html = html_bytes.decode("utf-8")

        pdf_bytes = await html_to_pdf_bytes(html)
        return Response(content=pdf_bytes, media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")


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

    