import streamlit as st
import boto3
import pandas as pd
from datetime import datetime
from Legacy_v1.config import TABLE_NAME, REGION

# --- CONFIGURATION ---
st.set_page_config(page_title="Automated Expense Audit & ETL Pipeline", page_icon="🛡️", layout="wide")

# Connect to DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# --- SIDEBAR FILTERS ---
st.sidebar.title("Risk Controls")
status_filter = st.sidebar.radio("Filter by Status", ["All", "FLAGGED", "APPROVED"])
date_filter = st.sidebar.date_input("Date Range", [])

# --- MAIN DASHBOARD ---
st.title("Automated Expense Audit & ETL Pipeline")
st.markdown("Live view of incoming financial documents and automated risk assessment.")

# 1. FETCH DATA
try:
    response = table.scan()
    items = response['Items']
    df = pd.DataFrame(items)
    
    if not df.empty:
        # Convert columns to correct types
        df['Total'] = pd.to_numeric(df['Total'])
        
        # 2. KPI METRICS (Top Row)
        col1, col2, col3, col4 = st.columns(4)
        
        total_spend = df['Total'].sum()
        flagged_count = len(df[df['RiskStatus'] == 'FLAGGED'])
        avg_ticket = df['Total'].mean()
        
        col1.metric("Total Spend", f"₹{total_spend:,.2f}")
        col2.metric("Receipts Processed", len(df))
        col3.metric("Risk Flags", flagged_count, delta_color="inverse")
        col4.metric("Avg. Ticket Size", f"₹{avg_ticket:,.2f}")
        
        st.divider()

        # 3. RISK VISUALIZATION
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Risk Distribution")
            st.bar_chart(df['RiskStatus'].value_counts(), color="#581717")
            
        with c2:
            st.subheader("High Value Transactions")
            # Show top 5 most expensive receipts
            top_expenses = df.nlargest(5, 'Total')[['Merchant', 'Total', 'RiskStatus']]
            st.dataframe(top_expenses, use_container_width=True)

        # 4. DATA TABLE
        st.subheader("Live Audit Log")
        
        # Apply Filters
        if status_filter != "All":
            df = df[df['RiskStatus'] == status_filter]
            
        # Style the dataframe (Highlight FLAGGED rows in red)
        def highlight_risk(row):
            return ['background-color: #ffe6e6' if row['RiskStatus'] == 'FLAGGED' else '' for _ in row]

        st.dataframe(
            df[['Date', 'Merchant', 'Total', 'RiskStatus', 'RiskFlags', 'ReceiptID']],
            use_container_width=True
        )
        
    else:
        st.info("No data found in DynamoDB. Upload a receipt to start.")

except Exception as e:
    st.error(f"Error connecting to Database: {e}")