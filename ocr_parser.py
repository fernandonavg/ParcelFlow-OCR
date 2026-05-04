"""OCR parsing logic for Parcel Flow 2.0.

This file was extracted and cleaned from the notebook workflow so it can be
called by a web backend. It expects PaddleOCR's `ocr.predict(file_path)` output.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable


LOCATION_LABELS = {
    "ship_from": ["ship from", "shipper", "consignor", "consigner"],
    "ship_to": ["ship to", "consignee"],
    "third_party": ["third party", "3rd party", "third-party", "bill to"],
}

NUMBER_LABELS = {
    "bol_number": [
        "bill of lading number",
        "bill of lading no",
        "bill of lading #",
        "bol number",
        "bol #",
        "b/l number",
    ],
    "load_number": ["load number", "load #", "load no", "load"],
    "po_number": [
        "po number",
        "purchase order number",
        "purchase order",
        "po #",
        "customer order number",
        "order number",
    ],
    "weight": ["weight", "total weight", "gross weight"],
}

FINAL_COLUMNS = [
    "file_name",
    "ship_from",
    "ship_to",
    "third_party",
    "bol_number",
    "load_number",
    "po_number",
    "weight",
]

ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
NUMBERISH_RE = re.compile(r"(?=.*\d)[A-Za-z0-9][A-Za-z0-9\-_/.,#\s]*")


def normalize_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text).lower().strip())


def flatten_labels(label_groups: Iterable[dict[str, list[str]]]) -> list[str]:
    labels: list[str] = []
    for group in label_groups:
        for values in group.values():
            labels.extend(values)
    return labels


def contains_any_label(text: str, label_groups: Iterable[dict[str, list[str]]]) -> bool:
    text_norm = normalize_text(text)
    return any(normalize_text(label) in text_norm for label in flatten_labels(label_groups))


def has_zip_code(text: str) -> bool:
    return bool(ZIP_RE.search(str(text)))


def looks_like_numberish(text: str) -> bool:
    cleaned = str(text).strip()
    return bool(NUMBERISH_RE.fullmatch(cleaned)) and any(ch.isdigit() for ch in cleaned)


def build_detections(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert PaddleOCR page output into normalized detection dictionaries."""
    detections: list[dict[str, Any]] = []
    texts = page.get("rec_texts", [])
    scores = page.get("rec_scores", [])
    boxes = page.get("rec_boxes", [])

    for text, score, box in zip(texts, scores, boxes):
        if len(box) != 4:
            continue
        x1, y1, x2, y2 = [int(v) for v in box]
        text = str(text).strip()
        if not text:
            continue
        detections.append(
            {
                "text": text,
                "score": float(score),
                "bbox": (x1, y1, x2, y2),
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "cx": (x1 + x2) / 2,
                "cy": (y1 + y2) / 2,
            }
        )

    detections.sort(key=lambda d: (d["y1"], d["x1"]))
    return detections


def find_label_and_match(detections: list[dict[str, Any]], possible_labels: list[str]):
    possible_labels = sorted(possible_labels, key=len, reverse=True)
    for det in detections:
        det_text = normalize_text(det["text"])
        for label in possible_labels:
            if normalize_text(label) in det_text:
                return det, label
    return None, None


def extract_text_after_label(full_text: str, matched_label: str) -> str:
    pattern = re.compile(re.escape(matched_label), flags=re.IGNORECASE)
    value = pattern.sub("", full_text, count=1)
    value = value.replace(":", " ").replace("#", " ").strip(" -—\t")
    return re.sub(r"\s+", " ", value).strip()


def collect_block_line_by_line(
    anchor_det: dict[str, Any],
    detections: list[dict[str, Any]],
    x_threshold: int = 220,
    y_threshold: int = 55,
) -> list[dict[str, Any]]:
    """Walk downward from a location label and collect the address block."""
    block: list[dict[str, Any]] = []
    current = anchor_det
    remaining = [d for d in detections if d is not anchor_det]

    while True:
        if block and has_zip_code(block[-1]["text"]):
            break

        candidates = []
        for candidate in remaining:
            if candidate in block:
                continue
            if contains_any_label(candidate["text"], [LOCATION_LABELS, NUMBER_LABELS]):
                continue

            dx = abs(candidate["x1"] - current["x1"])
            dy = candidate["y1"] - current["y1"]
            horizontal_overlap = min(candidate["x2"], current["x2"]) - max(candidate["x1"], current["x1"])

            if 0 < dy <= y_threshold and (dx <= x_threshold or horizontal_overlap > 0):
                candidates.append(candidate)

        if not candidates:
            break

        next_line = sorted(candidates, key=lambda d: (d["y1"], d["x1"]))[0]
        block.append(next_line)
        current = next_line

    return block


