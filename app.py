import streamlit as st
import requests
import pandas as pd
import boto3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# 1. Load Secrets (Prioritize Streamlit Secrets for Cloud)
if "API_URL" in st.secrets:
    API_URL = st.secrets["API_URL"]
    BUCKET_NAME = st.secrets["BUCKET_NAME"]
    
    # 🚨 CRITICAL FIX: Inject AWS Keys into Environment for Boto3
    if "AWS_ACCESS_KEY_ID" in st.secrets:
        os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["AWS_ACCESS_KEY_ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["AWS_SECRET_ACCESS_KEY"]
        os.environ["AWS_DEFAULT_REGION"] = st.secrets["AWS_DEFAULT_REGION"]
else:
    # Fallback for Localhost (.env)
    API_URL = os.getenv("API_URL")
    BUCKET_NAME = os.getenv("BUCKET_NAME")

st.set_page_config(page_title="Bill-E Audit Dashboard", layout="wide")

# --- SAFETY CHECK ---
if not API_URL or not BUCKET_NAME:
    st.error("🚨 Missing Configuration! Check your .env or Streamlit Secrets.")
    st.stop()

st.title("🧾 Bill-E: Live Audit Ledger")
st.markdown("---")

# --- UPLOAD SECTION ---
st.subheader("Upload New Receipt")
uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    if st.button("Upload to Cloud"):
        with st.spinner("Uploading..."):
            # Boto3 will now automatically find the keys we injected into os.environ
            s3 = boto3.client('s3')
            try:
                s3.upload_fileobj(uploaded_file, BUCKET_NAME, uploaded_file.name)
                st.success(f"Uploaded {uploaded_file.name} successfully! Wait 15 seconds for AI processing...")
            except Exception as e:
                st.error(f"Upload failed: {e}")

# --- FETCH DATA ---
try:
    response = requests.get(API_URL)
    if response.status_code == 200:
        data = response.json()
        
        if not data:
            st.info("The ledger is currently empty. Upload a receipt above to start!")
        else:
            df = pd.DataFrame(data)
            
            # --- PREPARE DATA ---
            expected_cols = ['Filename', 'RiskScore', 'RiskFlags', 'ExtractedText', 'Status', 'UploadDate']
            cols = [c for c in expected_cols if c in df.columns]
            df = df[cols]

            if 'RiskScore' in df.columns:
                df['RiskScore'] = pd.to_numeric(df['RiskScore'], errors='coerce').fillna(0)

            # --- STATS SECTION ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Receipts", len(df))
            
            if 'Status' in df.columns:
                processed_count = len(df[df['Status'].isin(['Processed', 'Analyzed'])])
            else:
                processed_count = 0
                
            col2.metric("Processed Successfully", processed_count)
            col3.metric("System Health", "Active")

            # --- TABLE WITH RISK HIGHLIGHTING ---
            st.subheader("Audit Trail")
            
            def highlight_risk(row):
                if 'RiskScore' in row and row['RiskScore'] > 0:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)

            st.dataframe(df.style.apply(highlight_risk, axis=1), width=1200)

    else:
        st.error(f"Failed to fetch data. API Status: {response.status_code}")

except Exception as e:
    st.error(f"Connection Error: {str(e)}")

# --- REFRESH BUTTON ---
if st.button(' Refresh Data'):
    st.rerun()