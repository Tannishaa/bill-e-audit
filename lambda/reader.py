import json
import boto3
from boto3.dynamodb.conditions import Key

# Helper to handle DynamoDB weird number formats
def decimal_encoder(obj):
    if isinstance(obj, float) or isinstance(obj, int):
        return str(obj)
    return str(obj)

def lambda_handler(event, context):
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('BillE_Expenses')
    
    try:
        # 1. Scan the table (Get all items)
        # In a huge production app, we would Query, not Scan. 
        # But for < 1000 items, Scan is perfectly fine
        response = table.scan()
        items = response.get('Items', [])
        
        # 2. Return the data as JSON
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*' # CORS: Allow any website to call this
            },
            'body': json.dumps(items, default=decimal_encoder)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error reading DB: {str(e)}")
        }