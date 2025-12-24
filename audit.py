import boto3
import requests
import re
from datetime import datetime
from config import TABLE_NAME, REGION, OCR_API_KEY

# --- CONSTANTS ---
FILE_NAME = "receipt.png"
OCR_ENDPOINT = "https://api.ocr.space/parse/image"

# --- HELPER: RISK ENGINE ---
def assess_risk(merchant, amount, date_str):
    flags = []
    
    # Rule 1: High Value Check
    if amount > 5000:
        flags.append("HIGH_VALUE")

    # Rule 2: Suspicious Merchants
    suspicious_keywords = ["bar", "pub", "gaming", "netflix", "casino", "club"]
    if any(keyword in merchant.lower() for keyword in suspicious_keywords):
        flags.append("NON_COMPLIANT_MERCHANT")
    
    # Rule 3: Weekend Check
    try:
        #normalized the date to YYYY-MM-DD in extract_financials
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if dt.weekday() >= 5: # 5=Saturday, 6=Sunday
            flags.append("WEEKEND_EXPENSE")
    except Exception as e:
        print(f"Risk Engine Date Error: {e}") 

    if flags:
        return "FLAGGED", flags
    return "APPROVED", ["NONE"]

# --- CORE FUNCTIONS ---

def get_ocr_text(filename):
    print(f"Scanning '{filename}'...")
    try:
        with open(filename, 'rb') as f:
            response = requests.post(
                OCR_ENDPOINT,
                data={'apikey': OCR_API_KEY, 'language': 'eng', 'isTable': True},
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
    UPGRADED: 
    1. Fixes 'Subtotal vs Total' bugs using scoring.
    2. Fixes 'Phone Number Bug' (ignores huge numbers).
    3. Normalizes Dates for the Risk Engine.
    """
    data = {}
    lines = text.split('\n')

    # 1. EXTRACT DATE & NORMALIZE (Fixing the Weekend Bug)
    # Regex looks for DD-MM-YYYY or YYYY-MM-DD
    date_match = re.search(r'(\d{2})[/-](\d{2})[/-](\d{4})|(\d{4})[/-](\d{2})[/-](\d{2})', text)
    if date_match:
        groups = date_match.groups()
        if groups[0]: # Found DD-MM-YYYY
            day, month, year = groups[0], groups[1], groups[2]
            data['Date'] = f"{year}-{month}-{day}"
        else: # Found YYYY-MM-DD
            year, month, day = groups[3], groups[4], groups[5]
            data['Date'] = f"{year}-{month}-{day}"
    else:
        data['Date'] = datetime.now().strftime("%Y-%m-%d")

    # 2. EXTRACT MERCHANT (First non-empty line)
    clean_lines = [line.strip() for line in lines if line.strip()]
    data['Merchant'] = clean_lines[0] if clean_lines else "Unknown"

    # 3. EXTRACT TOTAL (logic fix)
    candidates = []
    # Regex for currency: $10.00, 1,200.50, etc.
    money_pattern = r'[\$£€]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'

    for line in lines:
        line_lower = line.lower()
        
        # Filter Noise (Subtotals, Tax)
        if any(bad in line_lower for bad in ["subtotal", "tax", "vat", "change", "tender"]):
            continue

        match = re.search(money_pattern, line)
        if match:
            try:
                # Clean num
                amount_str = match.group(1).replace(',', '')
                amount = float(amount_str)
                
                # SANITY FILTERS 
                
                # Filter 1: Phone Numbers (The "Billion Dollar Bug" Fix)
                if amount > 200000: 
                    continue 

                # Filter 2: Years (e.g., 2024)
                if 2018 <= amount <= 2030 and "." not in match.group(1):
                    continue

                # SCORING LOGIC
                score = 0
                if "total" in line_lower: score += 10
                if "amount" in line_lower: score += 5
                if "due" in line_lower: score += 5
                
                candidates.append((amount, score))
            except ValueError:
                continue

    # Pick the winner: Highest Score -> Then Highest Amount
    if candidates:
        candidates.sort(key=lambda x: (x[1], x[0]), reverse=True)
        data['Total'] = candidates[0][0]
    else:
        data['Total'] = 0.0

    return data

def store_audit_record(data, risk_status, risk_flags):
    """
    Saves data + Risk Assessment to DynamoDB
    """
    dynamodb = boto3.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)
    
    print(f"Total: {data['Total']} | Merchant: {data['Merchant']}")
    print(f"Risk Status: {risk_status} | Flags: {risk_flags}")
    
    try:
        table.put_item(
            Item={
                'ReceiptID': str(datetime.now().timestamp()),
                'Merchant': data['Merchant'],
                'Date': data['Date'],
                'Total': str(data['Total']), # DynamoDB likes strings for currency to avoid float errors
                'Status': 'Audited',
                'RiskStatus': risk_status,    
                'RiskFlags': risk_flags,      
                'AuditedAt': datetime.now().isoformat()
            }
        )
        print("SUCCESS! Record saved to Cloud Ledger.")
    except Exception as e:
        print(f"Database Error: {e}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    # 1. Ingest
    raw_text = get_ocr_text(FILE_NAME)
    
    if raw_text:
        # 2. Extract Data
        clean_data = extract_financials(raw_text)
        
        # 3. Assess Risk 
        r_status, r_flags = assess_risk(clean_data['Merchant'], clean_data['Total'], clean_data['Date'])
        
        # 4. Storage
        store_audit_record(clean_data, r_status, r_flags)
    else:
        print("Failed to process receipt.")