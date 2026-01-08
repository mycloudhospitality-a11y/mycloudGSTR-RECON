import streamlit as st
import pandas as pd
import json
import os

# --------------------------------------------------
# 1️⃣ PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="mycloud GSTR Reconciliation",
    layout="wide"
)

# --------------------------------------------------
# 2️⃣ LOAD JSON CONFIG SAFELY
# --------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "gst_reconciliation_config.json")

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
except Exception as e:
    st.error("❌ Unable to load configuration file (gst_reconciliation_config.json)")
    st.exception(e)
    st.stop()

# --------------------------------------------------
# 3️⃣ APP HEADER
# --------------------------------------------------
st.title(config["app_meta"]["app_name"])
st.caption("Streamlit Cloud | GST Reconciliation")

st.info(
    "📌 **Upload limits (Streamlit Cloud)**\n\n"
    "- GST Export PDF: **Maximum 300 MB**\n"
    "- GSTR-1 Excel / CSV: **Maximum 10 MB**\n\n"
    "For larger PDFs, please use cloud storage (S3 / Azure Blob)."
)

st.divider()

# --------------------------------------------------
# 4️⃣ FILE UPLOAD SECTION
# --------------------------------------------------
st.header("Upload Input Files")

col1, col2 = st.columns(2)

with col1:
    gstr1_file = st.file_uploader(
        "Upload GSTR-1 Excel / CSV (≤ 10 MB)",
        type=["csv", "xlsx"]
    )

with col2:
    gst_pdf_file = st.file_uploader(
        "Upload GST Export PDF (≤ 300 MB)",
        type=["pdf"]
    )

if not gstr1_file or not gst_pdf_file:
    st.info("Please upload **both** files to proceed.")
    st.stop()

# --------------------------------------------------
# 5️⃣ FILE SIZE VALIDATION (CLOUD-SAFE)
# --------------------------------------------------
EXCEL_LIMIT_MB = 10
PDF_LIMIT_MB = 300

excel_size_mb = len(gstr1_file.getbuffer()) / (1024 * 1024)
pdf_size_mb = len(gst_pdf_file.getbuffer()) / (1024 * 1024)

if excel_size_mb > EXCEL_LIMIT_MB:
    st.error(
        f"❌ GSTR-1 Excel file is too large ({excel_size_mb:.2f} MB).\n\n"
        f"Maximum allowed size is {EXCEL_LIMIT_MB} MB."
    )
    st.stop()

if pdf_size_mb > PDF_LIMIT_MB:
    st.error(
        f"❌ GST Export PDF is too large ({pdf_size_mb:.2f} MB).\n\n"
        f"Maximum allowed size is {PDF_LIMIT_MB} MB.\n\n"
        "👉 Please split the PDF or upload via cloud storage."
    )
    st.stop()

st.success(
    f"✅ Files accepted\n\n"
    f"- Excel size: {excel_size_mb:.2f} MB\n"
    f"- PDF size: {pdf_size_mb:.2f} MB"
)

st.divider()

# --------------------------------------------------
# 6️⃣ RECONCILIATION LOGIC (TEMPORARY DEMO DATA)
# --------------------------------------------------
# NOTE:
# This is SAMPLE data only.
# These values WILL change dynamically once
# real Excel & PDF parsing is implemented.

data = [
    ["Total Taxable Value", 35842919.18, 35842919.18, "Aggregated HSN Taxable Value", "Matched", 0],
    ["B2B Taxable Value", 20599799.29, 20599799.29, "Registered Invoices", "Matched", 0],
    ["CGST Amount", 1493672.88, 1493672.88, "Central Tax Liability", "Matched", 0],
    ["SGST Amount", 1493672.88, 1493672.88, "State Tax Liability", "Matched", 0],
    ["IGST Amount", 363588.11, 363588.11, "Integrated Tax Liability", "Matched", 0],
    ["Total Cess", 1478.62, 1478.62, "Luxury / Additional Cess", "Matched", 0],
    ["Total Invoice Value", 40028847.02, 40028847.02, "Gross Invoice Value", "Matched", 0],
    ["Exempted / Non-GST", 1068679.02, 343463.57, "Non-taxable Supplies", "Difference", 725215.45],
    ["Advances Adjusted", 538054.02, 172332.22, "Advance Adjustments", "Difference", 365721.80]
]

df = pd.DataFrame(
    data,
    columns=config["output_table"]["columns"]
)

# --------------------------------------------------
# 7️⃣ OUTPUT TABLE
# --------------------------------------------------
st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

# --------------------------------------------------
# 8️⃣ EXPLANATION NOTES
# --------------------------------------------------
st.subheader("Explanation Notes")

st.info(config["explanation_notes"]["matched"])
st.warning(config["explanation_notes"]["exempted_difference"])
st.warning(config["explanation_notes"]["advance_difference"])

st.success(config["final_conclusion"])

# --------------------------------------------------
# 🔚 END OF APPLICATION
# --------------------------------------------------
