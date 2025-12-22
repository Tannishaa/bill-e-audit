import boto3
import requests
import re
from datetime import datetime
from config import TABLE_NAME, REGION, OCR_API_KEY

# --- CONSTANTS ---
FILE_NAME = "receipt.png"
OCR_ENDPOINT = "https://api.ocr.space/parse/image"

def get_ocr_text(filename):
    """
    Uploads the image to OCR.space API and returns the raw parsed text.
    """
    print(f"Scanning '{filename}'...")
    try:
        with open(filename, 'rb') as f:
            response = requests.post(
                OCR_ENDPOINT,
                data={'apikey': OCR_API_KEY, 'language': 'eng'},
                files={'file': f}
            )
        
        result = response.json()
        if result.get('ParsedResults'):
            return result['ParsedResults'][0]['ParsedText']
        
        print("Warning: No text found in image.")
        return ""
    except Exception as e:
        print(f"API Error: {e}")
        return ""

def extract_financials(text):
    """
    Analyzes raw text to identify the transaction Date, Merchant, and Total Amount.
    Uses regex and context-aware logic to handle messy OCR data.
    """
    data = {}
    
    # 1. EXTRACT DATE
    # Looks for patterns like DD/MM/YYYY
    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if date_match:
        data['Date'] = date_match.group(1)
        # Capture the year (e.g., 2020) to ensure we don't confuse it with the price
        ignored_year = float(data['Date'].split('/')[-1])
    else:
        data['Date'] = datetime.now().strftime("%Y-%m-%d")
        ignored_year = float(datetime.now().year)

    # 2. EXTRACT TOTAL AMOUNT
    # Logic: Look for keywords "Total/Due" and scan nearby lines for the price.
    lines = text.split('\n')
    total_found = False
    
    def get_valid_nums(s):
        """Helper to find valid prices in a string, ignoring IDs and Years."""
        nums = re.findall(r'\d+\.?\d*', s)
        valid = []
        for n in nums:
            try:
                val = float(n)
                if val != ignored_year and val < 50000: # Filter out phone numbers/IDs
                    valid.append(val)
            except ValueError:
                pass
        return valid

    for i, line in enumerate(lines):
        if "total" in line.lower() or "due" in line.lower():
            # Check current line + next 4 lines (handling OCR formatting gaps)
            for lookahead in range(0, 4):
                if i + lookahead < len(lines):
                    target_line = lines[i + lookahead]
                    nums = get_valid_nums(target_line)
                    if nums:
                        data['Total'] = max(nums)
                        total_found = True
                        break
            if total_found:
                break

    # Fallback: If no keyword found, take the largest valid number in the text
    if not total_found:
        all_nums = get_valid_nums(text)
        data['Total'] = max(all_nums) if all_nums else 0.0

    # 3. EXTRACT MERCHANT
    # Assumption: Merchant name is usually at the top of the receipt
    data['Merchant'] = lines[0].strip() if lines else "Unknown"
    
    return data

def store_audit_record(data):
    """
    Saves the structured financial data into AWS DynamoDB.
    """
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)
    
    print(f"Saving to Cloud Ledger: {data}")
    
    try:
        table.put_item(
            Item={
                'ReceiptID': str(datetime.now().timestamp()),
                'Merchant': data['Merchant'],
                'Date': data['Date'],
                'Total': str(data['Total']),
                'Status': 'Audited',
                'AuditedAt': datetime.now().isoformat()
            }
        )
        print("SUCCESS! Record saved to DynamoDB.")
    except Exception as e:
        print(f"Database Error: {e}")

if __name__ == "__main__":
    # 1. Ingest
    raw_text = get_ocr_text(FILE_NAME)
    
    if raw_text:
        # 2. Process
        clean_data = extract_financials(raw_text)
        print("\n--- AUDIT RESULT ---")
        print(clean_data)
        print("--------------------")
        
        # 3. Storage
        store_audit_record(clean_data)
    else:
        print("Failed to process receipt.")