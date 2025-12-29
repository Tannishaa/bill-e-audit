# config.py
import os

# AWS Configuration
BUCKET_NAME = "bill-e-receipts-xxxx" # Keep your actual bucket name here
TABLE_NAME = "ExpenseLedger"
REGION = "ap-south-1"

# API Configuration
# In a real job, we would use os.environ.get() for this
OCR_API_KEY = "you-api-key"  # API KEY