def collect_number_lines_below(
    anchor_det: dict[str, Any],
    detections: list[dict[str, Any]],
    x_threshold: int = 160,
    y_threshold: int = 55,
) -> list[str]:
    """Collect numeric or ID-looking lines directly below a number label."""
    values: list[str] = []
    current = anchor_det
    remaining = [d for d in detections if d is not anchor_det]

    while True:
        candidates = []
        for candidate in remaining:
            if candidate["text"] in values:
                continue
            if contains_any_label(candidate["text"], [LOCATION_LABELS, NUMBER_LABELS]):
                continue

            dx = abs(candidate["x1"] - current["x1"])
            dy = candidate["y1"] - current["y1"]
            if 0 < dy <= y_threshold and dx <= x_threshold and looks_like_numberish(candidate["text"]):
                candidates.append(candidate)

        if not candidates:
            break

        next_line = sorted(candidates, key=lambda d: (d["y1"], d["x1"]))[0]
        values.append(next_line["text"])
        current = next_line

    return values


def extract_location_field(
    detections: list[dict[str, Any]],
    field_name: str,
    x_threshold: int = 220,
    y_threshold: int = 55,
) -> str | None:
    if field_name not in LOCATION_LABELS:
        raise ValueError(f"Unknown location field: {field_name}")

    anchor_det, matched_label = find_label_and_match(detections, LOCATION_LABELS[field_name])
    if not anchor_det:
        return None

    inline_value = extract_text_after_label(anchor_det["text"], matched_label)
    block = collect_block_line_by_line(anchor_det, detections, x_threshold, y_threshold)
    lines = []
    if inline_value and not contains_any_label(inline_value, [LOCATION_LABELS, NUMBER_LABELS]):
        lines.append(inline_value)
    lines.extend(d["text"] for d in block)

    if not lines:
        return None

    # For addresses, prefer returning only if there is a ZIP somewhere. If no ZIP
    # is present, still return the collected text because some BOLs omit ZIPs.
    return " | ".join(lines)


def extract_number_field(
    detections: list[dict[str, Any]],
    field_name: str,
    x_threshold: int = 160,
    y_threshold: int = 55,
) -> list[str]:
    if field_name not in NUMBER_LABELS:
        raise ValueError(f"Unknown number field: {field_name}")

    anchor_det, matched_label = find_label_and_match(detections, NUMBER_LABELS[field_name])
    if not anchor_det:
        return []

    inline_value = extract_text_after_label(anchor_det["text"], matched_label)
    if inline_value and looks_like_numberish(inline_value):
        return [inline_value]

    return collect_number_lines_below(anchor_det, detections, x_threshold, y_threshold)


def parse_bill_fields(page: dict[str, Any]) -> dict[str, Any]:
    detections = build_detections(page)
    return {
        "ship_from": extract_location_field(detections, "ship_from"),
        "ship_to": extract_location_field(detections, "ship_to"),
        "third_party": extract_location_field(detections, "third_party"),
        "bol_number": extract_number_field(detections, "bol_number"),
        "load_number": extract_number_field(detections, "load_number"),
        "po_number": extract_number_field(detections, "po_number"),
        "weight": extract_number_field(detections, "weight"),
        "detections": detections,
    }


def normalize_row(row: dict[str, Any]) -> dict[str, str]:
    normalized = {}
    for column in FINAL_COLUMNS:
        value = row.get(column, "")
        if value is None:
            normalized[column] = ""
        elif isinstance(value, list):
            normalized[column] = " , ".join(str(v) for v in value)
        else:
            normalized[column] = str(value)
    return normalized


def run_ocr_file(file_path: str, ocr_model: Any) -> dict[str, Any]:
    """Run PaddleOCR on one uploaded file and parse the first page/image."""
    result = ocr_model.predict(file_path)
    if not result:
        raise ValueError("PaddleOCR returned no pages")

    page = result[0]
    row = parse_bill_fields(page)
    row["file_name"] = os.path.basename(file_path)
    return row
