import streamlit as st

# --------------------------------------------------
# SAFE BOOTSTRAP (prevents "Oh no" screen)
# --------------------------------------------------
st.set_page_config(
    page_title="mycloud GSTR-1 Reconciliation",
    layout="wide"
)

st.title("mycloud GSTR-1 Reconciliation")
st.caption("Secure, file-driven GST reconciliation for hotels")

# --------------------------------------------------
# SAFE IMPORTS (wrapped to avoid silent crashes)
# --------------------------------------------------
try:
    import pandas as pd
    import json
    import os
    import re
    import time
    from io import BytesIO
    import pdfplumber
except Exception as e:
    st.error("❌ Failed to load required libraries")
    st.exception(e)
    st.stop()

# --------------------------------------------------
# LOAD CONFIG SAFELY
# --------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "gst_reconciliation_config.json")

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error("❌ gst_reconciliation_config.json missing or invalid")
    st.exception(e)
    st.stop()

st.success("✅ Application initialized successfully")
st.divider()

# --------------------------------------------------
# FILE UPLOAD UI
# --------------------------------------------------
st.info(
    "📌 Upload limits\n\n"
    "- GSTR-1 Excel: **≤ 10 MB**\n"
    "- GST Export PDF: **≤ 300 MB**\n\n"
    "Each upload is processed independently."
)

col1, col2 = st.columns(2)

with col1:
    gstr1_file = st.file_uploader(
        "Upload GSTR-1 Excel / CSV (≤ 10 MB)",
        type=["xlsx", "csv"]
    )

with col2:
    gst_pdf_file = st.file_uploader(
        "Upload GST Export PDF (≤ 300 MB)",
        type=["pdf"]
    )

if not gstr1_file or not gst_pdf_file:
    st.info("⬆️ Upload both files to start reconciliation")
    st.stop()

# --------------------------------------------------
# FILE SIZE VALIDATION
# --------------------------------------------------
if len(gstr1_file.getbuffer()) / (1024 * 1024) > 10:
    st.error("❌ Excel file exceeds 10 MB limit")
    st.stop()

if len(gst_pdf_file.getbuffer()) / (1024 * 1024) > 300:
    st.error("❌ PDF file exceeds 300 MB limit")
    st.stop()

st.success("📂 Files accepted successfully")
st.divider()

# --------------------------------------------------
# PROGRESS UI
# --------------------------------------------------
st.subheader("Processing Status")
progress_bar = st.progress(0)
status_text = st.empty()

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def safe_number(value):
    """Safely convert GST numbers like '₹3,58,42,919.18' → float"""
    try:
        value = re.sub(r"[₹,]", "", str(value))
        return float(value)
    except Exception:
        return 0.0

# --------------------------------------------------
# STEP 1: EXTRACT METADATA
# --------------------------------------------------
status_text.text("🔍 Reading hotel metadata…")
progress_bar.progress(10)

xls = pd.ExcelFile(gstr1_file)
meta_df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

hotel = gstin = period = "Unknown"

rows, cols = meta_df.shape
for i in range(min(20, rows)):
    for j in range(min(10, cols)):
        cell = str(meta_df.iloc[i, j]).lower()
        if "gstin" in cell and j + 1 < cols:
            gstin = str(meta_df.iloc[i, j + 1]).strip()
        if ("legal name" in cell or "trade name" in cell) and j + 1 < cols:
            hotel = str(meta_df.iloc[i, j + 1]).strip()
        if "return period" in cell and j + 1 < cols:
            period = str(meta_df.iloc[i, j + 1]).strip()

progress_bar.progress(25)

# --------------------------------------------------
# STEP 2: PARSE GSTR-1 EXCEL (REAL VALUES)
# --------------------------------------------------
status_text.text("📊 Parsing GSTR-1 Excel…")

excel_totals = {
    "total_taxable_value": 0.0,
    "b2b_taxable_value": 0.0,
    "cgst_amount": 0.0,
    "sgst_amount": 0.0,
    "igst_amount": 0.0,
    "total_cess": 0.0,
    "total_invoice_value": 0.0,
    "exempted_non_gst": 0.0,
    "advances_adjusted": 0.0
}

