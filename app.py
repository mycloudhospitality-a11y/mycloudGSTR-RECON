import streamlit as st
import pandas toggle
import json
import os
import pandas as pd

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
    "- GSTR-1 Excel / CSV: **≤ 10 MB**\n"
    "- GST Export PDF: **≤ 300 MB**\n\n"
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
    f"Files accepted | Excel: {excel_size_mb:.2f} MB | PDF: {pdf_size_mb:.2f} MB"
)

st.divider()

# --------------------------------------------------
# 6️⃣ GSTR-1 EXCEL PARSER (FORMAT-LOCKED & CORRECT)
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

    # HSN SUMMARY
    if "hsn" in xls.sheet_names:
        df_hsn = pd.read_excel(xls, sheet_name="hsn", header=None)

        totals["total_invoice_value"] = float(df_hsn.iloc[1, 3])
        totals["total_taxable_value"] = float(df_hsn.iloc[1, 4])
        totals["igst_amount"] = float(df_hsn.iloc[1, 6])
        totals["cgst_amount"] = float(df_hsn.iloc[1, 7])
        totals["sgst_amount"] = float(df_hsn.iloc[1, 8])
        totals["total_cess"] = float(df_hsn.iloc[1, 9])

    # B2B SUMMARY
    if "b2b" in xls.sheet_names:
        df_b2b = pd.read_excel(xls, sheet_name="b2b", header=None)
        totals["b2b_taxable_value"] = float(df_b2b.iloc[1, 11])

    # EXEMPT / NON-GST
    if "exemp" in xls.sheet_names:
        df_ex = pd.read_excel(xls, sheet_name="exemp", header=None)
        totals["exempted_non_gst"] = float(df_ex.iloc[1, 3])

    # ADVANCE ADJUSTED
    if "atadj" in xls.sheet_names:
        df_adv = pd.read_excel(xls, sheet_name="atadj", header=None)
        totals["advances_adjusted"] = float(df_adv.iloc[1, 3])

    return {k: round(v, 2) for k, v in totals.items()}

# --------------------------------------------------
# 7️⃣ GST PDF PARSER (INTENTIONALLY PENDING)
# --------------------------------------------------
def parse_gst_pdf(_file):
    """
    PDF table extraction will be added later (Camelot / Tabula).
    Returning None avoids false 'Matched = 0' results.
    """
    return {
        "total_taxable_value": None,
        "b2b_taxable_value": None,
        "cgst_amount": None,
        "sgst_amount": None,
        "igst_amount": None,
        "total_cess": None,
        "total_invoice_value": None,
        "exempted_non_gst": None,
        "advances_adjusted": None
    }

# --------------------------------------------------
# 8️⃣ PROCESSING STATE
# --------------------------------------------------
with st.spinner("🔄 Reconciling GSTR-1 with GST Export… Please wait"):
    progress = st.progress(0)

    progress.progress(20)
    excel_totals = parse_gstr1_excel(gstr1_file)

    progress.progress(60)
    pdf_totals = parse_gst_pdf(gst_pdf_file)

    progress.progress(100)

st.success("✅ Reconciliation completed")

st.divider()

# --------------------------------------------------
# 9️⃣ BUILD RECON TABLE
# --------------------------------------------------
rows = []

for comp in config["reconciliation_components"]:
    key = comp["key"]

    excel_value = excel_totals.get(key)
    pdf_value = pdf_totals.get(key)

    if pdf_value is None:
        status = "Pending PDF Mapping"
        discrepancy = ""
    else:
        discrepancy = round(abs(excel_value - pdf_value), 2)
        if comp["match_type"] == "exact":
            status = "Matched" if discrepancy == 0 else "Difference"
        else:
            status = "Difference" if discrepancy != 0 else "Matched"

    rows.append([
        comp["label"],
        excel_value,
        pdf_value if pdf_value is not None else "—",
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
st.info("Matched → Excel and PDF values are identical.")
st.warning("Pending PDF Mapping → PDF extraction logic will be added next.")

st.success("Reconciliation is generated dynamically per hotel and per month.")
