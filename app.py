import streamlit as st
import requests
import pandas as pd
import boto3
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
API_URL = os.getenv("API_URL")
BUCKET_NAME = os.getenv("BUCKET_NAME")

st.set_page_config(page_title="Bill-E Audit Dashboard", layout="wide")

# --- SAFETY CHECK ---
if not API_URL or not BUCKET_NAME:
    st.error("Missing Configuration! Please check your .env file.")
    st.stop()

st.title("🧾 Bill-E: Live Audit Ledger")
st.markdown("---")

# --- UPLOAD SECTION ---
st.subheader("Upload New Receipt")
uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    if st.button("Upload to Cloud"):
        with st.spinner("Uploading..."):
            s3 = boto3.client('s3')
            try:
                s3.upload_fileobj(uploaded_file, BUCKET_NAME, uploaded_file.name)
                st.success(f"Uploaded {uploaded_file.name} successfully! Wait 10 seconds for AI processing...")
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
            if 'RiskScore' in df.columns:
                df['RiskScore'] = pd.to_numeric(df['RiskScore'], errors='coerce') # Turn "50" into 50
                df['RiskScore'] = df['RiskScore'].fillna(0) # Turn NaN (empty) into 0
            # --- PREPARE DATA ---
            # 1. Define columns (including AI fields)
            expected_cols = ['Filename', 'RiskScore', 'RiskFlags', 'ExtractedText', 'Status', 'UploadDate']
            cols = [c for c in expected_cols if c in df.columns]
            df = df[cols]

            # 2. Clean up RiskScore (Fill NaN with 0)
            if 'RiskScore' in df.columns:
                df['RiskScore'] = df['RiskScore'].fillna(0)

            # --- STATS SECTION (Moved to Top) ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Receipts", len(df))
            
            # Fixed Logic: Count 'Processed' OR 'Analyzed'
            if 'Status' in df.columns:
                processed_count = len(df[df['Status'].isin(['Processed', 'Analyzed'])])
            else:
                processed_count = 0
                
            col2.metric("Processed Successfully", processed_count)
            col3.metric("System Health", "Active")

            # --- TABLE WITH RISK HIGHLIGHTING ---
            st.subheader("Audit Trail")
            
            def highlight_risk(row):
                # Paint row RED if RiskScore > 0
                if 'RiskScore' in row and row['RiskScore'] > 0:
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)

            # Display the styled table (and silence the width warning)
            st.dataframe(df.style.apply(highlight_risk, axis=1), width=1200)

    else:
        st.error(f"Failed to fetch data. API Status: {response.status_code}")

except Exception as e:
    st.error(f"Connection Error: {str(e)}")

# --- REFRESH BUTTON ---
if st.button('Refresh Data'):
    st.rerun()