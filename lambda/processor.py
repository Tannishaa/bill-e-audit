import json
import boto3
import urllib.parse
import urllib.request
import os
import base64
import datetime
import hashlib

def lambda_handler(event, context):
    s3 = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    sns = boto3.client('sns')  # <---  Connect to SNS
    
    table = dynamodb.Table(os.environ['TABLE_NAME'])
    ocr_api_key = os.environ['OCR_API_KEY']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN'] # <---  Get the Topic Address

    for record in event['Records']:
        try:
            # 1. Parse Event
            payload = json.loads(record['body'])
            s3_event = payload['Records'][0]['s3']
            bucket_name = s3_event['bucket']['name']
            file_key = urllib.parse.unquote_plus(s3_event['object']['key'])
            
            print(f"Processing: {file_key}")

            # 2. Get Image from S3
            response = s3.get_object(Bucket=bucket_name, Key=file_key)
            image_bytes = response['Body'].read()
            
            # 3. Create Hash
            file_hash = hashlib.sha256(image_bytes).hexdigest()

            # 4. Call OCR API (Engine 2)
            b64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            data = urllib.parse.urlencode({
                'apikey': ocr_api_key,
                'base64Image': f"data:image/png;base64,{b64_image}",
                'language': 'eng',
                'scale': 'true',
                'OCREngine': '2',
            }).encode('ascii')

            req = urllib.request.Request("https://api.ocr.space/parse/image", data=data)
            
            with urllib.request.urlopen(req) as f:
                ocr_result = json.loads(f.read().decode('utf-8'))

            # 5. Extract Text & Analyze Risk
            extracted_text = "No text found"
            risk_score = 0
            risk_flags = []

            if ocr_result.get('ParsedResults'):
                extracted_text = ocr_result['ParsedResults'][0].get('ParsedText', '')
                
                # --- RISK ENGINE ---
                lower_text = extracted_text.lower()
                
                suspicious_keywords = ['casino', 'alcohol', 'bar', 'beer', 'wine', 'vodka']
                for word in suspicious_keywords:
                    if word in lower_text:
                        risk_score += 50
                        risk_flags.append(f"Suspicious Item: {word}")

            # 6. --- THE SNITCH PROTOCOL  --- 
            if risk_score > 0:
                print(f" HIGH RISK DETECTED: {risk_score}")
                message = (
                    f"ALERT: High Risk Receipt Detected!\n\n"
                    f"File: {file_key}\n"
                    f"Risk Score: {risk_score}\n"
                    f"Flags: {risk_flags}\n"
                    f"Text Snippet: {extracted_text[:100]}...\n"
                )
                try:
                    sns.publish(
                        TopicArn=sns_topic_arn,
                        Message=message,
                        Subject=f"BILL-E ALERT: Risk Score {risk_score}"
                    )
                    print("Alert Email Sent!")
                except Exception as e:
                    print(f"Failed to send email: {e}")

            # 7. Save to DynamoDB
            item = {
                'ReceiptID': file_hash,
                'Filename': file_key,
                'UploadDate': datetime.datetime.now().isoformat(),
                'Status': 'Analyzed',
                'ExtractedText': extracted_text[:100] + "...",
                'RiskScore': risk_score,
                'RiskFlags': risk_flags
            }
            
            table.put_item(Item=item)
            print(f"Analysis Complete for {file_key}. Risk Score: {risk_score}")

        except Exception as e:
            print(f"Error: {str(e)}")

    return {'statusCode': 200}
