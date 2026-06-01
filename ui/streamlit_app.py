"""Streamlit UI for interactive PII detection and masking."""

import os

import requests
import streamlit as st

API_BASE = os.getenv("PII_API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="PII Masking Demo",
    page_icon="🔒",
    layout="wide",
)

st.title("🔒 PII Detection & Masking")
st.caption("Powered by Microsoft Presidio + FastAPI")

col1, col2 = st.columns([2, 1])

with col1:
    text = st.text_area(
        "Enter text to analyze",
        height=200,
        placeholder="My name is Rajesh Kumar, Aadhaar 1234 5678 9012, email rajesh@example.com",
    )

with col2:
    st.subheader("API")
    api_url = st.text_input("API base URL", value=API_BASE)
    action = st.radio("Action", ["Anonymize", "Analyze only"])

if st.button("Run", type="primary"):
    if not text.strip():
        st.warning("Please enter some text.")
    else:
        endpoint = "/anonymize" if action == "Anonymize" else "/analyze"
        try:
            resp = requests.post(
                f"{api_url.rstrip('/')}{endpoint}",
                json={"text": text},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            if action == "Anonymize":
                st.subheader("Anonymized output")
                st.code(data.get("anonymized_text", ""))
                st.metric("Processing time (ms)", data.get("processing_time_ms", 0))
            else:
                st.metric("Entities found", data.get("entity_count", 0))
                st.metric("Processing time (ms)", data.get("processing_time_ms", 0))

            entities = data.get("detected_entities", [])
            if entities:
                st.subheader("Detected entities")
                st.dataframe(entities, use_container_width=True)
            else:
                st.info("No PII entities detected.")

        except requests.RequestException as exc:
            st.error(f"API error: {exc}")

with st.expander("Health check"):
    if st.button("Check API health"):
        try:
            h = requests.get(f"{api_url.rstrip('/')}/health", timeout=10).json()
            st.json(h)
        except requests.RequestException as exc:
            st.error(str(exc))
