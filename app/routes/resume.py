from fastapi import APIRouter, UploadFile, File, Form
from app.services.resume_service import generate_html_resume_service
from app.services.analysis_service import analyze_resume_service
from app.services.resume_service import parse_resume_file
import json

router = APIRouter()

@router.post("/generate")
async def generate_resume(body: dict):
    return generate_html_resume_service(body)

@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    return parse_resume_file(file)

@router.post("/analyze-with-context")
async def analyze_with_context(
    file: UploadFile = File(...),
    parsed_json: str = Form(...),
    target_job: str = Form(...),
):
    parsed_resume = json.loads(parsed_json)
    pdf_bytes = await file.read()
    return analyze_resume_service(pdf_bytes, parsed_resume, target_job)
