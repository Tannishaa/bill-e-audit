import requests
import json

# --- CONFIGURATION ---
API_KEY = "K81622954488957"  # <--- PASTE KEY FROM EMAIL HERE
FILE_NAME = "receipt.png"
# ---------------------

def extract_text_free(filename):
    print(f"🧠 Sending '{filename}' to Free OCR API...")
    
    try:
        # 1. Open the image file
        with open(filename, 'rb') as f:
            # 2. Send it to OCR.space
            payload = {
                'apikey': API_KEY,
                'language': 'eng',
            }
            files = {
                'file': f
            }
            
            response = requests.post(
                'https://api.ocr.space/parse/image',
                data=payload,
                files=files
            )

        # 3. Process the Result
        result = response.json()
        
        if result['IsErroredOnProcessing']:
            print("❌ API Error:", result['ErrorMessage'])
            return

        print("\n--- 📝 EXTRACTED DATA ---")
        parsed_results = result.get('ParsedResults', [])
        
        if parsed_results:
            text = parsed_results[0].get('ParsedText')
            print(text)
            print("-------------------------")
            print("✅ AI Read Complete (Zero Cost).")
        else:
            print("⚠️ No text found.")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    extract_text_free(FILE_NAME)