# backend/app/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import List
from dotenv import load_dotenv
import json
import io
import os
import requests
from groq import Groq

# PDF & DOCX libs
import fitz  # PyMuPDF
from docx import Document

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,     # adjust for prod domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
load_dotenv()

def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    # strip whitespace and accidental quotes
    return s.strip().strip('"').strip("'")

MAX_UPLOAD_MB = 20
ALLOWED_EXTS = {".pdf", ".docx"}

HF_TOKEN = _clean(os.getenv("HUGGINGFACE_API_TOKEN"))
HF_MODEL = _clean(os.getenv("HF_MODEL")) or "HuggingFaceH4/zephyr-7b-beta"
HF_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}

# Groq config
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# -----------------------------------------------------------------------------
# Routes: health/root
# -----------------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Welcome to Veris – Your AI Legal Assistant"}

@app.get("/api/hf_status")
def hf_status():
    try:
        r = requests.get(f"https://api-inference.huggingface.co/status/{HF_MODEL}", headers=HF_HEADERS, timeout=15)
        return {
            "model": HF_MODEL,
            "url": HF_URL,
            "status_code": r.status_code,
            "status_json": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text
        }
    except Exception as e:
        return {"model": HF_MODEL, "url": HF_URL, "error": str(e)}

# -----------------------------------------------------------------------------
# Helpers: extraction
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Endpoint: upload
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Summarizer: request/response models
# -----------------------------------------------------------------------------
class Clause(BaseModel):
    type: str
    snippet: str

class SummarizeRequest(BaseModel):
    text: str
    jurisdiction: str = "General"

class SummarizeResponse(BaseModel):
    summary: str
    clauses: List[Clause]

# -----------------------------------------------------------------------------
# Helpers: robust JSON parse from model output
# -----------------------------------------------------------------------------
def _try_parse_json(s: str):
    s = s.strip()
    # Strip accidental code fences
    if s.startswith("```"):
        s = s.strip("`")
        if s.startswith("json"):
            s = s[4:]
    # Direct parse
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Fallback: find largest {...} block
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start:end + 1])
        raise

