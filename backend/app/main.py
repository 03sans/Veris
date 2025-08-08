# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import io
import os

# PDF & DOCX libs
import fitz  # PyMuPDF
from docx import Document

app = FastAPI()

# Allow the Vite dev server to talk to FastAPI during development
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_MB = 20
ALLOWED_EXTS = {".pdf", ".docx"}


@app.get("/")
def read_root():
    return {"message": "Welcome to Veris – Your AI Legal Assistant"}


def extract_text_from_pdf(file_bytes: bytes):
    """Return (text, pages) from a PDF."""
    text_parts = []
    pages = 0
    with fitz.open(stream=file_bytes, filetype="pdf") as doc:
        pages = len(doc)
        for page in doc:
            text_parts.append(page.get_text("text"))
    return "\n".join(text_parts).strip(), pages


def extract_text_from_docx(file_bytes: bytes):
    """Return text from a DOCX."""
    bio = io.BytesIO(file_bytes)
    doc = Document(bio)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs).strip()


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # Validate extension
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload a .pdf or .docx file.")

    # Read bytes (enables size check + parsing)
    file_bytes = await file.read()

    # Size limit check
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File too large ({size_mb:.1f} MB). Max allowed is {MAX_UPLOAD_MB} MB.")

    # Extract text
    try:
        if ext == ".pdf":
            text, pages = extract_text_from_pdf(file_bytes)
            return {
                "filename": file.filename,
                "filetype": "pdf",
                "pages": pages,
                "text": text,
            }
        else:  # ".docx"
            text = extract_text_from_docx(file_bytes)
            return {
                "filename": file.filename,
                "filetype": "docx",
                "text": text,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")