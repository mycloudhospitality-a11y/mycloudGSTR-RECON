import streamlit as st
import pandas as pd
import json
import os
from io import BytesIO
import re
import pdfplumber
import time

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
    gstr1_file = st.file_uploader("Upload GSTR-1 Excel", type=["xlsx"])

with col2:
    gst_pdf_file = st.file_uploader("Upload GST Export PDF", type=["pdf"])

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
# 6️⃣ HELPERS
# --------------------------------------------------
def safe_number(value):
    try:
        if pd.isna(value):
            return 0.0
        value = str(value)
        value = re.sub(r"[₹,]", "", value)
        return float(value)
    except Exception:
        return 0.0

# --------------------------------------------------
# 7️⃣ METADATA EXTRACTION
# --------------------------------------------------
def extract_metadata(file):
    xls = pd.ExcelFile(file)
    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0], header=None)

    hotel, gstin, period = "Unknown", "Unknown", "Unknown"
    rows, cols = df.shape

    for i in range(min(20, rows)):
        for j in range(min(10, cols)):
            cell = str(df.iloc[i, j]).lower()
            if "gstin" in cell and j + 1 < cols:
                gstin = str(df.iloc[i, j + 1]).strip()
            if ("legal name" in cell or "trade name" in cell) and j + 1 < cols:
                hotel = str(df.iloc[i, j + 1]).strip()
            if "return period" in cell and j + 1 < cols:
                period = str(df.iloc[i, j + 1]).strip()

    return hotel, gstin, period

# --------------------------------------------------
# 8️⃣ GSTR-1 EXCEL PARSER
# --------------------------------------------------
def parse_gstr1_excel(file):
    xls = pd.ExcelFile(file)
    totals = dict.fromkeys(config["reconciliation_components"][0].keys(), 0)

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
        totals["total_invoice_value"] = safe_number(df.iloc[1, 3])
        totals["total_taxable_value"] = safe_number(df.iloc[1, 4])
        totals["igst_amount"] = safe_number(df.iloc[1, 6])
        totals["cgst_amount"] = safe_number(df.iloc[1, 7])
        totals["sgst_amount"] = safe_number(df.iloc[1, 8])
        totals["total_cess"] = safe_number(df.iloc[1, 9])

    if "b2b" in xls.sheet_names:
        df = pd.read_excel(xls, "b2b", header=None)
        totals["b2b_taxable_value"] = safe_number(df.iloc[1, 11])

    if "exemp" in xls.sheet_names:
        df = pd.read_excel(xls, "exemp", header=None)
        totals["exempted_non_gst"] = safe_number(df.iloc[1, 3])

    if "atadj" in xls.sheet_names:
        df = pd.read_excel(xls, "atadj", header=None)
        totals["advances_adjusted"] = safe_number(df.iloc[1, 3])

    return totals

# --------------------------------------------------
# 9️⃣ PDF PARSER WITH PAGE-LEVEL PROGRESS
# --------------------------------------------------
def parse_gst_pdf(file, progress_bar):
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
        total_pages = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            totals["total_taxable_value"] += safe_number(
                re.search(r"taxable value\s*([\d,\.]+)", text, re.I).group(1)
                if re.search(r"taxable value\s*([\d,\.]+)", text, re.I)
                else 0
            )

            totals["cgst_amount"] += safe_number(
                re.search(r"cgst\s*([\d,\.]+)", text, re.I).group(1)
                if re.search(r"cgst\s*([\d,\.]+)", text, re.I)
                else 0
            )

            totals["sgst_amount"] += safe_number(
                re.search(r"sgst\s*([\d,\.]+)", text, re.I).group(1)
                if re.search(r"sgst\s*([\d,\.]+)", text, re.I)
                else 0
            )

            totals["igst_amount"] += safe_number(
                re.search(r"igst\s*([\d,\.]+)", text, re.I).group(1)
                if re.search(r"igst\s*([\d,\.]+)", text, re.I)
                else 0
            )

            totals["total_cess"] += safe_number(
                re.search(r"cess\s*([\d,\.]+)", text, re.I).group(1)
                if re.search(r"cess\s*([\d,\.]+)", text, re.I)
                else 0
            )

            # Update progress: PDF parsing occupies 40–80%
            progress_bar.progress(40 + int((i + 1) / total_pages * 40))
            time.sleep(0.02)  # smooth UI

    totals["b2b_taxable_value"] = totals["total_taxable_value"]
    totals["total_invoice_value"] = (
        totals["total_taxable_value"]
        + totals["cgst_amount"]
        + totals["sgst_amount"]
        + totals["igst_amount"]
        + totals["total_cess"]
    )

    return totals

# --------------------------------------------------
# 🔟 PROCESSING WITH PROGRESS BAR
# --------------------------------------------------
st.subheader("Processing Status")

progress_bar = st.progress(0)
status_text = st.empty()

with st.spinner("Reconciling GSTR-1 with GST Export…"):
    status_text.text("🔍 Reading hotel metadata…")
    hotel, gstin, period = extract_metadata(gstr1_file)
    progress_bar.progress(10)

    status_text.text("📊 Parsing GSTR-1 Excel…")
    excel_totals = parse_gstr1_excel(gstr1_file)
    progress_bar.progress(40)

    status_text.text("📄 Parsing GST Export PDF…")
    pdf_totals = parse_gst_pdf(gst_pdf_file, progress_bar)

    status_text.text("🧮 Building reconciliation table…")
    progress_bar.progress(90)
    time.sleep(0.2)

progress_bar.progress(100)
status_text.text("✅ Reconciliation completed")

st.divider()

# --------------------------------------------------
# 11️⃣ DISPLAY METADATA
# --------------------------------------------------
st.subheader("Hotel Details")
st.write(f"**Hotel Name:** {hotel}")
st.write(f"**GSTIN:** {gstin}")
st.write(f"**Return Period:** {period}")

# --------------------------------------------------
# 12️⃣ BUILD TABLE
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
# 13️⃣ DOWNLOAD EXCEL
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
