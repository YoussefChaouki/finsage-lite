"""
FinSage-Lite Streamlit UI

Interactive interface for SEC 10-K filing analysis.
"""

import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="FinSage-Lite", page_icon="📊")

st.title("📊 FinSage-Lite")
st.markdown("**SEC 10-K Filing Analysis with RAG**")

# Health check
try:
    response = requests.get(f"{API_URL}/health", timeout=2)
    if response.ok:
        data = response.json()
        st.success(f"✓ API Connected ({data.get('status', 'unknown')})")
    else:
        st.error("❌ API unreachable")
except Exception as e:
    st.error(f"❌ API Connection Error: {e}")

st.markdown("---")
st.info("🚧 UI under construction. Stay tuned for document ingestion and search features!")
