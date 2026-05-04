"""FastAPI backend for Parcel Flow 2.0.

Run with:
    uvicorn app:app --reload
"""

from __future__ import annotations

import csv
import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ocr_parser import FINAL_COLUMNS, normalize_row, run_ocr_file

BASE_DIR = Path(__file__).resolve().parent
EXPORT_PATH = BASE_DIR / "bills_export.csv"

app = FastAPI(title="Parcel Flow 2.0 OCR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_ocr_model() -> Any:
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Run: pip install paddleocr paddlepaddle"
        ) from exc

    return PaddleOCR(use_angle_cls=True, lang="en")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/process")
async def process_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
        raise HTTPException(status_code=400, detail="Upload a PDF, PNG, JPG, or JPEG file.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        try:
            ocr_model = get_ocr_model()
            row = run_ocr_file(tmp_path, ocr_model)
            row["file_name"] = file.filename
            normalized = normalize_row(row)
            return {"ok": True, "row": normalized, "raw": row}
        finally:
            os.remove(tmp_path)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc


@app.post("/api/export")
async def export_row(row: dict[str, Any]):
    normalized = normalize_row(row)
    file_exists = EXPORT_PATH.exists()

    with EXPORT_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FINAL_COLUMNS)
        if not file_exists:
            writer.writeheader()
        writer.writerow(normalized)

    return {"ok": True, "saved_to": str(EXPORT_PATH.name), "row": normalized}


@app.get("/api/export/download")
def download_export():
    if not EXPORT_PATH.exists():
        raise HTTPException(status_code=404, detail="No exported rows yet.")
    return FileResponse(EXPORT_PATH, filename="bills_export.csv")


# Serve the frontend from the same backend during local development.
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="frontend")
