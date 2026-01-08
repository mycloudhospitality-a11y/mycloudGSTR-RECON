import streamlit as st
import pandas as pd
import json
import os
import pdfplumber
import re

# --------------------------------------------------
# 1️⃣ PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="mycloud GSTR Reconciliation",
    layout="wide"
)

# --------------------------------------------------
# 2️⃣ LOAD JSON CONFIG
# --------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "gst_reconciliation_config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# --------------------------------------------------
# 3️⃣ HEADER
# --------------------------------------------------
st.title(config["app_meta"]["app_name"])
st.caption("Multi-hotel | Multi-month | File-driven reconciliation")

st.info(
    "📌 Upload limits (Streamlit Cloud)\n\n"
    "- GST Export PDF: **≤ 300 MB**\n"
    "- GSTR-1 Excel / CSV: **≤ 10 MB**\n\n"
    "Each upload is processed independently. No data is reused."
)

st.divider()

# --------------------------------------------------
# 4️⃣ FILE UPLOAD
# --------------------------------------------------
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
    st.stop()

# --------------------------------------------------
# 5️⃣ FILE SIZE VALIDATION
# --------------------------------------------------
EXCEL_LIMIT_MB = 10
PDF_LIMIT_MB = 300

excel_size_mb = len(gstr1_file.getbuffer()) / (1024 * 1024)
pdf_size_mb = len(gst_pdf_file.getbuffer()) / (1024 * 1024)

if excel_size_mb > EXCEL_LIMIT_MB:
    st.error(f"❌ Excel too large ({excel_size_mb:.2f} MB). Max 10 MB.")
    st.stop()

if pdf_size_mb > PDF_LIMIT_MB:
    st.error(f"❌ PDF too large ({pdf_size_mb:.2f} MB). Max 300 MB.")
    st.stop()

st.success(f"Files accepted | Excel: {excel_size_mb:.2f} MB | PDF: {pdf_size_mb:.2f} MB")
st.divider()

# --------------------------------------------------
# 6️⃣ GSTR-1 EXCEL PARSING (REAL)
# --------------------------------------------------
def parse_gstr1_excel(file):
    df = pd.read_excel(file)

    totals = {
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

    for col in df.columns:
        c = col.lower()

        series = pd.to_numeric(df[col], errors="coerce").fillna(0)

        if "taxable" in c:
            totals["total_taxable_value"] += series.sum()
        if "cgst" in c:
            totals["cgst_amount"] += series.sum()
        if "sgst" in c:
            totals["sgst_amount"] += series.sum()
        if "igst" in c:
            totals["igst_amount"] += series.sum()
        if "cess" in c:
            totals["total_cess"] += series.sum()
        if "invoice" in c and "value" in c:
            totals["total_invoice_value"] += series.sum()
        if "exempt" in c or "non gst" in c:
            totals["exempted_non_gst"] += series.sum()
        if "advance" in c:
            totals["advances_adjusted"] += series.sum()

    totals["b2b_taxable_value"] = totals["total_taxable_value"]

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 7️⃣ GST PDF PARSING (REAL, PAGE-WISE)
# --------------------------------------------------
def extract_amount(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0

def parse_gst_pdf(file):
    totals = {
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

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            totals["total_taxable_value"] += extract_amount(r"Taxable Value\s*₹?\s*([\d,]+\.\d+)", text)
            totals["cgst_amount"] += extract_amount(r"CGST\s*₹?\s*([\d,]+\.\d+)", text)
            totals["sgst_amount"] += extract_amount(r"SGST\s*₹?\s*([\d,]+\.\d+)", text)
            totals["igst_amount"] += extract_amount(r"IGST\s*₹?\s*([\d,]+\.\d+)", text)
            totals["total_cess"] += extract_amount(r"Cess\s*₹?\s*([\d,]+\.\d+)", text)
            totals["total_invoice_value"] += extract_amount(r"Total Invoice Value\s*₹?\s*([\d,]+\.\d+)", text)
            totals["exempted_non_gst"] += extract_amount(r"Exempt\s*₹?\s*([\d,]+\.\d+)", text)
            totals["advances_adjusted"] += extract_amount(r"Advance\s*Adjusted\s*₹?\s*([\d,]+\.\d+)", text)

    totals["b2b_taxable_value"] = totals["total_taxable_value"]

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 8️⃣ RUN PARSERS
# --------------------------------------------------
excel_totals = parse_gstr1_excel(gstr1_file)
pdf_totals = parse_gst_pdf(gst_pdf_file)

# --------------------------------------------------
# 9️⃣ BUILD RECON TABLE
# --------------------------------------------------
rows = []

for comp in config["reconciliation_components"]:
    key = comp["key"]

    excel_value = excel_totals.get(key, 0)
    pdf_value = pdf_totals.get(key, 0)

    discrepancy = round(abs(excel_value - pdf_value), 2)

    if comp["match_type"] == "exact":
        status = "Matched" if discrepancy == 0 else "Difference"
    else:
        status = "Difference" if discrepancy != 0 else "Matched"

    rows.append([
        comp["label"],
        excel_value,
        pdf_value,
        comp["logic"],
        status,
        discrepancy
    ])

df = pd.DataFrame(rows, columns=config["output_table"]["columns"])

# --------------------------------------------------
# 🔟 DISPLAY OUTPUT
# --------------------------------------------------
st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

st.subheader("Explanation Notes")
st.info(config["explanation_templates"]["matched"])
st.warning(config["explanation_templates"]["difference_allowed"])

st.success(config["audit_note"])
