import boto3
import random
from datetime import datetime, timedelta
from config import TABLE_NAME, REGION

dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

merchants = ["Uber", "Starbucks", "Apple Store", "The Leela Palace", "Netflix", "Local Taxi", "Amazon AWS", "Go Air"]
risk_status = ["APPROVED", "FLAGGED"]

print("Injecting 20 Mock Records...")

for i in range(20):
    merchant = random.choice(merchants)
    amount = round(random.uniform(100, 15000), 2)
    
    # Simulate Risk Logic
    status = "APPROVED"
    flags = ["NONE"]
    
    if amount > 5000:
        status = "FLAGGED"
        flags = ["HIGH_VALUE"]
    if merchant == "Netflix":
        status = "FLAGGED"
        flags = ["NON_COMPLIANT"]
        
    item = {
        'ReceiptID': f"mock-{i}",
        'Merchant': merchant,
        'Date': (datetime.now() - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
        'Total': str(amount),
        'Status': 'Audited',
        'RiskStatus': status,
        'RiskFlags': flags,
        'AuditedAt': datetime.now().isoformat()
    }
    table.put_item(Item=item)
    print(f"Added: {merchant} - ₹{amount}")

print("Data Injection Complete. Refresh your Dashboard!")