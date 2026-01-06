import streamlit as st
import requests
import pandas as pd
import boto3
import os
import datetime
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURATION ---
load_dotenv()

# Securely load secrets (Streamlit Cloud or Local .env)
if "API_URL" in st.secrets:
    API_URL = st.secrets["API_URL"]
    BUCKET_NAME = st.secrets["BUCKET_NAME"]
    SNS_TOPIC_ARN = st.secrets.get("SNS_TOPIC_ARN")
    if "AWS_ACCESS_KEY_ID" in st.secrets:
        os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["AWS_ACCESS_KEY_ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["AWS_SECRET_ACCESS_KEY"]
        os.environ["AWS_DEFAULT_REGION"] = st.secrets["AWS_DEFAULT_REGION"]
else:
    API_URL = os.getenv("API_URL")
    BUCKET_NAME = os.getenv("BUCKET_NAME")
    SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")

st.set_page_config(page_title="Bill-E Audit Dashboard", layout="wide")

# --- AUTH STATE INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- PUBLIC HEADER (Visible to Everyone) ---
st.title("🧾 Bill-E: Live Audit Ledger")
st.markdown("This dashboard is **Public Read-Only**. Authentication is required for write operations.")
st.markdown("---")

# --- SAFETY CHECK ---
if not API_URL or not BUCKET_NAME:
    st.error(" Configuration Error: Secrets missing.")
    st.stop()

# --- FETCH & DISPLAY DATA (Public) ---
# This runs for EVERYONE so recruiters see the cool charts immediately.
try:
    response = requests.get(API_URL)
    if response.status_code == 200:
        data = response.json()
        
        if not data:
            st.info("The ledger is currently empty.")
        else:
            df = pd.DataFrame(data)
            
            # Data Cleanup
            expected_cols = ['Filename', 'RiskScore', 'RiskFlags', 'ExtractedText', 'Status', 'UploadDate']
            cols = [c for c in expected_cols if c in df.columns]
            df = df[cols]
            if 'RiskScore' in df.columns:
                df['RiskScore'] = pd.to_numeric(df['RiskScore'], errors='coerce').fillna(0)

            # --- METRICS SECTION ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Receipts", len(df))
            
            processed_count = len(df[df['Status'].isin(['Processed', 'Analyzed'])]) if 'Status' in df.columns else 0
            col2.metric("Processed Successfully", processed_count)
            
            # --- TABLE SECTION ---
            st.subheader("Public Audit Trail")
            
            def highlight_risk(row):
                if 'RiskScore' in row and row['RiskScore'] > 50: # Highlight High Risk
                    return ['background-color: #ffcccc'] * len(row)
                return [''] * len(row)

            st.dataframe(df.style.apply(highlight_risk, axis=1), width=1200)
            
    else:
        st.warning("API is sleeping (Cold Start). Refresh in 10s.")

except Exception as e:
    st.error(f"Connection Error: {str(e)}")


# --- PROTECTED SECTION (The Magic Part) ---
st.divider()
st.subheader("🔐 Admin Zone")

if not st.session_state["authenticated"]:
    # 1. SHOW LOCK SCREEN
    col_lock1, col_lock2 = st.columns([2, 1])
    with col_lock1:
        st.info("Upload functionality is restricted to authorized auditors.")
        password_input = st.text_input("Enter Access Code", type="password")
        
        if st.button("Unlock Admin Features"):
            if password_input == "admin123":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Access Denied")
else:
    # 2. SHOW UPLOAD TOOLS (Unlocked)
    st.success("Authenticated. Write Access Granted.")
    
    # The "Doorbell" Notification (Runs once upon unlock)
    if "doorbell_rung" not in st.session_state and SNS_TOPIC_ARN:
        try:
            sns = boto3.client('sns')
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=f"🔔 Admin Access Unlocked at {datetime.datetime.now()}",
                Subject="Bill-E Admin Alert"
            )
            st.session_state["doorbell_rung"] = True
        except:
            pass

    # File Uploader
    uploaded_file = st.file_uploader("Upload Receipt for Audit", type=['png', 'jpg', 'jpeg'])

    if uploaded_file is not None:
        if st.button("Upload to Cloud Pipeline"):
            with st.spinner("Uploading to S3..."):
                s3 = boto3.client('s3')
                try:
                    s3.upload_fileobj(uploaded_file, BUCKET_NAME, uploaded_file.name)
                    st.success(f"File {uploaded_file.name} sent to processing queue!")
                except Exception as e:
                    st.error(f"Upload failed: {e}")
    
    # Auto-Refresh Logic (Only runs for Admins to save costs)
    use_auto_refresh = st.checkbox("Enable Live Polling", value=True)
    if use_auto_refresh:
        st_autorefresh(interval=10000, limit=20, key="data_refresh")

    if st.button("Lock Dashboard"):
        st.session_state["authenticated"] = False
        st.rerun()