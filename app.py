import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
import re
import pdfplumber

# --------------------------------------------------
# 1️⃣ PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="mycloud GSTR-1 Reconciliation",
    layout="wide"
)

# --------------------------------------------------
# 2️⃣ LOAD CONFIG
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
    "- GSTR-1 Excel: **≤ 10 MB**\n"
    "- GST Export PDF: **≤ 300 MB**\n\n"
    "Each upload is processed independently."
)

st.divider()

# --------------------------------------------------
# 4️⃣ FILE UPLOAD
# --------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    gstr1_file = st.file_uploader(
        "Upload GSTR-1 Excel (≤ 10 MB)",
        type=["xlsx"]
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
if len(gstr1_file.getbuffer()) / (1024 * 1024) > 10:
    st.error("❌ Excel file exceeds 10 MB limit.")
    st.stop()

if len(gst_pdf_file.getbuffer()) / (1024 * 1024) > 300:
    st.error("❌ PDF file exceeds 300 MB limit.")
    st.stop()

st.success("Files accepted successfully")
st.divider()

# --------------------------------------------------
# 6️⃣ SAFE METADATA EXTRACTION
# --------------------------------------------------
def extract_metadata(file):
    xls = pd.ExcelFile(file)
    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

    hotel = "Unknown"
    gstin = "Unknown"
    period = "Unknown"

    max_rows, max_cols = df.shape

    for i in range(min(15, max_rows)):
        for j in range(min(10, max_cols)):
            try:
                cell = str(df.iloc[i, j]).lower()

                if "gstin" in cell and j + 1 < max_cols:
                    gstin = str(df.iloc[i, j + 1]).strip()

                if ("legal name" in cell or "trade name" in cell) and j + 1 < max_cols:
                    hotel = str(df.iloc[i, j + 1]).strip()

                if "return period" in cell and j + 1 < max_cols:
                    period = str(df.iloc[i, j + 1]).strip()

            except Exception:
                continue

    return hotel, gstin, period

# --------------------------------------------------
# 7️⃣ GSTR-1 EXCEL PARSER (YOUR FORMAT)
# --------------------------------------------------
def parse_gstr1_excel(file):
    xls = pd.ExcelFile(file)

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

    if "hsn" in xls.sheet_names:
        df = pd.read_excel(xls, "hsn", header=None)
        totals["total_invoice_value"] = float(df.iloc[1, 3])
        totals["total_taxable_value"] = float(df.iloc[1, 4])
        totals["igst_amount"] = float(df.iloc[1, 6])
        totals["cgst_amount"] = float(df.iloc[1, 7])
        totals["sgst_amount"] = float(df.iloc[1, 8])
        totals["total_cess"] = float(df.iloc[1, 9])

    if "b2b" in xls.sheet_names:
        df = pd.read_excel(xls, "b2b", header=None)
        totals["b2b_taxable_value"] = float(df.iloc[1, 11])

    if "exemp" in xls.sheet_names:
        df = pd.read_excel(xls, "exemp", header=None)
        totals["exempted_non_gst"] = float(df.iloc[1, 3])

    if "atadj" in xls.sheet_names:
        df = pd.read_excel(xls, "atadj", header=None)
        totals["advances_adjusted"] = float(df.iloc[1, 3])

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 8️⃣ SAFE PDF TEXT EXTRACTION (NO FAKE MATCHING)
# --------------------------------------------------
def extract_amount(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1).replace(",", "")) if match else 0.0

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

            totals["total_taxable_value"] += extract_amount(r"taxable value\s*₹?\s*([\d,]+\.\d+)", text)
            totals["cgst_amount"] += extract_amount(r"cgst\s*₹?\s*([\d,]+\.\d+)", text)
            totals["sgst_amount"] += extract_amount(r"sgst\s*₹?\s*([\d,]+\.\d+)", text)
            totals["igst_amount"] += extract_amount(r"igst\s*₹?\s*([\d,]+\.\d+)", text)
            totals["total_cess"] += extract_amount(r"cess\s*₹?\s*([\d,]+\.\d+)", text)

    totals["b2b_taxable_value"] = totals["total_taxable_value"]
    totals["total_invoice_value"] = (
        totals["total_taxable_value"]
        + totals["cgst_amount"]
        + totals["sgst_amount"]
        + totals["igst_amount"]
        + totals["total_cess"]
    )

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 9️⃣ PROCESSING STATE
# --------------------------------------------------
with st.spinner("🔄 Reconciling GSTR-1 with GST Export… Please wait"):
    hotel, gstin, period = extract_metadata(gstr1_file)
    excel_totals = parse_gstr1_excel(gstr1_file)
    pdf_totals = parse_gst_pdf(gst_pdf_file)

st.success("✅ Reconciliation completed")
st.divider()

# --------------------------------------------------
# 🔟 DISPLAY METADATA
# --------------------------------------------------
st.subheader("Hotel Details")
st.write(f"**Hotel Name:** {hotel}")
st.write(f"**GSTIN:** {gstin}")
st.write(f"**Return Period:** {period}")

# --------------------------------------------------
# 11️⃣ BUILD RECONCILIATION TABLE
# --------------------------------------------------
rows = []

for comp in config["reconciliation_components"]:
    key = comp["key"]

    excel_value = excel_totals.get(key, 0)
    pdf_value = pdf_totals.get(key, 0)

    discrepancy = round(abs(excel_value - pdf_value), 2)
    status = "Matched" if discrepancy == 0 else "Difference"

    rows.append([
        comp["label"],
        excel_value,
        pdf_value,
        comp["logic"],
        status,
        discrepancy
    ])

df = pd.DataFrame(rows, columns=config["output_table"]["columns"])

st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

# --------------------------------------------------
# 12️⃣ DOWNLOAD RECONCILIATION EXCEL
# --------------------------------------------------
def build_download(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reconciliation")
    return buffer.getvalue()

st.download_button(
    "⬇️ Download Reconciliation Excel",
    data=build_download(df),
    file_name=f"GSTR_Reconciliation_{gstin}_{period}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
