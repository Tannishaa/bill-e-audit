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

# Load Secrets
if "API_URL" in st.secrets:
    API_URL = st.secrets["API_URL"]
    BUCKET_NAME = st.secrets["BUCKET_NAME"]
    SNS_TOPIC_ARN = st.secrets.get("SNS_TOPIC_ARN") # <--- NEW
    
    if "AWS_ACCESS_KEY_ID" in st.secrets:
        os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["AWS_ACCESS_KEY_ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["AWS_SECRET_ACCESS_KEY"]
        os.environ["AWS_DEFAULT_REGION"] = st.secrets["AWS_DEFAULT_REGION"]
else:
    # Local fallback
    API_URL = os.getenv("API_URL")
    BUCKET_NAME = os.getenv("BUCKET_NAME")
    SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")

st.set_page_config(page_title="Bill-E Audit Dashboard", layout="wide")

# --- THE BOUNCER & THE DOORBELL ---
st.sidebar.title("🔒 Login")
password = st.sidebar.text_input("Enter Access Code", type="password")

if password == "admin123":
    # 1. Check if we already rang the doorbell for this user session
    if "doorbell_rung" not in st.session_state:
        # 2. Ring the Doorbell (Send Email)
        if SNS_TOPIC_ARN:
            try:
                sns = boto3.client('sns')
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=f"🔔 Ding Dong! Someone just logged into Bill-E Dashboard at {datetime.datetime.now()}.",
                    Subject=" Bill-E Visitor Alert"
                )
                print("Doorbell rung!")
            except Exception as e:
                print(f"Doorbell broken: {e}")
        
        # 3. Mark as rung so we don't spam you on every refresh
        st.session_state["doorbell_rung"] = True
        
    st.sidebar.success("Access Granted")

else:
    st.title("🧾 Bill-E: Live Audit Ledger")
    st.markdown("---")
    st.warning("Access Restricted")
    st.info("This is a live portfolio project. Please enter the access code to view the dashboard.")
    st.stop() 

# ---  APP STARTS HERE ---

# --- SAFETY CHECK ---
if not API_URL or not BUCKET_NAME:
    st.error("Missing Configuration! Check your secrets.")
    st.stop()

# --- SIDEBAR SETTINGS ---
st.sidebar.markdown("---")
st.sidebar.title("⚙️ Settings")
use_auto_refresh = st.sidebar.checkbox("Enable Live Updates", value=True)

if use_auto_refresh:
    count = st_autorefresh(interval=5000, limit=100, key="data_refresh")

st.title("🧾 Bill-E: Live Audit Ledger")
st.markdown("---")

# --- UPLOAD SECTION ---
st.subheader("Upload New Receipt")
uploaded_file = st.file_uploader("Choose a receipt image", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    if st.button(" Upload to Cloud"):
        with st.spinner("Uploading..."):
            s3 = boto3.client('s3')
            try:
                s3.upload_fileobj(uploaded_file, BUCKET_NAME, uploaded_file.name)
                st.success(f"Uploaded {uploaded_file.name} successfully!")
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

            # --- STATS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Receipts", len(df))
            
            if 'Status' in df.columns:
                processed_count = len(df[df['Status'].isin(['Processed', 'Analyzed'])])
            else:
                processed_count = 0
                
            col2.metric("Processed Successfully", processed_count)
            
            if use_auto_refresh:
                col3.metric("System Health", "Live Updates ON")
            else:
                col3.metric("System Health", "Live Updates OFF")

            # --- TABLE ---
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