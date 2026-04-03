"""Stress test specific endpoints."""

import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session as DBSession
from backend.database import get_db
from backend.auth import require_auth
from backend.models.session import Session
from backend.services.doc_extract import extract_text

router = APIRouter(prefix="/api", tags=["stress-test"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".xlsx", ".csv"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB


@router.post("/upload/stress-test")
async def upload_stress_test_document(
    file: UploadFile = File(...),
    _=Depends(require_auth),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {ext} not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_UPLOAD_SIZE // (1024*1024)}MB")

    try:
        content_text = extract_text(content, file.filename or "document")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    doc = {
        "id": str(uuid.uuid4()),
        "filename": file.filename or "document",
        "filetype": ext.lstrip("."),
        "content_text": content_text,
        "size_bytes": len(content),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "filetype": doc["filetype"],
        "size_bytes": doc["size_bytes"],
        "preview": content_text[:500],
        "uploaded_at": doc["uploaded_at"],
        "document": doc,
    }
