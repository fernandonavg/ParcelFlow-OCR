# Parcel Flow 2.0 OCR Demo

This version connects the front-end page to a Python FastAPI backend that runs your PaddleOCR parsing logic.

## What is inside

- `index.html` — front-end layout
- `styles.css` — UI styling
- `script.js` — upload, preview, OCR call, export call
- `app.py` — FastAPI backend
- `ocr_parser.py` — cleaned OCR extraction logic from the notebook
- `requirements.txt` — Python dependencies

## Run locally

```bash
cd parcelflow-demo
python -m venv .venv
source .venv/bin/activate   # Mac/Linux
# .venv\Scripts\activate    # Windows PowerShell
pip install -r requirements.txt
uvicorn app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Flow

1. Upload a PDF/JPG/PNG bill of lading.
2. Click **Run OCR**.
3. The browser sends the file to `/api/process`.
4. `app.py` calls PaddleOCR.
5. `ocr_parser.py` extracts shipper/ship from, consignee/ship to, third party, BOL, load, PO, and weight fields.
6. Review/edit fields.
7. Click **Export row** to append to `bills_export.csv`.
8. Click **Download CSV** to download the exported rows.

## Important notes

- GitHub Pages cannot run PaddleOCR because it only serves static files.
- For real OCR, run this backend locally or deploy it to a Python server.
- The first PaddleOCR run may be slow because it loads the model.
