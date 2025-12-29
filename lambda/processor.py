import json
import boto3
import hashlib
import datetime

def lambda_handler(event, context):
    s3_client = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('BillE_Expenses') # Must match the name in Terraform

    for record in event['Records']:
        payload = json.loads(record['body'])
        
        if 'Records' not in payload:
            print("Test event received. Skipping.")
            continue

        s3_info = payload['Records'][0]['s3']
        bucket_name = s3_info['bucket']['name']
        file_key = s3_info['object']['key']
        
        print(f" Processing: {file_key}")

        try:
            # 1. Get File & Hash
            response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
            file_content = response['Body'].read()
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # 2. Prepare the Data Item
            # In a real app, this is where we'd add the extracted OCR text too
            timestamp = datetime.datetime.now().isoformat()
            
            item = {
                'ReceiptID': file_hash, # Use Hash as ID to prevent duplicates!
                'Filename': file_key,
                'UploadDate': timestamp,
                'Bucket': bucket_name,
                'FileSize': len(file_content),
                'Status': 'Processed'
            }

            # 3. Write to DynamoDB
            table.put_item(Item=item)
            
            print(f" Saved to DynamoDB: {file_hash}")

        except Exception as e:
            print(f" Error: {str(e)}")
            # Ideally: Send to DLQ

    return {
        'statusCode': 200,
        'body': json.dumps('Ledger Updated')
    }