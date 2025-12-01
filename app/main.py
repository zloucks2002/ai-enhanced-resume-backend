from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import chatbot, resume

app = FastAPI(
    title="AI Enhanced Resume Assistant Backend",
    description="Backend API for chatbot, resume parsing, analysis, and HTML generation.",
    version="1.0.0"
)

# CORS for frontend/Lovable
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ROUTES
app.include_router(chatbot.router, prefix="/chatbot")
app.include_router(resume.router, prefix="/resume")

@app.get("/")
def root():
    return {"message": "Backend running successfully."}
