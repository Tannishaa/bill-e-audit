import boto3
import uuid

# --- CONFIGURATION ---
# We add a random UUID to ensure the bucket name is unique globally
unique_id = str(uuid.uuid4())[:8]
BUCKET_NAME = f"bill-e-receipts-{unique_id}"
TABLE_NAME = "ExpenseLedger"
REGION = "ap-south-1"  # Mumbai Region
# ---------------------

def create_infrastructure():
    s3 = boto3.client('s3', region_name=REGION)
    dynamodb = boto3.client('dynamodb', region_name=REGION)

    print(f"🚀 Initializing Cloud Infrastructure in {REGION}...")

    # 1. Create S3 Bucket
    try:
        s3.create_bucket(
            Bucket=BUCKET_NAME,
            CreateBucketConfiguration={'LocationConstraint': REGION}
        )
        print(f"✅ S3 Bucket Created: {BUCKET_NAME}")
    except Exception as e:
        print(f"❌ Error creating bucket: {e}")

    # 2. Create DynamoDB Table
    try:
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {'AttributeName': 'ReceiptID', 'KeyType': 'HASH'}  # Partition Key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'ReceiptID', 'AttributeType': 'S'}  # S = String
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(f"✅ DynamoDB Table Creating: {TABLE_NAME}")
        print("   (This might take 10-20 seconds to become active)")
    except Exception as e:
        if "ResourceInUseException" in str(e):
            print(f"⚠️  Table '{TABLE_NAME}' already exists. Skipping.")
        else:
            print(f"❌ Error creating table: {e}")

    # 3. Save the config for later use
    with open("config.py", "w") as f:
        f.write(f'BUCKET_NAME = "{BUCKET_NAME}"\n')
        f.write(f'TABLE_NAME = "{TABLE_NAME}"\n')
        f.write(f'REGION = "{REGION}"\n')
    print("💾 Configuration saved to config.py")

if __name__ == "__main__":
    create_infrastructure()