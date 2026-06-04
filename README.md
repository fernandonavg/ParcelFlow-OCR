# ParcelFlow — BOL Document Intelligence Pipeline

A production-deployed document intelligence system automatic extraction of structured fields from scanned freight Bills of Lading using spatial anchor-based parsing on top of PaddleOCR, aimed to eliminate manual data entry from billing operations.

Features:
- Multi-format BOL support
- Address block extraction
- Number detection
- Data base-ready structured output
- Web demo deployment via FastAPI and Hugging Face Spaces

---

## The Problem

Freight companies generate thousands of scanned BOL documents every day, which are being processed manually. Each document contains essential information for parcel delivery including addresses (sender, receiver, billing address), article description and package identification numbers.
Documents arrive with no standardized structure, so the system built handles a wide variety of formats, missing information, handwritten information and low quality scans,

---

## How It Works

ParcelFlow uses a spatial anchor-based extraction system that understands document structure:

```
Scanned BOL image
        │
        ▼
┌─────────────────────┐
│  PaddleOCR (PP-OCRv5│  ← Text detection + recognition
│  server model)      │     with bounding box coordinates
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Detection Builder  │  ← Each text block becomes a detection
│                     │     object: {text, bbox, cx, cy, score}
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  Anchor Matching    │  ← Scans detections for known field labels
│                     │     e.g. "ship from", "bill of lading number"
└─────────────────────┘
        │
     ┌──┴──┐
     ▼     ▼
Strategy 1  Strategy 2
(Inline)    (Vertical fallback)
"BOL: 123"  Label above, value below
     │           │
     └──────┬────┘
            ▼
┌─────────────────────┐
│  Normalization      │  ← Lists joined, None → "", type-safe
└─────────────────────┘
        │
        ▼
   Excel / SQL output
```

### Two-Strategy Field Extraction

**For numeric fields** (BOL number, PO number, load number, weight):
- **Strategy 1 — Inline**: checks if the value appears on the same line as the label (`"Bill of Lading Number: 3411000"`)
- **Strategy 2 — Vertical fallback**: if no inline value, walks downward from the anchor using bounding box coordinates to collect number-like lines below the label

**For location fields** (ship from, ship to, third party):
- Walks downward from the anchor, collecting address lines within configurable horizontal/vertical tolerances
- Uses ZIP code detection as a stop condition
- Validates that collected block contains a ZIP before returning (rejects partial addresses)

**Stop conditions** prevent field contamination:
- Another known label detected → stop (crossed into a different section)
- ZIP code found → stop (address complete)
- No candidate within spatial thresholds → stop

---

## Fields Extracted

| Field | Description |
|---|---|
| `ship_from` | Full shipper address (name + street + city/state/zip) |
| `ship_to` | Full consignee address |
| `third_party` | Third-party billing address (when present) |
| `bol_number` | Bill of Lading number |
| `load_number` | Load/trip number |
| `po_number` | Purchase order number(s) — supports multiple POs per BOL |
| `weight` | Shipment weight(s) |

---

## Example Output

Input: scanned BOL image (`.jpg`)

```python
{
  'ship_from': "King's Rook  1160 Research Blvd.  St. Louis, MO 63132",
  'ship_to':   "JOHN ALABAMA  450 ALABAMA STREET  MONTGOMERY, AL 36101",
  'third_party': None,
  'bol_number':  ['3411000'],
  'load_number': None,
  'po_number':   ['9710214818', '3005395012', '9810214774', '4655385217', '9605434506'],
  'weight':      ['120', '180', '60', '30', '120', '2,900']
}
```

Output: row appended to `bills.xlsx` (or any SQL-compatible target)

---

## Tech Stack

- **Python 3.13**
- **PaddleOCR (PP-OCRv5)** — production-grade OCR engine with document orientation correction (UVDoc) and text line orientation detection
- **Pandas** — data handling
- **openpyxl** — Excel output (designed to be swapped for SQLAlchemy/any DB)
- **re** — regex for ZIP detection and numeric field cleaning

---

## Project Structure

```
parcelFlow/
├── parcelFlow2_0_anotated.ipynb   # Annotated pipeline (main)
├── requirements.txt
└── README.md
```

---

## Getting Started

```bash
# Clone the repo
git clone https://github.com/<your-username>/parcelFlow.git
cd parcelFlow

# Install dependencies
pip install paddlepaddle paddleocr pandas openpyxl

# Run the notebook
jupyter notebook parcelFlow2_0_anotated.ipynb
```

Point `bill` to your BOL image path in the last cell and run.

---

## Design Decisions

**Why PaddleOCR over Tesseract?**  
PP-OCRv5 includes a document unwarping model (UVDoc) and orientation correction out of the box, which matters for scanned documents that arrive rotated or curved. Tesseract requires preprocessing pipelines to handle this.

**Why spatial anchoring instead of template matching?**  
BOL formats vary across carriers. Template matching breaks when layout changes. Spatial anchoring finds labels semantically and navigates relative to them — it degrades gracefully on new formats rather than failing hard.

**Why Excel output?**  
The output layer is intentionally thin. `append_row_to_excel()` writes the same dict that could go into any relational database. Excel was the right target for the deployment context; the architecture doesn't depend on it.

---

## Live Demo

[Try it on Hugging Face Spaces](<https://huggingface.co/spaces/fernandonavg/parcelflow-ocr)>)

---

## Author

Physics Engineer · Fernando Nava

www.linkedin.com/in/fernando-navag097
