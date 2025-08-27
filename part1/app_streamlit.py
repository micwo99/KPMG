import streamlit as st
import json
from dotenv import load_dotenv
from extract_fields import extract_fields_majority_vote

load_dotenv()

st.set_page_config(page_title="Part 1 – Form Extraction (Azure DI + GPT-4o)", layout="centered")

st.title("🧾 Part 1 – Form Extraction")
st.caption("OCR with Azure Document Intelligence → Field extraction with Azure OpenAI (GPT-4o) → JSON output")

uploaded = st.file_uploader("Upload a PDF or image (JPG/PNG) of the form", type=["pdf","jpg","jpeg","png"])
lang = st.selectbox("Language hint (optional)", options=["he","en"], index=0, help="Passes a locale hint to Document Intelligence")

if uploaded is not None:
    file_bytes = uploaded.read()
    if st.button("Extract fields"):
        with st.spinner("Running OCR + LLM extraction..."):
            normalized = extract_fields_majority_vote(file_bytes, language_hint=lang)
        st.subheader("JSON (normalized & validated)")
        st.json(normalized)
        st.download_button("⬇️ Download JSON", data=json.dumps(normalized, ensure_ascii=False, indent=2), file_name="extracted.json")
 
else:
    st.info("Upload a file to begin.")
