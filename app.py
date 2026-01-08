import streamlit as st
import pandas as pd
import json
import os

# --------------------------------------------------
# 1️⃣ STREAMLIT SERVER CONFIG (1 GB UPLOAD)
# --------------------------------------------------
# This MUST be set before file_uploader is used
# Works only for local / self-hosted Streamlit
st.set_option("server.maxUploadSize", 1024)  # MB → 1 GB

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
    st.error("❌ Failed to load configuration file")
    st.exception(e)
    st.stop()

# --------------------------------------------------
# 3️⃣ APP HEADER
# --------------------------------------------------
st.title(config["app_meta"]["app_name"])
st.caption("Self-hosted Streamlit | Large PDF enabled (up to 1 GB)")

st.divider()

# --------------------------------------------------
# 4️⃣ FILE UPLOAD SECTION
# --------------------------------------------------
st.header("Upload Input Files")

col1, col2 = st.columns(2)

with col1:
    gstr1_file = st.file_uploader(
        "Upload GSTR-1 Excel / CSV",
        type=["csv", "xlsx"],
        help="Upload GSTR-1 return file"
    )

with col2:
    gst_pdf_file = st.file_uploader(
        "Upload GST Export PDF (up to 1 GB)",
        type=["pdf"],
        help="Large PDF supported ONLY on self-hosted Streamlit"
    )

# --------------------------------------------------
# 5️⃣ VALIDATION
# --------------------------------------------------
if not gstr1_file or not gst_pdf_file:
    st.info("Please upload **both** GSTR-1 Excel and GST Export PDF to continue.")
    st.stop()

st.success("✅ Files uploaded successfully")

# --------------------------------------------------
# 6️⃣ FILE SIZE DISPLAY (DEBUG / CONFIDENCE)
# --------------------------------------------------
pdf_size_mb = len(gst_pdf_file.getbuffer()) / (1024 * 1024)

st.write(f"📄 **GST PDF Size:** {pdf_size_mb:.2f} MB")

if pdf_size_mb > 1024:
    st.error("❌ PDF exceeds 1 GB limit even for self-hosted setup.")
    st.stop()

# --------------------------------------------------
# 7️⃣ PLACEHOLDER RECON LOGIC (SAFE DEMO)
# --------------------------------------------------
# NOTE: We will replace this with real Excel + PDF parsing later

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
# 8️⃣ OUTPUT TABLE
# --------------------------------------------------
st.subheader("Reconciliation Summary")
st.dataframe(df, use_container_width=True)

# --------------------------------------------------
# 9️⃣ EXPLANATION NOTES
# --------------------------------------------------
st.subheader("Explanation Notes")

st.info(config["explanation_notes"]["matched"])
st.warning(config["explanation_notes"]["exempted_difference"])
st.warning(config["explanation_notes"]["advance_difference"])

st.success(config["final_conclusion"])

# --------------------------------------------------
# 🔚 END OF APP
# --------------------------------------------------
