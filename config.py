# config.py
import os

# AWS Configuration
BUCKET_NAME = "bill-e-receipts-19762e26" # Keep your actual bucket name here
TABLE_NAME = "ExpenseLedger"
REGION = "ap-south-1"

# API Configuration
# In a real job, we would use os.environ.get() for this
OCR_API_KEY = "K81622954488957"  # API KEY