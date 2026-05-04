const API_BASE = ""; // same origin when served by FastAPI

const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const currentFile = document.getElementById("currentFile");
const processBtn = document.getElementById("processBtn");
const exportBtn = document.getElementById("exportBtn");
const clearBtn = document.getElementById("clearBtn");
const downloadBtn = document.getElementById("downloadBtn");
const dropzone = document.querySelector(".dropzone");
const statusText = document.getElementById("statusText");
const confidence = document.getElementById("confidence");
const preview = document.getElementById("documentPreview");

const uploadedFiles = new Map();
let selectedFileName = null;
let selectedRow = null;

function setStatus(message, type = "neutral") {
  statusText.textContent = message;
  statusText.dataset.type = type;
}

function setButtonLoading(isLoading) {
  processBtn.disabled = isLoading || !selectedFileName;
  processBtn.textContent = isLoading ? "Processing..." : "Run OCR";
}

function rowToForm(row = {}) {
  document.getElementById("shipFrom").value = row.ship_from || "";
  document.getElementById("shipTo").value = row.ship_to || "";
  document.getElementById("bol").value = row.bol_number || "";
  document.getElementById("load").value = row.load_number || "";
  document.getElementById("thirdParty").value = row.third_party || "";
  document.getElementById("po").value = row.po_number || "";
  document.getElementById("weight").value = row.weight || "";
}

function formToRow() {
  return {
    file_name: selectedFileName || currentFile.textContent,
    ship_from: document.getElementById("shipFrom").value,
    ship_to: document.getElementById("shipTo").value,
    third_party: document.getElementById("thirdParty").value,
    bol_number: document.getElementById("bol").value,
    load_number: document.getElementById("load").value,
    po_number: document.getElementById("po").value,
    weight: document.getElementById("weight").value
  };
}

function renderPreview(file) {
  if (!file) {
    preview.innerHTML = `
      <div class="paper placeholder-paper">
        <div class="paper-line w-90"></div>
        <div class="paper-line w-70"></div>
        <div class="paper-grid"><div></div><div></div><div></div><div></div><div></div><div></div></div>
        <div class="paper-line w-80"></div>
        <div class="paper-line w-65"></div>
        <div class="ocr-box box-shipper">SHIPPER</div>
        <div class="ocr-box box-bol">BOL #</div>
      </div>`;
    return;
  }

  const url = URL.createObjectURL(file);
  if (file.type.startsWith("image/")) {
    preview.innerHTML = `<img class="real-preview" src="${url}" alt="Uploaded document preview" />`;
  } else if (file.type === "application/pdf") {
    preview.innerHTML = `<iframe class="pdf-preview" src="${url}" title="PDF preview"></iframe>`;
  } else {
    preview.innerHTML = `<div class="empty-preview">Preview unavailable for this file type.</div>`;
  }
}

function setActiveFile(fileName) {
  selectedFileName = fileName;
  currentFile.textContent = fileName;

  document.querySelectorAll(".file-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.name === fileName);
  });

  rowToForm({});
  selectedRow = null;
  confidence.textContent = "--";
  setStatus("Ready to process.");
  renderPreview(uploadedFiles.get(fileName));
  setButtonLoading(false);
}

function addFiles(files) {
  [...files].forEach((file) => {
    uploadedFiles.set(file.name, file);

    const existing = fileList.querySelector(`[data-name="${CSS.escape(file.name)}"]`);
    if (existing) return;

    const button = document.createElement("button");
    button.className = "file-item";
    button.dataset.name = file.name;
    button.textContent = file.name;
    button.addEventListener("click", () => setActiveFile(file.name));
    fileList.appendChild(button);
  });

  if (files.length > 0) setActiveFile(files[0].name);
}

async function runOcr() {
  const file = uploadedFiles.get(selectedFileName);
  if (!file) {
    setStatus("Upload and select a file first.", "error");
    return;
  }

  setButtonLoading(true);
  setStatus("OCR running. This can take a while for large PDFs.");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch(`${API_BASE}/api/process`, {
      method: "POST",
      body: formData
    });

    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.detail || "OCR request failed.");
    }

    selectedRow = payload.row;
    rowToForm(payload.row);
    confidence.textContent = "Review";
    setStatus("OCR complete. Review fields before exporting.", "success");
  } catch (error) {
    console.error(error);
    setStatus(error.message, "error");
  } finally {
    setButtonLoading(false);
  }
}

async function exportRow() {
  const row = formToRow();

  try {
    const response = await fetch(`${API_BASE}/api/export`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(row)
    });

    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.detail || "Export failed.");
    }

    setStatus("Row saved to bills_export.csv.", "success");
  } catch (error) {
    console.error(error);
    setStatus(error.message, "error");
  }
}

fileInput.addEventListener("change", (event) => addFiles(event.target.files));

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("drag-over");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("drag-over");
  });
});

dropzone.addEventListener("drop", (event) => addFiles(event.dataTransfer.files));
processBtn.addEventListener("click", runOcr);
exportBtn.addEventListener("click", exportRow);

clearBtn.addEventListener("click", () => {
  selectedRow = null;
  rowToForm({});
  confidence.textContent = "--";
  setStatus("Fields cleared.");
});

downloadBtn.addEventListener("click", () => {
  window.location.href = `${API_BASE}/api/export/download`;
});

async function preloadSampleDocument() {
  try {
    const response = await fetch(`${API_BASE}/prueba4.jpg`);

    if (!response.ok) {
      throw new Error("Sample document prueba4.jpg was not found.");
    }

    const blob = await response.blob();

    const sampleFile = new File([blob], "prueba4.jpg", {
      type: blob.type || "image/jpeg"
    });

    addFiles([sampleFile]);
    setStatus("Ready to process.");
  } catch (error) {
    console.error(error);
    renderPreview(null);
    setStatus("Upload a file or add prueba4.jpg to preload the demo.", "neutral");
    setButtonLoading(false);
  }
}

window.addEventListener("DOMContentLoaded", preloadSampleDocument);