def _estimate_tokens(text: str) -> int:
    # Rough heuristic: ~4 chars per token for English prose
    # (good enough for keeping well under limits)
    return max(1, len(text) // 4)

def _split_into_chunks(text: str, max_tokens: int = 1800):
    """
    Split text into chunks under ~max_tokens using paragraphs, then words.
    Returns a list of strings.
    """
    chunks = []
    current = []
    current_tokens = 0

    paragraphs = [p.strip() for p in text.split("\n")]

    for p in paragraphs:
        if not p:
            # preserve paragraph breaks a bit without adding tokens
            if current and current[-1] != "":
                current.append("")
            continue

        p_tokens = _estimate_tokens(p)
        if p_tokens > max_tokens:
            # paragraph itself too big → fall back to word splitting
            words = p.split()
            buf = []
            buf_tokens = 0
            for w in words:
                t = _estimate_tokens(w) + 1  # +1 for space
                if buf_tokens + t > max_tokens:
                    chunks.append(" ".join(buf).strip())
                    buf = [w]
                    buf_tokens = _estimate_tokens(w)
                else:
                    buf.append(w)
                    buf_tokens += t
            if buf:
                chunks.append(" ".join(buf).strip())
            continue

        # normal paragraph packing
        if current_tokens + p_tokens > max_tokens:
            chunks.append("\n".join(current).strip())
            current = [p]
            current_tokens = p_tokens
        else:
            current.append(p)
            current_tokens += p_tokens

    if current:
        chunks.append("\n".join(current).strip())

    # remove empties
    return [c for c in chunks if c]

def _merge_clauses(partials):
    """Deterministically merge clause lists from chunk summaries."""
    merged = []
    seen = set()
    for p in partials:
        for c in p.get("clauses", []) or []:
            t = (str(c.get("type", "")).strip().lower(),
                 str(c.get("snippet", "")).strip())
            if not t[1]:  # empty snippet
                continue
            if t in seen:
                continue
            seen.add(t)
            merged.append({"type": c.get("type", ""), "snippet": c.get("snippet", "")})
    # cap to something reasonable
    return merged[:100]

def _final_summary_from_chunks_summaries(summaries_text: str, jurisdiction: str) -> str:
    """
    Ask the model ONLY for a JSON with {"summary": "..."} using a small input.
    """
    system_msg = (
        "You are a legal assistant. Return STRICT JSON only, no markdown, no prose. "
        'Schema: {"summary": string}'
    )
    user_msg = f"""
Write a concise plain-English summary (120-180 words) for a non-lawyer,
tailored to the jurisdiction: {jurisdiction}.
Base your answer on the following combined chunk summaries:

\"\"\"{summaries_text}\"\"\"

Return ONLY the JSON.
"""

    chat = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = chat.choices[0].message.content or ""
    parsed = _try_parse_json(raw)
    # Be defensive: if model returns just a string, accept it
    if isinstance(parsed, dict) and "summary" in parsed:
        return str(parsed["summary"])
    if isinstance(parsed, str):
        return parsed
    # last resort
    return json.dumps(parsed)[:1000]
# -----------------------------------------------------------------------------
# Endpoint: summarize (Groq)
# -----------------------------------------------------------------------------
@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize_doc(payload: SummarizeRequest):
    """
    Summarize legal text in plain English and extract key clauses.
    Handles long docs by chunking and then merging results safely.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="No text provided.")
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured in .env.")

    # 1) Split into safe chunks
    MAX_CHUNK_TOKENS = 1600
    chunks = _split_into_chunks(payload.text, max_tokens=MAX_CHUNK_TOKENS)
    if not chunks:
        raise HTTPException(status_code=400, detail="Could not split text into chunks.")

    MAX_CHUNKS = 12
    if len(chunks) > MAX_CHUNKS:
        raise HTTPException(
            status_code=413,
            detail=f"Document is very large ({len(chunks)} chunks). Please try a shorter file or reduce content."
        )

    # 2) Summarize each chunk to JSON (summary + clauses)
    system_msg = (
        "You are a legal assistant. Return STRICT JSON only, no markdown, no prose. "
        'Schema: {"summary": string, "clauses": [{"type": string, "snippet": string}]} '
        "Clause types commonly include: termination, liability, ip, payment, confidentiality. "
        "If none found, use an empty array for clauses."
    )

    def summarize_chunk(chunk_text: str) -> dict:
        user_msg = f"""
Summarize the following legal text in plain English for a non-lawyer, and extract important clauses,
tailored to the jurisdiction: {payload.jurisdiction}.

Text:
\"\"\"{chunk_text}\"\"\"
Return ONLY the JSON.
"""
        chat = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = chat.choices[0].message.content or ""
        return _try_parse_json(raw)

    partials = []
    try:
        for ch in chunks:
            partials.append(summarize_chunk(ch))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization (chunk) failed: {str(e)}")

    # 3) Merge clauses deterministically (no model)
    merged_clauses = _merge_clauses(partials)

    # 4) Build a compact text of chunk summaries and get a final short summary from the model
    all_summaries_text = " ".join([p.get("summary", "") for p in partials if p.get("summary")])
    # keep the reduce prompt small
    if len(all_summaries_text) > 4000:
        all_summaries_text = all_summaries_text[:4000]

    try:
        final_summary = _final_summary_from_chunks_summaries(
            summaries_text=all_summaries_text,
            jurisdiction=payload.jurisdiction
        )
        return SummarizeResponse(summary=final_summary, clauses=merged_clauses)
    except Exception as e:
        # Fallback: if reduce fails, concatenate summaries and return merged clauses
        fallback_summary = all_summaries_text[:1200] or "Summary not available."
        return SummarizeResponse(summary=fallback_summary, clauses=merged_clauses)