if "hsn" in xls.sheet_names:
    hsn = pd.read_excel(xls, "hsn", header=None)
    excel_totals["total_invoice_value"] = safe_number(hsn.iloc[1, 3])
    excel_totals["total_taxable_value"] = safe_number(hsn.iloc[1, 4])
    excel_totals["igst_amount"] = safe_number(hsn.iloc[1, 6])
    excel_totals["cgst_amount"] = safe_number(hsn.iloc[1, 7])
    excel_totals["sgst_amount"] = safe_number(hsn.iloc[1, 8])
    excel_totals["total_cess"] = safe_number(hsn.iloc[1, 9])

if "b2b" in xls.sheet_names:
    b2b = pd.read_excel(xls, "b2b", header=None)
    excel_totals["b2b_taxable_value"] = safe_number(b2b.iloc[1, 11])

if "exemp" in xls.sheet_names:
    exemp = pd.read_excel(xls, "exemp", header=None)
    excel_totals["exempted_non_gst"] = safe_number(exemp.iloc[1, 3])

if "atadj" in xls.sheet_names:
    atadj = pd.read_excel(xls, "atadj", header=None)
    excel_totals["advances_adjusted"] = safe_number(atadj.iloc[1, 3])

progress_bar.progress(45)

# --------------------------------------------------
# STEP 3: PARSE GST PDF (PAGE-BY-PAGE)
# --------------------------------------------------
status_text.text("📄 Parsing GST Export PDF…")

pdf_totals = dict.fromkeys(excel_totals.keys(), 0.0)

with pdfplumber.open(gst_pdf_file) as pdf:
    total_pages = len(pdf.pages)
    for idx, page in enumerate(pdf.pages):
        text = page.extract_text() or ""

        pdf_totals["total_taxable_value"] += safe_number(
            re.search(r"taxable value\s*([\d,\.]+)", text, re.I).group(1)
            if re.search(r"taxable value\s*([\d,\.]+)", text, re.I)
            else 0
        )
        pdf_totals["cgst_amount"] += safe_number(
            re.search(r"cgst\s*([\d,\.]+)", text, re.I).group(1)
            if re.search(r"cgst\s*([\d,\.]+)", text, re.I)
            else 0
        )
        pdf_totals["sgst_amount"] += safe_number(
            re.search(r"sgst\s*([\d,\.]+)", text, re.I).group(1)
            if re.search(r"sgst\s*([\d,\.]+)", text, re.I)
            else 0
        )
        pdf_totals["igst_amount"] += safe_number(
            re.search(r"igst\s*([\d,\.]+)", text, re.I).group(1)
            if re.search(r"igst\s*([\d,\.]+)", text, re.I)
            else 0
        )
        pdf_totals["total_cess"] += safe_number(
            re.search(r"cess\s*([\d,\.]+)", text, re.I).group(1)
            if re.search(r"cess\s*([\d,\.]+)", text, re.I)
            else 0
        )

        progress_bar.progress(45 + int((idx + 1) / total_pages * 40))

pdf_totals["b2b_taxable_value"] = pdf_totals["total_taxable_value"]
pdf_totals["total_invoice_value"] = (
    pdf_totals["total_taxable_value"]
    + pdf_totals["cgst_amount"]
    + pdf_totals["sgst_amount"]
    + pdf_totals["igst_amount"]
    + pdf_totals["total_cess"]
)

progress_bar.progress(90)

# --------------------------------------------------
# STEP 4: BUILD RECON TABLE
# --------------------------------------------------
status_text.text("🧮 Building reconciliation…")

rows = []
for comp in config["reconciliation_components"]:
    key = comp["key"]
    ev = round(excel_totals.get(key, 0), 2)
    pv = round(pdf_totals.get(key, 0), 2)
    diff = round(abs(ev - pv), 2)
    status = "Matched" if diff == 0 else "Difference"

    rows.append([
        comp["label"],
        ev,
        pv,
        comp["logic"],
        status,
        diff
    ])

df = pd.DataFrame(rows, columns=config["output_table"]["columns"])

progress_bar.progress(100)
status_text.text("✅ Reconciliation completed")

st.divider()

# --------------------------------------------------
# OUTPUT
# --------------------------------------------------
st.subheader("Hotel Details")
st.write(f"**Hotel Name:** {hotel}")
st.write(f"**GSTIN:** {gstin}")
st.write(f"**Return Period:** {period}")

st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------
def build_download(dataframe):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="Reconciliation")
    return buffer.getvalue()

st.download_button(
    "⬇️ Download Reconciliation Excel",
    data=build_download(df),
    file_name=f"GSTR_Reconciliation_{gstin}_{period}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
