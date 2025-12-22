import boto3
import os
from config import BUCKET_NAME, REGION

def upload_file(file_name):
    s3 = boto3.client('s3', region_name=REGION)
    
    # 1. Check if file exists locally
    if not os.path.exists(file_name):
        print(f"❌ Error: '{file_name}' not found. Did you download a receipt image?")
        return

    print(f"🚀 Uploading {file_name} to {BUCKET_NAME}...")

    # 2. Upload to S3
    try:
        s3.upload_file(file_name, BUCKET_NAME, file_name)
        print("✅ Upload Successful!")
        print(f"   File is now safe in the cloud: s3://{BUCKET_NAME}/{file_name}")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")

if __name__ == "__main__":
    upload_file("receipt.png")