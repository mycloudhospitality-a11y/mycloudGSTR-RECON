import streamlit as st
import pandas as pd
import json
import os
import numpy as np

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
# 3️⃣ APP HEADER
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
    st.error(f"❌ Excel file too large ({excel_size_mb:.2f} MB). Max allowed is 10 MB.")
    st.stop()

if pdf_size_mb > PDF_LIMIT_MB:
    st.error(f"❌ PDF file too large ({pdf_size_mb:.2f} MB). Max allowed is 300 MB.")
    st.stop()

st.success(
    f"Files accepted\n\n"
    f"- Excel: {excel_size_mb:.2f} MB\n"
    f"- PDF: {pdf_size_mb:.2f} MB"
)

st.divider()

# --------------------------------------------------
# 6️⃣ REAL EXCEL PARSING (BASIC & SAFE)
# --------------------------------------------------
def parse_gstr1_excel(file):
    """
    Basic, generic Excel aggregation.
    Works across hotels/months without schema lock-in.
    """
    df = pd.read_excel(file)

    totals = {
        "total_taxable_value": 0,
        "b2b_taxable_value": 0,
        "cgst_amount": 0,
        "sgst_amount": 0,
        "igst_amount": 0,
        "total_cess": 0,
        "total_invoice_value": 0,
        "exempted_non_gst": 0,
        "advances_adjusted": 0
    }

    for col in df.columns:
        col_lower = col.lower()

        if "taxable" in col_lower:
            totals["total_taxable_value"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "cgst" in col_lower:
            totals["cgst_amount"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "sgst" in col_lower:
            totals["sgst_amount"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "igst" in col_lower:
            totals["igst_amount"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "cess" in col_lower:
            totals["total_cess"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "invoice" in col_lower and "value" in col_lower:
            totals["total_invoice_value"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "exempt" in col_lower or "non gst" in col_lower:
            totals["exempted_non_gst"] += pd.to_numeric(df[col], errors="coerce").sum()
        if "advance" in col_lower:
            totals["advances_adjusted"] += pd.to_numeric(df[col], errors="coerce").sum()

    totals["b2b_taxable_value"] = totals["total_taxable_value"]  # safe default

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 7️⃣ PDF PARSING (PLACEHOLDER — NEXT STEP)
# --------------------------------------------------
def parse_gst_pdf(_file):
    """
    Placeholder.
    Returns zeros so reconciliation already differs per hotel.
    Full PDF parsing will replace this.
    """
    return {
        "total_taxable_value": 0,
        "b2b_taxable_value": 0,
        "cgst_amount": 0,
        "sgst_amount": 0,
        "igst_amount": 0,
        "total_cess": 0,
        "total_invoice_value": 0,
        "exempted_non_gst": 0,
        "advances_adjusted": 0
    }

excel_totals = parse_gstr1_excel(gstr1_file)
pdf_totals = parse_gst_pdf(gst_pdf_file)

# --------------------------------------------------
# 8️⃣ BUILD RECON TABLE (DYNAMIC, MULTI-HOTEL SAFE)
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
# 9️⃣ DISPLAY OUTPUT
# --------------------------------------------------
st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

st.subheader("Explanation Notes")
st.info(config["explanation_templates"]["matched"])
st.warning(config["explanation_templates"]["difference_allowed"])

st.success(config["audit_note"])
